"""
test_decision_engine.py — Tests for Step 6: DecisionEngine + actionHash flow

Covers:
  - compute_action_hash matches Solidity abi.encode + keccak256
  - DecisionEngine.decide() with mocked Ollama (no real LLM needed)
  - QuoteStore stores/retrieves input_hash separately
  - /quotes/{digest} returns action_hash + separate input_hash
  - End-to-end: decide() -> store -> HTTP lookup
"""

from __future__ import annotations

import hashlib
import time
from unittest.mock import MagicMock, patch

import pytest
from eth_abi import encode as abi_encode
from eth_utils import keccak

from aegis_agent.decision_engine import (
    ACTION_EXPIRY_SECONDS,
    DecisionEngine,
    DecisionResult,
    compute_action_hash,
)
from aegis_agent.http_server import QuoteStore, get_store
from aegis_agent.ollama_client import LLMResponse
from aegis_agent.quote_generator import HASH_SIZE, AttestationQuote, QuoteGenerator


# ────────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────────

DEMO_USER = "0x36c6eB92bfABaF637aa1607EccE02e0EC952F82C"
DEMO_TARGET = "0x000000000000000000000000000000000000dEaD"
DEMO_BALANCE = 10**18  # 1 ETH
DEMO_NONCE = 0


def _make_mock_llm_response(action: str = "HOLD", amount: int = 0) -> LLMResponse:
    """Create a fake LLMResponse for testing without Ollama."""
    target = "0x0000000000000000000000000000000000000000" if action == "HOLD" else DEMO_TARGET
    response_text = (
        f'{{"action": "{action}", "amount_wei": {amount}, '
        f'"target": "{target}", '
        f'"reasoning": "Test decision"}}'
    )
    input_str = "SYSTEM:test\nUSER:test\nMODEL:qwen2.5:7b"
    return LLMResponse(
        model="qwen2.5:7b",
        prompt="test prompt",
        response=response_text,
        input_hash="0x" + hashlib.sha256(input_str.encode()).hexdigest(),
        output_hash="0x" + hashlib.sha256(response_text.encode()).hexdigest(),
        elapsed_ms=100,
        eval_count=50,
    )


def _make_mock_ollama(llm_response: LLMResponse) -> MagicMock:
    """Create a mock OllamaClient that returns a canned response."""
    mock = MagicMock()
    mock.generate.return_value = llm_response
    mock.parse_json_response = MagicMock(
        side_effect=lambda text: __import__("json").loads(text)
    )
    return mock


# ────────────────────────────────────────────────────────────────────────────
# Tests: compute_action_hash
# ────────────────────────────────────────────────────────────────────────────

class TestComputeActionHash:
    """Verify Python actionHash matches the Solidity computation."""

    def test_deterministic(self):
        """Same inputs produce the same hash."""
        h1 = compute_action_hash(DEMO_USER, 1000, DEMO_TARGET, 0, 1700000000)
        h2 = compute_action_hash(DEMO_USER, 1000, DEMO_TARGET, 0, 1700000000)
        assert h1 == h2
        assert len(h1) == 32

    def test_different_amount_different_hash(self):
        """Changing amount changes the hash."""
        h1 = compute_action_hash(DEMO_USER, 1000, DEMO_TARGET, 0, 1700000000)
        h2 = compute_action_hash(DEMO_USER, 2000, DEMO_TARGET, 0, 1700000000)
        assert h1 != h2

    def test_different_target_different_hash(self):
        """Changing target changes the hash."""
        h1 = compute_action_hash(DEMO_USER, 1000, DEMO_TARGET, 0, 1700000000)
        h2 = compute_action_hash(
            DEMO_USER, 1000,
            "0x0000000000000000000000000000000000000001",
            0, 1700000000,
        )
        assert h1 != h2

    def test_different_nonce_different_hash(self):
        """Changing nonce changes the hash (replay protection)."""
        h1 = compute_action_hash(DEMO_USER, 1000, DEMO_TARGET, 0, 1700000000)
        h2 = compute_action_hash(DEMO_USER, 1000, DEMO_TARGET, 1, 1700000000)
        assert h1 != h2

    def test_matches_manual_abi_encode(self):
        """Verify against manual eth_abi.encode + keccak."""
        user = DEMO_USER
        amount = 5000
        target = DEMO_TARGET
        nonce = 3
        ts = 1700000000

        # Manual computation
        encoded = abi_encode(
            ["address", "uint256", "address", "uint256", "uint256"],
            [user, amount, target, nonce, ts],
        )
        expected = keccak(encoded)

        result = compute_action_hash(user, amount, target, nonce, ts)
        assert result == expected

    def test_zero_amount_hold(self):
        """HOLD action (amount=0) still produces a valid 32-byte hash."""
        h = compute_action_hash(
            DEMO_USER, 0,
            "0x0000000000000000000000000000000000000000",
            0, 1700000000,
        )
        assert len(h) == 32
        assert h != b"\x00" * 32  # not all zeros


