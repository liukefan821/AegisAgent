"use client";

import { useAccount } from "wagmi";
import { ErrorCard } from "@/components/error-card";
import { AgentRowSkeleton } from "@/components/loading-states";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useRegisteredAgents } from "@/hooks/use-registry";
import { registryErrorMessage } from "@/lib/error-messages";
import { shortHex } from "@/lib/utils/format";

export default function AgentsPage() {
  const { isConnected } = useAccount();
  const agents = useRegisteredAgents();

  if (!isConnected) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-32 text-center">
        <h2 className="text-xl font-bold">Connect Wallet</h2>
        <p className="text-sm text-muted-foreground">
          Connect a wallet to manage agent authorizations.
        </p>
      </div>
    );
  }

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">Agents</h1>
        <p className="text-sm text-muted-foreground">
          Authorize TEE-verified agents to act on your vault, or revoke all
          permissions.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Registered Agents</CardTitle>
          <CardDescription>
            Agent images verified by the on-chain Registry. Source:{" "}
            <Badge variant="outline" className="ml-1">
              {agents.source}
            </Badge>
          </CardDescription>
        </CardHeader>
        <CardContent>
          {agents.error ? (
            <ErrorCard
              variant="inline"
              message={registryErrorMessage(agents.error)}
              onRetry={agents.refetch}
            />
          ) : agents.isLoading ? (
            <div className="space-y-3">
              <AgentRowSkeleton />
              <AgentRowSkeleton />
              <AgentRowSkeleton />
            </div>
          ) : !agents.data || agents.data.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">
              No agents registered.
            </p>
          ) : (
            <div className="space-y-3">
              {agents.data.map((mrEnclave) => (
                <div
                  key={mrEnclave}
                  className="flex flex-col gap-3 border-b pb-3 last:border-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
                >
                  <div className="flex min-w-0 flex-col gap-1">
                    <span className="truncate font-mono text-sm">
                      {shortHex(mrEnclave, 10, 8)}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      MR_ENCLAVE
                    </span>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="w-full sm:w-auto"
                    disabled={agents.source === "mock"}
                    onClick={() =>
                      alert("Authorize will be wired to Vault.authorizeAgent().")
                    }
                  >
                    Authorize
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-red-200 dark:border-red-900">
        <CardHeader>
          <CardTitle className="text-lg text-red-700 dark:text-red-400">
            Emergency Stop
          </CardTitle>
          <CardDescription>
            Immediately revoke <strong>all</strong> agent authorizations for
            your account. This cannot be undone. Agents you want to use later
            will need to be re-authorized.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="destructive"
            className="w-full sm:w-auto"
            disabled={agents.source === "mock"}
            onClick={() => {
              if (
                confirm(
                  "Revoke ALL agent authorizations? This action is irreversible."
                )
              ) {
                alert("Emergency stop will be wired to Vault.emergencyStop().");
              }
            }}
          >
            Revoke All Authorizations
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
