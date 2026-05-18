"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useAccount } from "wagmi";
import { ErrorCard } from "@/components/error-card";
import { AgentRowSkeleton } from "@/components/loading-states";
import { WriteStatus, writeButtonLabel } from "@/components/write-status";
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
import { useAgentAuthorization } from "@/hooks/use-vault";
import { useAuthorizeAgent, useEmergencyStop } from "@/hooks/use-vault-writes";
import { registryErrorMessage } from "@/lib/error-messages";
import type { Address, Bytes32 } from "@/lib/types";
import { shortHex } from "@/lib/utils/format";

export default function AgentsPage() {
  const { address, isConnected } = useAccount();
  const agents = useRegisteredAgents();
  const emergencyStop = useEmergencyStop();

  if (!isConnected) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-32 text-center">
        <h2 className="text-xl font-medium">Connect Wallet</h2>
        <p className="text-sm text-muted-foreground">
          Connect a wallet to manage agent authorizations.
        </p>
      </div>
    );
  }

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-medium">Agents</h1>
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
              <div className="space-y-3">
                {agents.data.map((mrEnclave, index) => (
                  <AgentAuthorizationRow
                    key={mrEnclave}
                    user={address}
                    mrEnclave={mrEnclave}
                    agentName={`Agent ${index + 1}`}
                    authorizationResetKey={emergencyStop.txHash}
                  />
                ))}
              </div>
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
            {/* TODO: Current contract makes emergency stop permanent; revisit this copy once the team decides recovery UX. */}
            Immediately revoke <strong>all</strong> agent authorizations for
            your account. This cannot be undone. Agents you want to use later
            will need to be re-authorized.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button
            variant="destructive"
            className="w-full sm:w-auto"
            disabled={emergencyStop.isPending || emergencyStop.isConfirming}
            onClick={() => {
              if (
                confirm(
                  "Revoke ALL agent authorizations? This action is irreversible."
                )
              ) {
                emergencyStop.submit();
              }
            }}
          >
            {writeButtonLabel(emergencyStop, "Revoke All Authorizations")}
          </Button>
          <WriteStatus
            write={emergencyStop}
            successMessage="Successfully revoked all authorizations."
          />
        </CardContent>
      </Card>
    </div>
  );
}

function AgentAuthorizationRow({
  user,
  mrEnclave,
  agentName,
  authorizationResetKey,
}: {
  user?: Address;
  mrEnclave: Bytes32;
  agentName: string;
  authorizationResetKey?: string;
}) {
  const authorization = useAgentAuthorization(user, mrEnclave);
  const authorize = useAuthorizeAgent();
  const [dismissedTxHash, setDismissedTxHash] = useState<string | undefined>();
  const writeRefs = useRef({
    authorizationRefetch: authorization.refetch,
    authorizeReset: authorize.reset,
  });
  useEffect(() => {
    writeRefs.current = {
      authorizationRefetch: authorization.refetch,
      authorizeReset: authorize.reset,
    };
  });
  const isAuthorized = authorization.data === true || authorize.isSuccess;
  const isBusy = authorize.isPending || authorize.isConfirming;
  const isChecking = authorization.isLoading;
  const isStatusDismissed =
    !!dismissedTxHash && dismissedTxHash === authorize.txHash;
  const authorizeStatus = useMemo(
    () => ({
      ...authorize,
      reset: () => {
        if (authorize.isSuccess) {
          setDismissedTxHash(authorize.txHash);
          return;
        }

        authorize.reset();
      },
    }),
    [authorize]
  );

  useEffect(() => {
    if (!authorize.isSuccess) {
      return;
    }

    writeRefs.current.authorizationRefetch?.();
  }, [authorize.isSuccess, authorize.txHash]);

  useEffect(() => {
    if (!authorizationResetKey) {
      return;
    }

    writeRefs.current.authorizeReset();
    writeRefs.current.authorizationRefetch?.();
  }, [authorizationResetKey]);

  return (
    <div className="space-y-3 border-b pb-3 last:border-0 last:pb-0">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className="truncate font-mono text-sm">
              {shortHex(mrEnclave, 10, 8)}
            </span>
            {isAuthorized ? (
              <Badge
                variant="secondary"
                className="bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200"
              >
                Authorized
              </Badge>
            ) : null}
          </div>
          <span className="text-xs text-muted-foreground">MR_ENCLAVE</span>
        </div>
        <Button
          size="sm"
          variant={isAuthorized ? "secondary" : "outline"}
          className="w-full sm:w-auto"
          disabled={isAuthorized || isChecking || isBusy}
          onClick={() => authorize.submit(mrEnclave)}
        >
          {isAuthorized
            ? "Authorized"
            : isChecking
              ? "Checking..."
              : writeButtonLabel(authorize, "Authorize")}
        </Button>
      </div>
      {isStatusDismissed ? null : (
        <WriteStatus
          write={authorizeStatus}
          successMessage={`Successfully authorized ${agentName}.`}
          successDetail={
            <span>
              MR_ENCLAVE:{" "}
              <span className="break-all font-mono text-xs">{mrEnclave}</span>
            </span>
          }
        />
      )}
    </div>
  );
}
