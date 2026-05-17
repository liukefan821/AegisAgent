"use client";

import { useReadContract } from "wagmi";
import { CONTRACTS, vaultAbi, isConfigured } from "@/lib/contracts";
import { IS_MOCK, MOCK_VAULT_BALANCE, MOCK_NONCE } from "@/lib/mocks";
import type { Address, Bytes32, HookResult } from "@/lib/types";

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
      refetch: () => {},
    };
  }

  return {
    data: query.data as bigint | undefined,
    isLoading: query.isLoading,
    error: query.error,
    source: "live",
    refetch: () => {
      void query.refetch();
    },
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
      refetch: () => {},
    };
  }

  return {
    data: query.data as bigint | undefined,
    isLoading: query.isLoading,
    error: query.error,
    source: "live",
    refetch: () => {
      void query.refetch();
    },
  };
}

export function useAgentAuthorization(
  user?: Address,
  mrEnclave?: Bytes32
): HookResult<boolean> {
  const query = useReadContract({
    address: CONTRACTS.vault,
    abi: vaultAbi,
    functionName: "isAgentAuthorizedFor",
    args: user && mrEnclave ? [user, mrEnclave] : undefined,
    query: {
      enabled:
        !IS_MOCK && !!user && !!mrEnclave && isConfigured(CONTRACTS.vault),
    },
  });

  if (IS_MOCK) {
    return {
      data: user && mrEnclave ? false : undefined,
      isLoading: false,
      error: null,
      source: "mock",
      refetch: () => {},
    };
  }

  return {
    data: query.data as boolean | undefined,
    isLoading: query.isLoading,
    error: query.error,
    source: "live",
    refetch: () => {
      void query.refetch();
    },
  };
}
