"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorCardProps {
  message: string;
  onRetry?: () => void;
  variant?: "inline" | "card";
  className?: string;
}

export function ErrorCard({
  message,
  onRetry,
  variant = "card",
  className,
}: ErrorCardProps) {
  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn(
        "rounded-lg border border-red-200 bg-red-50 text-red-950 dark:border-red-900/70 dark:bg-red-950/40 dark:text-red-100",
        variant === "card" ? "p-4" : "p-3",
        className
      )}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" />
        <div className="min-w-0 flex-1 space-y-2">
          <p className="text-sm font-medium">{message}</p>
          {onRetry && (
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={onRetry}
            >
              <RefreshCw />
              Retry
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
