# AegisAgent — Three-Layer Interface Contracts

**Author**: LIU Kefan
**Version**: 0.1 (first draft — open to feedback)
**Last updated**: 2026-04-22

> This document defines the contracts between the three layers (frontend, TEE agent, on-chain). Each teammate should code against this spec so the three modules can be developed in parallel without blocking each other.
>
> **If you need something not covered here, ping me on WeChat and we'll add it before you start coding that piece.**

---

## 1. System Boundaries

```
+------------+        +----------------+        +------------------+
|  Frontend  | <----> | Smart Contracts| <----  | TEE Agent        |
|  (Next.js) |  reads |  (Sepolia)     |  quote | (Phala TDX CVM)  |
+------------+        +----------------+        +------------------+
       |                                                 ^
       +------- HTTP /health (read-only) ----------------+
```

Three boundaries:
- **A. On-chain → Frontend**: functions to call, events to listen
- **B. TEE Agent → On-chain**: quote format, verifier function signature
- **C. Frontend → TEE Agent**: HTTP health endpoint (read-only; no write path)

---

## 2. Boundary A — On-chain ↔ Frontend

### 2.1 Contracts deployed on Sepolia

| Contract | Purpose | Owner |
|---|---|---|
| `AegisRegistry` | Registers approved enclave measurements | ZHU |
| `AegisVerifier` | Validates DCAP attestation quotes | ZHU |
| `AegisVault` | Holds user funds; releases only on verified action | ZHU |

### 2.2 Functions the frontend will call (read)

```solidity
// AegisRegistry.sol
function isRegistered(bytes32 mrEnclave) external view returns (bool);
function getRegisteredAgents() external view returns (bytes32[] memory);

// AegisVault.sol
function balanceOf(address user) external view returns (uint256);
function isAgentAuthorizedFor(address user, bytes32 mrEnclave) external view returns (bool);
function lastActionTimestamp(address user) external view returns (uint256);
```

### 2.3 Functions the frontend will call (write)

```solidity
// AegisVault.sol
function deposit() external payable;
function withdraw(uint256 amount) external;
function authorizeAgent(bytes32 mrEnclave) external;
function emergencyStop() external;  // revokes all agent authorizations for msg.sender
```

### 2.4 Events the frontend must subscribe to

```solidity
// AegisRegistry
event AgentRegistered(bytes32 indexed mrEnclave, address indexed registrar, uint256 timestamp);

// AegisVault
event Deposited(address indexed user, uint256 amount);
event Withdrawn(address indexed user, uint256 amount);
event AgentAuthorized(address indexed user, bytes32 indexed mrEnclave);
event EmergencyStopped(address indexed user);
event ActionExecuted(
    address indexed user,
    bytes32 indexed mrEnclave,
    bytes32 quoteDigest,
    uint256 amount,
    uint256 timestamp
);

// AegisVerifier
event QuoteVerified(bytes32 indexed mrEnclave, bytes32 quoteDigest, bool success);
```

**Frontend use cases → which events:**
- Vault balance panel → `Deposited` / `Withdrawn` / `ActionExecuted`
- Attestation status panel → `QuoteVerified` (latest one)
- Transaction history list → `ActionExecuted` (indexed by user)
- Emergency stop button feedback → `EmergencyStopped`

### 2.5 Frontend stack notes

- Use **wagmi v2** `useReadContract` for view functions
- Use **wagmi v2** `useWatchContractEvent` for live event streams
- ABIs will be published under `contracts/abi/` after each Sepolia deployment (ZHU will maintain)

---

## 3. Boundary B — TEE Agent ↔ On-chain

### 3.1 Quote structure

The TEE agent generates a DCAP attestation quote for **every** on-chain action. Quote is produced by the Dstack SDK inside the TDX CVM.

```python
# Python side (tee-agent/)
quote: bytes = dstack.get_quote(report_data=action_hash)
# Where action_hash = keccak256(abi.encode(user, amount, target, nonce, timestamp))
```

The quote is a ~4KB opaque binary blob (Intel DCAP v4 format).

### 3.2 Verifier function signature

```solidity
// AegisVerifier.sol
function verify(bytes calldata quote, bytes32 actionHash)
    external
    returns (bool success, bytes32 mrEnclave);
```

- `quote`: raw DCAP bytes from the agent
- `actionHash`: the 32-byte hash the agent signed over
- Returns `(true, mrEnclave)` if verification passes
- Returns `(false, bytes32(0))` otherwise

**Implementation shortcut (ZHU):** delegate the heavy DCAP parsing to Automata's already-deployed `IAttestationVerifier` on Sepolia — do not implement DCAP binary parsing from scratch. We just wrap their call and extract `mrEnclave`.

### 3.3 Vault's action flow

```solidity
// AegisVault.sol
function executeAction(
    bytes calldata quote,
    bytes32 actionHash,
    uint256 amount,
    address target
) external {
    (bool ok, bytes32 mrEnclave) = verifier.verify(quote, actionHash);
    require(ok, "Verification failed");
    require(registry.isRegistered(mrEnclave), "Agent not approved");
    require(isAgentAuthorizedFor(msg.sender, mrEnclave), "Not authorized by user");
    // ... reconstruct actionHash from (msg.sender, amount, target, nonce) and compare
    // ... transfer funds
    emit ActionExecuted(msg.sender, mrEnclave, keccak256(quote), amount, block.timestamp);
}
```

### 3.4 Nonce handling

To prevent replay, `actionHash` includes a per-user nonce that increments after every successful action. The agent must read the current nonce from `AegisVault.nonceOf(user)` before generating a quote.

---

## 4. Boundary C — Frontend ↔ TEE Agent (HTTP)

The agent exposes a **read-only** HTTP endpoint. The frontend does **not** directly command the agent — all actions go through the smart contract path.

### 4.1 `/health` endpoint

```
GET http://<agent-host>:8080/health
```

Response (JSON):
```json
{
  "status": "alive",
  "enclave_image_hash": "0x...",
  "last_quote_generated_at": 1714000000,
  "ollama_model": "qwen2.5:7b",
  "ollama_status": "ready"
}
```

**Frontend use:** poll every 10s, display in the attestation status panel.

### 4.2 What the frontend does NOT do

- ❌ Do not POST trading signals to the agent
- ❌ Do not expose any "stop agent" HTTP call — stopping happens on-chain via `emergencyStop()`
- ✅ All state flows through contracts; HTTP is only for liveness display

---

## 5. Open Questions (to resolve by Week 2)

- [ ] Should `ActionExecuted` event include the full quote or just `keccak256(quote)`? (Gas tradeoff)
- [ ] Nonce: per-user vs global counter?
- [ ] What happens if verifier succeeds but registry says agent not registered — revert with what error?
- [ ] Frontend: do we show a "pending" state between agent quote generation and on-chain verification?

---

## 6. Revision Log

| Date | Author | Change |
|---|---|---|
| 2026-04-22 | LIU Kefan | Initial draft |

---

*Questions / feedback → WeChat me. Changes to this document must be announced in the group chat.*
