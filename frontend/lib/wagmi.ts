import { getDefaultConfig } from "@rainbow-me/rainbowkit";
import {
  coinbaseWallet,
  metaMaskWallet,
  rainbowWallet,
  safeWallet,
  walletConnectWallet,
} from "@rainbow-me/rainbowkit/wallets";
import { sepolia } from "wagmi/chains";

coinbaseWallet.preference = {
  options: "all",
  telemetry: false,
};

const coinbaseOnlyWallet: typeof coinbaseWallet = (options) => {
  const wallet = coinbaseWallet(options);

  return {
    ...wallet,
    name: "Coinbase",
    shortName: "Coinbase",
  };
};

export const wagmiConfig = getDefaultConfig({
  appName: "AegisAgent",
  projectId: process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID ?? "",
  chains: [sepolia],
  ssr: true,
  wallets: [
    {
      groupName: "Popular",
      wallets: [
        safeWallet,
        rainbowWallet,
        coinbaseOnlyWallet,
        metaMaskWallet,
        walletConnectWallet,
      ],
    },
  ],
});
