"""Unit tests for http_server endpoints (15 tests).

Covers:
  - QuoteStore put/get/digest semantics
  - /health alive/degraded branching, schema, timestamp tracking
  - /quotes/{digest} success, 404, no-prefix lookup, report_data split
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from aegis_agent import http_server
from aegis_agent.http_server import QuoteStore, app, get_store
from aegis_agent.quote_generator import QuoteGenerator


# ────────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_store():
    """Reset the module-level singleton before/after every test."""
    http_server._store = QuoteStore()
    yield
    http_server._store = QuoteStore()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def sample_quote():
    gen = QuoteGenerator(mock=True)
    return gen.generate(b"\x11" * 32, b"\x22" * 32)


# ────────────────────────────────────────────────────────────────────────────
# QuoteStore
# ────────────────────────────────────────────────────────────────────────────

class TestQuoteStore:
    def test_put_and_get_roundtrip(self, sample_quote):
        store = QuoteStore()
        digest = store.put(sample_quote)
        assert digest.startswith("0x") and len(digest) == 66
        assert store.get(digest) is sample_quote

    def test_get_normalises_no_prefix(self, sample_quote):
        store = QuoteStore()
        digest = store.put(sample_quote)
        assert store.get(digest[2:]) is sample_quote

    def test_get_case_insensitive(self, sample_quote):
        store = QuoteStore()
        digest = store.put(sample_quote)
        assert store.get(digest.upper()) is sample_quote

    def test_missing_returns_none(self):
        assert QuoteStore().get("0x" + "ab" * 32) is None

    def test_last_timestamp_empty_is_zero(self):
        assert QuoteStore().last_timestamp() == 0

    def test_last_timestamp_returns_max(self, sample_quote):
        store = QuoteStore()
        store.put(sample_quote)
        assert store.last_timestamp() == sample_quote.timestamp

    def test_digest_is_keccak256_of_raw_quote(self, sample_quote):
        from eth_utils import keccak
        expected = "0x" + keccak(bytes.fromhex(sample_quote.quote_hex)).hex()
        assert QuoteStore.digest_for(sample_quote) == expected


# ────────────────────────────────────────────────────────────────────────────
# /health
# ────────────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_alive_when_ollama_ready(self, client):
        with patch.object(http_server, "_probe_ollama", return_value="ready"):
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"
        assert resp.json()["ollama_status"] == "ready"

    def test_health_degraded_when_ollama_unreachable(self, client):
        with patch.object(http_server, "_probe_ollama", return_value="unreachable"):
            resp = client.get("/health")
        assert resp.json()["status"] == "degraded"
        assert resp.json()["ollama_status"] == "unreachable"

    def test_health_schema_matches_interfaces_md(self, client):
        with patch.object(http_server, "_probe_ollama", return_value="ready"):
            resp = client.get("/health")
        body = resp.json()
        assert set(body.keys()) == {
            "status",
            "enclave_image_hash",
            "last_quote_generated_at",
            "ollama_model",
            "ollama_status",
        }

    def test_health_last_quote_zero_when_empty(self, client):
        with patch.object(http_server, "_probe_ollama", return_value="ready"):
            resp = client.get("/health")
        assert resp.json()["last_quote_generated_at"] == 0

    def test_health_last_quote_updates_after_put(self, client, sample_quote):
        get_store().put(sample_quote)
        with patch.object(http_server, "_probe_ollama", return_value="ready"):
            resp = client.get("/health")
        assert resp.json()["last_quote_generated_at"] == sample_quote.timestamp


# ────────────────────────────────────────────────────────────────────────────
# /quotes/{digest}
# ────────────────────────────────────────────────────────────────────────────

class TestQuotes:
    def test_get_quote_roundtrip(self, client, sample_quote):
        digest = get_store().put(sample_quote)
        resp = client.get(f"/quotes/{digest}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["digest"] == digest
        assert body["quote_hex"] == "0x" + sample_quote.quote_hex
        assert body["mr_enclave"] == "0x" + sample_quote.mr_enclave
        assert body["timestamp"] == sample_quote.timestamp
        assert body["is_mock"] is True

    def test_report_data_split_into_input_output(self, client, sample_quote):
        digest = get_store().put(sample_quote)
        resp = client.get(f"/quotes/{digest}")
        body = resp.json()
        assert body["input_hash"] == "0x" + ("11" * 32)
        assert body["output_hash"] == "0x" + ("22" * 32)
        assert body["report_data"] == "0x" + ("11" * 32) + ("22" * 32)

    def test_unknown_digest_returns_404(self, client):
        bogus = "0x" + "de" * 32
        resp = client.get(f"/quotes/{bogus}")
        assert resp.status_code == 404
        assert "No quote found" in resp.json()["detail"]

    def test_digest_without_0x_prefix(self, client, sample_quote):
        digest = get_store().put(sample_quote)
        resp = client.get(f"/quotes/{digest[2:]}")
        assert resp.status_code == 200
        assert resp.json()["digest"] == digest


# ────────────────────────────────────────────────────────────────────────────
# CORS middleware
# ────────────────────────────────────────────────────────────────────────────

class TestCORS:
    def test_cors_header_for_allowed_origin(self, client):
        resp = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_cors_preflight_get_allowed(self, client):
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert "GET" in resp.headers.get("access-control-allow-methods", "")
