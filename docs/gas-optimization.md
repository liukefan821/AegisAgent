# Gas Optimization Report — AegisAgent Smart Contracts

**Tool**: hardhat-gas-reporter v2.3.0
**Solidity**: 0.8.28 (optimizer off, 200 runs default)
**Date**: 2026-05-21

---

## 1. Gas Costs Per Operation

### Method Calls

| Contract       | Method          | Min Gas | Max Gas | Avg Gas | # Calls |
|----------------|-----------------|---------|---------|---------|---------|
| AegisRegistry  | registerAgent   | 75,474  | 92,574  | 90,864  | 10      |
| AegisVault     | authorizeAgent  | —       | —       | 45,482  | 8       |
| AegisVault     | deposit         | —       | —       | 45,204  | 8       |
| AegisVault     | emergencyStop   | —       | —       | 44,669  | 2       |
| AegisVault     | executeAction   | 118,859 | 118,871 | 118,865 | 2       |
| AegisVault     | withdraw        | —       | —       | 38,248  | 1       |

### Deployment Costs

| Contract       | Gas Cost   | % of Block Limit |
|----------------|------------|------------------|
| AegisRegistry  | 421,086    | 0.7%             |
| AegisVault     | 1,573,139  | 2.6%             |
| AegisVerifier  | 372,600    | 0.6%             |
| MockAutomata   | 150,761    | 0.3%             |

---

## 2. Analysis of Key Operations

### deposit() — 45,204 gas

Minimal overhead: one `SSTORE` (balance update) + one event emission. First
deposit to a new address costs ~20k more (cold storage slot). This is near
optimal for a payable deposit.

### withdraw() — 38,248 gas

One `SSTORE` (balance decrement) + one `CALL` for ETH transfer + one event.
Uses `call{value:}` instead of `transfer()` for compatibility with smart
contract wallets.

### executeAction() — ~118,865 gas

The most expensive operation, broken down approximately:

| Step                          | Estimated Gas |
|-------------------------------|---------------|
| Timestamp/balance checks      | ~2,000        |
| verifier.verify() external call | ~35,000     |
| registry.isRegistered() call  | ~5,000        |
| Authorization SLOAD           | ~2,100        |
| keccak256 + abi.encode        | ~1,500        |
| Balance update (SSTORE)       | ~5,000        |
| Nonce increment (SSTORE)      | ~5,000        |
| Timestamp update (SSTORE)     | ~5,000        |
| ETH transfer (CALL)           | ~21,000       |
| Event emission                | ~3,000        |
| Reentrancy lock (2x SSTORE)  | ~10,000       |
| Overhead + calldata           | ~25,000       |

The external call to `verifier.verify()` dominates. In production with a real
DCAP verifier, this would be significantly higher (500k+). zkDCAP would reduce
it to ~200k.

### registerAgent() — 75,474–92,574 gas

First registration costs more due to array push (dynamic storage expansion).
Subsequent registrations are cheaper if the array storage slot is already warm.

---

## 3. Optimizations Applied

### Checks-Effects-Interactions Pattern

All `require` checks execute before any state mutation or external call. This
ensures failed transactions revert early, minimizing wasted gas.

### Minimal Storage Writes

- `executeAction` writes exactly 3 storage slots per call (balance, nonce,
  timestamp).
- `deposit` and `withdraw` each write 1 storage slot.
- No redundant storage reads — each mapping is read once.

### Low-Level Call for ETH Transfer

Using `call{value:}` instead of `transfer()` avoids the 2300 gas stipend
limitation. Combined with the reentrancy guard, this is both safe and gas
efficient.

### Event-Based State Tracking

On-chain state is kept minimal. The frontend reconstructs activity history
from event logs rather than storing arrays on-chain, avoiding expensive
dynamic storage operations.

---

## 4. Recommended Further Optimizations

### Mark State Variables as `immutable`

Slither identified that `registry`, `verifier`, `automataVerifier`, and
`owner` are set once in constructors but not declared `immutable`.

**Savings**: ~2,100 gas per read (SLOAD replaced with PUSH at compile time).

For `executeAction`, which reads both `registry` and `verifier`, this saves
~4,200 gas per call.

### Enable Solidity Optimizer

The current build uses optimizer-off defaults. Enabling the optimizer with
200-1000 runs would reduce deployment size and runtime gas for frequently
called functions.

Estimated impact:
- Deployment: -10-20% bytecode size
- Runtime: -5-15% gas per call

### Custom Errors (Solidity 0.8.4+)

Replacing `require(condition, "string")` with custom errors saves ~50 gas per
revert (no ABI-encoding of the error string at runtime) and reduces deployment
bytecode.

```solidity
error InsufficientBalance();
error TimestampExpired();
error EmergencyStopActive();
// etc.
```

### Pack Storage Slots

`_lastActionTimestamp` and `_nonces` could be packed into a single struct per
user if `_nonces` is cast to `uint96` (sufficient for billions of actions):

```solidity
struct UserState {
    uint96  nonce;
    uint160 lastActionTimestamp;
}
```

This would save one SSTORE (~5,000 gas) per `executeAction` call.

---

## 5. Gas Cost Context

At 20 gwei gas price and ETH at $2,500:

| Operation     | Gas     | Cost (USD) |
|---------------|---------|------------|
| deposit       | 45,204  | $0.0023    |
| withdraw      | 38,248  | $0.0019    |
| executeAction | 118,865 | $0.0059    |
| registerAgent | 92,574  | $0.0046    |

All user-facing operations cost under $0.01 at current gas prices, making the
protocol economically viable for everyday use.
