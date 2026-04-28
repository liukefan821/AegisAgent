# tee-agent

Python LLM agent designed to run inside an Intel TDX TEE (Phala Cloud).
Owner: **LIU Kefan**

## Modules

| Module | Status | Purpose |
|---|---|---|
| `aegis_agent/ollama_client.py` | ✅ done | Local LLM inference + SHA-256 attestation hashing |
| `aegis_agent/chainlink_feed.py` | 🚧 next | Pull Sepolia price feeds for decision context |
| `aegis_agent/quote_generator.py` | 🚧 next | Wrap Dstack SDK to produce TDX attestation quotes |
| `aegis_agent/decision_engine.py` | 🚧 next | Combine LLM verdict + chainlink data → action |
| `aegis_agent/main.py` | 🚧 next | End-to-end orchestrator |

## Quick start

```bash
# 1. Activate env
conda activate aegisagent

# 2. Install deps
pip install -r requirements.txt

# 3. Make sure Ollama is running with qwen2.5:7b
ollama list | grep qwen2.5:7b   # should print the model
ollama serve                     # if not already running

# 4. Smoke test
python -m aegis_agent.ollama_client

# 5. Unit tests (no Ollama required, all mocked)
python -m pytest tests/ -v
```

## Attestation hashing contract

Every `OllamaClient.generate()` call returns an `LLMResponse` with two
0x-prefixed SHA-256 hashes:

- `input_hash`  — `sha256("SYSTEM:{system}\nUSER:{prompt}\nMODEL:{model}")`
- `output_hash` — `sha256(response_text)`

These are the values committed on-chain via `AegisVerifier.verifyDecision()`.
The format must stay stable; any change requires a coordinated update with
the contracts team.

## License

MIT
