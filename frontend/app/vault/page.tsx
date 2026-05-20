"use client";

import { useEffect, useRef, useState } from "react";
import { useAccount } from "wagmi";
import { ErrorCard } from "@/components/error-card";
import { BalanceCardSkeleton } from "@/components/loading-states";
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
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useUserNonce, useVaultBalance } from "@/hooks/use-vault";
import {
  useDeposit,
  useExecuteAction,
  useWithdraw,
} from "@/hooks/use-vault-writes";
import { vaultErrorMessage } from "@/lib/error-messages";
import type { AgentDecision } from "@/lib/types";
import { formatEth, shortHex } from "@/lib/utils/format";

const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8080";
type DecisionMode = "ai" | "demo-hold" | "demo-transfer";

const DECISION_LABEL: Record<DecisionMode, string> = {
  ai: "Run Agent Decision",
  "demo-hold": "Demo HOLD",
  "demo-transfer": "Demo TRANSFER",
};

export default function VaultPage() {
  const { address, isConnected } = useAccount();
  const balance = useVaultBalance(address);
  const nonce = useUserNonce(address);
  const deposit = useDeposit();
  const withdraw = useWithdraw();
  const executeAction = useExecuteAction();

  const [depositAmount, setDepositAmount] = useState("");
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const [lastDepositAmount, setLastDepositAmount] = useState("");
  const [lastWithdrawAmount, setLastWithdrawAmount] = useState("");
  const [decision, setDecision] = useState<AgentDecision | null>(null);
  const [isRequestingDecision, setIsRequestingDecision] = useState(false);
  const [activeDecisionMode, setActiveDecisionMode] =
    useState<DecisionMode>("ai");
  const [lastDecisionMode, setLastDecisionMode] = useState<DecisionMode>("ai");
  const [decisionError, setDecisionError] = useState<Error | null>(null);
  const balanceError = balance.error ?? nonce.error;
  const refetchVaultReads = useRef({
    balance: balance.refetch,
    nonce: nonce.refetch,
  });
  useEffect(() => {
    refetchVaultReads.current = {
      balance: balance.refetch,
      nonce: nonce.refetch,
    };
  });
  const retryBalance = () => {
    balance.refetch?.();
    nonce.refetch?.();
  };
  const submitDeposit = () => {
    const amount = depositAmount;
    if (deposit.submit(amount)) {
      setLastDepositAmount(amount);
      setDepositAmount("");
    }
  };
  const submitWithdraw = () => {
    const amount = withdrawAmount;
    if (withdraw.submit(amount)) {
      setLastWithdrawAmount(amount);
      setWithdrawAmount("");
    }
  };
  const runAgentDecision = async (mode: DecisionMode = "ai") => {
    setDecisionError(null);
    executeAction.reset();

    if (!address || balance.data === undefined || nonce.data === undefined) {
      setDecisionError(new Error("Vault balance and nonce must be loaded first."));
      return;
    }

    setLastDecisionMode(mode);
    setActiveDecisionMode(mode);
    setIsRequestingDecision(true);
    try {
      const body: Record<string, string | number> = {
        user: address,
        balance_wei: balance.data.toString(),
        nonce: nonce.data.toString(),
      };
      if (mode === "demo-hold") {
        body.demo_action = "HOLD";
      }
      if (mode === "demo-transfer") {
        body.demo_action = "TRANSFER";
        body.demo_transfer_bps = 2500;
      }

      const res = await fetch(`${AGENT_URL}/decisions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        throw new Error(`Decision request failed: ${res.status}`);
      }

      const nextDecision = (await res.json()) as AgentDecision;
      setDecision(nextDecision);

      if (!executeAction.submit(nextDecision)) {
        setDecisionError(new Error("Decision could not be submitted."));
      }
    } catch (error) {
      setDecisionError(
        error instanceof Error ? error : new Error("Decision request failed.")
      );
    } finally {
      setIsRequestingDecision(false);
    }
  };

  useEffect(() => {
    if (!deposit.isSuccess) {
      return;
    }

    refetchVaultReads.current.balance?.();
    refetchVaultReads.current.nonce?.();
  }, [deposit.isSuccess, deposit.txHash]);

  useEffect(() => {
    if (!withdraw.isSuccess) {
      return;
    }

    refetchVaultReads.current.balance?.();
    refetchVaultReads.current.nonce?.();
  }, [withdraw.isSuccess, withdraw.txHash]);

  useEffect(() => {
    if (!executeAction.isSuccess) {
      return;
    }

    refetchVaultReads.current.balance?.();
    refetchVaultReads.current.nonce?.();
  }, [executeAction.isSuccess, executeAction.txHash]);

  if (!isConnected) {
    return <ConnectGate />;
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-medium">Vault</h1>
        <p className="text-sm text-muted-foreground">
          Manage funds and authorized agents.
        </p>
      </div>

      {balanceError ? (
        <ErrorCard
          message={vaultErrorMessage(balanceError)}
          onRetry={retryBalance}
        />
      ) : balance.isLoading || nonce.isLoading ? (
        <BalanceCardSkeleton />
      ) : (
        <Card>
          <CardHeader>
            <CardDescription>Current Balance</CardDescription>
            <CardTitle className="break-words font-mono text-2xl sm:text-3xl">
              {balance.data !== undefined
                ? `${formatEth(balance.data)} Sepolia ETH`
                : "-"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs text-muted-foreground">
            <div>
              Address:{" "}
              <span className="font-mono">{shortHex(address ?? "", 8, 6)}</span>
            </div>
            <div>Nonce: {nonce.data?.toString() ?? "-"}</div>
            {balance.source === "mock" ? (
              <div>
                Source:{" "}
                <Badge variant="outline" className="text-xs">
                  mock
                </Badge>
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="deposit">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="deposit">Deposit</TabsTrigger>
          <TabsTrigger value="withdraw">Withdraw</TabsTrigger>
        </TabsList>
        <TabsContent value="deposit">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Deposit Sepolia ETH</CardTitle>
              <CardDescription>
                Funds become available for authorized agents.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input
                type="number"
                placeholder="0.0"
                value={depositAmount}
                onChange={(event) => setDepositAmount(event.target.value)}
                step="0.001"
                min="0"
              />
              <Button
                className="w-full"
                disabled={
                  !depositAmount || deposit.isPending || deposit.isConfirming
                }
                onClick={submitDeposit}
              >
                {writeButtonLabel(
                  deposit,
                  `Deposit ${depositAmount || "0"} Sepolia ETH`
                )}
              </Button>
              <WriteStatus
                write={deposit}
                successMessage={`Successfully deposited ${lastDepositAmount} Sepolia ETH.`}
              />
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="withdraw">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Withdraw Sepolia ETH</CardTitle>
              <CardDescription>
                Withdraw your unencumbered balance.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input
                type="number"
                placeholder="0.0"
                value={withdrawAmount}
                onChange={(event) => setWithdrawAmount(event.target.value)}
                step="0.001"
                min="0"
              />
              <Button
                className="w-full"
                variant="outline"
                disabled={
                  !withdrawAmount ||
                  withdraw.isPending ||
                  withdraw.isConfirming
                }
                onClick={submitWithdraw}
              >
                {writeButtonLabel(
                  withdraw,
                  `Withdraw ${withdrawAmount || "0"} Sepolia ETH`
                )}
              </Button>
              <WriteStatus
                write={withdraw}
                successMessage={`Successfully withdrew ${lastWithdrawAmount} Sepolia ETH.`}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Run Agent Decision</CardTitle>
          <CardDescription>
            Ask the TEE agent for an attested decision, then submit it to
            AegisVault.executeAction.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button
            className="w-full"
            variant="outline"
            disabled={
              isRequestingDecision ||
              executeAction.isPending ||
              executeAction.isConfirming ||
              balance.data === undefined ||
              nonce.data === undefined
            }
            onClick={() => {
              void runAgentDecision();
            }}
          >
            {isRequestingDecision
              ? `Requesting ${DECISION_LABEL[activeDecisionMode]}...`
              : writeButtonLabel(executeAction, "Run Agent Decision")}
          </Button>
          <div className="grid gap-2 sm:grid-cols-2">
            <Button
              className="w-full"
              variant="secondary"
              disabled={
                isRequestingDecision ||
                executeAction.isPending ||
                executeAction.isConfirming ||
                balance.data === undefined ||
                nonce.data === undefined
              }
              onClick={() => {
                void runAgentDecision("demo-hold");
              }}
            >
              {writeButtonLabel(executeAction, "Demo HOLD")}
            </Button>
            <Button
              className="w-full"
              variant="secondary"
              disabled={
                isRequestingDecision ||
                executeAction.isPending ||
                executeAction.isConfirming ||
                balance.data === undefined ||
                nonce.data === undefined
              }
              onClick={() => {
                void runAgentDecision("demo-transfer");
              }}
            >
              {writeButtonLabel(executeAction, "Demo TRANSFER")}
            </Button>
          </div>

          {decisionError ? (
            <ErrorCard
              variant="inline"
              message={decisionError.message}
              onRetry={() => {
                void runAgentDecision(lastDecisionMode);
              }}
            />
          ) : null}

          {decision ? (
            <div className="rounded-md border bg-muted/30 p-3 text-sm">
              <div className="font-medium">{decision.action}</div>
              <div className="mt-1 text-muted-foreground">
                {decision.reasoning}
              </div>
              <div className="mt-2 grid gap-1 font-mono text-xs text-muted-foreground">
                <div>
                  Amount: {formatEth(BigInt(decision.amount_wei))} Sepolia ETH
                </div>
                <div>Action: {shortHex(decision.action_hash, 8, 6)}</div>
                <div>Quote: {shortHex(decision.quote_digest, 8, 6)}</div>
              </div>
            </div>
          ) : null}

          <WriteStatus
            write={executeAction}
            successMessage="Agent decision executed on-chain."
            successDetail={
              decision ? (
                <span>
                  Quote digest:{" "}
                  <span className="break-all font-mono text-xs">
                    {decision.quote_digest}
                  </span>
                </span>
              ) : undefined
            }
          />
        </CardContent>
      </Card>
    </div>
  );
}

function ConnectGate() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-32 text-center">
      <h2 className="text-xl font-medium">Connect Wallet</h2>
      <p className="text-sm text-muted-foreground">
        Use the Connect button in the navbar to access your vault.
      </p>
    </div>
  );
}
