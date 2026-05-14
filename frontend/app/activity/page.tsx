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
        <h2 className="text-xl font-bold">Connect Wallet</h2>
        <p className="text-sm text-muted-foreground">
          Connect a wallet to view agent activity history.
        </p>
      </div>
    );
  }

  const actions = IS_MOCK ? MOCK_RESOLVED_ACTIONS : [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Activity</h1>
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
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
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
          )}
        </CardContent>
      </Card>
    </div>
  );
}
