"use client";

import { Badge } from "@/components/ui/badge";

export type AttestationStatus = "verified" | "pending" | "failed" | "unknown";

interface AttestationBadgeProps {
  status: AttestationStatus;
  digest?: string;
}

const STATUS_CONFIG = {
  verified: {
    label: "✓ Verified",
    className:
      "bg-emerald-100 text-emerald-900 hover:bg-emerald-100 dark:bg-emerald-950 dark:text-emerald-200",
  },
  pending: {
    label: "⋯ Pending",
    className:
      "bg-amber-100 text-amber-900 hover:bg-amber-100 dark:bg-amber-950 dark:text-amber-200",
  },
  failed: {
    label: "✕ Failed",
    className:
      "bg-red-100 text-red-900 hover:bg-red-100 dark:bg-red-950 dark:text-red-200",
  },
  unknown: {
    label: "? Unknown",
    className:
      "bg-zinc-100 text-zinc-900 hover:bg-zinc-100 dark:bg-zinc-800 dark:text-zinc-200",
  },
} satisfies Record<AttestationStatus, { label: string; className: string }>;

export function AttestationBadge({ status, digest }: AttestationBadgeProps) {
  const config = STATUS_CONFIG[status];

  return (
    <Badge
      variant="secondary"
      className={`font-mono text-xs ${config.className}`}
      title={digest ? `Quote digest: ${digest}` : "No digest available"}
    >
      {config.label}
    </Badge>
  );
}
