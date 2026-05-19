import type {
  AttestationQuote,
  LLMResponse,
  PriceData,
  HealthResponse,
  ActionExecutedEvent,
  QuoteVerifiedEvent,
  AgentRegisteredEvent,
  ResolvedAction,
  Address,
  Bytes32,
} from "@/lib/types";

const NOW = Math.floor(Date.now() / 1000);
const HOUR = 3600;

const MOCK_USER: Address = "0x0173b7c85995aa690736b065ddf84512a746f3f2";

const MR_ENCLAVE_QWEN: Bytes32 =
  "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef";
const MR_ENCLAVE_LLAMA: Bytes32 =
  "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890";

const MOCK_QUOTE_DIGEST_QWEN_1: Bytes32 =
  "0xaaaa11110000000000000000000000000000000000000000000000000000aaaa";
const MOCK_QUOTE_DIGEST_QWEN_2: Bytes32 =
  "0xbbbb22220000000000000000000000000000000000000000000000000000bbbb";

const MOCK_ACTION_HASH_QWEN_1: Bytes32 =
  "0xa11100000000000000000000000000000000000000000000000000000000a111";
const MOCK_ACTION_HASH_QWEN_2: Bytes32 =
  "0xb22200000000000000000000000000000000000000000000000000000000b222";
const MOCK_INPUT_HASH_QWEN_1: Bytes32 =
  "0x1111000000000000000000000000000000000000000000000000000000001111";
const MOCK_INPUT_HASH_QWEN_2: Bytes32 =
  "0x2222000000000000000000000000000000000000000000000000000000002222";
const MOCK_OUTPUT_HASH_QWEN_1: Bytes32 =
  "0x000000000000000000000000000000000000000000000000000000000000000a";
const MOCK_OUTPUT_HASH_QWEN_2: Bytes32 =
  "0x000000000000000000000000000000000000000000000000000000000000000b";

export const MOCK_QUOTES: Record<string, AttestationQuote> = {
  [MOCK_QUOTE_DIGEST_QWEN_1]: {
    quote_hex:
      "0x414547495f4d4f434b5f51554f54455f76311234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef0000000000000000000000000000000000000000000000000000000000000001",
    report_data: `0x${MOCK_ACTION_HASH_QWEN_1.slice(2)}${MOCK_OUTPUT_HASH_QWEN_1.slice(2)}`,
    action_hash: MOCK_ACTION_HASH_QWEN_1,
    input_hash: MOCK_INPUT_HASH_QWEN_1,
    output_hash: MOCK_OUTPUT_HASH_QWEN_1,
    mr_enclave: MR_ENCLAVE_QWEN,
    timestamp: NOW - 60,
    is_mock: true,
  },
  [MOCK_QUOTE_DIGEST_QWEN_2]: {
    quote_hex:
      "0x414547495f4d4f434b5f51554f54455f76311234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef0000000000000000000000000000000000000000000000000000000000000002",
    report_data: `0x${MOCK_ACTION_HASH_QWEN_2.slice(2)}${MOCK_OUTPUT_HASH_QWEN_2.slice(2)}`,
    action_hash: MOCK_ACTION_HASH_QWEN_2,
    input_hash: MOCK_INPUT_HASH_QWEN_2,
    output_hash: MOCK_OUTPUT_HASH_QWEN_2,
    mr_enclave: MR_ENCLAVE_QWEN,
    timestamp: NOW - 600,
    is_mock: true,
  },
};

export const MOCK_LLM_RESPONSE: LLMResponse = {
  model: "qwen2.5:7b",
  prompt: "Should I swap 0.1 ETH to USDC at the current price?",
  response:
    '{"action":"swap","from":"ETH","to":"USDC","amount":"0.1","reason":"Price appears stable; small position sizing within risk limits."}',
  input_hash:
    "0x1111111111111111111111111111111111111111111111111111111111111111",
  output_hash:
    "0x222222222222222222222222222222222222222222222222222222222222222a",
  elapsed_ms: 4823,
  eval_count: 142,
};

export const MOCK_PRICE_DATA: PriceData = {
  price: "3245.18",
  round_id: BigInt("18446744073709553817"),
  updated_at: NOW - 120,
  answered_in_round: BigInt("18446744073709553817"),
  feed_address: "0x694AA1769357215DE4FAC081bf1f309aDC325306",
  decimals: 8,
  description: "ETH / USD",
  raw_answer: "324518000000",
  data_hash:
    "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
};

export const MOCK_HEALTH: HealthResponse = {
  status: "alive",
  enclave_image_hash: MR_ENCLAVE_QWEN.slice(2),
  last_quote_generated_at: NOW - 60,
  ollama_model: "qwen2.5:7b",
  ollama_status: "ready",
};

export const MOCK_REGISTERED_AGENTS: Bytes32[] = [
  MR_ENCLAVE_QWEN,
  MR_ENCLAVE_LLAMA,
];

export const MOCK_AGENT_REGISTERED_EVENTS: AgentRegisteredEvent[] = [
  {
    mr_enclave: MR_ENCLAVE_QWEN,
    registrar: MOCK_USER,
    timestamp: BigInt(NOW - 24 * HOUR),
  },
  {
    mr_enclave: MR_ENCLAVE_LLAMA,
    registrar: MOCK_USER,
    timestamp: BigInt(NOW - 12 * HOUR),
  },
];

export const MOCK_ACTION_EVENTS: ActionExecutedEvent[] = [
  {
    user: MOCK_USER,
    mr_enclave: MR_ENCLAVE_QWEN,
    quote_digest: MOCK_QUOTE_DIGEST_QWEN_1,
    amount: BigInt("100000000000000000"),
    timestamp: BigInt(NOW - 60),
    block_number: BigInt("5000000"),
    transaction_hash:
      "0x9999999999999999999999999999999999999999999999999999999999999999",
  },
  {
    user: MOCK_USER,
    mr_enclave: MR_ENCLAVE_QWEN,
    quote_digest: MOCK_QUOTE_DIGEST_QWEN_2,
    amount: BigInt("250000000000000000"),
    timestamp: BigInt(NOW - 600),
    block_number: BigInt("4999950"),
    transaction_hash:
      "0x8888888888888888888888888888888888888888888888888888888888888888",
  },
];

export const MOCK_QUOTE_VERIFIED_EVENTS: QuoteVerifiedEvent[] = [
  {
    mr_enclave: MR_ENCLAVE_QWEN,
    quote_digest: MOCK_QUOTE_DIGEST_QWEN_1,
    success: true,
    block_number: BigInt("5000000"),
    transaction_hash:
      "0x9999999999999999999999999999999999999999999999999999999999999999",
  },
  {
    mr_enclave: MR_ENCLAVE_QWEN,
    quote_digest: MOCK_QUOTE_DIGEST_QWEN_2,
    success: true,
    block_number: BigInt("4999950"),
    transaction_hash:
      "0x8888888888888888888888888888888888888888888888888888888888888888",
  },
];

export const MOCK_RESOLVED_ACTIONS: ResolvedAction[] = MOCK_ACTION_EVENTS.map(
  (event) => {
    return {
      event,
      quote: MOCK_QUOTES[event.quote_digest.toLowerCase()],
      verified:
        MOCK_QUOTE_VERIFIED_EVENTS.find(
          (q) => q.quote_digest === event.quote_digest
        )?.success ?? false,
    };
  }
);

export const MOCK_VAULT_BALANCE = BigInt("500000000000000000");
export const MOCK_NONCE = BigInt("7");
