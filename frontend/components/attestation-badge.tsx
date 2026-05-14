"use client";

import { AttestationModal } from "@/components/attestation-modal";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogTrigger } from "@/components/ui/dialog";
import { badgeVariants } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Bytes32, Hex } from "@/lib/types";

export type AttestationStatus = "verified" | "pending" | "failed" | "unknown";

interface AttestationBadgeProps {
  status: AttestationStatus;
  digest?: Bytes32;
  txHash?: Hex;
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

export function AttestationBadge({ status, digest, txHash }: AttestationBadgeProps) {
  const config = STATUS_CONFIG[status];
  const className = cn(
    badgeVariants({ variant: "secondary" }),
    "font-mono text-xs",
    digest && "cursor-pointer hover:ring-2 hover:ring-ring/40",
    config.className
  );

  if (!digest) {
    return (
      <Badge
        variant="secondary"
        className={className}
        title="No digest available"
      >
        {config.label}
      </Badge>
    );
  }

  return (
    <Dialog>
      <DialogTrigger
        className={className}
        title={`Quote digest: ${digest}`}
      >
        {config.label}
      </DialogTrigger>
      <AttestationModal digest={digest} status={status} txHash={txHash} />
    </Dialog>
  );
}
