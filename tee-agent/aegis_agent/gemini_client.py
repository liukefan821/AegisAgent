"""
gemini_client.py — Google Gemini LLM client for AegisAgent.

This client intentionally returns the same LLMResponse shape as OllamaClient so
the decision engine can switch providers without changing attestation hashing.
"""
from __future__ import annotations

import hashlib
import time
from typing import Optional

import requests

from aegis_agent.ollama_client import LLMResponse, MAX_RETRIES

DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"
DEFAULT_TIMEOUT = 120


class GeminiClient:
    """HTTP client for Google's Gemini generateContent API."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_GEMINI_MODEL,
        base_url: str = DEFAULT_GEMINI_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _model_path(self) -> str:
        return self.model if self.model.startswith("models/") else f"models/{self.model}"

    def _url(self, method: str) -> str:
        return f"{self.base_url}/{self._model_path()}:{method}?key={self.api_key}"

    def health_check(self) -> bool:
        """Return True if the API key can access the configured Gemini model."""
        if not self.api_key:
            return False
        try:
            resp = requests.get(
                f"{self.base_url}/{self._model_path()}",
                params={"key": self.api_key},
                timeout=5,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Run a single Gemini generation and return attestation-ready hashes."""
        if not self.api_key:
            raise RuntimeError("Gemini API key is not configured")

        canonical_input = (
            f"SYSTEM:{system or ''}\n"
            f"USER:{prompt}\n"
            f"MODEL:{self.model}"
        )
        input_hash = hashlib.sha256(canonical_input.encode("utf-8")).hexdigest()

        payload: dict = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        last_err: Optional[Exception] = None
        start = time.time()

        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(
                    self._url("generateContent"),
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                candidates = data.get("candidates", [])
                parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
                response_text = "".join(part.get("text", "") for part in parts).strip()

                output_hash = hashlib.sha256(response_text.encode("utf-8")).hexdigest()
                elapsed_ms = int((time.time() - start) * 1000)
                usage = data.get("usageMetadata", {})

                return LLMResponse(
                    model=self.model,
                    prompt=prompt,
                    response=response_text,
                    input_hash=f"0x{input_hash}",
                    output_hash=f"0x{output_hash}",
                    elapsed_ms=elapsed_ms,
                    eval_count=usage.get("candidatesTokenCount", 0),
                )
            except (requests.RequestException, KeyError, IndexError, ValueError) as e:
                last_err = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                continue

        raise RuntimeError(
            f"Gemini generate failed after {MAX_RETRIES} attempts: {last_err}"
        )
