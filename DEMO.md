# AegisAgent Demo Guide

This guide shows the current live demo path: deposit Sepolia ETH, authorize the
registered TEE agent, run an attested agent decision, and inspect the resulting
on-chain activity.

## What This Demo Shows

AegisAgent is a verifiable AI execution demo. The important idea is not that the
AI is a complete trading strategy today. The important idea is:

1. An agent decision is produced by the tee-agent.
2. The decision is bound to an `action_hash`.
3. The tee-agent generates an attestation quote.
4. The frontend submits the decision and quote to `AegisVault.executeAction`.
5. The contract verifies the quote/action data before executing.
6. The frontend displays the resulting on-chain activity and quote details.

## Prerequisites

- Node.js and npm
- Python environment for `tee-agent`
- MetaMask or another wallet on Sepolia
- Sepolia ETH for gas and deposit testing
- Gemini API key for live mode

## Start The Demo

From the repository root:

```bash
./scripts/dev-setup.sh
```

Choose:

```text
1 = mock mode
2 = live mode
```

For the full demo, choose `2`. The script starts:

- Frontend: `http://localhost:3000`
- Phone frontend: `http://<your-lan-ip>:3000`
- TEE agent: `http://<your-lan-ip>:8080`

If this is your first live run, the script asks for a Gemini API key and stores
it in `tee-agent/.env.local`. This file is ignored by git.

## Recommended Live Demo Flow

1. Open the frontend.
2. Connect a wallet on Sepolia.
3. Go to **Vault**.
4. Deposit a small amount of Sepolia ETH, for example `0.01`.
5. Go to **Agents**.
6. Authorize the registered agent.
7. Go back to **Vault**.
8. Click **Run Agent Decision** to ask the tee-agent/Gemini for a real decision.
9. Click **Demo HOLD** to show a deterministic hold path.
10. Click **Demo TRANSFER** to show a deterministic transfer path.
11. Go to **Activity**.
12. Confirm that Deposit, Withdraw, and Agent Action events are listed.
13. Click the attestation badge on an Agent Action.
14. Inspect Action Hash, Input Hash, Output Hash, raw quote, and Etherscan link.

## Decision Buttons

| Button | Meaning |
|---|---|
| Run Agent Decision | Calls the tee-agent and asks the configured LLM to decide from market context. |
| Demo HOLD | Bypasses the LLM choice and creates a deterministic HOLD decision for presentation. |
| Demo TRANSFER | Bypasses the LLM choice and creates a deterministic TRANSFER decision for presentation. |

`Demo TRANSFER` transfers 25% of the current vault balance to the emergency safe
wallet. In the current demo, the emergency safe wallet is the connected user
wallet.

The LLM is allowed to decide `HOLD` or `TRANSFER` and the amount. The transfer
destination is not trusted from the model output. The tee-agent code forces all
TRANSFER targets to the emergency safe wallet.

## Mock Mode

Mock mode is useful for UI review and development:

- No Python server is required.
- No Gemini key is required.
- Contract reads and writes use local fixtures.
- Write actions simulate wallet confirmation and transaction confirmation.

Mock mode is not a chain demo. Use live mode for Sepolia transactions.

## Current Limitations

- The Sepolia verifier currently uses MockAutomata for testnet integration.
  Production requires a real DCAP verifier.
- The quote lookup store is in tee-agent memory. If tee-agent restarts, old
  on-chain Activity events remain visible, but clicking their attestation badge
  may show `Quote not found`.
- The current AI action space is only `HOLD` or `TRANSFER`.
- There is no swap, buy, sell, or portfolio rebalancing yet.
- `Demo HOLD` and `Demo TRANSFER` are deterministic presentation paths, not real
  Gemini choices.
- The current emergency safe wallet defaults to the connected user wallet.

## Troubleshooting

| Symptom | Check |
|---|---|
| TEE agent unreachable | Confirm the tee-agent is running and `NEXT_PUBLIC_AGENT_URL` points to it. |
| Phone cannot open the app | Use the printed LAN URL and keep phone/laptop on the same network. |
| LLM status is not ready | Check `tee-agent/.env.local` has `LLM_PROVIDER=gemini` and `GEMINI_API_KEY`. |
| Activity is empty | Live Activity only shows events that happened on the deployed Vault. |
| Quote not found | The tee-agent memory store was likely restarted after the action was created. |

