"""
test_decision_engine_swap.py — Tests for SWAP action extension

Covers:
  - DecisionEngine.decide() returns SWAP when LLM says SWAP
  - swap_calldata, swap_calldata_hash, swap_amount_out_min populated
  - SWAP target overridden to Uniswap Router (not LLM-supplied address)
  - SWAP amount defaults to 30% if LLM gives 0
  - SWAP amount clamped to balance
  - HOLD/TRANSFER still work (regression, including forced target)
  - DecisionResult optional fields default to None for non-SWAP
"""

from __future__ import annotations

import hashlib
import time
from unittest.mock import MagicMock, patch

import pytest
from eth_abi.abi import encode as abi_encode
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
from aegis_agent.swap_encoder import SwapConfig

# ────────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────────

DEMO_USER = "0x36c6eB92bfABaF637aa1607EccE02e0EC952F82C"
DEMO_TARGET = "0x000000000000000000000000000000000000dEaD"
DEMO_BALANCE = 10**18  # 1 ETH
DEMO_NONCE = 0


def _make_llm_response(action: str, amount: int, target: str = "") -> LLMResponse:
    """Create a fake LLMResponse for testing without a real LLM."""
    if not target:
        target = "0x0000000000000000000000000000000000000000"
    response_text = (
        f'{{"action": "{action}", "amount_wei": {amount}, '
        f'"target": "{target}", '
        f'"reasoning": "Test {action} decision"}}'
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


def _make_engine() -> DecisionEngine:
    """Build a DecisionEngine with mocked LLM client (no real LLM)."""
    ollama = MagicMock()
    ollama.health_check.return_value = True
    ollama.model = "qwen2.5:7b"
    quote_gen = QuoteGenerator(mock=True)
    return DecisionEngine(ollama=ollama, quote_gen=quote_gen, chainlink=None)


# ────────────────────────────────────────────────────────────────────────────
# SWAP action tests
# ────────────────────────────────────────────────────────────────────────────

class TestSwapAction:
    """Tests for the new SWAP action type."""

    def test_swap_action_recognised(self):
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response(
            "SWAP", 3 * 10**17,
        )
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="3500.00",
        )
        assert result.action == "SWAP"

    def test_swap_has_calldata(self):
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response(
            "SWAP", 3 * 10**17,
        )
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="3500.00",
        )
        assert result.swap_calldata is not None
        assert result.swap_calldata.startswith("0x7ff36ab5")

    def test_swap_has_calldata_hash(self):
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response(
            "SWAP", 3 * 10**17,
        )
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="3500.00",
        )
        assert result.swap_calldata_hash is not None
        assert result.swap_calldata_hash.startswith("0x")
        assert len(result.swap_calldata_hash) == 66  # 0x + 64 hex

    def test_swap_has_amount_out_min(self):
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response(
            "SWAP", 3 * 10**17,
        )
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="3500.00",
        )
        assert result.swap_amount_out_min is not None
        assert result.swap_amount_out_min > 0

    def test_swap_target_is_router(self):
        """SWAP must override target to Uniswap Router, not LLM address."""
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response(
            "SWAP", 3 * 10**17,
            target="0x000000000000000000000000000000000000dEaD",
        )
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="3500.00",
        )
        assert result.target == SwapConfig().router

    def test_swap_amount_defaults_30pct(self):
        """If LLM gives amount_wei=0 for SWAP, default to 30% of balance."""
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response("SWAP", 0)
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="3500.00",
        )
        expected = int(DEMO_BALANCE * 0.3)
        assert result.amount_wei == expected

    def test_swap_amount_clamped_to_balance(self):
        """SWAP amount cannot exceed vault balance."""
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response(
            "SWAP", 2 * 10**18,  # 2 ETH > 1 ETH balance
        )
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="3500.00",
        )
        assert result.amount_wei == DEMO_BALANCE

    def test_swap_action_hash_uses_router_target(self):
        """actionHash must use Router as target (not ZERO_ADDRESS)."""
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response(
            "SWAP", 3 * 10**17,
        )
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="3500.00",
        )
        expected = compute_action_hash(
            DEMO_USER, result.amount_wei, SwapConfig().router,
            DEMO_NONCE, result.timestamp,
        )
        assert result.action_hash == "0x" + expected.hex()

    def test_swap_calldata_both_non_none(self):
        """Same inputs produce valid calldata."""
        engine = _make_engine()
        resp = _make_llm_response("SWAP", 3 * 10**17)
        engine.ollama.generate.return_value = resp
        r1 = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="3500.00",
        )
        engine.ollama.generate.return_value = resp
        r2 = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="3500.00",
        )
        assert r1.swap_calldata is not None
        assert r2.swap_calldata is not None
        # Both start with the same selector
        assert r1.swap_calldata[:10] == r2.swap_calldata[:10]

    def test_swap_slippage_protects_output(self):
        """amount_out_min should reflect 1% slippage from price."""
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response(
            "SWAP", 10**18,  # 1 ETH
        )
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="2500.00",
        )
        # 1 ETH @ $2500, 1% slippage = min $2475 = 2475000000 USDC units
        assert result.swap_amount_out_min == 2475_000_000


