"""
swap_encoder.py — Uniswap V2 swap calldata encoder for AegisAgent

Encodes calldata for swapExactETHForTokens on Uniswap V2 Router02,
enabling the TEE agent to construct verifiable swap transactions.

The encoded calldata is included in DecisionResult so the frontend /
relayer can pass it to AegisVault when the contract supports calldata
execution (future upgrade).  Until then it serves as a proof-of-concept
that the attestation pipeline covers arbitrary DeFi operations.

Sepolia testnet addresses are used as defaults.

Author: LIU Kefan
Project: AegisAgent (SC6107, NTU CCDS, 2026)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from eth_abi import encode as abi_encode
from eth_utils import keccak

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Uniswap V2 Router02 — swapExactETHForTokens selector
# keccak256("swapExactETHForTokens(uint256,address[],address,uint256)")[:4]
# ────────────────────────────────────────────────────────────────────────────
SWAP_EXACT_ETH_SELECTOR = bytes.fromhex("7ff36ab5")

# ────────────────────────────────────────────────────────────────────────────
# Default Sepolia addresses (overridable via env vars)
# ────────────────────────────────────────────────────────────────────────────
DEFAULT_ROUTER = os.getenv(
    "AEGIS_UNISWAP_ROUTER",
    "0xC532a74256D3Db42D0Bf7a0400fEFDbad7694008",   # Uniswap V2 Router02 (Sepolia)
)
DEFAULT_WETH = os.getenv(
    "AEGIS_WETH_ADDRESS",
    "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14",   # WETH (Sepolia)
)
DEFAULT_USDC = os.getenv(
    "AEGIS_USDC_ADDRESS",
    "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",   # USDC (Sepolia, Circle)
)

# Slippage
DEFAULT_SLIPPAGE_BPS = 100   # 1%
USDC_DECIMALS = 6


# ────────────────────────────────────────────────────────────────────────────
# Data classes
# ────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SwapConfig:
    """Network-specific addresses for Uniswap V2 swap."""

    router: str = DEFAULT_ROUTER
    weth: str = DEFAULT_WETH
    usdc: str = DEFAULT_USDC


@dataclass(frozen=True)
class SwapParams:
    """Fully encoded swap parameters ready for on-chain submission."""

    target: str           # Router address
    calldata: str         # 0x-prefixed hex-encoded calldata
    amount_in_wei: int    # ETH to send as msg.value
    amount_out_min: int   # Minimum USDC output (slippage-adjusted)
    path: list[str]       # [WETH, USDC]
    deadline: int         # Unix timestamp deadline
    calldata_hash: str    # 0x-prefixed keccak256(calldata) for audit trail


# ────────────────────────────────────────────────────────────────────────────
# Calldata encoding
# ────────────────────────────────────────────────────────────────────────────

def encode_swap_exact_eth_for_tokens(
    amount_out_min: int,
    path: list[str],
    to: str,
    deadline: int,
) -> bytes:
    """Encode calldata for Uniswap V2 Router.swapExactETHForTokens().

    Solidity signature::

        function swapExactETHForTokens(
            uint amountOutMin,
            address[] calldata path,
            address to,
            uint deadline
        ) external payable returns (uint[] memory amounts);

    The ETH amount is sent as msg.value, not encoded in calldata.

    Args:
        amount_out_min: Minimum output tokens (slippage-protected).
        path: Token swap path, e.g. [WETH, USDC].
        to: Recipient address for output tokens.
        deadline: Unix timestamp after which the tx reverts.

    Returns:
        4-byte selector + ABI-encoded params.

    Raises:
        ValueError: If path has fewer than 2 addresses.
    """
    if len(path) < 2:
        raise ValueError(f"Swap path must have >= 2 tokens, got {len(path)}")

    params = abi_encode(
        ["uint256", "address[]", "address", "uint256"],
        [amount_out_min, path, to, deadline],
    )
    return SWAP_EXACT_ETH_SELECTOR + params


def compute_amount_out_min(
    amount_in_wei: int,
    eth_price_usd: float,
    slippage_bps: int = DEFAULT_SLIPPAGE_BPS,
    usdc_decimals: int = USDC_DECIMALS,
) -> int:
    """Estimate minimum USDC output with slippage protection.

    Uses a simplified price-based calculation.  A production system
    would query on-chain reserves or a Quoter contract.

    Args:
        amount_in_wei: ETH input in wei.
        eth_price_usd: Current ETH/USD price from Chainlink.
        slippage_bps: Slippage tolerance in basis points (100 = 1%).
        usdc_decimals: USDC decimal places (default 6).

    Returns:
        Minimum USDC amount in smallest unit (6 decimals).

    Raises:
        ValueError: If inputs are non-positive.
    """
    if amount_in_wei <= 0:
        raise ValueError(f"amount_in_wei must be positive, got {amount_in_wei}")
    if eth_price_usd <= 0:
        raise ValueError(f"eth_price_usd must be positive, got {eth_price_usd}")
    if not 0 <= slippage_bps <= 5000:
        raise ValueError(f"slippage_bps must be 0-5000, got {slippage_bps}")

    eth_amount = amount_in_wei / 1e18
    expected_usdc = eth_amount * eth_price_usd
    slippage_factor = 1 - (slippage_bps / 10_000)
    min_usdc = expected_usdc * slippage_factor
    return int(min_usdc * (10 ** usdc_decimals))


def build_swap_params(
    user: str,
    amount_wei: int,
    eth_price_usd: float,
    deadline: int,
    slippage_bps: int = DEFAULT_SLIPPAGE_BPS,
    config: SwapConfig | None = None,
) -> SwapParams:
    """Build complete swap parameters for ETH -> USDC.

    This is the main entry point used by DecisionEngine when the
    LLM returns action="SWAP".

    Args:
        user: User address — recipient of USDC output.
        amount_wei: ETH amount to swap (in wei).
        eth_price_usd: Current ETH/USD price for slippage calculation.
        deadline: Unix timestamp deadline for the swap tx.
        slippage_bps: Slippage tolerance in basis points.
        config: Network-specific addresses (defaults to Sepolia).

    Returns:
        SwapParams with target, encoded calldata, and audit hashes.
    """
    if config is None:
        config = SwapConfig()

    path = [config.weth, config.usdc]
    amount_out_min = compute_amount_out_min(
        amount_wei, eth_price_usd, slippage_bps,
    )

    calldata_bytes = encode_swap_exact_eth_for_tokens(
        amount_out_min=amount_out_min,
        path=path,
        to=user,
        deadline=deadline,
    )
    calldata_hex = "0x" + calldata_bytes.hex()
    calldata_hash = "0x" + keccak(calldata_bytes).hex()

    logger.info(
        "Swap calldata: %d wei ETH -> min %d USDC (%d bps slippage), hash=%s...",
        amount_wei, amount_out_min, slippage_bps, calldata_hash[:14],
    )

    return SwapParams(
        target=config.router,
        calldata=calldata_hex,
        amount_in_wei=amount_wei,
        amount_out_min=amount_out_min,
        path=path,
        deadline=deadline,
        calldata_hash=calldata_hash,
    )
