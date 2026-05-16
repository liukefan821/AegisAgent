"use client";

import "@rainbow-me/rainbowkit/styles.css";
import {
  RainbowKitProvider,
  darkTheme,
  lightTheme,
} from "@rainbow-me/rainbowkit";
import { WagmiProvider } from "wagmi";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { wagmiConfig } from "@/lib/wagmi";
import { ThemeProvider, useTheme } from "@/components/theme-provider";
import { useMemo, useState } from "react";

const appFontStack =
  "var(--font-geist-sans), ui-sans-serif, system-ui, sans-serif";

function RainbowKitThemeProvider({ children }: { children: React.ReactNode }) {
  const { resolvedTheme } = useTheme();
  const rainbowKitTheme = useMemo(() => {
    const theme = resolvedTheme === "dark" ? darkTheme() : lightTheme();

    return {
      ...theme,
      fonts: {
        ...theme.fonts,
        body: appFontStack,
      },
    };
  }, [resolvedTheme]);

  return (
    <RainbowKitProvider
      theme={rainbowKitTheme}
      modalSize="compact"
      locale="en-US"
    >
      {children}
    </RainbowKitProvider>
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <ThemeProvider>
      <WagmiProvider config={wagmiConfig}>
        <QueryClientProvider client={queryClient}>
          <RainbowKitThemeProvider>{children}</RainbowKitThemeProvider>
        </QueryClientProvider>
      </WagmiProvider>
    </ThemeProvider>
  );
}
