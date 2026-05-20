"""
test_swap_encoder.py — Tests for Uniswap V2 swap calldata encoding

Covers:
  - Function selector correctness (matches Solidity signature)
  - Calldata ABI encoding structure
  - Slippage calculation with various inputs
  - Input validation (negative amounts, bad slippage)
  - build_swap_params end-to-end
  - Custom SwapConfig override
"""

from __future__ import annotations

import time

import pytest
from eth_abi import decode as abi_decode
from eth_utils import keccak

from aegis_agent.swap_encoder import (
    DEFAULT_SLIPPAGE_BPS,
    SWAP_EXACT_ETH_SELECTOR,
    SwapConfig,
    SwapParams,
    build_swap_params,
    compute_amount_out_min,
    encode_swap_exact_eth_for_tokens,
)

# ────────────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────────────

DEMO_USER = "0x36c6eB92bfABaF637aa1607EccE02e0EC952F82C"
DEMO_DEADLINE = int(time.time()) + 300


# ────────────────────────────────────────────────────────────────────────────
# Selector
# ────────────────────────────────────────────────────────────────────────────

class TestSelector:
    """Verify the 4-byte selector matches the Solidity function signature."""

    def test_selector_matches_solidity_signature(self):
        sig = "swapExactETHForTokens(uint256,address[],address,uint256)"
        computed = keccak(text=sig)[:4]
        assert computed == SWAP_EXACT_ETH_SELECTOR

    def test_selector_is_4_bytes(self):
        assert len(SWAP_EXACT_ETH_SELECTOR) == 4

    def test_selector_hex_value(self):
        assert SWAP_EXACT_ETH_SELECTOR.hex() == "7ff36ab5"


# ────────────────────────────────────────────────────────────────────────────
# encode_swap_exact_eth_for_tokens
# ────────────────────────────────────────────────────────────────────────────

class TestEncodeSwap:
    """Test low-level calldata encoding."""

    def test_calldata_starts_with_selector(self):
        calldata = encode_swap_exact_eth_for_tokens(
            amount_out_min=1000,
            path=["0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14",
                  "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"],
            to=DEMO_USER,
            deadline=DEMO_DEADLINE,
        )
        assert calldata[:4] == SWAP_EXACT_ETH_SELECTOR

    def test_calldata_is_decodable(self):
        """Verify the params portion can be ABI-decoded back."""
        path = ["0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14",
                "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"]
        amount_out_min = 247500000
        deadline = DEMO_DEADLINE

        calldata = encode_swap_exact_eth_for_tokens(
            amount_out_min=amount_out_min,
            path=path,
            to=DEMO_USER,
            deadline=deadline,
        )
        # Strip 4-byte selector, decode the rest
        decoded = abi_decode(
            ["uint256", "address[]", "address", "uint256"],
            calldata[4:],
        )
        assert decoded[0] == amount_out_min
        assert len(decoded[1]) == 2
        assert decoded[1][0].lower() == path[0].lower()
        assert decoded[1][1].lower() == path[1].lower()
        assert decoded[2].lower() == DEMO_USER.lower()
        assert decoded[3] == deadline

    def test_path_too_short_raises(self):
        with pytest.raises(ValueError, match="must have >= 2 tokens"):
            encode_swap_exact_eth_for_tokens(
                amount_out_min=1000,
                path=["0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"],
                to=DEMO_USER,
                deadline=DEMO_DEADLINE,
            )

    def test_empty_path_raises(self):
        with pytest.raises(ValueError, match="must have >= 2 tokens"):
            encode_swap_exact_eth_for_tokens(
                amount_out_min=0, path=[], to=DEMO_USER, deadline=DEMO_DEADLINE,
            )

    def test_three_hop_path(self):
        """WETH -> DAI -> USDC (multi-hop) should encode fine."""
        path = [
            "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14",
            "0x68194a729C2450ad26072b3D33ADaCbcef39D574",  # fake DAI
            "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
        ]
        calldata = encode_swap_exact_eth_for_tokens(
            amount_out_min=100, path=path, to=DEMO_USER, deadline=DEMO_DEADLINE,
        )
        decoded = abi_decode(["uint256", "address[]", "address", "uint256"], calldata[4:])
        assert len(decoded[1]) == 3

    def test_deterministic_encoding(self):
        """Same inputs must produce identical calldata."""
        args = dict(
            amount_out_min=999,
            path=["0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14",
                  "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"],
            to=DEMO_USER,
            deadline=1700000000,
        )
        assert encode_swap_exact_eth_for_tokens(**args) == encode_swap_exact_eth_for_tokens(**args)


# ────────────────────────────────────────────────────────────────────────────
# compute_amount_out_min
# ────────────────────────────────────────────────────────────────────────────

