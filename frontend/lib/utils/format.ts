import type { Hex } from "@/lib/types";

export function ensureHex(s: string): Hex {
  const normalized = s.startsWith("0x") ? s : `0x${s}`;
  if (!/^0x[0-9a-fA-F]*$/.test(normalized)) {
    throw new Error(`Invalid hex string: ${s}`);
  }
  return normalized as Hex;
}

export function shortHex(hex: string, head: number = 6, tail: number = 4): string {
  if (hex.length <= head + tail + 2) return hex;
  return `${hex.slice(0, head + 2)}...${hex.slice(-tail)}`;
}

export function formatTimestamp(unixSeconds: number | bigint): string {
  const ms = Number(unixSeconds) * 1000;
  return new Date(ms).toLocaleString();
}

export function formatEth(wei: bigint, decimals: number = 4): string {
  const eth = Number(wei) / 1e18;
  return eth.toFixed(decimals);
}
