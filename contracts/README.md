# contracts

Solidity smart contracts: AegisRegistry, AegisVault, AegisVerifier.
Owner: **ZHU Ruiqi**

## Modules

| Module | Purpose |
|---|---|
| `contracts/AegisVault.sol` | User fund custody, agent authorization, TEE-verified action execution |
| `contracts/AegisRegistry.sol` | Whitelist of trusted TEE enclave image hashes (mrEnclave) |
| `contracts/AegisVerifier.sol` | Wrapper around Automata DCAP verifier for attestation quote validation |
| `contracts/MockAutomata.sol` | Mock DCAP verifier for testnet integration (always returns success) |
| `test/AegisAgent.test.ts` | Hardhat integration tests |
| `test/foundry/AegisVault.t.sol` | Foundry fuzz tests and invariant tests |

## Deployed Contracts (Sepolia)

| Contract | Address |
|---|---|
| AegisVault | [0x4d04...3f1d](https://sepolia.etherscan.io/address/0x4d046e39071b5650b6486e4997f7e5629cdf3f1d#code) |
| AegisRegistry | [0x77c7...5227](https://sepolia.etherscan.io/address/0x77c75bd03df409906130fde880b3c9303ff35227#code) |
| AegisVerifier | [0x5c94...76fd](https://sepolia.etherscan.io/address/0x5c949780db9482ab63dd004a23d2d82b719176fd#code) |
| MockAutomata | [0x02e5...d5f3](https://sepolia.etherscan.io/address/0x02e53c5c81d781a8fd59e1c0efa5a8c60d86d5f3#code) |

## Setup

To compile and test the contracts locally:

```bash
cd contracts
npm install
npx hardhat test
```

The contracts are already deployed on Sepolia (see addresses above), so you
do not need to deploy them yourself to run the frontend or TEE agent.
