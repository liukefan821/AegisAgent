"""
http_server.py — FastAPI HTTP server for AegisAgent TEE Agent

Exposes two read-only endpoints for the frontend:
  - GET /health           — liveness + status panel (interfaces.md §4.1)
  - GET /quotes/{digest}  — reverse-lookup full quote by on-chain digest

The on-chain ActionExecuted event only emits keccak256(quote) for gas
efficiency. The frontend AttestationBadge needs the full quote to display
mr_enclave / report_data / timestamp, so the agent keeps an in-memory
digest -> AttestationQuote map and serves it here.

The QuoteStore is a module-level singleton. The decision engine (Step 6)
will call get_store().put(quote) immediately after quote_generator mints
a quote, making the digest queryable before the on-chain tx is mined.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

import httpx
from eth_utils import keccak
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from aegis_agent.quote_generator import AttestationQuote, HASH_SIZE

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# Response schemas (match docs/interfaces.md §4.1 + frontend AttestationBadge)
# ────────────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = Field(..., description='"alive" | "degraded" | "down"')
    enclave_image_hash: str
    last_quote_generated_at: int
    ollama_model: str
    ollama_status: str = Field(..., description='"ready" | "unreachable"')


class QuoteResponse(BaseModel):
    digest: str = Field(..., description="0x-prefixed keccak256(quote)")
    quote_hex: str = Field(..., description="0x-prefixed full TDX quote bytes")
    mr_enclave: str = Field(..., description="0x-prefixed 32-byte enclave measurement")
    report_data: str = Field(..., description="0x-prefixed 64B input_hash||output_hash")
    input_hash: str
    output_hash: str
    timestamp: int
    is_mock: bool


# ────────────────────────────────────────────────────────────────────────────
# QuoteStore — in-memory digest -> AttestationQuote
# ────────────────────────────────────────────────────────────────────────────

class QuoteStore:
    """Module-level singleton mapping keccak256(quote) -> AttestationQuote."""

    def __init__(self) -> None:
        self._records: Dict[str, AttestationQuote] = {}

    @staticmethod
    def digest_for(quote: AttestationQuote) -> str:
        """Return the 0x-prefixed keccak256(quote_bytes) digest."""
        quote_bytes = bytes.fromhex(quote.quote_hex)
        return "0x" + keccak(quote_bytes).hex()

    def put(self, quote: AttestationQuote) -> str:
        """Store a quote under its on-chain digest. Returns the digest."""
        digest = self.digest_for(quote)
        self._records[digest] = quote
        logger.info(
            "Stored quote digest=%s... (total=%d)",
            digest[:10], len(self._records),
        )
        return digest

    def get(self, digest: str) -> Optional[AttestationQuote]:
        digest = digest.lower()
        if not digest.startswith("0x"):
            digest = "0x" + digest
        return self._records.get(digest)

    def __len__(self) -> int:
        return len(self._records)

    def last_timestamp(self) -> int:
        if not self._records:
            return 0
        return max(q.timestamp for q in self._records.values())


# Module-level singleton — orchestrator/decision_engine call put() here.
_store = QuoteStore()


def get_store() -> QuoteStore:
    return _store


# ────────────────────────────────────────────────────────────────────────────
# Ollama liveness probe
# ────────────────────────────────────────────────────────────────────────────

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
ENCLAVE_IMAGE_HASH = os.getenv("ENCLAVE_IMAGE_HASH", "0x" + "00" * HASH_SIZE)


def _probe_ollama(timeout: float = 2.0) -> str:
    """Cheap GET on /api/tags — no model load, ~5ms when Ollama is up."""
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{OLLAMA_URL}/api/tags")
            return "ready" if r.status_code == 200 else "unreachable"
    except Exception as e:
        logger.debug("Ollama probe failed: %s", e)
        return "unreachable"


# ────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AegisAgent TEE Agent",
    version="0.1.0",
    description="Read-only HTTP API for enclave status and attestation quote lookup.",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness + status. Frontend polls every ~10s."""
    ollama_status = _probe_ollama()
    return HealthResponse(
        status="alive" if ollama_status == "ready" else "degraded",
        enclave_image_hash=ENCLAVE_IMAGE_HASH,
        last_quote_generated_at=get_store().last_timestamp(),
        ollama_model=OLLAMA_MODEL,
        ollama_status=ollama_status,
    )


@app.get("/quotes/{digest}", response_model=QuoteResponse)
def get_quote(digest: str) -> QuoteResponse:
    """Reverse-lookup a full quote by its on-chain keccak256(quote) digest."""
    normalised = digest.lower()
    if not normalised.startswith("0x"):
        normalised = "0x" + normalised

    quote = get_store().get(normalised)
    if quote is None:
        raise HTTPException(
            status_code=404,
            detail=f"No quote found for digest {normalised}",
        )

    report_data = quote.report_data
    input_hash = report_data[:HASH_SIZE]
    output_hash = report_data[HASH_SIZE:]

    return QuoteResponse(
        digest=normalised,
        quote_hex="0x" + quote.quote_hex,
        mr_enclave="0x" + quote.mr_enclave,
        report_data="0x" + report_data.hex(),
        input_hash="0x" + input_hash.hex(),
        output_hash="0x" + output_hash.hex(),
        timestamp=quote.timestamp,
        is_mock=quote.is_mock,
    )
