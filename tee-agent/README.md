# tee-agent

Python LLM agent designed to run inside an Intel TDX TEE or local demo
environment.

Owner: **LIU Kefan**

## What It Does

The tee-agent is the off-chain decision and attestation layer for AegisAgent.

Current live flow:

1. Receive user, vault balance, and nonce from the frontend.
2. Read ETH/USD context from Chainlink when configured, otherwise use a mock price.
3. Ask the configured LLM provider for a `HOLD` or `TRANSFER` decision.
4. Build `action_hash = keccak256(abi.encode(user, amount, target, nonce, timestamp))`.
5. Generate an attestation quote with `report_data = action_hash || output_hash`.
6. Store the quote in memory so the frontend can later call `/quotes/{digest}`.
7. Return all fields needed for `AegisVault.executeAction`.

The LLM can choose the action and amount. It cannot choose the final destination.
For every `TRANSFER`, the tee-agent forces `target` to the emergency safe wallet.
In the current demo, the emergency safe wallet is the connected user wallet.

## Modules

| Module | Status | Purpose |
|---|---|---|
| `aegis_agent/http_server.py` | Done | FastAPI server for `/health`, `/decisions`, and `/quotes/{digest}` |
| `aegis_agent/decision_engine.py` | Done | Price/context -> LLM decision -> action hash -> quote -> store |
| `aegis_agent/llm_client.py` | Done | Provider factory for Gemini or Ollama |
| `aegis_agent/gemini_client.py` | Done | Gemini API inference using the shared LLM response shape |
| `aegis_agent/ollama_client.py` | Done | Local Ollama inference using the shared LLM response shape |
| `aegis_agent/chainlink_feed.py` | Done | Optional Sepolia Chainlink ETH/USD price feed |
| `aegis_agent/quote_generator.py` | Done | Mock quote generation locally, Dstack quote path for TEE deployment |
| `aegis_agent/main.py` | Done | Server entrypoint and environment loading |

## Setup

See the [root README](../README.md#quick-start) for the recommended one-command
startup.

To run the TEE agent on its own:

```bash
cd tee-agent
pip install -r requirements.txt
cp .env.example .env.local
```

Edit `.env.local` to pick an LLM provider.

### Option A — Gemini

```text
LLM_PROVIDER=gemini
GEMINI_API_KEY=<your-key>
GEMINI_MODEL=gemini-2.5-flash-lite
AEGIS_MOCK_QUOTE=true
```

### Option B — Ollama

```text
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
AEGIS_MOCK_QUOTE=true
```

Make sure Ollama is running if you choose this option:

```bash
ollama serve
ollama pull qwen2.5:7b
```

Start the server:

```bash
uvicorn aegis_agent.main:app --host 0.0.0.0 --port 8080
```

Health check:

```bash
curl http://localhost:8080/health
```

## HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness, LLM provider status, enclave image hash, last quote timestamp |
| `POST` | `/decisions` | Run the decision pipeline and return executeAction fields |
| `GET` | `/quotes/{digest}` | Return full quote metadata for an on-chain quote digest |

## Decision Modes

The frontend uses three decision paths:

| Mode | Behavior |
|---|---|
| Run Agent Decision | Calls the configured LLM provider and uses the model's `HOLD` / `TRANSFER` decision. |
| Demo HOLD | Bypasses the LLM choice and returns a deterministic HOLD decision. |
| Demo TRANSFER | Bypasses the LLM choice and returns a deterministic TRANSFER of 25% of the vault balance. |

Demo modes still generate hashes and quotes, so they are useful for presenting
the full on-chain execution path even when the real LLM would choose HOLD.

## Attestation Hashing Contract

Every LLM client `generate()` call returns an `LLMResponse` with two
0x-prefixed SHA-256 hashes:

- `input_hash` — `sha256("SYSTEM:{system}\nUSER:{prompt}\nMODEL:{model}")`
- `output_hash` — `sha256(response_text)`

Step 6 report data layout:

```text
report_data[0:32]  = action_hash
report_data[32:64] = output_hash
```

The real `input_hash` is stored separately in `QuoteStore` and returned by
`GET /quotes/{digest}` for audit display.

## Current Limitations

- Local/live demo mode uses `AEGIS_MOCK_QUOTE=true` by default.
- Sepolia verification currently uses MockAutomata for testnet integration.
  Production requires a real DCAP verifier.
- Quote metadata is stored in process memory. If tee-agent restarts, old
  on-chain events remain visible, but `/quotes/{digest}` may return 404.
- The current AI action space is only `HOLD` or `TRANSFER`.
- No swap, buy, sell, or portfolio rebalancing logic is implemented yet.
- The emergency safe wallet currently defaults to the connected user wallet.

## Tests

Run unit tests:

```bash
python -m pytest tests/ -v
```

The decision-engine tests cover action hash computation, report data layout,
quote lookup, and the rule that transfer targets are forced to the emergency
safe wallet.

## License

MIT

