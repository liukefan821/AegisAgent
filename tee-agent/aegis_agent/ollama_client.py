"""
ollama_client.py — Local LLM inference client for AegisAgent

Wraps the Ollama HTTP API for use inside the TEE agent. Provides:
- Synchronous generation with optional system prompt
- SHA-256 input/output hashing for on-chain attestation
- Retry logic with exponential backoff
- JSON response parsing helpers (handles ```json``` fences)

This module is the *only* component allowed to talk to the LLM.
All other agent modules go through OllamaClient so that every
inference produces a deterministic (input_hash, output_hash) pair
that can be committed to the AegisVerifier contract.

Author: LIU Kefan
Project: AegisAgent (SC6107, NTU CCDS, 2026)
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Optional

import requests

# ──────────────────────────────────────────────────────────────────────
# Defaults
# ──────────────────────────────────────────────────────────────────────
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_TIMEOUT = 120  # seconds
MAX_RETRIES = 3


# ──────────────────────────────────────────────────────────────────────
# Response container
# ──────────────────────────────────────────────────────────────────────
@dataclass
class LLMResponse:
    """A single LLM call result, with hashes ready for on-chain commit."""

    model: str
    prompt: str
    response: str
    input_hash: str        # 0x-prefixed SHA-256(system + user + model)
    output_hash: str       # 0x-prefixed SHA-256(response)
    elapsed_ms: int
    eval_count: int        # tokens generated (from Ollama)

    def to_dict(self) -> dict:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────
# Client
# ──────────────────────────────────────────────────────────────────────
class OllamaClient:
    """HTTP client for a local Ollama daemon."""

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_URL,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    # ---------- health ----------
    def health_check(self) -> bool:
        """Return True if Ollama is reachable and the configured model is pulled."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            return self.model in models
        except (requests.RequestException, KeyError, ValueError):
            return False

    # ---------- core generate ----------
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        json_mode: bool = False,
    ) -> LLMResponse:
        """
        Run a single non-streaming generation.

        Args:
            prompt: User-side prompt.
            system: Optional system prompt.
            temperature: 0.0–1.0 sampling temperature.
            max_tokens: Cap on tokens to generate.
            json_mode: If True, ask Ollama to emit valid JSON.

        Returns:
            LLMResponse with input_hash, output_hash for attestation.

        Raises:
            RuntimeError: if all retry attempts fail.
        """
        # Canonical input for hashing — order matters, keep stable!
        canonical_input = (
            f"SYSTEM:{system or ''}\n"
            f"USER:{prompt}\n"
            f"MODEL:{self.model}"
        )
        input_hash = hashlib.sha256(canonical_input.encode("utf-8")).hexdigest()

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        last_err: Optional[Exception] = None
        start = time.time()

        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                response_text = data.get("response", "")

                output_hash = hashlib.sha256(response_text.encode("utf-8")).hexdigest()
                elapsed_ms = int((time.time() - start) * 1000)

                return LLMResponse(
                    model=self.model,
                    prompt=prompt,
                    response=response_text,
                    input_hash=f"0x{input_hash}",
                    output_hash=f"0x{output_hash}",
                    elapsed_ms=elapsed_ms,
                    eval_count=data.get("eval_count", 0),
                )
            except requests.RequestException as e:
                last_err = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)  # 1s, 2s, 4s
                continue

        raise RuntimeError(
            f"Ollama generate failed after {MAX_RETRIES} attempts: {last_err}"
        )

    # ---------- helpers ----------
    @staticmethod
    def parse_json_response(text: str) -> dict:
        """Extract a JSON object from an LLM response (handles ```json fences)."""
        text = text.strip()
        if text.startswith("```"):
            lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
            text = "\n".join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
            raise ValueError(f"Could not parse JSON from response: {text[:200]}")


# ──────────────────────────────────────────────────────────────────────
# Smoke test:  $ python -m aegis_agent.ollama_client
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("AegisAgent — OllamaClient smoke test")
    print("=" * 60)

    client = OllamaClient()
    ok = client.health_check()
    print(f"[1/2] Health check (model={client.model}): {'OK' if ok else 'FAILED'}")
    if not ok:
        raise SystemExit(
            "Ollama is not reachable or the model is not pulled. "
            "Run `ollama serve` and `ollama pull qwen2.5:7b`."
        )

    result = client.generate(
        prompt=(
            "What are the top 3 risks of using a leveraged DeFi yield farming "
            "strategy? Answer in 2 short sentences."
        ),
        system="You are AegisAgent, a TEE-protected DeFi risk assessment AI.",
        temperature=0.1,
    )

    print(f"[2/2] Generation OK")
    print("-" * 60)
    print(f"Input hash : {result.input_hash}")
    print(f"Output hash: {result.output_hash}")
    print(f"Elapsed    : {result.elapsed_ms} ms")
    print(f"Tokens     : {result.eval_count}")
    print("-" * 60)
    print("Response:")
    print(result.response)
    print("=" * 60)
