"""
chainlink_feed.py — Sepolia Chainlink price feed reader for AegisAgent

Reads ETH/USD price from the Chainlink AggregatorV3 contract on Sepolia.
Provides deterministic, on-chain-verifiable price data that the
decision_engine can include in its TEE attestation input.

This module is the *only* component allowed to read off-chain prices.
All other agent modules go through ChainlinkFeed so that every
price observation is tied to a specific Chainlink round_id, which
can be independently verified by anyone reading Sepolia.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass
from decimal import Decimal

from web3 import Web3
from web3.exceptions import ContractLogicError, Web3Exception

logger = logging.getLogger(__name__)

# Chainlink ETH/USD price feed on Sepolia
# Source: https://docs.chain.link/data-feeds/price-feeds/addresses
SEPOLIA_ETH_USD_FEED = "0x694AA1769357215DE4FAC081bf1f309aDC325306"

# AggregatorV3Interface ABI (minimal — only what we use)
AGGREGATOR_V3_ABI = [
    {
        "inputs": [],
        "name": "latestRoundData",
        "outputs": [
            {"internalType": "uint80", "name": "roundId", "type": "uint80"},
            {"internalType": "int256", "name": "answer", "type": "int256"},
            {"internalType": "uint256", "name": "startedAt", "type": "uint256"},
            {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
            {"internalType": "uint80", "name": "answeredInRound", "type": "uint80"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "description",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# Default: reject prices that haven't updated in this many seconds
DEFAULT_STALENESS_THRESHOLD_SEC = 3600  # 1 hour


# ---------- Exceptions ----------

class ChainlinkFeedError(Exception):
    """Base exception for ChainlinkFeed errors."""


class StalePriceError(ChainlinkFeedError):
    """Raised when the price feed is too old to be trusted."""


class FeedConnectionError(ChainlinkFeedError):
    """Raised when we can't reach the RPC endpoint."""


# ---------- Data class ----------

@dataclass(frozen=True)
class PriceData:
    """Snapshot of a Chainlink price feed at a specific round.

    For attestation hashing, use `data_hash` which is deterministic over
    (feed_address, round_id, raw_answer, updated_at).

    Note: `data_hash` is internal to tee-agent — it gets folded into the
    LLM input that ollama_client hashes. The on-chain AegisVerifier only
    sees the final input_hash/output_hash pair from the decision_engine.
    """
    price: Decimal               # human-readable, scaled by decimals
    round_id: int                # Chainlink uint80 round identifier
    updated_at: int              # unix timestamp of last update
    answered_in_round: int
    feed_address: str            # checksummed address
    decimals: int
    description: str             # e.g., "ETH / USD"
    raw_answer: int              # raw int256 before decimal scaling

    @property
    def data_hash(self) -> str:
        """SHA-256 hash for inclusion in the LLM input attestation.

        Format: sha256("FEED:{addr_lower}\\nROUND:{round_id}\\nANSWER:{raw}\\nUPDATED:{ts}")
        Returns: hex string with '0x' prefix.
        """
        payload = (
            f"FEED:{self.feed_address.lower()}\n"
            f"ROUND:{self.round_id}\n"
            f"ANSWER:{self.raw_answer}\n"
            f"UPDATED:{self.updated_at}"
        )
        return "0x" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------- Client ----------

class ChainlinkFeed:
    """Read-only client for a Chainlink AggregatorV3 price feed.

    Example:
        feed = ChainlinkFeed.from_env()
        data = feed.get_latest_price()
        print(f"{data.description} = {data.price} (round {data.round_id})")
        print(f"Attestation hash: {data.data_hash}")
    """

    def __init__(
        self,
        rpc_url: str,
        feed_address: str = SEPOLIA_ETH_USD_FEED,
        staleness_threshold_sec: int = DEFAULT_STALENESS_THRESHOLD_SEC,
        request_timeout: int = 10,
    ):
        if not rpc_url:
            raise ValueError("rpc_url is required (e.g., from SEPOLIA_RPC_URL env)")

        self.rpc_url = rpc_url
        self.feed_address = Web3.to_checksum_address(feed_address)
        self.staleness_threshold_sec = staleness_threshold_sec

        self.w3 = Web3(
            Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": request_timeout})
        )
        if not self.w3.is_connected():
            raise FeedConnectionError(f"Cannot connect to RPC at {rpc_url}")

        self.contract = self.w3.eth.contract(
            address=self.feed_address, abi=AGGREGATOR_V3_ABI
        )

        # Cache static feed metadata (decimals + description never change)
        try:
            self._decimals: int = self.contract.functions.decimals().call()
            self._description: str = self.contract.functions.description().call()
        except (ContractLogicError, Web3Exception) as e:
            raise ChainlinkFeedError(f"Failed to read feed metadata: {e}") from e

        logger.info(
            "ChainlinkFeed initialized: %s @ %s (%d decimals)",
            self._description,
            self.feed_address,
            self._decimals,
        )

    @classmethod
    def from_env(
        cls,
        feed_address: str = SEPOLIA_ETH_USD_FEED,
        staleness_threshold_sec: int = DEFAULT_STALENESS_THRESHOLD_SEC,
    ) -> "ChainlinkFeed":
        """Construct from SEPOLIA_RPC_URL env var.

        Note: does not auto-load .env — caller is responsible for
        calling python-dotenv if needed.
        """
        rpc_url = os.environ.get("SEPOLIA_RPC_URL")
        if not rpc_url:
            raise ValueError("SEPOLIA_RPC_URL not set in environment")
        return cls(rpc_url, feed_address, staleness_threshold_sec)

    def get_latest_price(self, *, check_staleness: bool = True) -> PriceData:
        """Read latestRoundData() and return as a PriceData snapshot.

        Args:
            check_staleness: If True (default), raise StalePriceError when the
                feed hasn't updated within staleness_threshold_sec. Set to
                False in tests or when stale data is acceptable.

        Raises:
            ChainlinkFeedError: on RPC/contract errors or invalid (negative) price.
            StalePriceError: when updatedAt is older than the threshold.
        """
        try:
            (
                round_id,
                answer,
                started_at,
                updated_at,
                answered_in_round,
            ) = self.contract.functions.latestRoundData().call()
        except (ContractLogicError, Web3Exception) as e:
            raise ChainlinkFeedError(f"latestRoundData() call failed: {e}") from e

        if answer < 0:
            raise ChainlinkFeedError(f"Negative price answer: {answer}")

        if check_staleness:
            now = int(time.time())
            age = now - updated_at
            if age > self.staleness_threshold_sec:
                raise StalePriceError(
                    f"Price feed is {age}s old "
                    f"(threshold {self.staleness_threshold_sec}s); "
                    f"updated_at={updated_at}, now={now}"
                )

        scale = Decimal(10) ** self._decimals
        price = Decimal(answer) / scale

        return PriceData(
            price=price,
            round_id=round_id,
            updated_at=updated_at,
            answered_in_round=answered_in_round,
            feed_address=self.feed_address,
            decimals=self._decimals,
            description=self._description,
            raw_answer=answer,
        )

    @property
    def decimals(self) -> int:
        return self._decimals

    @property
    def description(self) -> str:
        return self._description
