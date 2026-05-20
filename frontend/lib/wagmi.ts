import { getDefaultConfig } from "@rainbow-me/rainbowkit";
import {
  coinbaseWallet,
  metaMaskWallet,
  rainbowWallet,
  safeWallet,
  walletConnectWallet,
} from "@rainbow-me/rainbowkit/wallets";
import { http } from "wagmi";
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

const sepoliaRpcUrl = process.env.NEXT_PUBLIC_SEPOLIA_RPC_URL;

export const wagmiConfig = getDefaultConfig({
  appName: "AegisAgent",
  projectId: process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID ?? "",
  chains: [sepolia],
  ...(sepoliaRpcUrl
    ? {
        transports: {
          [sepolia.id]: http(sepoliaRpcUrl),
        },
      }
    : {}),
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
