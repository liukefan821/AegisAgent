"""
decision_engine.py — Step 6: End-to-end decision orchestrator for AegisAgent

Orchestrates the full pipeline:
  1. Read ETH/USD price from Chainlink (Sepolia)
  2. Query Ollama LLM for a DeFi risk assessment decision
  3. Compute actionHash = keccak256(abi.encode(user, amount, target, nonce, timestamp))
     matching AegisVault.executeAction() on-chain
  4. Generate TDX attestation quote with report_data = actionHash || output_hash
  5. Store quote + metadata in QuoteStore for frontend lookup
  6. Return DecisionResult with all data needed to call executeAction()

Author: LIU Kefan
Project: AegisAgent (SC6107, NTU CCDS, 2026)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from eth_abi import encode as abi_encode
from eth_utils import keccak

from aegis_agent.chainlink_feed import ChainlinkFeed, PriceData
from aegis_agent.http_server import get_store
from aegis_agent.ollama_client import LLMResponse, OllamaClient
from aegis_agent.quote_generator import AttestationQuote, QuoteGenerator

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are AegisAgent, a TEE-protected autonomous DeFi risk assessment AI.
You run inside an Intel TDX Trusted Execution Environment on Phala Cloud.
Every decision you make is cryptographically attested and verified on-chain.

## Risk Assessment Rules

Evaluate market risk based on the ETH/USD price provided:

- LOW risk (ETH price stable, above $2500): HOLD. Keep all funds in vault.
- MEDIUM risk (ETH price between $1800-$2500, or dropped 3-8% recently):
  TRANSFER 25% of vault balance to the emergency safe address.
- HIGH risk (ETH price below $1800, or dropped more than 8%):
  TRANSFER 50% of vault balance to the emergency safe address.

## Safety Constraints

- NEVER transfer to any address except the emergency safe address provided.
- If emergency safe address is not provided, always HOLD.
- amount_wei must not exceed the vault balance.
- When in doubt, HOLD.

Respond ONLY with valid JSON (no markdown, no explanation outside JSON):
{
  "action": "HOLD" or "TRANSFER",
  "amount_wei": 0,
  "target": "emergency_safe_address_here",
  "reasoning": "brief risk assessment explanation"
}"""

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# Action expiry: seconds into the future for the on-chain timestamp deadline
ACTION_EXPIRY_SECONDS = 300  # 5 minutes


# ────────────────────────────────────────────────────────────────────────────
# Data class
# ────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DecisionResult:
    """Everything needed to call AegisVault.executeAction() on-chain.

    The frontend / relayer takes these fields and submits:
        vault.executeAction(user, quote, actionHash, amount, target, timestamp)
    """
    # LLM decision
    action: str                # "HOLD" or "TRANSFER"
    reasoning: str
    # On-chain action parameters (match executeAction signature)
    user: str                  # checksummed address
    amount_wei: int
    target: str                # checksummed address
    nonce: int
    timestamp: int             # expiry deadline (block.timestamp must be < this)
    action_hash: str           # 0x-prefixed keccak256(abi.encode(user,amount,target,nonce,ts))
    # Attestation
    quote_hex: str             # 0x-prefixed TDX quote bytes
    quote_digest: str          # 0x-prefixed keccak256(quote) — on-chain event key
    mr_enclave: str            # 0x-prefixed 32-byte enclave measurement
    is_mock: bool
    # Hashes for audit trail
    input_hash: str            # 0x-prefixed SHA-256 of LLM input
    output_hash: str           # 0x-prefixed SHA-256 of LLM output
    # Price context
    eth_usd_price: str
    chainlink_round_id: int


# ────────────────────────────────────────────────────────────────────────────
# actionHash computation — MUST match AegisVault.executeAction() on-chain
# ────────────────────────────────────────────────────────────────────────────

def compute_action_hash(
    user: str,
    amount: int,
    target: str,
    nonce: int,
    timestamp: int,
) -> bytes:
    """Compute actionHash exactly as the Vault contract does.

    Solidity:
        bytes32 expectedHash = keccak256(abi.encode(
            user, amount, target, _nonces[user], timestamp
        ));

    Python equivalent uses eth_abi.encode with the same ABI types.

    Returns:
        32-byte keccak256 hash.
    """
    encoded = abi_encode(
        ["address", "uint256", "address", "uint256", "uint256"],
        [user, amount, target, nonce, timestamp],
    )
    return keccak(encoded)


