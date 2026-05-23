# AegisAgent

> **TEE-Verified Autonomous DeFi Agent on Ethereum**
> Don't trust the agent. Verify the silicon.

**Course**: SC6107 — Blockchain Technology · NTU CCTF
**Group**: 1
**Status**: Active development (Apr 2026 – May 23, 2026)

---

## Overview

AegisAgent is a verifiable AI DeFi execution demo. Users deposit Sepolia ETH into
`AegisVault`, authorize a registered TEE agent, and submit agent decisions that
are bound to an `action_hash` and attestation quote before the Vault executes
them on-chain.

The current live demo focuses on proving the execution pipeline:

1. Frontend reads Vault/Registry state from Sepolia.
2. tee-agent calls an LLM provider, currently Gemini or Ollama.
3. tee-agent builds `action_hash = keccak256(abi.encode(user, amount, target, nonce, timestamp))`.
4. tee-agent generates a quote with `report_data = action_hash || output_hash`.
5. Frontend submits the decision to `AegisVault.executeAction`.
6. Activity shows Deposit, Withdraw, and Agent Action events with attestation details.

See [DEMO.md](DEMO.md) for the recommended presentation flow.

## Team

| Member | Module | Path |
|---|---|---|
| HE Huzhengxiong | DevOps · Testing · Delivery | `.github/workflows/` `scripts/` |
| LIU Kefan | Architecture · TEE Agent · Interface | `tee-agent/` `integration/` `docs/` |
| ZHOU Congxiang | Frontend (Next.js + RainbowKit) | `frontend/` |
| ZHU Ruiqi | Smart Contracts (Solidity + Hardhat) | `contracts/` |

## Architecture

```
 +-------------------+       +----------------------+       +--------------------+
 |                   |       |                      |       |                    |
 |  Frontend         | ----> |  TEE Agent           | ----> |  Smart Contracts   |
 |  (Next.js 16)     |       |  (Phala TDX CVM)     |       |  (Sepolia)         |
 |                   |       |  Gemini/Ollama +     |       |  Registry / Vault  |
 |                   |       |  Dstack SDK          |       |  / Verifier        |
 +-------------------+       +----------------------+       +--------------------+
         ^                              |                            ^
         |                              |                            |
         |                              +--- attestation quote ------+
         |
         +----------------- reads on-chain state --------------------+
```

Flow:
1. User deposits funds to `AegisVault` via frontend
2. User authorizes a registered TEE agent measurement
3. TEE agent reads market context, asks the LLM for `HOLD` or `TRANSFER`, and generates an attestation quote
4. Frontend submits the quote and action data to `AegisVault.executeAction`
5. Only if verification passes, `AegisVault` executes the agent's action
6. Frontend displays the resulting on-chain events in Activity

## Repository Structure

| Path | Owner | Purpose |
|---|---|---|
| `contracts/` | ZHU | Solidity: AegisRegistry, AegisVault, AegisVerifier |
| `frontend/` | ZHOU | Next.js 16 dApp + RainbowKit |
| `tee-agent/` | LIU | Python LLM agent inside Phala TEE CVM |
| `integration/` | LIU | Interface contracts + incremental integration |
| `scripts/` | HE | Deployment, gas reports, build scripts |
| `docs/` | LIU | Architecture, proposal, interface specs |
| `.github/` | HE | CI workflows, issue/PR templates |

## Prerequisites

- Node.js >= 18
- npm >= 9
- Python >= 3.10 and pip (live mode only)
- A Gemini API key (live mode only)

## Quick Start

From the repository root:

```bash
./scripts/dev-setup.sh
```

The script prompts for a mode:

| Input | Mode | What it starts |
|-------|------|----------------|
| `1` | Mock | Frontend only — all contract reads and writes use local fixtures. No Python, no API key needed. |
| `2` | Live | Frontend + TEE agent — connects to deployed Sepolia contracts and calls Gemini for LLM inference. Prompts for your Gemini API key on first run. |

The script detects your LAN IP automatically, so you can also open the frontend on a phone connected to the same network.

After startup the script prints:

```
Laptop frontend: http://localhost:3000
Phone frontend:  http://<your-lan-ip>:3000
TEE agent:       http://<your-lan-ip>:8080   (live mode only)
```

Press `Ctrl+C` to stop all servers.

If the script errors or does not work on your system, see
[scripts/README.md](scripts/README.md#manual-setup-without-script) for manual
setup steps.

## Demo Flow

For a live Sepolia demo, follow [DEMO.md](DEMO.md). The short version is:

1. Start live mode with `./scripts/dev-setup.sh`
2. Connect wallet on Sepolia
3. Deposit Sepolia ETH into Vault
4. Authorize the registered agent
5. Run Agent Decision, Demo HOLD, or Demo TRANSFER
6. Inspect Activity and attestation details

`Demo TRANSFER` deterministically transfers 25% of the current vault balance to
the emergency safe wallet. In the current demo, that safe wallet is the connected
user wallet.

## Current Demo Scope

- The current AI action space is `HOLD` or `TRANSFER`.
- The LLM may decide whether to transfer and how much, but the tee-agent code
  forces all transfer targets to the emergency safe wallet.
- There is no swap, buy, sell, or portfolio rebalancing yet.
- Sepolia verification currently uses MockAutomata for testnet integration.
  Production requires a real DCAP verifier.
- Quote metadata is stored in tee-agent memory. If tee-agent restarts, old
  on-chain Activity events still appear, but quote detail lookup may return
  `Quote not found`.

## AI Tools Used

AI tools, including Claude and ChatGPT, were used to assist with bug fixing,
test coverage improvements, documentation drafting, and presentation
preparation. All submitted code was reviewed, modified where necessary, and
tested by the contributor whose GitHub account authored the commits. The
contributor takes responsibility for the final implementation.

## License

MIT — see LICENSE
