"""Unit tests for QuoteGenerator (mock backend)."""

from __future__ import annotations

import hashlib
import time
from dataclasses import FrozenInstanceError

import pytest

from aegis_agent.quote_generator import (
    DEFAULT_MOCK_MR_ENCLAVE,
    HASH_SIZE,
    MOCK_QUOTE_MAGIC,
    REPORT_DATA_SIZE,
    AttestationQuote,
    QuoteGenerationError,
    QuoteGenerator,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def gen() -> QuoteGenerator:
    """Default mock generator."""
    return QuoteGenerator(mock=True)


@pytest.fixture
def sample_hashes() -> tuple[bytes, bytes]:
    """Two distinct 32-byte SHA-256 digests."""
    h_in = hashlib.sha256(b"input-prompt").digest()
    h_out = hashlib.sha256(b"output-decision").digest()
    return h_in, h_out


# ── Initialisation ────────────────────────────────────────────────────────

class TestInit:
    def test_default_is_mock(self, gen: QuoteGenerator) -> None:
        assert gen.mock is True
    def test_real_backend_requires_socket(self) -> None:
        """mock=False without a dstack socket raises QuoteGenerationError."""
        with pytest.raises(QuoteGenerationError, match="not found"):
            QuoteGenerator(mock=False)



            QuoteGenerator(mock=False)

    def test_default_mr_enclave(self, gen: QuoteGenerator) -> None:
        assert gen._mr_enclave == DEFAULT_MOCK_MR_ENCLAVE

    def test_custom_mr_enclave(self) -> None:
        custom = "ab" * 32  # 64 hex chars
        g = QuoteGenerator(mock=True, mock_mr_enclave=custom)
        assert g._mr_enclave == custom

    def test_invalid_mr_enclave_length(self) -> None:
        with pytest.raises(ValueError, match="64 hex chars"):
            QuoteGenerator(mock=True, mock_mr_enclave="abcd")

    def test_invalid_mr_enclave_not_hex(self) -> None:
        with pytest.raises(ValueError, match="not valid hex"):
            QuoteGenerator(mock=True, mock_mr_enclave="zz" * 32)


# ── generate() — happy path ───────────────────────────────────────────────

class TestGenerateHappyPath:
    def test_returns_attestation_quote(
        self, gen: QuoteGenerator, sample_hashes: tuple[bytes, bytes]
    ) -> None:
        h_in, h_out = sample_hashes
        q = gen.generate(h_in, h_out)
        assert isinstance(q, AttestationQuote)

    def test_is_mock_flag(
        self, gen: QuoteGenerator, sample_hashes: tuple[bytes, bytes]
    ) -> None:
        h_in, h_out = sample_hashes
        q = gen.generate(h_in, h_out)
        assert q.is_mock is True

    def test_report_data_layout(
        self, gen: QuoteGenerator, sample_hashes: tuple[bytes, bytes]
    ) -> None:
        h_in, h_out = sample_hashes
        q = gen.generate(h_in, h_out)
        assert len(q.report_data) == REPORT_DATA_SIZE
        assert q.report_data[:HASH_SIZE] == h_in
        assert q.report_data[HASH_SIZE:] == h_out

    def test_mr_enclave_propagated(
        self, gen: QuoteGenerator, sample_hashes: tuple[bytes, bytes]
    ) -> None:
        h_in, h_out = sample_hashes
        q = gen.generate(h_in, h_out)
        assert q.mr_enclave == DEFAULT_MOCK_MR_ENCLAVE

    def test_quote_hex_is_valid_hex(
        self, gen: QuoteGenerator, sample_hashes: tuple[bytes, bytes]
    ) -> None:
        h_in, h_out = sample_hashes
        q = gen.generate(h_in, h_out)
        bytes.fromhex(q.quote_hex)  # raises if not valid hex

    def test_timestamp_is_recent(
        self, gen: QuoteGenerator, sample_hashes: tuple[bytes, bytes]
    ) -> None:
        h_in, h_out = sample_hashes
        before = int(time.time())
        q = gen.generate(h_in, h_out)
        after = int(time.time())
        assert before <= q.timestamp <= after


# ── Mock-quote structure ──────────────────────────────────────────────────

class TestMockStructure:
    def test_quote_starts_with_magic(
        self, gen: QuoteGenerator, sample_hashes: tuple[bytes, bytes]
    ) -> None:
        h_in, h_out = sample_hashes
        q = gen.generate(h_in, h_out)
        quote_bytes = bytes.fromhex(q.quote_hex)
        assert quote_bytes.startswith(MOCK_QUOTE_MAGIC), (
            "Mock quote MUST carry the AEGIS_MOCK_QUOTE_v1 magic prefix "
            "so on-chain verifiers can reject mocks."
        )

    def test_quote_contains_report_data(
        self, gen: QuoteGenerator, sample_hashes: tuple[bytes, bytes]
    ) -> None:
        h_in, h_out = sample_hashes
        q = gen.generate(h_in, h_out)
        assert q.report_data in bytes.fromhex(q.quote_hex)

    def test_quote_is_deterministic_for_same_inputs(
        self, sample_hashes: tuple[bytes, bytes]
    ) -> None:
        # Mock backend should be deterministic so unit tests can use snapshots.
        h_in, h_out = sample_hashes
        g1 = QuoteGenerator(mock=True)
        g2 = QuoteGenerator(mock=True)
        q1 = g1.generate(h_in, h_out)
        q2 = g2.generate(h_in, h_out)
        assert q1.quote_hex == q2.quote_hex

    def test_different_inputs_yield_different_quotes(
        self, gen: QuoteGenerator
    ) -> None:
        a = hashlib.sha256(b"A").digest()
        b = hashlib.sha256(b"B").digest()
        c = hashlib.sha256(b"C").digest()
        q1 = gen.generate(a, b)
        q2 = gen.generate(a, c)
        assert q1.quote_hex != q2.quote_hex


# ── Validation errors ─────────────────────────────────────────────────────

class TestValidation:
    @pytest.mark.parametrize("bad", [b"", b"too short", b"x" * 31, b"x" * 33])
    def test_input_hash_wrong_length(
        self, gen: QuoteGenerator, bad: bytes
    ) -> None:
        with pytest.raises(ValueError, match="input_hash"):
            gen.generate(bad, b"y" * 32)

    @pytest.mark.parametrize("bad", [b"", b"too short", b"x" * 31, b"x" * 33])
    def test_output_hash_wrong_length(
        self, gen: QuoteGenerator, bad: bytes
    ) -> None:
        with pytest.raises(ValueError, match="output_hash"):
            gen.generate(b"x" * 32, bad)

    def test_input_hash_wrong_type(self, gen: QuoteGenerator) -> None:
        with pytest.raises(ValueError, match="must be bytes"):
            gen.generate("not bytes", b"y" * 32)  # type: ignore[arg-type]

    def test_bytearray_accepted(self, gen: QuoteGenerator) -> None:
        # bytearray is bytes-like; should be accepted and normalised.
        h_in = bytearray(hashlib.sha256(b"x").digest())
        h_out = bytearray(hashlib.sha256(b"y").digest())
        q = gen.generate(h_in, h_out)
        assert q.report_data[:HASH_SIZE] == bytes(h_in)


# ── Immutability ──────────────────────────────────────────────────────────

class TestDataclass:
    def test_attestation_quote_is_frozen(
        self, gen: QuoteGenerator, sample_hashes: tuple[bytes, bytes]
    ) -> None:
        h_in, h_out = sample_hashes
        q = gen.generate(h_in, h_out)
        with pytest.raises(FrozenInstanceError):
            q.is_mock = False  # type: ignore[misc]