# ────────────────────────────────────────────────────────────────────────────
# Decision engine
# ────────────────────────────────────────────────────────────────────────────

class DecisionEngine:
    """Full decision pipeline: price -> LLM -> actionHash -> quote -> store.

    Usage:
        engine = DecisionEngine(ollama, quote_gen)
        result = engine.decide(user="0x...", balance_wei=10**18, nonce=0)
        # result contains everything to call vault.executeAction()
    """

    def __init__(
        self,
        ollama: OllamaClient,
        quote_gen: QuoteGenerator,
        chainlink: Optional[ChainlinkFeed] = None,
    ) -> None:
        self.ollama = ollama
        self.quote_gen = quote_gen
        self.chainlink = chainlink
        logger.info("DecisionEngine initialised (chainlink=%s)", chainlink is not None)

    def decide(
        self,
        user: str,
        balance_wei: int,
        nonce: int,
        *,
        mock_price: Optional[str] = None,
    ) -> DecisionResult:
        """Run the full decision pipeline.

        Args:
            user: Checksummed Ethereum address of the vault depositor.
            balance_wei: User's current vault balance in wei.
            nonce: Current on-chain nonce from AegisVault.nonceOf(user).
            mock_price: If set, skip Chainlink and use this as ETH/USD price.

        Returns:
            DecisionResult with all fields for executeAction + audit.
        """
        # ── 1. Price feed ────────────────────────────────────────────────
        if self.chainlink is not None and mock_price is None:
            price_data = self.chainlink.get_latest_price()
            price_str = str(price_data.price)
            round_id = price_data.round_id
            price_line = (
                f"ETH/USD: ${price_str} "
                f"(Chainlink round {round_id}, data_hash {price_data.data_hash})"
            )
        else:
            price_str = mock_price or "2500.00"
            round_id = 0
            price_line = f"ETH/USD: ${price_str} (mock price)"

        # ── 2. LLM inference ─────────────────────────────────────────────
        balance_eth = balance_wei / 1e18
        emergency_safe = user  # default: send back to user's own wallet
        prompt = (
            f"{price_line}\n"
            f"User: {user}\n"
            f"Vault balance: {balance_eth:.6f} ETH ({balance_wei} wei)\n"
            f"Current nonce: {nonce}\n"
            f"Emergency safe address: {emergency_safe}\n\n"
            f"Assess market risk level and decide: HOLD or TRANSFER?"
        )

        llm_result = self.ollama.generate(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            json_mode=True,
            max_tokens=1024,
            temperature=0.1,
        )
        logger.info(
            "LLM responded in %dms (input_hash=%s...)",
            llm_result.elapsed_ms,
            llm_result.input_hash[:10],
        )

        # ── 3. Parse LLM decision ───────────────────────────────────────
        try:
            parsed = OllamaClient.parse_json_response(llm_result.response)
        except (ValueError, KeyError) as e:
            logger.warning("LLM response unparseable (%s), defaulting to HOLD", e)
            parsed = {
                "action": "HOLD",
                "amount_wei": 0,
                "target": ZERO_ADDRESS,
                "reasoning": "LLM parse error, defaulting to safe HOLD",
            }

        action = parsed.get("action", "HOLD").upper()
        amount_wei = int(parsed.get("amount_wei", 0))
        target = parsed.get("target", ZERO_ADDRESS)
        if target.startswith("0x") and len(target) < 42: target = target[:2] + target[2:].zfill(40)
        reasoning = parsed.get("reasoning", "")

        # Safety: clamp invalid decisions
        if action != "TRANSFER":
            action = "HOLD"
            amount_wei = 0
            target = ZERO_ADDRESS
        if amount_wei < 0:
            amount_wei = 0
        if amount_wei > balance_wei:
            logger.warning(
                "LLM requested %d wei but balance is %d, clamping",
                amount_wei, balance_wei,
            )
            amount_wei = balance_wei

        # ── 4. Compute actionHash (matches Vault contract) ──────────────
        timestamp = int(time.time()) + ACTION_EXPIRY_SECONDS
        action_hash_bytes = compute_action_hash(
            user, amount_wei, target, nonce, timestamp,
        )
        logger.info("actionHash = 0x%s...", action_hash_bytes.hex()[:16])

        # ── 5. Generate attestation quote ────────────────────────────────
        # report_data layout: actionHash (32B) || output_hash (32B)
        # input_hash is saved separately in QuoteStore for audit.
        output_hash_bytes = bytes.fromhex(llm_result.output_hash.removeprefix("0x"))
        input_hash_bytes = bytes.fromhex(llm_result.input_hash.removeprefix("0x"))

        quote = self.quote_gen.generate(
            input_hash=action_hash_bytes,    # report_data[0:32] = actionHash
            output_hash=output_hash_bytes,   # report_data[32:64] = output_hash
        )

        # ── 6. Store in QuoteStore (with real input_hash as extra field) ─
        store = get_store()
        digest = store.put(quote, input_hash=input_hash_bytes)

        logger.info(
            "Decision complete: %s | amount=%d wei | target=%s | digest=%s...",
            action, amount_wei, target[:10], digest[:10],
        )

        return DecisionResult(
            action=action,
            reasoning=reasoning,
            user=user,
            amount_wei=amount_wei,
            target=target,
            nonce=nonce,
            timestamp=timestamp,
            action_hash="0x" + action_hash_bytes.hex(),
            quote_hex="0x" + quote.quote_hex,
            quote_digest=digest,
            mr_enclave="0x" + quote.mr_enclave,
            is_mock=quote.is_mock,
            input_hash=llm_result.input_hash,
            output_hash=llm_result.output_hash,
            eth_usd_price=price_str,
            chainlink_round_id=round_id,
        )


