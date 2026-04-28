"""Unit tests for chainlink_feed.py."""

from __future__ import annotations

import hashlib
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from aegis_agent.chainlink_feed import (
    AGGREGATOR_V3_ABI,
    SEPOLIA_ETH_USD_FEED,
    ChainlinkFeed,
    ChainlinkFeedError,
    FeedConnectionError,
    PriceData,
    StalePriceError,
)


# ----- Helpers -----

def make_price_data(**overrides):
    defaults = dict(
        price=Decimal("3245.78"),
        round_id=12345,
        updated_at=1700000000,
        answered_in_round=12345,
        feed_address="0x694AA1769357215DE4FAC081bf1f309aDC325306",
        decimals=8,
        description="ETH / USD",
        raw_answer=324578000000,
    )
    defaults.update(overrides)
    return PriceData(**defaults)


@pytest.fixture
def mock_web3():
    """Patch the Web3 class inside chainlink_feed to return a controllable mock."""
    with patch("aegis_agent.chainlink_feed.Web3") as W3:
        instance = MagicMock()
        instance.is_connected.return_value = True

        contract = MagicMock()
        contract.functions.decimals.return_value.call.return_value = 8
        contract.functions.description.return_value.call.return_value = "ETH / USD"
        instance.eth.contract.return_value = contract

        W3.return_value = instance
        W3.HTTPProvider = MagicMock()
        W3.to_checksum_address = lambda a: a  # passthrough for tests
        yield W3, instance, contract


# ----- PriceData hash tests -----

def test_price_data_hash_is_deterministic():
    pd = make_price_data()
    assert pd.data_hash == pd.data_hash


def test_price_data_hash_format():
    pd = make_price_data()
    h = pd.data_hash
    assert h.startswith("0x")
    assert len(h) == 66  # '0x' + 64 hex chars
    assert all(c in "0123456789abcdef" for c in h[2:])


def test_price_data_hash_changes_with_round_id():
    a = make_price_data(round_id=100)
    b = make_price_data(round_id=101)
    assert a.data_hash != b.data_hash


def test_price_data_hash_changes_with_raw_answer():
    a = make_price_data(raw_answer=324578000000)
    b = make_price_data(raw_answer=324578000001)
    assert a.data_hash != b.data_hash


def test_price_data_hash_changes_with_updated_at():
    a = make_price_data(updated_at=1700000000)
    b = make_price_data(updated_at=1700000001)
    assert a.data_hash != b.data_hash


def test_price_data_hash_known_value():
    """Pin the exact hash format so accidental refactors break the test."""
    pd = make_price_data(
        feed_address="0x694AA1769357215DE4FAC081bf1f309aDC325306",
        round_id=12345,
        raw_answer=324578000000,
        updated_at=1700000000,
    )
    expected_payload = (
        "FEED:0x694aa1769357215de4fac081bf1f309adc325306\n"
        "ROUND:12345\n"
        "ANSWER:324578000000\n"
        "UPDATED:1700000000"
    )
    expected = "0x" + hashlib.sha256(expected_payload.encode()).hexdigest()
    assert pd.data_hash == expected


def test_price_data_address_lowercased_in_hash():
    """Mixed-case and lowercase addresses must produce the same hash."""
    upper = make_price_data(feed_address="0x694AA1769357215DE4FAC081bf1f309aDC325306")
    lower = make_price_data(feed_address="0x694aa1769357215de4fac081bf1f309adc325306")
    assert upper.data_hash == lower.data_hash


# ----- ChainlinkFeed init tests -----

def test_init_requires_rpc_url(mock_web3):
    with pytest.raises(ValueError, match="rpc_url is required"):
        ChainlinkFeed(rpc_url="")


def test_init_caches_metadata(mock_web3):
    _, _, contract = mock_web3
    feed = ChainlinkFeed(rpc_url="http://test")
    assert feed.decimals == 8
    assert feed.description == "ETH / USD"
    # Calling .decimals again should not trigger another RPC call
    contract.functions.decimals.return_value.call.assert_called_once()


def test_init_raises_on_disconnected(mock_web3):
    _, instance, _ = mock_web3
    instance.is_connected.return_value = False
    with pytest.raises(FeedConnectionError, match="Cannot connect"):
        ChainlinkFeed(rpc_url="http://bad")


def test_from_env_missing_var(monkeypatch):
    monkeypatch.delenv("SEPOLIA_RPC_URL", raising=False)
    with pytest.raises(ValueError, match="SEPOLIA_RPC_URL not set"):
        ChainlinkFeed.from_env()


# ----- get_latest_price tests -----

def test_get_latest_price_happy_path(mock_web3):
    _, _, contract = mock_web3
    now = int(time.time())
    contract.functions.latestRoundData.return_value.call.return_value = (
        12345,           # round_id
        324578000000,    # answer (= 3245.78 * 1e8)
        now - 60,        # started_at
        now - 30,        # updated_at (30s ago — fresh)
        12345,           # answered_in_round
    )
    feed = ChainlinkFeed(rpc_url="http://test")
    data = feed.get_latest_price()

    assert data.price == Decimal("3245.78")
    assert data.round_id == 12345
    assert data.raw_answer == 324578000000
    assert data.updated_at == now - 30
    assert data.description == "ETH / USD"


def test_get_latest_price_raises_on_stale(mock_web3):
    _, _, contract = mock_web3
    now = int(time.time())
    contract.functions.latestRoundData.return_value.call.return_value = (
        12345, 324578000000, now - 7200, now - 7200, 12345
    )  # 2 hours old → stale
    feed = ChainlinkFeed(rpc_url="http://test")
    with pytest.raises(StalePriceError, match="old"):
        feed.get_latest_price()


def test_get_latest_price_skip_staleness_check(mock_web3):
    _, _, contract = mock_web3
    now = int(time.time())
    contract.functions.latestRoundData.return_value.call.return_value = (
        12345, 324578000000, now - 7200, now - 7200, 12345
    )
    feed = ChainlinkFeed(rpc_url="http://test")
    data = feed.get_latest_price(check_staleness=False)
    assert data.price == Decimal("3245.78")


def test_get_latest_price_negative_answer_raises(mock_web3):
    _, _, contract = mock_web3
    contract.functions.latestRoundData.return_value.call.return_value = (
        12345, -100, 0, int(time.time()), 12345
    )
    feed = ChainlinkFeed(rpc_url="http://test")
    with pytest.raises(ChainlinkFeedError, match="Negative price"):
        feed.get_latest_price()


# ----- Constants sanity -----

def test_sepolia_address_is_canonical():
    """Catch typos in the hardcoded feed address."""
    assert SEPOLIA_ETH_USD_FEED == "0x694AA1769357215DE4FAC081bf1f309aDC325306"


def test_abi_has_required_functions():
    names = {item["name"] for item in AGGREGATOR_V3_ABI if "name" in item}
    assert {"latestRoundData", "decimals", "description"}.issubset(names)
