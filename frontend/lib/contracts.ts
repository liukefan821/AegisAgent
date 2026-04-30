import type { Address } from "@/lib/types";

const PLACEHOLDER: Address = "0x0000000000000000000000000000000000000000";

export const CONTRACTS = {
  registry: (process.env.NEXT_PUBLIC_REGISTRY_ADDRESS ?? PLACEHOLDER) as Address,
  vault: (process.env.NEXT_PUBLIC_VAULT_ADDRESS ?? PLACEHOLDER) as Address,
  verifier: (process.env.NEXT_PUBLIC_VERIFIER_ADDRESS ?? PLACEHOLDER) as Address,
} as const;

export const registryAbi = [
  {
    type: "function",
    name: "isRegistered",
    stateMutability: "view",
    inputs: [{ name: "mrEnclave", type: "bytes32" }],
    outputs: [{ name: "", type: "bool" }],
  },
  {
    type: "function",
    name: "getRegisteredAgents",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "", type: "bytes32[]" }],
  },
  {
    type: "event",
    name: "AgentRegistered",
    inputs: [
      { name: "mrEnclave", type: "bytes32", indexed: true },
      { name: "registrar", type: "address", indexed: true },
      { name: "timestamp", type: "uint256", indexed: false },
    ],
  },
] as const;

export const vaultAbi = [
  {
    type: "function",
    name: "balanceOf",
    stateMutability: "view",
    inputs: [{ name: "user", type: "address" }],
    outputs: [{ name: "", type: "uint256" }],
  },
  {
    type: "function",
    name: "isAgentAuthorizedFor",
    stateMutability: "view",
    inputs: [
      { name: "user", type: "address" },
      { name: "mrEnclave", type: "bytes32" },
    ],
    outputs: [{ name: "", type: "bool" }],
  },
  {
    type: "function",
    name: "lastActionTimestamp",
    stateMutability: "view",
    inputs: [{ name: "user", type: "address" }],
    outputs: [{ name: "", type: "uint256" }],
  },
  {
    type: "function",
    name: "nonceOf",
    stateMutability: "view",
    inputs: [{ name: "user", type: "address" }],
    outputs: [{ name: "", type: "uint256" }],
  },
  {
    type: "function",
    name: "deposit",
    stateMutability: "payable",
    inputs: [],
    outputs: [],
  },
  {
    type: "function",
    name: "withdraw",
    stateMutability: "nonpayable",
    inputs: [{ name: "amount", type: "uint256" }],
    outputs: [],
  },
  {
    type: "function",
    name: "authorizeAgent",
    stateMutability: "nonpayable",
    inputs: [{ name: "mrEnclave", type: "bytes32" }],
    outputs: [],
  },
  {
    type: "function",
    name: "emergencyStop",
    stateMutability: "nonpayable",
    inputs: [],
    outputs: [],
  },
  {
    type: "event",
    name: "Deposited",
    inputs: [
      { name: "user", type: "address", indexed: true },
      { name: "amount", type: "uint256", indexed: false },
    ],
  },
  {
    type: "event",
    name: "Withdrawn",
    inputs: [
      { name: "user", type: "address", indexed: true },
      { name: "amount", type: "uint256", indexed: false },
    ],
  },
  {
    type: "event",
    name: "AgentAuthorized",
    inputs: [
      { name: "user", type: "address", indexed: true },
      { name: "mrEnclave", type: "bytes32", indexed: true },
    ],
  },
  {
    type: "event",
    name: "EmergencyStopped",
    inputs: [{ name: "user", type: "address", indexed: true }],
  },
  {
    type: "event",
    name: "ActionExecuted",
    inputs: [
      { name: "user", type: "address", indexed: true },
      { name: "mrEnclave", type: "bytes32", indexed: true },
      { name: "quoteDigest", type: "bytes32", indexed: false },
      { name: "amount", type: "uint256", indexed: false },
      { name: "timestamp", type: "uint256", indexed: false },
    ],
  },
] as const;

export function isConfigured(address: Address): boolean {
  return address !== "0x0000000000000000000000000000000000000000";
}

export const verifierAbi = [
  {
    type: "event",
    name: "QuoteVerified",
    inputs: [
      { name: "mrEnclave", type: "bytes32", indexed: true },
      { name: "quoteDigest", type: "bytes32", indexed: false },
      { name: "success", type: "bool", indexed: false },
    ],
  },
] as const;
