import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import { Navbar } from "@/components/navbar";
import { ThemeToggle } from "@/components/theme-toggle";
import { THEME_STORAGE_KEY } from "@/lib/theme";
import { Providers } from "./providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AegisAgent",
  description: "TEE-verified autonomous DeFi agent on Ethereum",
};

function ThemeScript() {
  const script = `
    (function() {
      try {
        var stored = window.localStorage.getItem("${THEME_STORAGE_KEY}");
        var preference = stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
        var systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        var shouldUseDark = preference === "dark" || (preference === "system" && systemDark);
        document.documentElement.classList.toggle("dark", shouldUseDark);
      } catch (error) {}
    })();
  `;

  return (
    <Script
      id="aegis-theme-script"
      strategy="beforeInteractive"
      dangerouslySetInnerHTML={{ __html: script }}
    />
  );
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <ThemeScript />
      <body className="flex min-h-full flex-col font-sans">
        <Providers>
          <Navbar />
          <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
            {children}
          </main>
          <ThemeToggle />
        </Providers>
      </body>
    </html>
  );
}
