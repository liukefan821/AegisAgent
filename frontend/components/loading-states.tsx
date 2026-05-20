"use client";

import {
  Card,
  CardContent,
  CardHeader,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function LoadingStatus({ label }: { label: string }) {
  return (
    <span className="sr-only" role="status" aria-live="polite">
      {label}
    </span>
  );
}

export function StatCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={className}>
      <LoadingStatus label="Loading stat card" />
      <CardHeader className="pb-3">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="mt-2 h-8 w-24" />
      </CardHeader>
    </Card>
  );
}

export function BalanceCardSkeleton() {
  return (
    <Card>
      <LoadingStatus label="Loading balance" />
      <CardHeader>
        <Skeleton className="h-4 w-28" />
        <Skeleton className="mt-2 h-10 w-48" />
      </CardHeader>
      <CardContent className="space-y-2">
        <Skeleton className="h-3 w-44" />
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-5 w-20" />
      </CardContent>
    </Card>
  );
}

export function AgentRowSkeleton() {
  return (
    <div className="flex items-center justify-between gap-4 border-b pb-3 last:border-0 last:pb-0">
      <LoadingStatus label="Loading agent" />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <Skeleton className="h-4 w-44 max-w-full" />
        <Skeleton className="h-3 w-20" />
      </div>
      <Skeleton className="h-7 w-20" />
    </div>
  );
}

export function ActionRowSkeleton() {
  return (
    <div className="flex items-center justify-between gap-4 border-b pb-3 last:border-0 last:pb-0">
      <LoadingStatus label="Loading activity" />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-4 w-28" />
        </div>
        <Skeleton className="h-3 w-48 max-w-full" />
      </div>
      <Skeleton className="h-5 w-20" />
    </div>
  );
}
