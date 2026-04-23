"use client";

import { ConnectButton } from "@rainbow-me/rainbowkit";
import { useAccount } from "wagmi";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function Home() {
  const { address, isConnected, chain } = useAccount();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-6 bg-zinc-50 dark:bg-zinc-950">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-4xl font-bold tracking-tight">AegisAgent</h1>
        <p className="text-sm text-muted-foreground max-w-md">
          TEE-verified autonomous DeFi agent. Every on-chain action is cryptographically
          attested by Intel TDX hardware.
        </p>
      </div>

      <ConnectButton />

      {isConnected && (
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              Wallet
              <Badge variant={chain?.id === 11155111 ? "default" : "destructive"}>
                {chain?.name ?? "Unknown"}
              </Badge>
            </CardTitle>
            <CardDescription className="font-mono text-xs break-all">
              {address}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {chain?.id === 11155111
                ? "✓ Connected to Sepolia. Ready for AegisAgent interactions."
                : "⚠ Please switch to Sepolia testnet."}
            </p>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
