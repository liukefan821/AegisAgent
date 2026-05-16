"use client";

import { ConnectButton } from "@rainbow-me/rainbowkit";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/vault", label: "Vault" },
  { href: "/agents", label: "Agents" },
  { href: "/activity", label: "Activity" },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b bg-background">
      <div className="mx-auto grid max-w-6xl grid-cols-[1fr_auto] items-center gap-x-3 gap-y-3 px-4 py-3 sm:grid-cols-[1fr_auto_1fr] sm:px-6">
        <Link
          href="/"
          className="col-start-1 row-start-1 shrink-0 justify-self-start text-[1.625rem] font-bold leading-none tracking-tight sm:text-3xl"
        >
          AegisAgent
        </Link>

        <div className="col-start-2 row-start-1 shrink-0 justify-self-end sm:col-start-3">
          <ConnectButton showBalance={false} chainStatus="icon" />
        </div>

        <nav className="col-span-2 row-start-2 -mx-1 flex min-w-0 items-center justify-center gap-1.5 overflow-x-auto px-1 sm:col-span-1 sm:col-start-2 sm:row-start-1 sm:mx-0 sm:gap-3 sm:justify-self-center sm:px-0">
          {NAV_ITEMS.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`shrink-0 rounded-md px-3 py-1.5 text-sm transition-colors sm:px-3.5 ${
                  isActive
                    ? "bg-zinc-100 text-foreground dark:bg-zinc-800"
                    : "text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:hover:bg-zinc-900"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