class TestAmountOutMin:
    """Test slippage-adjusted USDC output calculation."""

    def test_1_eth_at_2500_no_slippage(self):
        result = compute_amount_out_min(10**18, 2500.0, slippage_bps=0)
        assert result == 2500_000_000  # $2500 in 6-decimal USDC

    def test_1_eth_at_2500_1pct_slippage(self):
        result = compute_amount_out_min(10**18, 2500.0, slippage_bps=100)
        assert result == 2475_000_000  # $2475

    def test_half_eth(self):
        result = compute_amount_out_min(5 * 10**17, 2000.0, slippage_bps=0)
        assert result == 1000_000_000  # $1000

    def test_small_amount(self):
        result = compute_amount_out_min(10**15, 2500.0, slippage_bps=100)  # 0.001 ETH
        assert result == 2_475_000  # $2.475

    def test_5pct_slippage(self):
        result = compute_amount_out_min(10**18, 2000.0, slippage_bps=500)
        assert result == 1900_000_000  # $1900

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError, match="must be positive"):
            compute_amount_out_min(-1, 2500.0)

    def test_zero_amount_raises(self):
        with pytest.raises(ValueError, match="must be positive"):
            compute_amount_out_min(0, 2500.0)

    def test_negative_price_raises(self):
        with pytest.raises(ValueError, match="must be positive"):
            compute_amount_out_min(10**18, -100.0)

    def test_slippage_out_of_range_raises(self):
        with pytest.raises(ValueError, match="must be 0-5000"):
            compute_amount_out_min(10**18, 2500.0, slippage_bps=6000)

    def test_max_slippage_50pct(self):
        result = compute_amount_out_min(10**18, 2500.0, slippage_bps=5000)
        assert result == 1250_000_000  # $1250


# ────────────────────────────────────────────────────────────────────────────
# build_swap_params
# ────────────────────────────────────────────────────────────────────────────

class TestBuildSwapParams:
    """Test the main entry point used by DecisionEngine."""

    def test_returns_swap_params(self):
        result = build_swap_params(
            user=DEMO_USER,
            amount_wei=10**18,
            eth_price_usd=2500.0,
            deadline=DEMO_DEADLINE,
        )
        assert isinstance(result, SwapParams)

    def test_target_is_router(self):
        result = build_swap_params(
            user=DEMO_USER, amount_wei=10**18,
            eth_price_usd=2500.0, deadline=DEMO_DEADLINE,
        )
        assert result.target == SwapConfig().router

    def test_calldata_starts_with_0x_and_selector(self):
        result = build_swap_params(
            user=DEMO_USER, amount_wei=10**18,
            eth_price_usd=2500.0, deadline=DEMO_DEADLINE,
        )
        assert result.calldata.startswith("0x7ff36ab5")

    def test_calldata_hash_is_keccak(self):
        result = build_swap_params(
            user=DEMO_USER, amount_wei=10**18,
            eth_price_usd=2500.0, deadline=DEMO_DEADLINE,
        )
        raw = bytes.fromhex(result.calldata.removeprefix("0x"))
        expected_hash = "0x" + keccak(raw).hex()
        assert result.calldata_hash == expected_hash

    def test_path_is_weth_usdc(self):
        cfg = SwapConfig()
        result = build_swap_params(
            user=DEMO_USER, amount_wei=10**18,
            eth_price_usd=2500.0, deadline=DEMO_DEADLINE,
        )
        assert result.path == [cfg.weth, cfg.usdc]

    def test_amount_in_wei_preserved(self):
        result = build_swap_params(
            user=DEMO_USER, amount_wei=12345,
            eth_price_usd=2500.0, deadline=DEMO_DEADLINE,
        )
        assert result.amount_in_wei == 12345

    def test_custom_config(self):
        custom = SwapConfig(
            router="0x0000000000000000000000000000000000000001",
            weth="0x0000000000000000000000000000000000000002",
            usdc="0x0000000000000000000000000000000000000003",
        )
        result = build_swap_params(
            user=DEMO_USER, amount_wei=10**18,
            eth_price_usd=2500.0, deadline=DEMO_DEADLINE,
            config=custom,
        )
        assert result.target == custom.router
        assert result.path == [custom.weth, custom.usdc]

    def test_custom_slippage(self):
        result_1pct = build_swap_params(
            user=DEMO_USER, amount_wei=10**18,
            eth_price_usd=2500.0, deadline=DEMO_DEADLINE,
            slippage_bps=100,
        )
        result_5pct = build_swap_params(
            user=DEMO_USER, amount_wei=10**18,
            eth_price_usd=2500.0, deadline=DEMO_DEADLINE,
            slippage_bps=500,
        )
        assert result_1pct.amount_out_min > result_5pct.amount_out_min

    def test_frozen_dataclass(self):
        result = build_swap_params(
            user=DEMO_USER, amount_wei=10**18,
            eth_price_usd=2500.0, deadline=DEMO_DEADLINE,
        )
        with pytest.raises(AttributeError):
            result.target = "0xdead"  # type: ignore
