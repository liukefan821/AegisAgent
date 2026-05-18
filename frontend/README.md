# AegisAgent Frontend

Web interface for AegisAgent — a TEE-verified autonomous DeFi agent on Ethereum Sepolia.

## Stack

- Next.js 16 (App Router)
- React 19
- TypeScript
- Tailwind CSS 4
- wagmi v2 + viem + RainbowKit

## Development

```bash
npm install
npm run dev
```

Open http://localhost:3000.

Create `.env.local` from `.env.example` before running locally:

```bash
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=<walletconnect-project-id>
NEXT_PUBLIC_USE_MOCK=true
NEXT_PUBLIC_AGENT_URL=http://localhost:8080
NEXT_PUBLIC_REGISTRY_ADDRESS=
NEXT_PUBLIC_VAULT_ADDRESS=
NEXT_PUBLIC_VERIFIER_ADDRESS=
```

`NEXT_PUBLIC_USE_MOCK=true` is the recommended local demo mode while the
Sepolia contracts are not yet available.

## Structure

- `app/` — pages and layouts
- `components/` — shared UI components
- `lib/` — wagmi config, contract ABIs, utilities
- `hooks/` — custom React hooks for contract interactions

## Going Live After Sepolia Deployment

After the contracts team provides deployed addresses, update `.env.local`:

```bash
NEXT_PUBLIC_USE_MOCK=false
NEXT_PUBLIC_VAULT_ADDRESS=0x...
NEXT_PUBLIC_REGISTRY_ADDRESS=0x...
NEXT_PUBLIC_VERIFIER_ADDRESS=0x...
NEXT_PUBLIC_AGENT_URL=<tee-agent-url>
```

Then restart the development server. Next.js reads `NEXT_PUBLIC_*` variables at
startup, so changing `.env.local` while the server is running is not enough.

For local live testing, run tee-agent on port `8080` and use:

```bash
NEXT_PUBLIC_AGENT_URL=http://localhost:8080
```

The frontend imports ABI-only TypeScript files from `lib/abis/`. If the Solidity
contracts change, refresh those ABI files from the latest compiled artifacts,
keep the `as const` export, and rerun TypeScript/lint checks.

## Related

See `../docs/interfaces.md` for the on-chain / frontend / TEE agent contract.
