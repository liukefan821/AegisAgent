"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

const STORAGE_KEY = "aegis-theme";
type ThemePreference = "system" | "light" | "dark";

function getStoredPreference(): ThemePreference {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "system" || stored === "light" || stored === "dark") {
    return stored;
  }

  return "system";
}

function systemPrefersDark() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyTheme(preference: ThemePreference) {
  const shouldUseDark =
    preference === "dark" || (preference === "system" && systemPrefersDark());

  document.documentElement.classList.toggle("dark", shouldUseDark);
}

function nextPreference(preference: ThemePreference): ThemePreference {
  if (preference === "system") {
    return "light";
  }

  if (preference === "light") {
    return "dark";
  }

  return "system";
}

export function ThemeToggle() {
  const [mounted, setMounted] = useState(false);
  const [preference, setPreference] = useState<ThemePreference>("system");

  useEffect(() => {
    const initialPreference = getStoredPreference();
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleSystemThemeChange = () => {
      if (getStoredPreference() === "system") {
        applyTheme("system");
      }
    };

    applyTheme(initialPreference);
    mediaQuery.addEventListener("change", handleSystemThemeChange);

    const timer = window.setTimeout(() => {
      setPreference(initialPreference);
      setMounted(true);
    }, 0);

    return () => {
      window.clearTimeout(timer);
      mediaQuery.removeEventListener("change", handleSystemThemeChange);
    };
  }, []);

  useEffect(() => {
    if (!mounted) {
      return;
    }

    applyTheme(preference);
    window.localStorage.setItem(STORAGE_KEY, preference);
  }, [mounted, preference]);

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
        setPreference((current) => nextPreference(current));
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
