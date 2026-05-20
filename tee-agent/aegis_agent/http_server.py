"""
http_server.py — FastAPI HTTP server for AegisAgent TEE Agent

Exposes read-only endpoints for the frontend:
  - GET /health           — liveness + status panel (interfaces.md §4.1)
  - GET /quotes/{digest}  — reverse-lookup full quote by on-chain digest

The on-chain ActionExecuted event only emits keccak256(quote) for gas
efficiency. The frontend AttestationBadge needs the full quote to display
mr_enclave / report_data / timestamp, so the agent keeps an in-memory
digest -> AttestationQuote map and serves it here.

The QuoteStore is a module-level singleton. The decision engine (Step 6)
calls get_store().put(quote, input_hash=...) after generating a quote,
making the digest queryable before the on-chain tx is mined.

Step 6 update: report_data layout changed from input_hash||output_hash
to actionHash||output_hash. The real input_hash is saved separately in
QuoteStore and returned in the API response for audit purposes.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

import httpx
from dotenv import load_dotenv
from eth_utils import keccak
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from aegis_agent.llm_client import configured_model, configured_provider, probe_llm
from aegis_agent.quote_generator import AttestationQuote, HASH_SIZE

load_dotenv()
load_dotenv(".env.local", override=False)

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
    report_data: str = Field(..., description="0x-prefixed 64B raw report_data")
    action_hash: str = Field(..., description="0x-prefixed report_data[0:32] — binds quote to on-chain action")
    input_hash: str = Field(..., description="0x-prefixed SHA-256 of LLM input (stored separately)")
    output_hash: str = Field(..., description="0x-prefixed report_data[32:64]")
    timestamp: int
    is_mock: bool


class DecisionRequest(BaseModel):
    user: str = Field(..., description="0x-prefixed user wallet address")
    balance_wei: int = Field(..., ge=0, description="Current vault balance in wei")
    nonce: int = Field(..., ge=0, description="Current AegisVault nonce for user")
    mock_price: Optional[str] = Field(
        None,
        description="Optional ETH/USD price override; if omitted, Chainlink is used when configured.",
    )
    demo_action: Optional[str] = Field(
        None,
        description='Optional demo override: "HOLD" or "TRANSFER". Bypasses only the AI choice.',
    )
    demo_target: Optional[str] = Field(
        None,
        description="Optional safe target address for demo TRANSFER. Defaults to the user address.",
    )
    demo_transfer_bps: int = Field(
        2500,
        ge=0,
        le=10000,
        description="Basis points of vault balance to transfer for demo TRANSFER.",
    )


class DecisionResponse(BaseModel):
    action: str
    reasoning: str
    user: str
    amount_wei: str
    target: str
    nonce: int
    timestamp: int
    action_hash: str
    quote_hex: str
    quote_digest: str
    mr_enclave: str
    is_mock: bool
    input_hash: str
    output_hash: str
    eth_usd_price: str
    chainlink_round_id: int


# ────────────────────────────────────────────────────────────────────────────
# QuoteStore — in-memory digest -> AttestationQuote + metadata
# ────────────────────────────────────────────────────────────────────────────

class QuoteStore:
    """Module-level singleton mapping keccak256(quote) -> AttestationQuote.

    Step 6: also stores the real input_hash separately, since report_data[0:32]
    is now actionHash. input_hash is audit metadata and is no longer directly
    recoverable from report_data.
    """

    def __init__(self) -> None:
        self._records: Dict[str, AttestationQuote] = {}
        self._input_hashes: Dict[str, bytes] = {}

    @staticmethod
    def digest_for(quote: AttestationQuote) -> str:
        """Return the 0x-prefixed keccak256(quote_bytes) digest."""
        quote_bytes = bytes.fromhex(quote.quote_hex)
        return "0x" + keccak(quote_bytes).hex()

    def put(
        self,
        quote: AttestationQuote,
        *,
        input_hash: Optional[bytes] = None,
    ) -> str:
        """Store a quote under its on-chain digest.

        Args:
            quote: The attestation quote to store.
            input_hash: (Step 6) The real LLM input_hash, saved separately
                        because report_data[0:32] is now actionHash.

        Returns:
            The 0x-prefixed keccak256 digest.
        """
        digest = self.digest_for(quote)
        self._records[digest] = quote
        if input_hash is not None:
            self._input_hashes[digest] = input_hash
        logger.info(
            "Stored quote digest=%s... (total=%d, has_input_hash=%s)",
            digest[:10], len(self._records), input_hash is not None,
        )
        return digest

    def get(self, digest: str) -> Optional[AttestationQuote]:
        digest = digest.lower()
        if not digest.startswith("0x"):
            digest = "0x" + digest
        return self._records.get(digest)

    def get_input_hash(self, digest: str) -> Optional[bytes]:
        """Retrieve the separately-stored LLM input_hash for a quote."""
        digest = digest.lower()
        if not digest.startswith("0x"):
            digest = "0x" + digest
        return self._input_hashes.get(digest)

    def __len__(self) -> int:
        return len(self._records)

    def last_timestamp(self) -> int:
        if not self._records:
            return 0
        return max(q.timestamp for q in self._records.values())


# Module-level singleton — decision_engine calls put() here.
_store = QuoteStore()


def get_store() -> QuoteStore:
    return _store


# ────────────────────────────────────────────────────────────────────────────
# LLM liveness probe
# ────────────────────────────────────────────────────────────────────────────

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = configured_model()
ENCLAVE_IMAGE_HASH = os.getenv("ENCLAVE_IMAGE_HASH", "0x" + "00" * HASH_SIZE)


def _probe_ollama(timeout: float = 2.0) -> str:
    """Backward-compatible probe used by tests and /health.

    If LLM_PROVIDER=gemini, this checks the Gemini API/model instead of Ollama.
    """
    if configured_provider() == "gemini":
        return probe_llm()
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
    version="0.2.0",
    description="Read-only HTTP API for enclave status and attestation quote lookup.",
)


# CORS — frontend (Next.js dev server on :3000) calls this API on :8080.
from fastapi.middleware.cors import CORSMiddleware

_FRONTEND_ORIGINS = os.getenv(
    "AEGIS_FRONTEND_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_FRONTEND_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
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
    """Reverse-lookup a full quote by its on-chain keccak256(quote) digest.

    Step 6 update: response now includes action_hash (report_data[0:32])
    and input_hash (stored separately in QuoteStore, not from report_data).
    """
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
    # Step 6: report_data[0:32] = actionHash, report_data[32:64] = output_hash
    action_hash_bytes = report_data[:HASH_SIZE]
    output_hash_bytes = report_data[HASH_SIZE:]

    # input_hash is stored separately for audit; it is not in report_data.
    stored_input_hash = get_store().get_input_hash(normalised)
    if stored_input_hash is not None:
        input_hash_hex = "0x" + stored_input_hash.hex()
    else:
        # Backward compat: old quotes without separate input_hash
        # Fall back to report_data[0:32] (which was input_hash before Step 6)
        input_hash_hex = "0x" + action_hash_bytes.hex()

    return QuoteResponse(
        digest=normalised,
        quote_hex="0x" + quote.quote_hex,
        mr_enclave="0x" + quote.mr_enclave,
        report_data="0x" + report_data.hex(),
        action_hash="0x" + action_hash_bytes.hex(),
        input_hash=input_hash_hex,
        output_hash="0x" + output_hash_bytes.hex(),
        timestamp=quote.timestamp,
        is_mock=quote.is_mock,
    )


@app.post("/decisions", response_model=DecisionResponse)
def create_decision(request: DecisionRequest) -> DecisionResponse:
    """Run the full decision pipeline and store the generated quote.

    The returned fields are the arguments needed by AegisVault.executeAction:
        user, quote_hex, action_hash, amount_wei, target, timestamp

    The quote is also saved in QuoteStore, so /quotes/{quote_digest} can be
    queried immediately after this call.
    """
    try:
        from aegis_agent.chainlink_feed import ChainlinkFeed, ChainlinkFeedError
        from aegis_agent.decision_engine import DecisionEngine
        from aegis_agent.llm_client import create_llm_client
        from aegis_agent.quote_generator import QuoteGenerator

        chainlink = None
        if request.mock_price is None and os.getenv("SEPOLIA_RPC_URL"):
            try:
                chainlink = ChainlinkFeed.from_env()
            except ChainlinkFeedError as e:
                logger.warning("Chainlink unavailable, falling back to mock price: %s", e)

        mock_quote = os.getenv("AEGIS_MOCK_QUOTE", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        engine = DecisionEngine(
            ollama=create_llm_client(),
            quote_gen=QuoteGenerator(
                mock=mock_quote,
                mock_mr_enclave=os.getenv("MOCK_MR_ENCLAVE"),
                dstack_socket=os.getenv("DSTACK_SOCKET_PATH"),
            ),
            chainlink=chainlink,
        )
        result = engine.decide(
            user=request.user,
            balance_wei=request.balance_wei,
            nonce=request.nonce,
            mock_price=request.mock_price,
            demo_action=request.demo_action,
            demo_target=request.demo_target,
            demo_transfer_bps=request.demo_transfer_bps,
        )
    except Exception as e:
        logger.exception("Decision generation failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return DecisionResponse(
        action=result.action,
        reasoning=result.reasoning,
        user=result.user,
        amount_wei=str(result.amount_wei),
        target=result.target,
        nonce=result.nonce,
        timestamp=result.timestamp,
        action_hash=result.action_hash,
        quote_hex=result.quote_hex,
        quote_digest=result.quote_digest,
        mr_enclave=result.mr_enclave,
        is_mock=result.is_mock,
        input_hash=result.input_hash,
        output_hash=result.output_hash,
        eth_usd_price=result.eth_usd_price,
        chainlink_round_id=result.chainlink_round_id,
    )
