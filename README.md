# AegisAgent

> **TEE-Verified Autonomous DeFi Agent on Ethereum**
> Don't trust the agent. Verify the silicon.

**Course**: SC6107 — Blockchain Technology · NTU CCDS
**Group**: 1
**Status**: Active development (Apr–May 2026)

---

## Overview

AegisAgent is an autonomous DeFi agent whose every on-chain action is cryptographically attested by an Intel TDX Trusted Execution Environment. A Solidity verifier validates the TEE attestation quote before any vault transaction executes — eliminating the black-box trust assumption in current LLM-powered DeFi agents.

See `docs/architecture/` for the full system design and `docs/proposal.pdf` for the original proposal.

## Team

| Member | Module | Path |
|---|---|---|
| HE Huzhengxiong | DevOps · Testing · Delivery | `.github/workflows/` `scripts/` |
| **LIU Kefan** | **Architecture · TEE Agent · Interface** | **`tee-agent/` `integration/` `docs/`** |
| ZHOU Congxiang | Frontend (Next.js + RainbowKit) | `frontend/` |
| ZHU Ruiqi | Smart Contracts (Solidity + Hardhat) | `contracts/` |

## Architecture

```
 +-------------------+       +----------------------+       +--------------------+
 |                   |       |                      |       |                    |
 |  Frontend         | ----> |  TEE Agent           | ----> |  Smart Contracts   |
 |  (Next.js 14)     |       |  (Phala TDX CVM)     |       |  (Sepolia)         |
 |                   |       |  Ollama + Dstack SDK |       |  Registry / Vault  |
 |                   |       |                      |       |  / Verifier        |
 +-------------------+       +----------------------+       +--------------------+
         ^                              |                            ^
         |                              |                            |
         |                              +--- attestation quote ------+
         |
         +----------------- reads on-chain state --------------------+
```

Flow:
1. User deposits funds to `AegisVault` via frontend
2. TEE agent reads market data, decides action, generates TDX attestation quote
3. Quote is submitted to `AegisVerifier` on-chain
4. Only if verification passes, `AegisVault` executes the agent's action

## Repository Structure

| Path | Owner | Purpose |
|---|---|---|
| `contracts/` | ZHU | Solidity: Registry, Vault, AttestationVerifier |
| `frontend/` | ZHOU | Next.js 14 dApp + RainbowKit |
| `tee-agent/` | LIU | Python LLM agent inside Phala TEE CVM |
| `integration/` | LIU | Interface contracts + incremental integration |
| `scripts/` | HE | Deployment, gas reports, build scripts |
| `docs/` | LIU | Architecture, proposal, interface specs |
| `.github/` | HE | CI workflows, issue/PR templates |

## License

MIT — see LICENSE
