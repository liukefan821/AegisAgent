/**
 * AegisAgent — Frontend Type Definitions
 *
 * Mirrors:
 * - Python dataclasses in `tee-agent/aegis_agent/*.py`
 * - Solidity events/functions in `docs/interfaces.md`
 *
 * Naming convention: snake_case fields are kept verbatim from Python
 * to make 1:1 mapping obvious during code review and avoid serialization
 * mismatches when calling the future `/quotes/{digest}` endpoint.
 */

// ────────────────────────────────────────────────────────────────────
// Hex utility type — enforces 0x-prefixed strings at compile time
// ────────────────────────────────────────────────────────────────────
export type Hex = `0x${string}`;
export type Address = `0x${string}`;
export type Bytes32 = `0x${string}`;

// ────────────────────────────────────────────────────────────────────
// TEE agent outputs (mirror tee-agent/aegis_agent/*.py)
// ────────────────────────────────────────────────────────────────────

/**
 * Mirror of `quote_generator.AttestationQuote` (Python dataclass).
 *
 * Field names match Python exactly.
 * The `is_mock` flag IS part of the schema.
 */
export interface AttestationQuote {
  quote_hex: string;
  report_data: Hex;
  /**
   * First 32 bytes of report_data. Pre-split server-side by tee-agent's
   * `GET /quotes/{digest}` endpoint so the frontend doesn't slice bytes itself.
   */
  input_hash: Hex;
  /**
   * Last 32 bytes of report_data. Pre-split server-side by tee-agent's
   * `GET /quotes/{digest}` endpoint.
   */
  output_hash: Hex;
  mr_enclave: string;
  timestamp: number;
  is_mock: boolean;
}

/** Mirror of `ollama_client.LLMResponse`. */
export interface LLMResponse {
  model: string;
  prompt: string;
  response: string;
  input_hash: Hex;
  output_hash: Hex;
  elapsed_ms: number;
  eval_count: number;
}

/** Mirror of `chainlink_feed.PriceData`. */
export interface PriceData {
  price: string;
  round_id: bigint;
  updated_at: number;
  answered_in_round: bigint;
  feed_address: Address;
  decimals: number;
  description: string;
  raw_answer: string;
  data_hash: Hex;
}

/**
 * Confirmed schema after tee-agent PR #6 (FastAPI HTTP server).
 * - `status`: "alive" iff `ollama_status === "ready"`, else "degraded".
 * - `last_quote_generated_at`: 0 if no quote has been generated yet.
 */
export interface HealthResponse {
  status: "alive" | "degraded";
  enclave_image_hash: string;
  last_quote_generated_at: number;
  ollama_model: string;
  ollama_status: "ready" | "unreachable";
}

// ────────────────────────────────────────────────────────────────────
// On-chain decoded events (mirror docs/interfaces.md)
// ────────────────────────────────────────────────────────────────────

export interface ActionExecutedEvent {
  user: Address;
  mr_enclave: Bytes32;
  quote_digest: Bytes32;
  amount: bigint;
  timestamp: bigint;
  block_number: bigint;
  transaction_hash: Hex;
}

export interface QuoteVerifiedEvent {
  mr_enclave: Bytes32;
  quote_digest: Bytes32;
  success: boolean;
  block_number: bigint;
  transaction_hash: Hex;
}

export interface AgentRegisteredEvent {
  mr_enclave: Bytes32;
  registrar: Address;
  timestamp: bigint;
}

// ────────────────────────────────────────────────────────────────────
// Composite types
// ────────────────────────────────────────────────────────────────────

export interface ResolvedAction {
  event: ActionExecutedEvent;
  quote?: AttestationQuote;
  verified: boolean;
}

export interface HookResult<T> {
  data: T | undefined;
  isLoading: boolean;
  error: Error | null;
  source: "mock" | "live";
}
