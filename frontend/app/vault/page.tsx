"use client";

import { useState } from "react";
import { useAccount } from "wagmi";
import { ErrorCard } from "@/components/error-card";
import { BalanceCardSkeleton } from "@/components/loading-states";
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
import { vaultErrorMessage } from "@/lib/error-messages";
import { formatEth, shortHex } from "@/lib/utils/format";

export default function VaultPage() {
  const { address, isConnected } = useAccount();
  const balance = useVaultBalance(address);
  const nonce = useUserNonce(address);

  const [depositAmount, setDepositAmount] = useState("");
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const balanceError = balance.error ?? nonce.error;
  const retryBalance = () => {
    balance.refetch?.();
    nonce.refetch?.();
  };

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
                disabled={balance.source === "mock" || !depositAmount}
                onClick={() =>
                  alert("Deposit will be wired to Vault.deposit().")
                }
              >
                {balance.source === "mock"
                  ? "Deposit (disabled in mock mode)"
                  : `Deposit ${depositAmount || "0"} Sepolia ETH`}
              </Button>
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
                disabled={balance.source === "mock" || !withdrawAmount}
                onClick={() =>
                  alert("Withdraw will be wired to Vault.withdraw().")
                }
              >
                {balance.source === "mock"
                  ? "Withdraw (disabled in mock mode)"
                  : `Withdraw ${withdrawAmount || "0"} Sepolia ETH`}
              </Button>
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
