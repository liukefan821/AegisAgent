"use client";

import { useState } from "react";
import { AttestationModal } from "@/components/attestation-modal";
import { Badge, badgeVariants } from "@/components/ui/badge";
import { Dialog, DialogTrigger } from "@/components/ui/dialog";
import {
  ATTESTATION_STATUS_CONFIG,
  type AttestationStatus,
} from "@/lib/attestation-status";
import { cn } from "@/lib/utils";
import type { Bytes32, Hex } from "@/lib/types";

export type { AttestationStatus } from "@/lib/attestation-status";

interface AttestationBadgeProps {
  status: AttestationStatus;
  digest?: Bytes32;
  txHash?: Hex;
}

export function AttestationBadge({ status, digest, txHash }: AttestationBadgeProps) {
  const [open, setOpen] = useState(false);
  const config = ATTESTATION_STATUS_CONFIG[status];
  const className = cn(
    badgeVariants({ variant: "secondary" }),
    "font-mono text-xs",
    digest && "cursor-pointer hover:ring-2 hover:ring-ring/40",
    config.badgeClassName
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
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        className={className}
        title={`Quote digest: ${digest}`}
      >
        {config.label}
      </DialogTrigger>
      {open && (
        <AttestationModal digest={digest} status={status} txHash={txHash} />
      )}
    </Dialog>
  );
}
