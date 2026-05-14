"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/components/theme-provider";

export function ThemeToggle() {
  const { mounted, preference, cyclePreference } = useTheme();

  const label = mounted
    ? `Color mode: ${preference}. Click to switch.`
    : "Toggle color mode";

  return (
    <Button
      type="button"
      variant="outline"
      size="icon-sm"
      className="fixed bottom-4 left-4 z-50 shadow-sm"
      aria-label={label}
      title={label}
      onClick={() => {
        if (!mounted) {
          return;
        }
        cyclePreference();
      }}
    >
      {mounted && preference === "light" ? (
        <Sun />
      ) : mounted && preference === "dark" ? (
        <Moon />
      ) : (
        <Monitor />
      )}
    </Button>
  );
}
