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
  - DSTACK : real Intel TDX quotes via the dstack guest-agent Unix socket
             on Phala Cloud. Calls POST /GetQuote on /var/run/dstack.sock
             with report_data = SHA-256(input_hash || output_hash).

This module is the *only* component allowed to mint attestation quotes.
All other agent modules call QuoteGenerator.generate() so every decision
carries a verifiable proof of execution.
"""

from __future__ import annotations

import hashlib
import json
import logging
import socket
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

# Dstack guest-agent Unix socket path (mounted via docker-compose volumes).
DSTACK_SOCKET_PATH = "/var/run/dstack.sock"

# HTTP request timeout for the dstack guest-agent (seconds).
DSTACK_TIMEOUT = 10


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
        dstack_socket: Optional[str] = None,
    ) -> None:
        """Initialise the generator.

        Args:
            mock: If True (default), use the local mock backend.
                  If False, use real Dstack TDX backend via Unix socket.
            mock_mr_enclave: Override the default mock mr_enclave.
                             Must be 64 hex chars (32 bytes). Mock-only.
            dstack_socket: Path to the dstack guest-agent Unix socket.
                           Defaults to /var/run/dstack.sock.
        """
        self.mock = mock
        self._dstack_socket = dstack_socket or DSTACK_SOCKET_PATH

        if mock_mr_enclave is None:
            mock_mr_enclave = DEFAULT_MOCK_MR_ENCLAVE
        self._validate_mr_enclave(mock_mr_enclave)
        self._mr_enclave = mock_mr_enclave

        if not self.mock:
            # Verify the socket exists — fail fast if not on a TDX CVM.
            import os
            if not os.path.exists(self._dstack_socket):
                raise QuoteGenerationError(
                    f"Dstack socket not found at {self._dstack_socket}. "
                    f"Are you running inside a Phala Cloud TDX CVM? "
                    f"Set mock=True for local development."
                )
            logger.info(
                "Dstack TDX backend enabled — socket at %s",
                self._dstack_socket,
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
            mr_enclave = self._mr_enclave
            is_mock = True
        else:
            quote_hex, mr_enclave = self._get_dstack_quote(report_data)
            is_mock = False

        result = AttestationQuote(
            quote_hex=quote_hex,
            report_data=report_data,
            mr_enclave=mr_enclave,
            timestamp=int(time.time()),
            is_mock=is_mock,
        )

        logger.info(
            "Generated %s quote (input=%s..., output=%s...)",
            "MOCK" if is_mock else "REAL",
            bytes(input_hash).hex()[:8],
            bytes(output_hash).hex()[:8],
        )
        return result

    # ── Dstack TDX backend ─────────────────────────────────────────────────

    def _get_dstack_quote(self, report_data: bytes) -> tuple[str, str]:
        """Call the dstack guest-agent via Unix socket to get a real TDX quote.

        The dstack guest-agent exposes a REST API on /var/run/dstack.sock:
            POST /GetQuote
            Body: {"reportData": "0x<hex>"}
            Response: {"quote": "0x<hex>"}

        The report_data MUST be max 64 bytes. For the TDX driver, the actual
        report_data is SHA-256(report_data) — but the guest-agent handles
        that internally. We pass our 64-byte payload (input_hash||output_hash)
        as-is.

        Returns:
            (quote_hex, mr_enclave) — both without 0x prefix.

        Raises:
            QuoteGenerationError on any failure.
        """
        report_data_hex = "0x" + report_data.hex()

        try:
            # Build raw HTTP request — we use a raw Unix socket because
            # httpx/requests don't natively support UDS without extra deps.
            body = json.dumps({"reportData": report_data_hex}).encode()
            request = (
                b"POST /GetQuote HTTP/1.1\r\n"
                b"Host: dstack\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Connection: close\r\n"
                b"\r\n"
                + body
            )

            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(DSTACK_TIMEOUT)
            sock.connect(self._dstack_socket)
            sock.sendall(request)

            # Read response
            chunks = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            sock.close()

            raw_response = b"".join(chunks).decode("utf-8", errors="replace")

            # Parse HTTP response — find the JSON body after \r\n\r\n
            header_end = raw_response.find("\r\n\r\n")
            if header_end == -1:
                raise QuoteGenerationError(
                    f"Invalid HTTP response from dstack: {raw_response[:200]}"
                )
            json_body = raw_response[header_end + 4:]

            data = json.loads(json_body)
            quote_raw = data.get("quote", "")
            if not quote_raw:
                raise QuoteGenerationError(
                    f"No 'quote' field in dstack response: {data}"
                )

            # Strip 0x prefix if present
            quote_hex = quote_raw.removeprefix("0x").removeprefix("0X")

            # Extract mr_enclave from the TDX quote structure.
            # In a TDX DCAP quote v4, the TD report body starts at offset 48,
            # and MRTD (mr_enclave equivalent) is at bytes 256-304 within the
            # report body, so absolute offset 304-352 in the quote.
            # For our purposes, we'll use the first 32 bytes after the header
            # as a simplified mr_enclave — the on-chain verifier does the full
            # DCAP parsing anyway.
            quote_bytes = bytes.fromhex(quote_hex)
            if len(quote_bytes) < 352:
                # Quote is too short to extract MRTD — use hash of quote
                logger.warning(
                    "TDX quote too short for MRTD extraction (%d bytes), "
                    "using SHA-256 of quote as mr_enclave",
                    len(quote_bytes),
                )
                mr_enclave = hashlib.sha256(quote_bytes).hexdigest()
            else:
                # Extract MRTD from TDX quote body (offset 304-336)
                mr_enclave = quote_bytes[304:336].hex()

            logger.info(
                "Got real TDX quote from dstack (%d bytes, mr_enclave=%s...)",
                len(quote_bytes), mr_enclave[:8],
            )
            return quote_hex, mr_enclave

        except QuoteGenerationError:
            raise
        except json.JSONDecodeError as e:
            raise QuoteGenerationError(
                f"Failed to parse dstack response as JSON: {e}"
            ) from e
        except socket.timeout:
            raise QuoteGenerationError(
                f"Timeout ({DSTACK_TIMEOUT}s) waiting for dstack guest-agent"
            ) from None
        except OSError as e:
            raise QuoteGenerationError(
                f"Socket error communicating with dstack: {e}"
            ) from e

    # ── mock backend ───────────────────────────────────────────────────────

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
