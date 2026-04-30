"use client";

import { useReadContract } from "wagmi";
import { CONTRACTS, registryAbi } from "@/lib/contracts";
import { IS_MOCK, MOCK_REGISTERED_AGENTS } from "@/lib/mocks";
import type { Bytes32, HookResult } from "@/lib/types";

export function useRegisteredAgents(): HookResult<readonly Bytes32[]> {
  const query = useReadContract({
    address: CONTRACTS.registry,
    abi: registryAbi,
    functionName: "getRegisteredAgents",
    query: { enabled: !IS_MOCK },
  });

  if (IS_MOCK) {
    return {
      data: MOCK_REGISTERED_AGENTS,
      isLoading: false,
      error: null,
      source: "mock",
    };
  }

  return {
    data: query.data as readonly Bytes32[] | undefined,
    isLoading: query.isLoading,
    error: query.error,
    source: "live",
  };
}

export function useIsRegistered(mrEnclave?: Bytes32): HookResult<boolean> {
  const query = useReadContract({
    address: CONTRACTS.registry,
    abi: registryAbi,
    functionName: "isRegistered",
    args: mrEnclave ? [mrEnclave] : undefined,
    query: { enabled: !IS_MOCK && !!mrEnclave },
  });

  if (IS_MOCK) {
    return {
      data: mrEnclave
        ? MOCK_REGISTERED_AGENTS.includes(mrEnclave)
        : undefined,
      isLoading: false,
      error: null,
      source: "mock",
    };
  }

  return {
    data: query.data as boolean | undefined,
    isLoading: query.isLoading,
    error: query.error,
    source: "live",
  };
}
