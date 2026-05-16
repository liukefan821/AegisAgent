"use client";

import Link from "next/link";
import { useAccount } from "wagmi";
import { AttestationBadge } from "@/components/attestation-badge";
import { ErrorCard } from "@/components/error-card";
import { StatCardSkeleton } from "@/components/loading-states";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAgentHealth } from "@/hooks/use-agent-health";
import { useRegisteredAgents } from "@/hooks/use-registry";
import { useVaultBalance } from "@/hooks/use-vault";
import {
  agentHealthErrorMessage,
  registryErrorMessage,
  vaultErrorMessage,
} from "@/lib/error-messages";
import { IS_MOCK, MOCK_RESOLVED_ACTIONS } from "@/lib/mocks";
import { formatEth, formatTimestamp, shortHex } from "@/lib/utils/format";

export default function DashboardPage() {
  const { address, isConnected } = useAccount();
  const balance = useVaultBalance(address);
  const health = useAgentHealth();
  const agents = useRegisteredAgents();

  if (!isConnected) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-32 text-center">
        <h1 className="text-2xl font-medium">Welcome to AegisAgent</h1>
        <p className="max-w-md text-muted-foreground">
          A TEE-verified autonomous DeFi agent. Connect your wallet to view your
          vault and agent activity.
        </p>
      </div>
    );
  }

  const recentActions = IS_MOCK ? MOCK_RESOLVED_ACTIONS.slice(0, 3) : [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-medium">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          {balance.source === "mock" &&
            "⚠ Showing mock data — set NEXT_PUBLIC_USE_MOCK=false after contract deployment."}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {balance.error ? (
          <ErrorCard
            message={vaultErrorMessage(balance.error)}
            onRetry={balance.refetch}
          />
        ) : balance.isLoading ? (
          <StatCardSkeleton />
        ) : (
          <Card>
            <CardHeader className="pb-3">
              <CardDescription>Vault Balance</CardDescription>
              <CardTitle className="font-mono text-2xl">
                {balance.data !== undefined
                  ? `${formatEth(balance.data)} Sepolia ETH`
                  : "-"}
              </CardTitle>
            </CardHeader>
          </Card>
        )}

        {health.error ? (
          <ErrorCard
            message={agentHealthErrorMessage(health.error)}
            onRetry={health.refetch}
          />
        ) : health.isLoading ? (
          <StatCardSkeleton />
        ) : (
          <Card>
            <CardHeader className="pb-3">
              <CardDescription>TEE Agent Status</CardDescription>
              <CardTitle className="flex items-center gap-2">
                {health.data ? (
                  <>
                    <span
                      className={`inline-block size-2 rounded-full ${
                        health.data.status === "alive"
                          ? "bg-emerald-500"
                          : "bg-amber-500"
                      }`}
                    />
                    <span className="capitalize">{health.data.status}</span>
                  </>
                ) : (
                  "-"
                )}
              </CardTitle>
            </CardHeader>
            {health.data && (
              <CardContent className="space-y-0.5 text-xs text-muted-foreground">
                <div>Model: {health.data.ollama_model}</div>
                <div>Ollama: {health.data.ollama_status}</div>
              </CardContent>
            )}
          </Card>
        )}

        {agents.error ? (
          <ErrorCard
            message={registryErrorMessage(agents.error)}
            onRetry={agents.refetch}
          />
        ) : agents.isLoading ? (
          <StatCardSkeleton />
        ) : (
          <Card>
            <CardHeader className="pb-3">
              <CardDescription>Registered Agents</CardDescription>
              <CardTitle className="font-mono text-2xl">
                {agents.data?.length ?? "-"}
              </CardTitle>
            </CardHeader>
          </Card>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Recent Actions</CardTitle>
          <CardDescription>Last 3 verified agent operations</CardDescription>
        </CardHeader>
        <CardContent>
          {recentActions.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">No actions yet.</p>
          ) : (
            <div className="space-y-3">
              {recentActions.map((action) => (
                <div
                  key={action.event.transaction_hash}
                  className="flex flex-col gap-2 border-b pb-3 last:border-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex flex-col gap-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm">
                        {formatEth(action.event.amount)} Sepolia ETH
                      </span>
                      <AttestationBadge
                        status={action.verified ? "verified" : "failed"}
                        digest={action.event.quote_digest}
                        txHash={action.event.transaction_hash}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {formatTimestamp(action.event.timestamp)} · digest{" "}
                      <span className="font-mono">
                        {shortHex(action.event.quote_digest)}
                      </span>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="mt-4 text-right">
            <Link href="/activity" className="text-sm text-primary hover:underline">
              View all activity →
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