# ────────────────────────────────────────────────────────────────────────────
# CLI demo:  python -m aegis_agent.decision_engine
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
    print("=" * 70)
    print("AegisAgent — DecisionEngine end-to-end demo (mock mode)")
    print("=" * 70)

    ollama = OllamaClient()
    if not ollama.health_check():
        print("ERROR: Ollama not reachable. Run `ollama serve` first.")
        sys.exit(1)

    quote_gen = QuoteGenerator(mock=True)
    engine = DecisionEngine(ollama=ollama, quote_gen=quote_gen, chainlink=None)

    demo_user = "0x36c6eB92bfABaF637aa1607EccE02e0EC952F82C"
    demo_balance = 10 ** 18  # 1 ETH
    demo_nonce = 0

    print(f"\nUser:    {demo_user}")
    print(f"Balance: {demo_balance} wei (1.0 ETH)")
    print(f"Nonce:   {demo_nonce}")
    print("-" * 70)

    result = engine.decide(
        user=demo_user,
        balance_wei=demo_balance,
        nonce=demo_nonce,
        mock_price="2500.00",
    )

    print(f"\n{'=' * 70}")
    print(f"Decision:      {result.action}")
    print(f"Reasoning:     {result.reasoning}")
    print(f"Amount:        {result.amount_wei} wei")
    print(f"Target:        {result.target}")
    print(f"Timestamp:     {result.timestamp}")
    print(f"Action Hash:   {result.action_hash}")
    print(f"Quote Digest:  {result.quote_digest}")
    print(f"MR Enclave:    {result.mr_enclave}")
    print(f"Mock:          {result.is_mock}")
    print(f"Input Hash:    {result.input_hash}")
    print(f"Output Hash:   {result.output_hash}")
    print(f"ETH/USD:       ${result.eth_usd_price}")
    print(f"{'=' * 70}")
    print("\nThis DecisionResult can be passed to AegisVault.executeAction():")
    print(f"  vault.executeAction(")
    print(f"    user      = {result.user},")
    print(f"    quote     = {result.quote_hex[:20]}...,")
    print(f"    actionHash= {result.action_hash},")
    print(f"    amount    = {result.amount_wei},")
    print(f"    target    = {result.target},")
    print(f"    timestamp = {result.timestamp}")
    print(f"  )")