# ────────────────────────────────────────────────────────────────────────────
# Tests: QuoteStore with input_hash
# ────────────────────────────────────────────────────────────────────────────

class TestQuoteStoreInputHash:
    """Test the Step 6 input_hash storage in QuoteStore."""

    def test_put_with_input_hash(self):
        store = QuoteStore()
        quote = QuoteGenerator(mock=True).generate(
            input_hash=b"\xaa" * 32,
            output_hash=b"\xbb" * 32,
        )
        fake_input = b"\xcc" * 32
        digest = store.put(quote, input_hash=fake_input)

        assert store.get_input_hash(digest) == fake_input

    def test_put_without_input_hash_backward_compat(self):
        store = QuoteStore()
        quote = QuoteGenerator(mock=True).generate(
            input_hash=b"\xaa" * 32,
            output_hash=b"\xbb" * 32,
        )
        digest = store.put(quote)

        assert store.get_input_hash(digest) is None

    def test_get_input_hash_normalises_digest(self):
        store = QuoteStore()
        quote = QuoteGenerator(mock=True).generate(
            input_hash=b"\xaa" * 32,
            output_hash=b"\xbb" * 32,
        )
        fake_input = b"\xdd" * 32
        digest = store.put(quote, input_hash=fake_input)

        # Query without 0x prefix
        bare = digest.removeprefix("0x")
        assert store.get_input_hash(bare) == fake_input

    def test_multiple_quotes_independent_input_hashes(self):
        store = QuoteStore()
        gen = QuoteGenerator(mock=True)

        q1 = gen.generate(input_hash=b"\x01" * 32, output_hash=b"\x02" * 32)
        q2 = gen.generate(input_hash=b"\x03" * 32, output_hash=b"\x04" * 32)

        ih1 = b"\xaa" * 32
        ih2 = b"\xbb" * 32
        d1 = store.put(q1, input_hash=ih1)
        d2 = store.put(q2, input_hash=ih2)

        assert store.get_input_hash(d1) == ih1
        assert store.get_input_hash(d2) == ih2


# ────────────────────────────────────────────────────────────────────────────
# Tests: DecisionEngine
# ────────────────────────────────────────────────────────────────────────────

