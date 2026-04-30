"use client";

import { useReadContract } from "wagmi";
import { CONTRACTS, vaultAbi, isConfigured } from "@/lib/contracts";
import { IS_MOCK, MOCK_VAULT_BALANCE, MOCK_NONCE } from "@/lib/mocks";
import type { Address, HookResult } from "@/lib/types";

export function useVaultBalance(user?: Address): HookResult<bigint> {
  const query = useReadContract({
    address: CONTRACTS.vault,
    abi: vaultAbi,
    functionName: "balanceOf",
    args: user ? [user] : undefined,
    query: { enabled: !IS_MOCK && !!user && isConfigured(CONTRACTS.vault) },
  });

  if (IS_MOCK) {
    return {
      data: user ? MOCK_VAULT_BALANCE : undefined,
      isLoading: false,
      error: null,
      source: "mock",
    };
  }

  return {
    data: query.data as bigint | undefined,
    isLoading: query.isLoading,
    error: query.error,
    source: "live",
  };
}

export function useUserNonce(user?: Address): HookResult<bigint> {
  const query = useReadContract({
    address: CONTRACTS.vault,
    abi: vaultAbi,
    functionName: "nonceOf",
    args: user ? [user] : undefined,
    query: { enabled: !IS_MOCK && !!user && isConfigured(CONTRACTS.vault) },
  });

  if (IS_MOCK) {
    return {
      data: user ? MOCK_NONCE : undefined,
      isLoading: false,
      error: null,
      source: "mock",
    };
  }

  return {
    data: query.data as bigint | undefined,
    isLoading: query.isLoading,
    error: query.error,
    source: "live",
  };
}