# ────────────────────────────────────────────────────────────────────────────
# Regression: HOLD and TRANSFER still work with forced target
# ────────────────────────────────────────────────────────────────────────────

class TestNonSwapRegression:
    """Ensure HOLD/TRANSFER are not broken by SWAP addition."""

    def test_hold_has_no_swap_fields(self):
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response("HOLD", 0)
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="2500.00",
        )
        assert result.action == "HOLD"
        assert result.swap_calldata is None
        assert result.swap_calldata_hash is None
        assert result.swap_amount_out_min is None

    def test_transfer_has_no_swap_fields(self):
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response(
            "TRANSFER", 2 * 10**17,
            target=DEMO_TARGET,
        )
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="1700.00",
        )
        assert result.action == "TRANSFER"
        assert result.swap_calldata is None

    def test_transfer_target_forced_to_emergency_safe(self):
        """Regression: TRANSFER target must always be user (emergency safe)."""
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response(
            "TRANSFER", 5 * 10**17,
            target=DEMO_TARGET,
        )
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="1700.00",
        )
        assert result.target == DEMO_USER

    def test_unknown_action_defaults_to_hold(self):
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response("YOLO", 999)
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="2500.00",
        )
        assert result.action == "HOLD"
        assert result.amount_wei == 0
        assert result.swap_calldata is None

    def test_hold_still_produces_valid_action_hash(self):
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response("HOLD", 0)
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="2500.00",
        )
        assert result.action_hash.startswith("0x")
        assert len(result.action_hash) == 66

    def test_transfer_clamps_amount(self):
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response(
            "TRANSFER", 5 * 10**18,  # 5 ETH > 1 ETH balance
            target=DEMO_USER,
        )
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="1500.00",
        )
        assert result.amount_wei == DEMO_BALANCE


# ────────────────────────────────────────────────────────────────────────────
# QuoteStore with SWAP
# ────────────────────────────────────────────────────────────────────────────

class TestSwapQuoteStore:
    """Verify SWAP decisions get stored in QuoteStore like HOLD/TRANSFER."""

    def test_swap_quote_stored(self):
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response(
            "SWAP", 3 * 10**17,
        )
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="3500.00",
        )
        store = get_store()
        entry = store.get(result.quote_digest)
        assert entry is not None

    def test_swap_quote_has_action_hash(self):
        engine = _make_engine()
        engine.ollama.generate.return_value = _make_llm_response(
            "SWAP", 3 * 10**17,
        )
        result = engine.decide(
            user=DEMO_USER, balance_wei=DEMO_BALANCE,
            nonce=DEMO_NONCE, mock_price="3500.00",
        )
        store = get_store()
        entry = store.get(result.quote_digest)
        assert entry is not None
        assert result.action_hash.startswith("0x")
        assert len(result.action_hash) == 66
