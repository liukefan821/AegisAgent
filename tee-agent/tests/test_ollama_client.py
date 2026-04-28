"""
Unit tests for aegis_agent.ollama_client

These tests do NOT require a live Ollama daemon.
All HTTP calls are mocked via unittest.mock.
"""
from __future__ import annotations

import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from aegis_agent.ollama_client import (
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_URL,
    LLMResponse,
    OllamaClient,
)


# ──────────────────────────────────────────────────────────────────────
# Construction
# ──────────────────────────────────────────────────────────────────────
class TestConstruction:
    def test_defaults(self):
        client = OllamaClient()
        assert client.base_url == DEFAULT_OLLAMA_URL
        assert client.model == DEFAULT_MODEL
        assert client.timeout == 120

    def test_custom(self):
        client = OllamaClient(
            base_url="http://example.com:8080/",  # trailing slash should be stripped
            model="llama3.2:latest",
            timeout=60,
        )
        assert client.base_url == "http://example.com:8080"
        assert client.model == "llama3.2:latest"
        assert client.timeout == 60


# ──────────────────────────────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────────────────────────────
class TestHealthCheck:
    @patch("aegis_agent.ollama_client.requests.get")
    def test_model_available(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"models": [{"name": "qwen2.5:7b"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = OllamaClient(model="qwen2.5:7b")
        assert client.health_check() is True

    @patch("aegis_agent.ollama_client.requests.get")
    def test_model_missing(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"models": [{"name": "llama3.2:latest"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = OllamaClient(model="qwen2.5:7b")
        assert client.health_check() is False

    @patch("aegis_agent.ollama_client.requests.get")
    def test_connection_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("Connection refused")
        client = OllamaClient()
        assert client.health_check() is False


# ──────────────────────────────────────────────────────────────────────
# Generation + hashing
# ──────────────────────────────────────────────────────────────────────
class TestGenerate:
    @patch("aegis_agent.ollama_client.requests.post")
    def test_basic_generation(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "response": "Hello from Ollama.",
            "eval_count": 5,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = OllamaClient(model="qwen2.5:7b")
        result = client.generate(prompt="Say hi", system="Be brief.")

        assert isinstance(result, LLMResponse)
        assert result.model == "qwen2.5:7b"
        assert result.response == "Hello from Ollama."
        assert result.eval_count == 5
        assert result.input_hash.startswith("0x")
        assert result.output_hash.startswith("0x")
        assert len(result.input_hash) == 66  # 0x + 64 hex chars
        assert len(result.output_hash) == 66

    @patch("aegis_agent.ollama_client.requests.post")
    def test_input_hash_is_deterministic(self, mock_post):
        """Same prompt + system + model must always produce the same input_hash."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "x", "eval_count": 1}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = OllamaClient(model="qwen2.5:7b")
        r1 = client.generate(prompt="What is 2+2?", system="Math tutor")
        r2 = client.generate(prompt="What is 2+2?", system="Math tutor")
        assert r1.input_hash == r2.input_hash

    @patch("aegis_agent.ollama_client.requests.post")
    def test_input_hash_changes_with_prompt(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "x", "eval_count": 1}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = OllamaClient(model="qwen2.5:7b")
        r1 = client.generate(prompt="What is 2+2?")
        r2 = client.generate(prompt="What is 3+3?")
        assert r1.input_hash != r2.input_hash

    @patch("aegis_agent.ollama_client.requests.post")
    def test_output_hash_matches_sha256(self, mock_post):
        """output_hash must equal SHA-256 of the response text."""
        response_text = "deterministic answer"
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": response_text, "eval_count": 2}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = OllamaClient()
        result = client.generate(prompt="anything")

        expected = "0x" + hashlib.sha256(response_text.encode()).hexdigest()
        assert result.output_hash == expected

    @patch("aegis_agent.ollama_client.time.sleep", return_value=None)  # don't actually sleep
    @patch("aegis_agent.ollama_client.requests.post")
    def test_retry_on_transient_failure(self, mock_post, _mock_sleep):
        """Should retry on RequestException and succeed on later attempts."""
        success = MagicMock()
        success.json.return_value = {"response": "ok", "eval_count": 1}
        success.raise_for_status = MagicMock()

        mock_post.side_effect = [
            requests.ConnectionError("fail 1"),
            requests.ConnectionError("fail 2"),
            success,
        ]

        client = OllamaClient()
        result = client.generate(prompt="hi")
        assert result.response == "ok"
        assert mock_post.call_count == 3

    @patch("aegis_agent.ollama_client.time.sleep", return_value=None)
    @patch("aegis_agent.ollama_client.requests.post")
    def test_raises_after_max_retries(self, mock_post, _mock_sleep):
        mock_post.side_effect = requests.ConnectionError("always fails")
        client = OllamaClient()
        with pytest.raises(RuntimeError, match="failed after 3 attempts"):
            client.generate(prompt="hi")


# ──────────────────────────────────────────────────────────────────────
# JSON parsing helper
# ──────────────────────────────────────────────────────────────────────
class TestParseJson:
    def test_plain_json(self):
        out = OllamaClient.parse_json_response('{"a": 1, "b": "hello"}')
        assert out == {"a": 1, "b": "hello"}

    def test_with_markdown_fence(self):
        text = '```json\n{"score": 42}\n```'
        assert OllamaClient.parse_json_response(text) == {"score": 42}

    def test_with_prefix_text(self):
        text = 'Here is the result:\n{"verdict": "safe"}\nDone.'
        assert OllamaClient.parse_json_response(text) == {"verdict": "safe"}

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Could not parse JSON"):
            OllamaClient.parse_json_response("not json at all")
