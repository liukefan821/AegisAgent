"use client";

import { useQuery } from "@tanstack/react-query";
import { parseAbiItem } from "viem";
import { usePublicClient } from "wagmi";
import { CONTRACTS, isConfigured } from "@/lib/contracts";
import { IS_MOCK, MOCK_RESOLVED_ACTIONS } from "@/lib/mocks";
import type { Address, Hex, HookResult, VaultActivityItem } from "@/lib/types";

const DEFAULT_VAULT_DEPLOY_BLOCK = 10_879_000n;
const ACTIVITY_REFETCH_MS = 12_000;
const ACTION_EXECUTED_EVENT = parseAbiItem(
  "event ActionExecuted(address indexed user, bytes32 indexed mrEnclave, bytes32 quoteDigest, uint256 amount, uint256 timestamp)"
);
const DEPOSITED_EVENT = parseAbiItem(
  "event Deposited(address indexed user, uint256 amount)"
);
const WITHDRAWN_EVENT = parseAbiItem(
  "event Withdrawn(address indexed user, uint256 amount)"
);

function vaultDeployBlock(): bigint {
  const raw = process.env.NEXT_PUBLIC_VAULT_DEPLOY_BLOCK;
  if (!raw) {
    return DEFAULT_VAULT_DEPLOY_BLOCK;
  }

  try {
    return BigInt(raw);
  } catch {
    return DEFAULT_VAULT_DEPLOY_BLOCK;
  }
}

function mockActivity(): VaultActivityItem[] {
  return MOCK_RESOLVED_ACTIONS.map((action) => ({
    kind: "action",
    user: action.event.user,
    mr_enclave: action.event.mr_enclave,
    quote_digest: action.event.quote_digest,
    amount: action.event.amount,
    timestamp: action.event.timestamp,
    block_number: action.event.block_number,
    transaction_hash: action.event.transaction_hash,
    verified: action.verified,
  }));
}

export function useVaultActivity(user?: Address): HookResult<VaultActivityItem[]> {
  const publicClient = usePublicClient();

  const query = useQuery({
    queryKey: ["vault-activity", user, CONTRACTS.vault],
    enabled:
      !IS_MOCK && !!user && !!publicClient && isConfigured(CONTRACTS.vault),
    refetchInterval: ACTIVITY_REFETCH_MS,
    queryFn: async () => {
      if (!user || !publicClient) {
        return [];
      }

      const fromBlock = vaultDeployBlock();
      const [actionLogs, depositLogs, withdrawLogs] = await Promise.all([
        publicClient.getLogs({
          address: CONTRACTS.vault,
          event: ACTION_EXECUTED_EVENT,
          args: { user },
          fromBlock,
          toBlock: "latest",
        }),
        publicClient.getLogs({
          address: CONTRACTS.vault,
          event: DEPOSITED_EVENT,
          args: { user },
          fromBlock,
          toBlock: "latest",
        }),
        publicClient.getLogs({
          address: CONTRACTS.vault,
          event: WITHDRAWN_EVENT,
          args: { user },
          fromBlock,
          toBlock: "latest",
        }),
      ]);

      const blocks = Array.from(
        new Set(
          [...actionLogs, ...depositLogs, ...withdrawLogs].map((log) =>
            log.blockNumber.toString()
          )
        )
      );
      const blockTimestamps = new Map<string, bigint>();
      await Promise.all(
        blocks.map(async (blockNumber) => {
          const block = await publicClient.getBlock({
            blockNumber: BigInt(blockNumber),
          });
          blockTimestamps.set(blockNumber, block.timestamp);
        })
      );

      const items: VaultActivityItem[] = [
        ...actionLogs.flatMap((log) => {
          const { amount, mrEnclave, quoteDigest, timestamp, user: logUser } = log.args;
          if (!logUser || !mrEnclave || !quoteDigest || amount === undefined) {
            return [];
          }

          return [
            {
              kind: "action" as const,
              user: logUser as Address,
              mr_enclave: mrEnclave,
              quote_digest: quoteDigest,
              amount,
              timestamp:
                timestamp ??
                blockTimestamps.get(log.blockNumber.toString()) ??
                0n,
              block_number: log.blockNumber,
              transaction_hash: log.transactionHash as Hex,
              verified: true,
            },
          ];
        }),
        ...depositLogs.flatMap((log) => {
          const { amount, user: logUser } = log.args;
          if (!logUser || amount === undefined) {
            return [];
          }

          return [
            {
              kind: "deposit" as const,
              user: logUser as Address,
              amount,
              timestamp: blockTimestamps.get(log.blockNumber.toString()) ?? 0n,
              block_number: log.blockNumber,
              transaction_hash: log.transactionHash as Hex,
            },
          ];
        }),
        ...withdrawLogs.flatMap((log) => {
          const { amount, user: logUser } = log.args;
          if (!logUser || amount === undefined) {
            return [];
          }

          return [
            {
              kind: "withdraw" as const,
              user: logUser as Address,
              amount,
              timestamp: blockTimestamps.get(log.blockNumber.toString()) ?? 0n,
              block_number: log.blockNumber,
              transaction_hash: log.transactionHash as Hex,
            },
          ];
        }),
      ];

      return items.sort((a, b) => {
        if (a.block_number === b.block_number) {
          return b.transaction_hash.localeCompare(a.transaction_hash);
        }
        return a.block_number > b.block_number ? -1 : 1;
      });
    },
  });

  if (IS_MOCK) {
    return {
      data: mockActivity(),
      isLoading: false,
      error: null,
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
