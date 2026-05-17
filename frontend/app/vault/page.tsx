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
import { useDeposit, useWithdraw } from "@/hooks/use-vault-writes";
import { vaultErrorMessage } from "@/lib/error-messages";
import { formatEth, shortHex } from "@/lib/utils/format";

export default function VaultPage() {
  const { address, isConnected } = useAccount();
  const balance = useVaultBalance(address);
  const nonce = useUserNonce(address);
  const deposit = useDeposit();
  const withdraw = useWithdraw();

  const [depositAmount, setDepositAmount] = useState("");
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const [lastDepositAmount, setLastDepositAmount] = useState("");
  const [lastWithdrawAmount, setLastWithdrawAmount] = useState("");
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

  if (!isConnected) {
    return <ConnectGate />;
  }

  return (
    <div className="flex max-w-2xl flex-col gap-6">
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
            <div>
              Source:{" "}
              <Badge variant="outline" className="text-xs">
                {balance.source}
              </Badge>
            </div>
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