class TestDecisionEngine:
    """Test DecisionEngine.decide() with mocked dependencies."""

    def _make_engine(self, llm_response: LLMResponse) -> DecisionEngine:
        mock_ollama = _make_mock_ollama(llm_response)
        quote_gen = QuoteGenerator(mock=True)
        return DecisionEngine(
            ollama=mock_ollama,
            quote_gen=quote_gen,
            chainlink=None,
        )

    def test_hold_decision(self):
        resp = _make_mock_llm_response(action="HOLD", amount=0)
        engine = self._make_engine(resp)

        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="2500.00",
        )

        assert isinstance(result, DecisionResult)
        assert result.action == "HOLD"
        assert result.amount_wei == 0
        assert result.user == DEMO_USER
        assert result.nonce == DEMO_NONCE
        assert result.is_mock is True
        assert result.eth_usd_price == "2500.00"

    def test_transfer_decision(self):
        resp = _make_mock_llm_response(action="TRANSFER", amount=500000)
        engine = self._make_engine(resp)

        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="1800.00",
        )

        assert result.action == "TRANSFER"
        assert result.amount_wei == 500000
        assert result.target == DEMO_USER

    def test_transfer_target_forced_to_emergency_safe(self):
        """The model can choose TRANSFER and amount, but not destination."""
        resp = _make_mock_llm_response(action="TRANSFER", amount=500000)
        engine = self._make_engine(resp)

        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="1800.00",
        )

        assert DEMO_TARGET in resp.response
        assert result.action == "TRANSFER"
        assert result.target == DEMO_USER

    def test_action_hash_is_32_bytes_hex(self):
        resp = _make_mock_llm_response(action="HOLD", amount=0)
        engine = self._make_engine(resp)

        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="2500.00",
        )

        assert result.action_hash.startswith("0x")
        assert len(result.action_hash) == 66  # 0x + 64 hex chars

    def test_action_hash_matches_contract_logic(self):
        """The action_hash in result must match what the Vault would compute."""
        resp = _make_mock_llm_response(action="HOLD", amount=0)
        engine = self._make_engine(resp)

        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="2500.00",
        )

        # Recompute from result fields
        expected = compute_action_hash(
            result.user, result.amount_wei, result.target,
            result.nonce, result.timestamp,
        )
        assert result.action_hash == "0x" + expected.hex()

    def test_quote_stored_in_quote_store(self):
        resp = _make_mock_llm_response(action="HOLD", amount=0)
        engine = self._make_engine(resp)

        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="2500.00",
        )

        # The quote should be retrievable from the global store
        store = get_store()
        quote = store.get(result.quote_digest)
        assert quote is not None
        assert quote.is_mock is True

    def test_input_hash_stored_separately(self):
        resp = _make_mock_llm_response(action="HOLD", amount=0)
        engine = self._make_engine(resp)

        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="2500.00",
        )

        store = get_store()
        stored_ih = store.get_input_hash(result.quote_digest)
        assert stored_ih is not None
        assert "0x" + stored_ih.hex() == result.input_hash

    def test_amount_clamped_to_balance(self):
        """If LLM requests more than balance, clamp to balance."""
        huge_amount = DEMO_BALANCE * 10
        resp = _make_mock_llm_response(action="TRANSFER", amount=huge_amount)
        engine = self._make_engine(resp)

        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="2500.00",
        )

        assert result.amount_wei == DEMO_BALANCE  # clamped

    def test_timestamp_in_future(self):
        resp = _make_mock_llm_response(action="HOLD", amount=0)
        engine = self._make_engine(resp)

        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="2500.00",
        )

        assert result.timestamp > int(time.time())
        assert result.timestamp <= int(time.time()) + ACTION_EXPIRY_SECONDS + 2

    def test_report_data_layout(self):
        """report_data[0:32] = actionHash, report_data[32:64] = output_hash."""
        resp = _make_mock_llm_response(action="HOLD", amount=0)
        engine = self._make_engine(resp)

        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="2500.00",
        )

        store = get_store()
        quote = store.get(result.quote_digest)
        rd = quote.report_data

        # First 32 bytes = actionHash
        assert "0x" + rd[:32].hex() == result.action_hash
        # Second 32 bytes = output_hash
        assert "0x" + rd[32:].hex() == result.output_hash


# ────────────────────────────────────────────────────────────────────────────
# Tests: HTTP endpoint with action_hash
# ────────────────────────────────────────────────────────────────────────────

class TestQuoteEndpointActionHash:
    """Test GET /quotes/{digest} returns action_hash + separate input_hash."""

    @pytest.fixture
    def client(self):
        from httpx import ASGITransport, AsyncClient
        from aegis_agent.http_server import app
        import asyncio

        transport = ASGITransport(app=app)
        # Use sync wrapper for async client
        return transport

    def test_quote_response_has_action_hash(self):
        """After storing a quote with input_hash, endpoint returns action_hash."""
        store = get_store()
        gen = QuoteGenerator(mock=True)

        action_hash_bytes = b"\xab" * 32
        output_hash_bytes = b"\xcd" * 32
        real_input_hash = b"\xef" * 32

        quote = gen.generate(
            input_hash=action_hash_bytes,
            output_hash=output_hash_bytes,
        )
        digest = store.put(quote, input_hash=real_input_hash)

        # Call endpoint via test client
        from starlette.testclient import TestClient
        from aegis_agent.http_server import app

        with TestClient(app) as tc:
            resp = tc.get(f"/quotes/{digest}")

        assert resp.status_code == 200
        body = resp.json()

        # action_hash = report_data[0:32]
        assert body["action_hash"] == "0x" + action_hash_bytes.hex()
        # input_hash from separate storage, NOT from report_data
        assert body["input_hash"] == "0x" + real_input_hash.hex()
        # output_hash = report_data[32:64]
        assert body["output_hash"] == "0x" + output_hash_bytes.hex()
        # action_hash != input_hash (they're different!)
        assert body["action_hash"] != body["input_hash"]
