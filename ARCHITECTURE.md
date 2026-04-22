# AegisAgent — System Architecture

**Author**: LIU Kefan
**Version**: 0.1 (initial)
**Last updated**: 2026-04-22

## 1. Design Goals

1. Verifiable autonomy — every agent action carries a TDX attestation quote that an on-chain verifier checks before execution.
2. Gas efficiency — explore Risc Zero zkDCAP to reduce verifier gas cost.
3. Reproducibility — identical Docker image hash across machines; SHA256 measurement registered on-chain.

## 2. Three-Layer Architecture

### 2.1 On-chain (Solidity, Sepolia)
- AgentRegistry.sol — registers approved agent measurements (MR_ENCLAVE-equivalent)
- AttestationVerifier.sol — parses Intel DCAP quote, validates signature chain
- Vault.sol — user-funded vault that only releases funds after verifier passes

### 2.2 TEE (Phala Cloud CVM)
- Python 3.11 agent runtime inside Intel TDX enclave
- Ollama (qwen2.5:7b) for local inference — no external API leakage
- Dstack SDK for quote generation and key management

### 2.3 Frontend (Next.js 14)
- Wallet connect via RainbowKit
- Live attestation status panel
- Vault deposit / emergency stop UI

## 3. Trust Boundary

The TEE is the only place plaintext user funds intent exists. Quote generation happens on every decision; the on-chain verifier is the trust anchor.

## 4. Open Questions

- [ ] zkDCAP gas comparison vs. raw DCAP
- [ ] Attestation freshness window (replay window)
- [ ] Reproducible build verification protocol (3-way SHA256)

See `docs/interfaces.md` for three-layer interface contracts.
