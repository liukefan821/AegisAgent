"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  THEME_STORAGE_KEY,
  type ResolvedTheme,
  type ThemePreference,
} from "@/lib/theme";

interface ThemeContextValue {
  preference: ThemePreference;
  resolvedTheme: ResolvedTheme;
  mounted: boolean;
  setPreference: (preference: ThemePreference) => void;
  cyclePreference: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function safeGetStoredPreference(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "system" || stored === "light" || stored === "dark") {
      return stored;
    }
  } catch {
    // Storage can be unavailable in private or restricted browser contexts.
  }

  return "system";
}

function safeSetStoredPreference(preference: ThemePreference) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Keep the in-memory theme usable even when persistence is blocked.
  }
}

function systemTheme(): ResolvedTheme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference === "system") {
    return systemTheme();
  }

  return preference;
}

function applyResolvedTheme(resolvedTheme: ResolvedTheme) {
  document.documentElement.classList.toggle("dark", resolvedTheme === "dark");
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

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);
  const [preference, setPreferenceState] =
    useState<ThemePreference>("system");
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>("light");

  const setPreference = useCallback((next: ThemePreference) => {
    const nextResolvedTheme = resolveTheme(next);

    setPreferenceState(next);
    setResolvedTheme(nextResolvedTheme);
    applyResolvedTheme(nextResolvedTheme);
    safeSetStoredPreference(next);
  }, []);

  useEffect(() => {
    const storedPreference = safeGetStoredPreference();
    const initialResolvedTheme = resolveTheme(storedPreference);

    applyResolvedTheme(initialResolvedTheme);

    const timer = window.setTimeout(() => {
      setPreferenceState(storedPreference);
      setResolvedTheme(initialResolvedTheme);
      setMounted(true);
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    if (preference !== "system") {
      return;
    }

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleSystemThemeChange = () => {
      const nextResolvedTheme = systemTheme();

      setResolvedTheme(nextResolvedTheme);
      applyResolvedTheme(nextResolvedTheme);
    };

    mediaQuery.addEventListener("change", handleSystemThemeChange);

    return () => {
      mediaQuery.removeEventListener("change", handleSystemThemeChange);
    };
  }, [preference]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      preference,
      resolvedTheme,
      mounted,
      setPreference,
      cyclePreference: () => {
        setPreference(nextPreference(preference));
      },
    }),
    [mounted, preference, resolvedTheme, setPreference]
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }

  return context;
}
