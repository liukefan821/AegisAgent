"use client";

import type { WriteHookResult } from "@/lib/types";
import { shortHex } from "@/lib/utils/format";
import type { ReactNode } from "react";

type WriteStatusValue = Pick<
  WriteHookResult,
  "isError" | "isSuccess" | "txHash" | "error" | "reset"
>;

type WriteButtonValue = Pick<WriteHookResult, "isPending" | "isConfirming">;

export function writeButtonLabel(
  write: WriteButtonValue,
  idleLabel: string
): string {
  if (write.isPending) {
    return "Confirm in wallet...";
  }

  if (write.isConfirming) {
    return "Confirming...";
  }

  return idleLabel;
}

export function WriteStatus({
  write,
  successMessage,
  successDetail,
  showDismiss = true,
}: {
  write: WriteStatusValue;
  successMessage?: ReactNode;
  successDetail?: ReactNode;
  showDismiss?: boolean;
}) {
  if (write.isError && write.error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-950 dark:border-red-900/70 dark:bg-red-950/40 dark:text-red-100">
        <div>{write.error.message}</div>
        {showDismiss ? (
          <button
            type="button"
            className="mt-2 text-xs font-medium underline"
            onClick={write.reset}
          >
            Dismiss
          </button>
        ) : null}
      </div>
    );
  }

  if (write.isSuccess && write.txHash) {
    return (
      <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-950 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-100">
        <div>{successMessage ?? "Transaction confirmed."}</div>
        {successDetail ? <div className="mt-1">{successDetail}</div> : null}
        {successMessage ? <div className="mt-1">Transaction confirmed.</div> : null}
        <div className="mt-1 font-mono text-xs">
          Tx: {shortHex(write.txHash)}
        </div>
        {showDismiss ? (
          <button
            type="button"
            className="mt-2 text-xs font-medium underline"
            onClick={write.reset}
          >
            Dismiss
          </button>
        ) : null}
      </div>
    );
  }

  return null;
}
