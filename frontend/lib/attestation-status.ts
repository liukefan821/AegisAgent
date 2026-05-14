export type AttestationStatus = "verified" | "pending" | "failed" | "unknown";

export const ATTESTATION_STATUS_CONFIG = {
  verified: {
    label: "✓ Verified",
    badgeClassName:
      "bg-emerald-100 text-emerald-900 hover:bg-emerald-100 dark:bg-emerald-950 dark:text-emerald-200",
    modalClassName:
      "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  },
  pending: {
    label: "⋯ Pending",
    badgeClassName:
      "bg-amber-100 text-amber-900 hover:bg-amber-100 dark:bg-amber-950 dark:text-amber-200",
    modalClassName:
      "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  },
  failed: {
    label: "✕ Failed",
    badgeClassName:
      "bg-red-100 text-red-900 hover:bg-red-100 dark:bg-red-950 dark:text-red-200",
    modalClassName: "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200",
  },
  unknown: {
    label: "? Unknown",
    badgeClassName:
      "bg-zinc-100 text-zinc-900 hover:bg-zinc-100 dark:bg-zinc-800 dark:text-zinc-200",
    modalClassName:
      "bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-200",
  },
} satisfies Record<
  AttestationStatus,
  { label: string; badgeClassName: string; modalClassName: string }
>;
