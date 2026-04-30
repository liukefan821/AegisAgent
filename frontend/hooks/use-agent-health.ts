"use client";

import { useQuery } from "@tanstack/react-query";
import { IS_MOCK, MOCK_HEALTH } from "@/lib/mocks";
import type { HealthResponse, HookResult } from "@/lib/types";

const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8080";
const POLL_INTERVAL_MS = 10_000;

async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${AGENT_URL}/health`, {
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }
  return res.json();
}

export function useAgentHealth(): HookResult<HealthResponse> {
  const query = useQuery({
    queryKey: ["agent-health"],
    queryFn: fetchHealth,
    refetchInterval: POLL_INTERVAL_MS,
    enabled: !IS_MOCK,
    retry: 1,
  });

  if (IS_MOCK) {
    return {
      data: MOCK_HEALTH,
      isLoading: false,
      error: null,
      source: "mock",
    };
  }

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error as Error | null,
    source: "live",
  };
}
