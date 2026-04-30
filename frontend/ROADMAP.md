# Frontend Roadmap

Owner: ZHOU Congxiang
Module: `frontend/`

## Goal

Build the user interface for AegisAgent — wallet connection, vault deposits/withdrawals,
agent authorization, activity feed with attestation verification display.

All interfaces defined in `../docs/interfaces.md`.

## Pages

| Route | Purpose | Contract calls |
|---|---|---|
| `/` | Dashboard: balance, stats, live event feed | `Vault.balanceOf`, event subs |
| `/vault` | Deposit / withdraw ETH (+ future ERC-20) | `deposit`, `withdraw` |
| `/agents` | Register and authorize enclave measurements | `Registry.getRegisteredAgents`, `Vault.authorizeAgent`, `Vault.emergencyStop` |
| `/activity` | History of `ActionExecuted` events with attestation badges | `ActionExecuted` + `QuoteVerified` events |

## Components (WOW-factor target)

- `<ConnectButton />` — RainbowKit (done)
- `<AttestationBadge />` — decoded quote display (MRENCLAVE, timestamp, tx hash binding)
- `<EventFeed />` — live streaming of on-chain events via `useWatchContractEvent`
- `<AgentHealth />` — polls `GET /health` from TEE agent every 10s

## Tech Stack

- Next.js 16 (App Router) + React 19 + TypeScript
- Tailwind CSS 4 + shadcn/ui (new-york style)
- wagmi v2 + viem + RainbowKit
- TanStack Query

## Weekly Plan

| Week | Deliverable | Status |
|---|---|---|
| W1 | Scaffold + wallet connection + Sepolia enforcement | ⏳ In progress |
| W2 | Dashboard + Vault deposit/withdraw (mock mode) | ⬜ |
| W3 | Integrate first real contracts from `feat/contracts-*`; `/agents` page | ⬜ |
| W4 | `/activity` event feed + `<AttestationBadge />` (WOW component) | ⬜ |
| W5 | Integrate TEE agent `/health`; error states, loading skeletons, empty states | ⬜ |
| W6 | Mobile responsive + dark mode polish + demo video | ⬜ |

## Mock Mode

Set `NEXT_PUBLIC_USE_MOCK=true` in `.env.local` to run the UI against fixtures in
`lib/mocks/` before real contracts and the TEE agent are deployed. This unblocks frontend
development during weeks when the other modules are still being built.

## Contract Dependencies

Waiting on from `contracts/`:
- Deployed addresses (Sepolia) → will be placed in `lib/contracts.ts`
- Compiled ABIs → `lib/abis/` (CI should copy these automatically)

Waiting on from `tee-agent/`:
- `/health` endpoint URL → `NEXT_PUBLIC_AGENT_URL` in `.env.local`

## Open Questions (pinged in group chat)

- Is `nonceOf(user)` a public read function on Vault? (3.4 implies yes, 2.2 doesn't list it)
- Will `ActionExecuted` emit full quote bytes or only `keccak256(quote)`? Affects how much we can render in `<AttestationBadge />`.
- "Pending" state between quote generation and on-chain verification — where does frontend get this signal?