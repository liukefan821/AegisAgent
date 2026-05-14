"use client";

import { useQuery } from "@tanstack/react-query";
import { IS_MOCK, MOCK_QUOTES } from "@/lib/mocks";
import type { AttestationQuote, Bytes32, HookResult } from "@/lib/types";

const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8080";

type QuoteResponse = AttestationQuote & {
  digest: Bytes32;
};

async function fetchQuote(digest: Bytes32): Promise<QuoteResponse> {
  const res = await fetch(`${AGENT_URL}/quotes/${digest}`, {
    signal: AbortSignal.timeout(5000),
  });

  if (res.status === 404) {
    throw new Error("Quote not found");
  }

  if (!res.ok) {
    throw new Error(`Quote lookup failed: ${res.status}`);
  }

  return res.json() as Promise<QuoteResponse>;
}

export function useQuote(digest?: Bytes32): HookResult<AttestationQuote> {
  const normalizedDigest = digest?.toLowerCase() as Bytes32 | undefined;

  const query = useQuery({
    queryKey: ["quote", normalizedDigest],
    queryFn: () => {
      if (!normalizedDigest) {
        throw new Error("Quote digest is required");
      }
      return fetchQuote(normalizedDigest);
    },
    enabled: !IS_MOCK && !!normalizedDigest,
    retry: (failureCount, error) => {
      if (error instanceof Error && error.message === "Quote not found") {
        return false;
      }
      return failureCount < 1;
    },
  });

  if (IS_MOCK) {
    const quote = normalizedDigest ? MOCK_QUOTES[normalizedDigest] : undefined;

    return {
      data: quote,
      isLoading: false,
      error: normalizedDigest && !quote ? new Error("Quote not found") : null,
      source: "mock",
      refetch: () => {},
    };
  }

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error as Error | null,
    source: "live",
    refetch: () => {
      void query.refetch();
    },
  };
}
