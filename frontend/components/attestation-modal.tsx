"use client";

import { Check, ChevronDown, Copy, ExternalLink } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useQuote } from "@/hooks/use-quote";
import {
  ATTESTATION_STATUS_CONFIG,
  type AttestationStatus,
} from "@/lib/attestation-status";
import type { Bytes32, Hex } from "@/lib/types";
import { cn } from "@/lib/utils";
import { formatTimestamp, shortHex } from "@/lib/utils/format";

interface AttestationModalProps {
  digest: Bytes32;
  status: AttestationStatus;
  txHash?: Hex;
}

function normalizeHex(hex: string): string {
  return hex.startsWith("0x") ? hex.slice(2) : hex;
}

function splitHexLines(hex: string, width: number = 64): string[] {
  const raw = normalizeHex(hex);
  const lines: string[] = [];
  for (let i = 0; i < raw.length; i += width) {
    lines.push(raw.slice(i, i + width));
  }
  return lines;
}

function friendlyErrorMessage(error: Error): string {
  if (error.message === "Quote not found") {
    return "Quote not found";
  }

  if (
    error.message.includes("Failed to fetch") ||
    error.message.includes("NetworkError") ||
    error.message.includes("Load failed")
  ) {
    return "TEE agent may not be running or reachable.";
  }

  return error.message;
}

function FieldRow({
  label,
  value,
  copyKey,
  copiedKey,
  onCopy,
}: {
  label: string;
  value: string;
  copyKey: string;
  copiedKey: string | null;
  onCopy: (key: string, value: string) => void;
}) {
  const copied = copiedKey === copyKey;

  return (
    <div className="grid gap-1 rounded-lg border bg-muted/20 p-3 sm:grid-cols-[9rem_minmax(0,1fr)_auto] sm:items-center">
      <dt className="text-xs font-medium uppercase text-muted-foreground">
        {label}
      </dt>
      <dd
        className="overflow-x-auto font-mono text-xs text-foreground"
        title={value}
      >
        {value.length > 42 ? shortHex(value, 10, 8) : value}
      </dd>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={`Copy ${label}`}
        title={`Copy ${label}`}
        onClick={() => onCopy(copyKey, value)}
      >
        {copied ? <Check className="text-emerald-600" /> : <Copy />}
      </Button>
    </div>
  );
}

export function AttestationModal({
  digest,
  status,
  txHash,
}: AttestationModalProps) {
  const quote = useQuote(digest);
  const quoteData = quote.data;
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const statusConfig = ATTESTATION_STATUS_CONFIG[status];

  const rawQuoteLines = useMemo(
    () => (quoteData ? splitHexLines(quoteData.quote_hex) : []),
    [quoteData]
  );
  const rawQuoteDisplay = rawQuoteLines.join("\n");
  const rawQuoteBytes = quoteData
    ? normalizeHex(quoteData.quote_hex).length / 2
    : 0;

  async function handleCopy(key: string, value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedKey(key);
      window.setTimeout(() => setCopiedKey(null), 1500);
    } catch {
      setCopiedKey(null);
    }
  }

  return (
    <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>Attestation Details</DialogTitle>
        <DialogDescription>
          Quote digest{" "}
          <span className="font-mono text-xs">{shortHex(digest, 10, 8)}</span>
        </DialogDescription>
      </DialogHeader>

      {quote.isLoading && (
        <div className="space-y-3">
          <div className="h-8 w-32 animate-pulse rounded-md bg-muted" />
          <div className="h-16 animate-pulse rounded-lg bg-muted" />
          <div className="h-16 animate-pulse rounded-lg bg-muted" />
          <div className="h-24 animate-pulse rounded-lg bg-muted" />
        </div>
      )}

      {quote.error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900 dark:border-red-900/70 dark:bg-red-950/40 dark:text-red-200">
          <div className="font-medium">Unable to load quote</div>
          <div className="mt-1">{friendlyErrorMessage(quote.error)}</div>
        </div>
      )}

      {quoteData && (
        <div className="space-y-4">
          <section className="space-y-3">
            <Badge
              variant="secondary"
              className={cn("font-mono text-sm", statusConfig.modalClassName)}
            >
              {statusConfig.label}
            </Badge>

            {(quoteData.is_mock || quote.source === "mock") && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-100">
                Mock quote — not a real TEE attestation
              </div>
            )}
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-medium">Decoded Fields</h3>
            <dl className="space-y-2">
              <FieldRow
                label="MR_ENCLAVE"
                value={quoteData.mr_enclave}
                copyKey="mr_enclave"
                copiedKey={copiedKey}
                onCopy={handleCopy}
              />
              <FieldRow
                label="Input Hash"
                value={quoteData.input_hash}
                copyKey="input_hash"
                copiedKey={copiedKey}
                onCopy={handleCopy}
              />
              <FieldRow
                label="Output Hash"
                value={quoteData.output_hash}
                copyKey="output_hash"
                copiedKey={copiedKey}
                onCopy={handleCopy}
              />
              <FieldRow
                label="Timestamp"
                value={formatTimestamp(quoteData.timestamp)}
                copyKey="timestamp"
                copiedKey={copiedKey}
                onCopy={handleCopy}
              />
            </dl>
          </section>

          <Collapsible className="rounded-lg border">
            <div className="flex items-center justify-between gap-2 border-b p-3">
              <CollapsibleTrigger className="flex min-w-0 items-center gap-2 text-sm font-medium">
                <ChevronDown className="size-4" />
                <span>Raw Quote ({rawQuoteBytes.toLocaleString()} bytes)</span>
              </CollapsibleTrigger>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Copy raw quote"
                title="Copy raw quote"
                onClick={() => handleCopy("quote_hex", quoteData.quote_hex)}
              >
                {copiedKey === "quote_hex" ? (
                  <Check className="text-emerald-600" />
                ) : (
                  <Copy />
                )}
              </Button>
            </div>
            <CollapsibleContent>
              <div className="grid max-h-60 grid-cols-[2rem_minmax(0,1fr)] overflow-y-auto p-3 font-mono text-xs leading-relaxed">
                <span className="select-none text-muted-foreground">0x</span>
                <pre className="whitespace-pre-wrap break-all">
                  {rawQuoteDisplay}
                </pre>
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>
      )}

      {txHash && (
        <DialogFooter>
          <a
            href={`https://sepolia.etherscan.io/tx/${txHash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
          >
            View on Etherscan <ExternalLink className="size-3.5" />
          </a>
        </DialogFooter>
      )}
    </DialogContent>
  );
}
