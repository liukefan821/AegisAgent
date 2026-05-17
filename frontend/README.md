# AegisAgent Frontend

Web interface for AegisAgent — a TEE-verified autonomous DeFi agent on Ethereum Sepolia.

## Stack

- Next.js 16 (App Router)
- React 19
- TypeScript
- Tailwind CSS 4
- wagmi v2 + viem + RainbowKit (to be added)

## Development

```bash
npm install
npm run dev
```

Open http://localhost:3000.

## Structure

- `app/` — pages and layouts
- `components/` — shared UI components
- `lib/` — wagmi config, contract ABIs, utilities
- `hooks/` — custom React hooks for contract interactions

## Related

See `../docs/interfaces.md` for the on-chain / frontend / TEE agent contract.