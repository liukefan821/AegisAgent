"use client";

import { type ReactNode, useMemo, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { useAccount } from "wagmi";
import { AttestationBadge } from "@/components/attestation-badge";
import { ErrorCard } from "@/components/error-card";
import { ActionRowSkeleton } from "@/components/loading-states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useVaultActivity } from "@/hooks/use-vault-activity";
import { IS_MOCK } from "@/lib/mocks";
import type { VaultActivityItem } from "@/lib/types";
import { formatEth, formatTimestamp, shortHex } from "@/lib/utils/format";

type TimeFilter = "all" | "today" | "week" | "custom";
type ActivityKindFilter = "action" | "deposit" | "withdraw";
type AmountFilter = "all" | "in" | "out";

interface ActivityFilters {
  time: TimeFilter;
  kinds: ActivityKindFilter[];
  amount: AmountFilter;
  from: string;
  to: string;
}

const DEFAULT_FILTERS: ActivityFilters = {
  time: "all",
  kinds: [],
  amount: "all",
  from: "",
  to: "",
};

const TYPE_OPTIONS: Array<{ value: ActivityKindFilter; label: string }> = [
  { value: "action", label: "Agent" },
  { value: "deposit", label: "Deposit" },
  { value: "withdraw", label: "Withdraw" },
];

export default function ActivityPage() {
  const { address, isConnected } = useAccount();
  const activity = useVaultActivity(address);
  const [filters, setFilters] = useState<ActivityFilters>(DEFAULT_FILTERS);
  const items = useMemo(() => activity.data ?? [], [activity.data]);
  const filteredItems = useMemo(
    () => items.filter((item) => matchesActivityFilters(item, filters)),
    [items, filters]
  );
  const activeFilterCount = countActiveFilters(filters);

  if (!isConnected) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-32 text-center">
        <h2 className="text-xl font-medium">Connect Wallet</h2>
        <p className="text-sm text-muted-foreground">
          Connect a wallet to view agent activity history.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-medium">Activity</h1>
          <p className="text-sm text-muted-foreground">
            On-chain agent operations with attestation status.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {IS_MOCK ? <Badge variant="outline">mock</Badge> : null}
          <ActivityFilterDialog
            filters={filters}
            activeFilterCount={activeFilterCount}
            onApply={setFilters}
          />
        </div>
      </div>

      <Card>
        <CardContent>
          {activity.error ? (
            <ErrorCard
              variant="inline"
              message={activity.error.message}
              onRetry={activity.refetch}
            />
          ) : activity.isLoading ? (
            <div className="space-y-3">
              <ActionRowSkeleton />
              <ActionRowSkeleton />
              <ActionRowSkeleton />
            </div>
          ) : items.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-sm text-muted-foreground">
                No activity yet. Deposits, withdrawals, and agent operations
                will appear here once they are confirmed on-chain.
              </p>
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-sm text-muted-foreground">
                No activity matches the current filters.
              </p>
            </div>
          ) : (
            <>
              <div className="divide-y md:hidden">
                {filteredItems.map((item) => (
                  <ActivityMobileRow key={item.transaction_hash} item={item} />
                ))}
              </div>

              <div className="hidden overflow-x-auto md:block">
                <table className="min-w-[760px] w-full text-sm">
                  <thead>
                    <tr className="border-b text-xs uppercase text-muted-foreground">
                      <th className="py-2 text-left font-medium">Time</th>
                      <th className="py-2 text-left font-medium">Type</th>
                      <th className="py-2 text-left font-medium">Amount</th>
                      <th className="py-2 text-left font-medium">
                        Agent (MR_ENCLAVE)
                      </th>
                      <th className="py-2 text-left font-medium">Quote</th>
                      <th className="py-2 text-left font-medium">Status</th>
                      <th className="py-2 text-right font-medium">Tx</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map((item) => (
                      <ActivityTableRow
                        key={item.transaction_hash}
                        item={item}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function countActiveFilters(filters: ActivityFilters): number {
  let count = 0;
  if (filters.time !== "all") {
    count += 1;
  }
  if (filters.kinds.length > 0) {
    count += 1;
  }
  if (filters.amount !== "all") {
    count += 1;
  }
  return count;
}

function amountDirection(item: VaultActivityItem): "+" | "-" {
  if (item.kind === "deposit") {
    return "+";
  }
  if (item.kind === "withdraw") {
    return "-";
  }
  return item.amount === 0n ? "+" : "-";
}

function startOfTodaySeconds(): bigint {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  return BigInt(Math.floor(date.getTime() / 1000));
}

function startOfWeekSeconds(): bigint {
  const date = new Date();
  const day = date.getDay();
  const daysSinceMonday = day === 0 ? 6 : day - 1;
  date.setDate(date.getDate() - daysSinceMonday);
  date.setHours(0, 0, 0, 0);
  return BigInt(Math.floor(date.getTime() / 1000));
}

function dateInputToSeconds(value: string, endOfDay = false): bigint | null {
  if (!value) {
    return null;
  }
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  if (endOfDay) {
    date.setHours(23, 59, 59, 999);
  }
  return BigInt(Math.floor(date.getTime() / 1000));
}

function matchesActivityFilters(
  item: VaultActivityItem,
  filters: ActivityFilters
): boolean {
  if (filters.kinds.length > 0 && !filters.kinds.includes(item.kind)) {
    return false;
  }

  if (filters.amount === "in" && amountDirection(item) !== "+") {
    return false;
  }
  if (filters.amount === "out" && amountDirection(item) !== "-") {
    return false;
  }

  if (filters.time === "today" && item.timestamp < startOfTodaySeconds()) {
    return false;
  }
  if (filters.time === "week" && item.timestamp < startOfWeekSeconds()) {
    return false;
  }
  if (filters.time === "custom") {
    const from = dateInputToSeconds(filters.from);
    const to = dateInputToSeconds(filters.to, true);
    if (from !== null && item.timestamp < from) {
      return false;
    }
    if (to !== null && item.timestamp > to) {
      return false;
    }
  }

  return true;
}

function ActivityFilterDialog({
  filters,
  activeFilterCount,
  onApply,
}: {
  filters: ActivityFilters;
  activeFilterCount: number;
  onApply: (filters: ActivityFilters) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(filters);

  const updateDraft = (next: Partial<ActivityFilters>) => {
    setDraft((current) => ({ ...current, ...next }));
  };
  const toggleKind = (kind: ActivityKindFilter) => {
    setDraft((current) => ({
      ...current,
      kinds: current.kinds.includes(kind)
        ? current.kinds.filter((item) => item !== kind)
        : [...current.kinds, kind],
    }));
  };
  const resetFilters = () => {
    setDraft(DEFAULT_FILTERS);
    onApply(DEFAULT_FILTERS);
    setOpen(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (nextOpen) {
          setDraft(filters);
        }
      }}
    >
      <DialogTrigger
        className="inline-flex h-7 shrink-0 items-center justify-center gap-1 rounded-lg border border-border bg-background px-2 text-xs font-medium transition-all hover:bg-muted hover:text-foreground"
        title="Filter activity"
      >
        <SlidersHorizontal className="size-3.5" />
        Filter{activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Filter Activity</DialogTitle>
        </DialogHeader>

        <div className="grid gap-5">
          <FilterSection title="Time">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <FilterButton
                active={draft.time === "all"}
                onClick={() => updateDraft({ time: "all" })}
              >
                All time
              </FilterButton>
              <FilterButton
                active={draft.time === "today"}
                onClick={() => updateDraft({ time: "today" })}
              >
                Today
              </FilterButton>
              <FilterButton
                active={draft.time === "week"}
                onClick={() => updateDraft({ time: "week" })}
              >
                This week
              </FilterButton>
              <FilterButton
                active={draft.time === "custom"}
                onClick={() => updateDraft({ time: "custom" })}
              >
                Custom
              </FilterButton>
            </div>
            {draft.time === "custom" ? (
              <div className="grid gap-2 sm:grid-cols-2">
                <label className="grid gap-1 text-xs text-muted-foreground">
                  From
                  <Input
                    type="date"
                    value={draft.from}
                    onChange={(event) =>
                      updateDraft({ from: event.target.value })
                    }
                  />
                </label>
                <label className="grid gap-1 text-xs text-muted-foreground">
                  To
                  <Input
                    type="date"
                    value={draft.to}
                    onChange={(event) => updateDraft({ to: event.target.value })}
                  />
                </label>
              </div>
            ) : null}
          </FilterSection>

          <FilterSection title="Type">
            <div className="grid grid-cols-3 gap-2">
              {TYPE_OPTIONS.map((option) => (
                <FilterButton
                  key={option.value}
                  active={draft.kinds.includes(option.value)}
                  onClick={() => toggleKind(option.value)}
                >
                  {option.label}
                </FilterButton>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Leave all unselected to show every type.
            </p>
          </FilterSection>

          <FilterSection title="Amount">
            <div className="grid grid-cols-3 gap-2">
              <FilterButton
                active={draft.amount === "all"}
                onClick={() => updateDraft({ amount: "all" })}
              >
                All
              </FilterButton>
              <FilterButton
                active={draft.amount === "in"}
                onClick={() => updateDraft({ amount: "in" })}
              >
                Incoming (+)
              </FilterButton>
              <FilterButton
                active={draft.amount === "out"}
                onClick={() => updateDraft({ amount: "out" })}
              >
                Outgoing (-)
              </FilterButton>
            </div>
          </FilterSection>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={resetFilters}>
            Reset
          </Button>
          <DialogClose
            render={
              <Button
                onClick={() => {
                  onApply(draft);
                }}
              />
            }
          >
            Apply
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function FilterSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="grid gap-2">
      <h3 className="text-xs font-medium uppercase text-muted-foreground">
        {title}
      </h3>
      {children}
    </section>
  );
}

function FilterButton({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <Button
      type="button"
      variant={active ? "secondary" : "outline"}
      size="sm"
      className="justify-center"
      onClick={onClick}
    >
      {children}
    </Button>
  );
}

function activityLabel(kind: VaultActivityItem["kind"]): string {
  if (kind === "deposit") {
    return "Deposit";
  }
  if (kind === "withdraw") {
    return "Withdraw";
  }
  return "Agent Action";
}

function activityAmount(item: VaultActivityItem): {
  label: string;
  className: string;
} {
  if (item.kind === "deposit") {
    return {
      label: `+${formatEth(item.amount)} Sepolia ETH`,
      className: "text-emerald-700 dark:text-emerald-300",
    };
  }

  if (item.kind === "withdraw") {
    return {
      label: `-${formatEth(item.amount)} Sepolia ETH`,
      className: "text-red-700 dark:text-red-300",
    };
  }

  if (item.amount === 0n) {
    return {
      label: `+${formatEth(item.amount)} Sepolia ETH`,
      className: "text-emerald-700 dark:text-emerald-300",
    };
  }

  return {
    label: `-${formatEth(item.amount)} Sepolia ETH`,
    className: "text-red-700 dark:text-red-300",
  };
}

function ActivityTypeBadge({ kind }: { kind: VaultActivityItem["kind"] }) {
  const className =
    kind === "action"
      ? "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-200"
      : "";

  return (
    <Badge
      variant={kind === "action" ? "secondary" : "outline"}
      className={className}
    >
      {activityLabel(kind)}
    </Badge>
  );
}

function ActivityMobileRow({ item }: { item: VaultActivityItem }) {
  const amount = activityAmount(item);

  return (
    <div className="space-y-3 py-4 first:pt-0 last:pb-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <ActivityTypeBadge kind={item.kind} />
          </div>
          <div className={`mt-2 font-mono text-sm ${amount.className}`}>
            {amount.label}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {formatTimestamp(item.timestamp)}
          </div>
        </div>
        {item.kind === "action" ? (
          <AttestationBadge
            status={item.verified ? "verified" : "failed"}
            digest={item.quote_digest}
            txHash={item.transaction_hash}
          />
        ) : null}
      </div>

      <div className="grid gap-2 text-xs">
        {item.kind === "action" ? (
          <>
            <KeyValue label="MR_ENCLAVE" value={shortHex(item.mr_enclave, 10, 8)} />
            <KeyValue label="Quote" value={shortHex(item.quote_digest, 10, 8)} />
          </>
        ) : (
          <KeyValue label="Status" value="Confirmed" />
        )}
        <div className="flex items-center justify-between gap-3">
          <span className="shrink-0 text-muted-foreground">Tx</span>
          <a
            href={`https://sepolia.etherscan.io/tx/${item.transaction_hash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="min-w-0 truncate font-mono text-primary hover:underline"
          >
            {shortHex(item.transaction_hash, 8, 6)} ↗
          </a>
        </div>
      </div>
    </div>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="min-w-0 truncate font-mono">{value}</span>
    </div>
  );
}

function ActivityTableRow({ item }: { item: VaultActivityItem }) {
  const amount = activityAmount(item);

  return (
    <tr className="border-b last:border-0">
      <td className="py-3 text-xs text-muted-foreground">
        {formatTimestamp(item.timestamp)}
      </td>
      <td className="py-3">
        <ActivityTypeBadge kind={item.kind} />
      </td>
      <td className={`py-3 font-mono ${amount.className}`}>
        {amount.label}
      </td>
      <td className="py-3 font-mono text-xs">
        {item.kind === "action" ? shortHex(item.mr_enclave, 8, 6) : "-"}
      </td>
      <td className="py-3 font-mono text-xs">
        {item.kind === "action" ? shortHex(item.quote_digest, 8, 6) : "-"}
      </td>
      <td className="py-3">
        {item.kind === "action" ? (
          <AttestationBadge
            status={item.verified ? "verified" : "failed"}
            digest={item.quote_digest}
            txHash={item.transaction_hash}
          />
        ) : (
          <Badge variant="outline">confirmed</Badge>
        )}
      </td>
      <td className="py-3 text-right">
        <a
          href={`https://sepolia.etherscan.io/tx/${item.transaction_hash}`}
          target="_blank"
          rel="noopener noreferrer"
          className="font-mono text-xs text-primary hover:underline"
        >
          {shortHex(item.transaction_hash, 6, 4)} ↗
        </a>
      </td>
    </tr>
  );
}
