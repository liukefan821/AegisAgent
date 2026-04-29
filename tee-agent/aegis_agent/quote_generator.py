"""
quote_generator.py — TDX attestation quote generator for AegisAgent

Wraps an agent decision (input_hash, output_hash) into a TEE attestation
quote that the on-chain AegisVerifier can verify. The quote commits to:
  - report_data = input_hash || output_hash  (64 bytes)
  - mr_enclave  = hash of the LLM model image (matches AegisRegistry)

Two backends are supported:
  - MOCK   : deterministic, structurally-valid quotes for local dev / CI.
             Carries an "AEGIS_MOCK_QUOTE_v1" magic prefix so on-chain
             verifiers and tests can immediately distinguish dev quotes
             from production ones.
  - DSTACK : real Intel TDX quotes via the Dstack SDK on Phala Cloud.
             Implemented in Step 5 once the TDX host is provisioned.

This module is the *only* component allowed to mint attestation quotes.
All other agent modules call QuoteGenerator.generate() so every decision
carries a verifiable proof of execution.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────────────

# TDX report_data is exactly 64 bytes. We pack: input_hash || output_hash.
REPORT_DATA_SIZE = 64
HASH_SIZE = 32

# Magic prefix for mock quotes — makes mocks instantly recognisable so the
# on-chain verifier and CI can reject them immediately.
MOCK_QUOTE_MAGIC = b"AEGIS_MOCK_QUOTE_v1"

# Default mock mr_enclave — placeholder fingerprint of the qwen2.5:7b model.
# In production this is replaced by the real measurement of the running TD.
DEFAULT_MOCK_MR_ENCLAVE = "1234567890abcdef" * 4  # 64 hex chars = 32 bytes


# ────────────────────────────────────────────────────────────────────────────
# Exceptions & data classes
# ────────────────────────────────────────────────────────────────────────────

class QuoteGenerationError(RuntimeError):
    """Raised when the quote backend fails to produce a valid quote."""


@dataclass(frozen=True)
class AttestationQuote:
    """Output of QuoteGenerator.generate().

    Attributes:
        quote_hex:   hex-encoded TDX quote bytes (no '0x' prefix).
        report_data: 64-byte payload = input_hash || output_hash.
        mr_enclave:  32-byte hex identifying the LLM model image.
        timestamp:   Unix time when the quote was generated.
        is_mock:     True if produced by the mock backend.
    """
    quote_hex: str
    report_data: bytes
    mr_enclave: str
    timestamp: int
    is_mock: bool


# ────────────────────────────────────────────────────────────────────────────
# Quote generator
# ────────────────────────────────────────────────────────────────────────────

class QuoteGenerator:
    """Generate TDX attestation quotes binding an agent decision to a TEE.

    The generated quote can be submitted to AegisVerifier.verifyDecision()
    on Sepolia, where the on-chain logic checks the Intel PCK signature
    and extracts input_hash / output_hash from the report_data field.
    """

    def __init__(
        self,
        mock: bool = True,
        mock_mr_enclave: Optional[str] = None,
    ) -> None:
        """Initialise the generator.

        Args:
            mock: If True (default), use the local mock backend.
                  If False, attempt to use Dstack SDK (Step 5+ only).
            mock_mr_enclave: Override the default mock mr_enclave.
                             Must be 64 hex chars (32 bytes). Mock-only.
        """
        self.mock = mock

        if mock_mr_enclave is None:
            mock_mr_enclave = DEFAULT_MOCK_MR_ENCLAVE
        self._validate_mr_enclave(mock_mr_enclave)
        self._mr_enclave = mock_mr_enclave

        if not self.mock:
            raise NotImplementedError(
                "Real Dstack TDX backend is not implemented yet. "
                "Set mock=True for local development. "
                "Real backend will be added in Step 5 (Phala Cloud deploy)."
            )

        logger.info(
            "QuoteGenerator initialised (backend=%s, mr_enclave=%s...)",
            "MOCK" if self.mock else "DSTACK",
            self._mr_enclave[:8],
        )

    # ── public API ─────────────────────────────────────────────────────────

    def generate(
        self,
        input_hash: bytes,
        output_hash: bytes,
    ) -> AttestationQuote:
        """Generate an attestation quote for the given decision hashes.

        Args:
            input_hash:  32-byte SHA-256 of the agent's input prompt.
            output_hash: 32-byte SHA-256 of the agent's output decision.

        Returns:
            AttestationQuote with the hex-encoded quote and metadata.

        Raises:
            ValueError: if either hash is not exactly 32 bytes.
            QuoteGenerationError: if the backend fails.
        """
        self._validate_hash(input_hash, "input_hash")
        self._validate_hash(output_hash, "output_hash")

        report_data = bytes(input_hash) + bytes(output_hash)
        assert len(report_data) == REPORT_DATA_SIZE

        if self.mock:
            quote_hex = self._build_mock_quote(report_data)
        else:  # pragma: no cover — guarded in __init__
            raise QuoteGenerationError("Real backend not implemented")

        result = AttestationQuote(
            quote_hex=quote_hex,
            report_data=report_data,
            mr_enclave=self._mr_enclave,
            timestamp=int(time.time()),
            is_mock=self.mock,
        )

        logger.info(
            "Generated %s quote (input=%s..., output=%s...)",
            "MOCK" if self.mock else "REAL",
            bytes(input_hash).hex()[:8],
            bytes(output_hash).hex()[:8],
        )
        return result

    # ── internals ──────────────────────────────────────────────────────────

    @staticmethod
    def _validate_hash(value: bytes, name: str) -> None:
        if not isinstance(value, (bytes, bytearray)):
            raise ValueError(
                f"{name} must be bytes, got {type(value).__name__}"
            )
        if len(value) != HASH_SIZE:
            raise ValueError(
                f"{name} must be exactly {HASH_SIZE} bytes, got {len(value)}"
            )

    @staticmethod
    def _validate_mr_enclave(value: str) -> None:
        if not isinstance(value, str):
            raise ValueError("mr_enclave must be a hex string")
        if len(value) != HASH_SIZE * 2:
            raise ValueError(
                f"mr_enclave must be {HASH_SIZE * 2} hex chars, got {len(value)}"
            )
        try:
            bytes.fromhex(value)
        except ValueError as e:
            raise ValueError(f"mr_enclave is not valid hex: {e}") from e

    def _build_mock_quote(self, report_data: bytes) -> str:
        """Construct a deterministic mock quote.

        Layout:
            magic (19B) || mr_enclave (32B) || report_data (64B) || sig (32B)

        The signature is SHA-256 of all preceding fields — NOT a real Intel
        PCK signature. On-chain verifiers MUST reject any quote that begins
        with AEGIS_MOCK_QUOTE_v1.
        """
        mr_enclave_bytes = bytes.fromhex(self._mr_enclave)
        body = MOCK_QUOTE_MAGIC + mr_enclave_bytes + report_data
        sig = hashlib.sha256(body).digest()
        return (body + sig).hex()
