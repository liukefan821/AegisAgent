# integration

Interface notes and smoke-test checklist for the three-layer AegisAgent system.

Owner: **LIU Kefan**

This folder documents how the frontend, tee-agent, and contracts connect. It is
not a runtime package. Use it as the current integration map when checking that
all layers agree on request shapes, contract calls, and emitted events.

## Current Layers

| Layer | Path | Responsibility |
|---|---|---|
| Frontend | `frontend/` | Wallet UI, contract reads/writes, Activity, quote viewer |
| TEE agent | `tee-agent/` | LLM decision, action hash, quote generation, quote lookup |
| Contracts | `contracts/` | Vault, Registry, Verifier on Sepolia |

## Frontend ↔ TEE Agent

The frontend talks to the tee-agent over HTTP. `NEXT_PUBLIC_AGENT_URL` controls
the base URL.

| Method | Endpoint | Used by | Purpose |
|---|---|---|---|
| `GET` | `/health` | Dashboard agent card | Shows tee-agent/LLM readiness |
| `POST` | `/decisions` | Vault page | Generates decision + quote data for `executeAction` |
| `GET` | `/quotes/{digest}` | Attestation modal | Looks up full quote metadata from an on-chain quote digest |

### `/decisions` request

```json
{
  "user": "0x...",
  "balance_wei": "10000000000000000",
  "nonce": "0",
  "demo_action": "TRANSFER",
  "demo_target": "0x...",
  "demo_transfer_bps": 2500
}
```

`demo_action`, `demo_target`, and `demo_transfer_bps` are optional. They are used
only for deterministic demo paths.

### `/decisions` response

The response contains the fields needed by `AegisVault.executeAction`:

```json
{
  "action": "TRANSFER",
  "reasoning": "...",
  "user": "0x...",
  "amount_wei": "2500000000000000",
  "target": "0x...",
  "nonce": 0,
  "timestamp": 1714000000,
  "action_hash": "0x...",
  "quote_hex": "0x...",
  "quote_digest": "0x...",
  "mr_enclave": "0x...",
  "is_mock": true,
  "input_hash": "0x...",
  "output_hash": "0x...",
  "eth_usd_price": "2500.00",
  "chainlink_round_id": 0
}
```

Important safety rule: the LLM can choose `HOLD` or `TRANSFER` and the amount,
but it cannot choose the final destination. For every `TRANSFER`, the tee-agent
forces `target` to the emergency safe wallet. In the current demo, that safe
wallet is the connected user wallet.

## Frontend ↔ Contracts

The frontend reads and writes the deployed Sepolia contracts through wagmi/viem.

### Read calls

| Contract | Function | Used by |
|---|---|---|
| `AegisVault` | `balanceOf(address)` | Dashboard, Vault |
| `AegisVault` | `nonceOf(address)` | Vault agent decision |
| `AegisVault` | `isAgentAuthorizedFor(address, bytes32)` | Agents |
| `AegisRegistry` | `getRegisteredAgents()` | Dashboard, Agents |

### Write calls

| Contract | Function | Used by |
|---|---|---|
| `AegisVault` | `deposit()` payable | Vault deposit |
| `AegisVault` | `withdraw(uint256 amount)` | Vault withdraw |
| `AegisVault` | `authorizeAgent(bytes32 mrEnclave)` | Agents authorization |
| `AegisVault` | `emergencyStop()` | Agents revoke all authorizations |
| `AegisVault` | `executeAction(...)` | Vault agent decision execution |

`executeAction` is called with the tee-agent decision response. The frontend
does not reconstruct the quote; it submits the `quote_hex`, `action_hash`,
`amount_wei`, `target`, and `timestamp` returned by tee-agent.

## Contract Events → Activity UI

The Activity page and Dashboard recent actions read live events from
`AegisVault`.

| Event | Activity kind | Meaning |
|---|---|---|
| `Deposited(address user, uint256 amount)` | `deposit` | ETH moved into the Vault |
| `Withdrawn(address user, uint256 amount)` | `withdraw` | ETH moved out of the Vault by user |
| `ActionExecuted(...)` | `action` | Agent decision was verified and executed |

Agent actions also expose the quote digest. The frontend uses that digest to
call `/quotes/{digest}` and display Action Hash, Input Hash, Output Hash,
MR_ENCLAVE, raw quote, and Etherscan link.

## Deployed Sepolia Contracts

| Contract | Address |
|---|---|
| AegisVault | `0x4d046e39071b5650b6486e4997f7e5629cdf3f1d` |
| AegisRegistry | `0x77c75bd03df409906130fde880b3c9303ff35227` |
| AegisVerifier | `0x5c949780db9482ab63dd004a23d2d82b719176fd` |
| MockAutomata | `0x02e53c5c81d781a8fd59e1c0efa5a8c60d86d5f3` |

The deployed registry is initialized with this test TEE image hash:

```text
0x0000000000000000000000000000000000000000000000000000000000000001
```

## Live Smoke Test

Use this checklist after changing any integration boundary:

1. Start live mode:

   ```bash
   ./scripts/dev-setup.sh
   ```

2. Choose `2` for live mode.
3. Connect a wallet on Sepolia.
4. Confirm Dashboard shows tee-agent health.
5. Confirm Agents lists the registered test MR_ENCLAVE.
6. Deposit a small amount of Sepolia ETH.
7. Authorize the registered agent.
8. Run Agent Decision or Demo TRANSFER.
9. Confirm Activity shows Deposit and Agent Action rows.
10. Click the attestation badge and confirm quote details load.
11. Open the Etherscan link and confirm the transaction exists.

## Known Integration Limitations

- Sepolia verification currently uses MockAutomata. Production requires real
  DCAP verification.
- Quote metadata is stored in tee-agent memory. If tee-agent restarts, old
  on-chain events remain visible, but `/quotes/{digest}` may return 404.
- The current AI action space is only `HOLD` or `TRANSFER`.
- Demo HOLD and Demo TRANSFER are deterministic presentation paths.
- `docs/interfaces.md` is an earlier interface draft and may contain stale
  function names. Prefer this README plus the current source code for live demo
  integration checks.

