"""LLM provider factory for AegisAgent."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Protocol

from dotenv import load_dotenv

from aegis_agent.gemini_client import DEFAULT_GEMINI_MODEL, GeminiClient
from aegis_agent.ollama_client import DEFAULT_MODEL, DEFAULT_OLLAMA_URL, LLMResponse, OllamaClient

load_dotenv()
load_dotenv(".env.local", override=False)


class LLMClient(Protocol):
    model: str

    def health_check(self) -> bool:
        ...

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        json_mode: bool = False,
    ) -> LLMResponse:
        ...


def configured_provider() -> str:
    return os.getenv("LLM_PROVIDER", "ollama").strip().lower()


def configured_model() -> str:
    if configured_provider() == "gemini":
        return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    return os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)


@lru_cache(maxsize=1)
def create_llm_client() -> LLMClient:
    provider = configured_provider()
    if provider == "gemini":
        return GeminiClient(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
            base_url=os.getenv(
                "GEMINI_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta",
            ),
        )
    if provider != "ollama":
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
    return OllamaClient(
        base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL),
        model=os.getenv("OLLAMA_MODEL", DEFAULT_MODEL),
    )


def probe_llm() -> str:
    try:
        return "ready" if create_llm_client().health_check() else "unreachable"
    except Exception:
        return "unreachable"
