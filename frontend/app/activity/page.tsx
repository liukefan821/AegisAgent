"use client";

import { useAccount } from "wagmi";
import { AttestationBadge } from "@/components/attestation-badge";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { IS_MOCK, MOCK_RESOLVED_ACTIONS } from "@/lib/mocks";
import { formatEth, formatTimestamp, shortHex } from "@/lib/utils/format";

export default function ActivityPage() {
  const { isConnected } = useAccount();

  if (!isConnected) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-32 text-center">
        <h2 className="text-xl font-medium">Connect Wallet</h2>
        <p className="text-sm text-muted-foreground">
          Connect a wallet to view agent activity history.
        </p>
      </div>
    );
  }

  const actions = IS_MOCK ? MOCK_RESOLVED_ACTIONS : [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-medium">Activity</h1>
          <p className="text-sm text-muted-foreground">
            On-chain agent operations with attestation status.
          </p>
        </div>
        <Badge variant="outline">{IS_MOCK ? "mock" : "live"}</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Action History</CardTitle>
          <CardDescription>
            Each row pairs an ActionExecuted event with its quote verification
            status.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {actions.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-sm text-muted-foreground">
                No actions yet. Agent operations will appear here once executed
                on-chain.
              </p>
            </div>
          ) : (
            <>
              <div className="divide-y md:hidden">
                {actions.map((action) => (
                  <div
                    key={action.event.transaction_hash}
                    className="space-y-3 py-4 first:pt-0 last:pb-0"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-mono text-sm">
                          {formatEth(action.event.amount)} Sepolia ETH
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {formatTimestamp(action.event.timestamp)}
                        </div>
                      </div>
                      <AttestationBadge
                        status={action.verified ? "verified" : "failed"}
                        digest={action.event.quote_digest}
                        txHash={action.event.transaction_hash}
                      />
                    </div>

                    <div className="grid gap-2 text-xs">
                      <div className="flex items-center justify-between gap-3">
                        <span className="shrink-0 text-muted-foreground">
                          MR_ENCLAVE
                        </span>
                        <span className="min-w-0 truncate font-mono">
                          {shortHex(action.event.mr_enclave, 10, 8)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="shrink-0 text-muted-foreground">
                          Quote
                        </span>
                        <span className="min-w-0 truncate font-mono">
                          {shortHex(action.event.quote_digest, 10, 8)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="shrink-0 text-muted-foreground">
                          Tx
                        </span>
                        <a
                          href={`https://sepolia.etherscan.io/tx/${action.event.transaction_hash}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="min-w-0 truncate font-mono text-primary hover:underline"
                        >
                          {shortHex(action.event.transaction_hash, 8, 6)} ↗
                        </a>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="hidden overflow-x-auto md:block">
                <table className="min-w-[760px] w-full text-sm">
                  <thead>
                    <tr className="border-b text-xs uppercase text-muted-foreground">
                      <th className="py-2 text-left font-medium">Time</th>
                      <th className="py-2 text-left font-medium">Amount</th>
                      <th className="py-2 text-left font-medium">
                        Agent (MR_ENCLAVE)
                      </th>
                      <th className="py-2 text-left font-medium">Quote</th>
                      <th className="py-2 text-left font-medium">Status</th>
                      <th className="py-2 text-right font-medium">Tx</th>
                    </tr>
                  </thead>
                  <tbody>
                    {actions.map((action) => (
                      <tr
                        key={action.event.transaction_hash}
                        className="border-b last:border-0"
                      >
                        <td className="py-3 text-xs text-muted-foreground">
                          {formatTimestamp(action.event.timestamp)}
                        </td>
                        <td className="py-3 font-mono">
                          {formatEth(action.event.amount)} Sepolia ETH
                        </td>
                        <td className="py-3 font-mono text-xs">
                          {shortHex(action.event.mr_enclave, 8, 6)}
                        </td>
                        <td className="py-3 font-mono text-xs">
                          {shortHex(action.event.quote_digest, 8, 6)}
                        </td>
                        <td className="py-3">
                          <AttestationBadge
                            status={action.verified ? "verified" : "failed"}
                            digest={action.event.quote_digest}
                            txHash={action.event.transaction_hash}
                          />
                        </td>
                        <td className="py-3 text-right">
                          <a
                            href={`https://sepolia.etherscan.io/tx/${action.event.transaction_hash}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-mono text-xs text-primary hover:underline"
                          >
                            {shortHex(action.event.transaction_hash, 6, 4)} ↗
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
