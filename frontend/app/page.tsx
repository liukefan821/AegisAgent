"use client";

import type { ReactNode } from "react";
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
import { useVaultActivity } from "@/hooks/use-vault-activity";
import {
  agentHealthErrorMessage,
  registryErrorMessage,
  vaultErrorMessage,
} from "@/lib/error-messages";
import type { VaultActivityItem } from "@/lib/types";
import { cn } from "@/lib/utils";
import { formatEth, formatTimestamp, shortHex } from "@/lib/utils/format";

export default function DashboardPage() {
  const { address, isConnected } = useAccount();
  const balance = useVaultBalance(address);
  const health = useAgentHealth();
  const agents = useRegisteredAgents();
  const activity = useVaultActivity(address);

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

  const recentActivity = (activity.data ?? []).slice(0, 3);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-medium">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          {balance.source === "mock" &&
            "⚠ Showing mock data — set NEXT_PUBLIC_USE_MOCK=false after contract deployment."}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        {balance.error ? (
          <ErrorCard
            className="col-span-2 md:col-span-1"
            message={vaultErrorMessage(balance.error)}
            onRetry={balance.refetch}
          />
        ) : balance.isLoading ? (
          <StatCardSkeleton className="col-span-2 md:col-span-1" />
        ) : (
          <DashboardCardLink
            href="/vault"
            label="Open vault page"
            className="col-span-2 md:col-span-1"
          >
            <CardHeader className="pb-3">
              <CardDescription>Vault Balance</CardDescription>
              <CardTitle className="font-mono text-2xl">
                {balance.data !== undefined
                  ? `${formatEth(balance.data)} Sepolia ETH`
                  : "-"}
              </CardTitle>
            </CardHeader>
          </DashboardCardLink>
        )}

        {health.error ? (
          <ErrorCard
            className="col-span-1"
            message={agentHealthErrorMessage(health.error)}
            onRetry={health.refetch}
          />
        ) : health.isLoading ? (
          <StatCardSkeleton />
        ) : (
          <DashboardCardLink href="/agents" label="Open agents page">
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
              <CardContent className="space-y-0.5 break-words text-[0.65rem] leading-snug text-muted-foreground sm:text-xs">
                <div>Model: {health.data.ollama_model}</div>
                <div>LLM: {health.data.ollama_status}</div>
              </CardContent>
            )}
          </DashboardCardLink>
        )}

        {agents.error ? (
          <ErrorCard
            className="col-span-1"
            message={registryErrorMessage(agents.error)}
            onRetry={agents.refetch}
          />
        ) : agents.isLoading ? (
          <StatCardSkeleton />
        ) : (
          <DashboardCardLink href="/agents" label="Open agents page">
            <CardHeader className="pb-3">
              <CardDescription>Registered Agents</CardDescription>
              <CardTitle className="font-mono text-2xl">
                {agents.data?.length ?? "-"}
              </CardTitle>
            </CardHeader>
          </DashboardCardLink>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Recent Actions</CardTitle>
          <CardDescription>
            Last 3 vault operations and agent actions
          </CardDescription>
        </CardHeader>
        <CardContent>
          {activity.error ? (
            <ErrorCard
              variant="inline"
              message={activity.error.message}
              onRetry={activity.refetch}
            />
          ) : activity.isLoading ? (
            <div className="space-y-3">
              <RecentActivitySkeleton />
              <RecentActivitySkeleton />
              <RecentActivitySkeleton />
            </div>
          ) : recentActivity.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">No actions yet.</p>
          ) : (
            <div className="space-y-3">
              {recentActivity.map((item) => (
                <RecentActivityRow key={item.transaction_hash} item={item} />
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

function DashboardCardLink({
  href,
  label,
  className,
  children,
}: {
  href: string;
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-label={label}
      className={cn("block h-full rounded-xl", className)}
    >
      <Card className="h-full transition-colors hover:bg-muted/40 focus-within:ring-2 focus-within:ring-ring/40">
        {children}
      </Card>
    </Link>
  );
}

function activityLabel(kind: VaultActivityItem["kind"]): string {
  if (kind === "deposit") {
    return "Deposit";
  }
  if (kind === "withdraw") {
    return "Withdraw";
  }
  return "Agent Action";
}

function RecentActivityRow({ item }: { item: VaultActivityItem }) {
  return (
    <div className="flex flex-col gap-2 border-b pb-3 last:border-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium">{activityLabel(item.kind)}</span>
          <span className="font-mono text-sm">
            {formatEth(item.amount)} Sepolia ETH
          </span>
          {item.kind === "action" ? (
            <AttestationBadge
              status={item.verified ? "verified" : "failed"}
              digest={item.quote_digest}
              txHash={item.transaction_hash}
            />
          ) : null}
        </div>
        <span className="text-xs text-muted-foreground">
          {formatTimestamp(item.timestamp)}
          {item.kind === "action" ? (
            <>
              {" "}
              · digest{" "}
              <span className="font-mono">{shortHex(item.quote_digest)}</span>
            </>
          ) : (
            <>
              {" "}
              · tx{" "}
              <span className="font-mono">{shortHex(item.transaction_hash)}</span>
            </>
          )}
        </span>
      </div>
    </div>
  );
}

function RecentActivitySkeleton() {
  return (
    <div className="space-y-2 border-b pb-3 last:border-0 last:pb-0">
      <div className="h-4 w-40 animate-pulse rounded-md bg-muted" />
      <div className="h-3 w-64 max-w-full animate-pulse rounded-md bg-muted" />
    </div>
  );
}
