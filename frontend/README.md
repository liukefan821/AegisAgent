# AegisAgent Frontend

Web interface for AegisAgent — a TEE-verified autonomous DeFi agent on Ethereum Sepolia.
Owner: **ZHOU Congxiang**

## Modules

| Module | Purpose |
|---|---|
| `app/page.tsx` | Dashboard — vault balance, agent health, registered agents, recent actions |
| `app/vault/page.tsx` | Deposit and withdraw Sepolia ETH |
| `app/agents/page.tsx` | Authorize TEE agents and emergency stop |
| `app/activity/page.tsx` | Action history with attestation status and Etherscan links |
| `hooks/use-vault.ts` | Read hooks for vault balance, nonce, agent authorization |
| `hooks/use-vault-writes.ts` | Write hooks for deposit, withdraw, authorize, emergency stop |
| `hooks/use-registry.ts` | Read hook for registered agents list |
| `hooks/use-agent-health.ts` | TEE agent health polling |
| `hooks/use-quote.ts` | Fetch attestation quote by digest |
| `hooks/use-vault-activity.ts` | Fetch on-chain action events |
| `components/attestation-modal.tsx` | Quote detail viewer with verification status |
| `components/write-status.tsx` | Shared success/error feedback for write transactions |
| `lib/contracts.ts` | Contract addresses and ABI re-exports |
| `lib/abis/` | Full compiled ABIs for Vault, Registry, Verifier |
| `lib/mocks/` | Mock fixtures for local demo mode |
| `lib/wagmi.ts` | RainbowKit and wagmi chain configuration |

## Stack

- Next.js 16 (App Router)
- React 19
- TypeScript
- Tailwind CSS 4
- wagmi v2 + viem + RainbowKit

## Setup

See the [root README](../README.md#quick-start) for how to start the full project.

To run the frontend on its own (mock mode, no other services needed):

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000. Mock mode is enabled by default in `.env.example`.

To run against live Sepolia contracts, edit `.env.local`:

```
NEXT_PUBLIC_USE_MOCK=false
NEXT_PUBLIC_VAULT_ADDRESS=0x4d046e39071b5650b6486e4997f7e5629cdf3f1d
NEXT_PUBLIC_REGISTRY_ADDRESS=0x77c75bd03df409906130fde880b3c9303ff35227
NEXT_PUBLIC_VERIFIER_ADDRESS=0x5c949780db9482ab63dd004a23d2d82b719176fd
NEXT_PUBLIC_AGENT_URL=http://localhost:8080
```

Then restart `npm run dev`. Live mode requires the TEE agent running on port 8080.

## Structure

- `app/` — pages and layouts
- `components/` — shared UI components
- `lib/` — wagmi config, contract ABIs, utilities
- `hooks/` — custom React hooks for contract interactions

## Deployed Contracts (Sepolia)

| Contract | Address |
|---|---|
| AegisVault | [0x4d04...3f1d](https://sepolia.etherscan.io/address/0x4d046e39071b5650b6486e4997f7e5629cdf3f1d#code) |
| AegisRegistry | [0x77c7...5227](https://sepolia.etherscan.io/address/0x77c75bd03df409906130fde880b3c9303ff35227#code) |
| AegisVerifier | [0x5c94...76fd](https://sepolia.etherscan.io/address/0x5c949780db9482ab63dd004a23d2d82b719176fd#code) |
| MockAutomata | [0x02e5...d5f3](https://sepolia.etherscan.io/address/0x02e53c5c81d781a8fd59e1c0efa5a8c60d86d5f3#code) |

The deployed registry is initialized with this test TEE image hash:

```text
0x0000000000000000000000000000000000000000000000000000000000000001
```

The Sepolia verifier currently uses `MockAutomata` for testnet integration,
so quote verification is not production-grade DCAP verification yet. Production
deployment requires a real Automata DCAP verifier.

## ABI Files

The frontend imports compiled ABI files from `lib/abis/`. If the Solidity
contracts change, refresh those files from the latest compiled artifacts,
keep the `as const` export, and rerun TypeScript/lint checks.
