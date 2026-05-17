import { registryAbi } from "@/lib/abis/registry";
import { vaultAbi } from "@/lib/abis/vault";
import { verifierAbi } from "@/lib/abis/verifier";
import type { Address } from "@/lib/types";

const PLACEHOLDER: Address = "0x0000000000000000000000000000000000000000";

export const CONTRACTS = {
  registry: (process.env.NEXT_PUBLIC_REGISTRY_ADDRESS ?? PLACEHOLDER) as Address,
  vault: (process.env.NEXT_PUBLIC_VAULT_ADDRESS ?? PLACEHOLDER) as Address,
  verifier: (process.env.NEXT_PUBLIC_VERIFIER_ADDRESS ?? PLACEHOLDER) as Address,
} as const;

export function isConfigured(address: Address): boolean {
  return address !== PLACEHOLDER;
}

export { registryAbi, vaultAbi, verifierAbi };
