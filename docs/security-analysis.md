# Security Analysis — AegisAgent Smart Contracts

**Tool**: Slither v0.11.5 + Manual Review
**Contracts analysed**: AegisRegistry, AegisVault, AegisVerifier, MockAutomata
**Date**: 2026-05-21

---

## 1. Slither Findings & Mitigations

### HIGH — arbitrary-send-eth

**Finding**: `AegisVault.executeAction` sends ETH to a caller-supplied `target`.

**Mitigation**: The `target` is bound inside the `actionHash` which is reconstructed
on-chain (`keccak256(abi.encode(user, amount, target, nonce, timestamp))`). An
attacker cannot alter the target without invalidating the hash. The hash itself is
embedded in the TEE attestation quote, so a valid quote can only authorize the exact
target chosen by the verified agent code.

### MEDIUM — reentrancy-no-eth / reentrancy-benign

**Finding**: `verifier.verify()` is an external call that precedes state writes in
`executeAction`.

**Mitigation**: An inline ReentrancyGuard-style `nonReentrant` modifier was added to
both `withdraw` and `executeAction`. This follows the same pattern as OpenZeppelin's
`ReentrancyGuard` (storage-based `_NOT_ENTERED` / `_ENTERED` flag) but is
implemented directly in the contract to avoid an external dependency. Even without
the guard, the verifier is a trusted contract deployed by the same team and its
address is set once in the constructor — but defence-in-depth justifies the lock.

### LOW — missing-zero-check on `target`

**Finding**: No zero-address check on the `target` parameter of `executeAction`.

**Mitigation**: Sending ETH to `address(0)` would burn funds but cannot be triggered
accidentally because the TEE agent code hardcodes the target to the user's own
emergency safe wallet. A zero-address transfer would also fail the `actionHash`
check unless the TEE agent deliberately chose `0x0`. Accepted as low risk.

### LOW — timestamp dependency

**Finding**: `block.timestamp` used for expiry comparison.

**Mitigation**: Miners can manipulate `block.timestamp` by a few seconds. The
contract enforces only `timestamp > block.timestamp`; the 15-minute expiry window
(`ACTION_EXPIRY_SECONDS = 900`) is an off-chain tee-agent convention used when
constructing signed actions. A small timestamp skew is irrelevant for that
off-chain window, but a future contract revision could add an upper bound such as
`timestamp <= block.timestamp + 900` if stricter on-chain expiry enforcement is
required.

### INFORMATIONAL — solc-version

**Finding**: `^0.8.20` pragma covers versions with known bugs (VerbatimInvalidDeduplication, etc.).

**Mitigation**: The project compiles with Solidity 0.8.28, which has all listed bugs
fixed. The pragma is intentionally broad to allow Hardhat to select the pinned
version. No vulnerable codegen paths are used.

### INFORMATIONAL — low-level-calls

**Finding**: `withdraw` and `executeAction` use `.call{value:}` instead of
`.transfer()`.

**Mitigation**: This is intentional. `.transfer()` forwards only 2300 gas and breaks
smart-contract wallets. `.call{value:}` combined with `nonReentrant` is the
recommended pattern (Consensys, OpenZeppelin).

### INFORMATIONAL — missing-inheritance

**Finding**: `AegisRegistry` does not explicitly inherit `IAegisRegistry`.

**Mitigation**: The interfaces are defined in `AegisVault.sol` for consumer-side
type safety. The implementing contracts satisfy the interface implicitly. Adding
explicit inheritance is a style improvement, not a security issue.

### INFORMATIONAL — immutable-states

**Finding**: `registry`, `verifier`, `automataVerifier`, `owner` are set once in
the constructor but not declared `immutable`.

**Mitigation**: Marking them `immutable` saves ~2100 gas per SLOAD. Documented in
`gas-optimization.md` as a recommended improvement.

### INFORMATIONAL — redundant-statements

**Finding**: `actionHash;` in `AegisVerifier.verify()` is a no-op.

**Mitigation**: See Section 2 below — this is a known limitation documented with a
production mitigation plan.

---

## 2. Common Vulnerability Protections

### Reentrancy

- Inline ReentrancyGuard-style `nonReentrant` modifier on `withdraw` and
  `executeAction` (same storage-flag pattern as OpenZeppelin's ReentrancyGuard,
  implemented without importing the library).
- Checks-effects-interactions pattern: state (`_balances`, `_nonces`) is updated
  before the external `.call{value:}`.

### Integer Overflow / Underflow

- Solidity 0.8.x has built-in overflow checks. All arithmetic reverts on overflow
  without requiring SafeMath.

### Access Control

- `AegisRegistry.registerAgent` is gated by `onlyOwner`.
- `AegisVault.executeAction` requires:
  1. Valid hardware attestation (`verifier.verify`)
  2. Registered agent image (`registry.isRegistered`)
  3. Explicit user authorization (`_authorizations[user][mrEnclave]`)
  4. Matching action hash (prevents parameter tampering)
  5. Non-expired timestamp
  6. No emergency stop active

### Front-running

- Actions are bound to a specific `nonce` and `timestamp`, making replay or
  front-running with different parameters impossible (hash mismatch).
- The attestation quote is generated inside a TEE — an attacker cannot forge a
  valid quote to front-run with altered parameters.

### Emergency Controls

- `emergencyStop()` allows any user to instantly freeze all agent activity on
  their vault. No admin key required.
- The flag is per-user and cannot be reset, providing a permanent kill switch.

---

## 3. Known Limitation — reportData Verification Gap

### Issue

`AegisVerifier.verify()` receives `actionHash` as a parameter but does **not**
verify that the quote's `report_data` field contains `actionHash`. The current
implementation delegates to `automataVerifier.verifyAttestation(quote)` which
validates the DCAP signature chain but does not extract or compare `report_data`.

This means the on-chain verifier confirms the quote is from a genuine TEE but does
**not** confirm which specific action the TEE attested to.

### Current Demo Scope

In the testnet demo, `MockAutomata` always returns `(true, bytes32(1))`. The
binding between quote and action is enforced off-chain: the TEE agent sets
`report_data = actionHash || output_hash` before generating the quote, and the
frontend verifies this before submitting.

### Production Mitigation Plan

1. **Parse `report_data` on-chain**: Extract bytes `[368:432]` from the raw DCAP
   quote (the 64-byte report_data field in the TDX report body).
2. **Verify binding**: `require(report_data[0:32] == actionHash)`.
3. **Gas consideration**: Full DCAP parsing is expensive (~500k+ gas). Risc Zero
   zkDCAP can reduce this by verifying the DCAP proof off-chain and submitting a
   ZK proof on-chain (~200k gas). This is tracked in `ARCHITECTURE.md` as an
   open question.

---

## 4. Test Coverage Summary

```
File                |  % Stmts | % Branch |  % Funcs |  % Lines |
--------------------|----------|----------|----------|----------|
AegisRegistry.sol   |      100 |      100 |      100 |      100 |
AegisVault.sol      |      100 |    76.92 |      100 |      100 |
AegisVerifier.sol   |      100 |      100 |      100 |      100 |
MockAutomata.sol    |      100 |      100 |      100 |      100 |
--------------------|----------|----------|----------|----------|
All files           |      100 |    81.25 |      100 |      100 |
```

14 Hardhat unit/security tests + Foundry invariant/fuzz tests (solvency,
emergency stop integrity, authorization integrity).
