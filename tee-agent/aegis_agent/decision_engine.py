"""
decision_engine.py — Step 6: End-to-end decision orchestrator for AegisAgent

Orchestrates the full pipeline:
  1. Read ETH/USD price from Chainlink (Sepolia)
  2. Query LLM (Gemini or Ollama) for a DeFi risk assessment decision
  3. Compute actionHash = keccak256(abi.encode(user, amount, target, nonce, timestamp))
     matching AegisVault.executeAction() on-chain
  4. Generate TDX attestation quote with report_data = actionHash || output_hash
  5. Store quote + metadata in QuoteStore for frontend lookup
  6. Return DecisionResult with all data needed to call executeAction()

Author: LIU Kefan
Project: AegisAgent (SC6107, NTU CCDS, 2026)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

from eth_abi.abi import encode as abi_encode
from eth_utils import keccak

from aegis_agent.chainlink_feed import ChainlinkFeed, PriceData
from aegis_agent.http_server import get_store
from aegis_agent.llm_client import LLMClient, create_llm_client
from aegis_agent.ollama_client import LLMResponse, OllamaClient
from aegis_agent.quote_generator import AttestationQuote, QuoteGenerator
from aegis_agent.swap_encoder import SwapParams, build_swap_params

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
- PROFIT-TAKING opportunity (ETH price above $3200, strong uptrend):
  SWAP 30% of vault ETH to USDC via Uniswap to lock in profits.
- DIP-BUYING opportunity (ETH price below $1500, potential reversal):
  SWAP is not applicable (vault holds ETH, not USDC). Use HOLD or TRANSFER.

## Safety Constraints

- NEVER transfer to any address except the emergency safe address provided.
- If emergency safe address is not provided, always HOLD.
- amount_wei must not exceed the vault balance.
- SWAP target is always the Uniswap Router (set automatically by the system).
- When in doubt, HOLD.

Respond ONLY with valid JSON (no markdown, no explanation outside JSON):
{
  "action": "HOLD" or "TRANSFER" or "SWAP",
  "amount_wei": 0,
  "target": "emergency_safe_address_here",
  "reasoning": "brief risk assessment explanation"
}

Note: For SWAP actions, the system will override "target" with the Uniswap
Router address and encode the swap calldata automatically. You only need to
specify the ETH amount_wei to swap."""

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# Action expiry: seconds into the future for the on-chain timestamp deadline
ACTION_EXPIRY_SECONDS = 900  # 15 minutes for wallet confirmation during demos


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
    action: str                # "HOLD", "TRANSFER", or "SWAP"
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
    # Swap extension (None for HOLD/TRANSFER)
    swap_calldata: Optional[str] = None         # 0x-prefixed Uniswap calldata
    swap_calldata_hash: Optional[str] = None    # 0x-prefixed keccak256(calldata)
    swap_amount_out_min: Optional[int] = None   # minimum USDC output


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
        ollama: LLMClient,
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
        demo_action: Optional[str] = None,
        demo_transfer_bps: int = 2500,
    ) -> DecisionResult:
        """Run the full decision pipeline.

        Args:
            user: Checksummed Ethereum address of the vault depositor.
            balance_wei: User's current vault balance in wei.
            nonce: Current on-chain nonce from AegisVault.nonceOf(user).
            mock_price: If set, skip Chainlink and use this as ETH/USD price.
            demo_action: If set, bypass LLM and use this action deterministically.
            demo_transfer_bps: Basis points for demo TRANSFER amount.

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
            f"Assess market risk level and decide: HOLD, TRANSFER, or SWAP?"
        )

        if demo_action is not None:
            parsed = self._build_demo_decision(
                action=demo_action,
                user=user,
                balance_wei=balance_wei,
                transfer_bps=demo_transfer_bps,
            )
            llm_result = self._build_demo_llm_response(prompt, parsed)
            logger.info("Using demo decision override: %s", parsed["action"])
        else:
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

            # ── 3. Parse LLM decision ───────────────────────────────────
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
        if target.startswith("0x") and len(target) < 42:
            target = target[:2] + target[2:].zfill(40)
        reasoning = parsed.get("reasoning", "")

        # ── 3b. Swap calldata (extension) ────────────────────────────────
        swap_calldata: Optional[str] = None
        swap_calldata_hash: Optional[str] = None
        swap_amount_out_min: Optional[int] = None

        if action == "SWAP":
            # Clamp amount
            if amount_wei <= 0:
                amount_wei = int(balance_wei * 0.3)  # default 30%
                logger.info("SWAP: LLM gave no amount, defaulting to 30%% = %d wei", amount_wei)
            if amount_wei > balance_wei:
                logger.warning("SWAP: clamping %d -> %d (balance)", amount_wei, balance_wei)
                amount_wei = balance_wei

            timestamp = int(time.time()) + ACTION_EXPIRY_SECONDS
            try:
                eth_price_float = float(price_str)
            except ValueError:
                eth_price_float = 2500.0

            swap_params = build_swap_params(
                user=user,
                amount_wei=amount_wei,
                eth_price_usd=eth_price_float,
                deadline=timestamp,
            )
            target = swap_params.target          # Uniswap Router
            swap_calldata = swap_params.calldata
            swap_calldata_hash = swap_params.calldata_hash
            swap_amount_out_min = swap_params.amount_out_min
            logger.info(
                "SWAP: %d wei ETH -> min %d USDC, router=%s",
                amount_wei, swap_amount_out_min, target[:10],
            )

        elif action == "TRANSFER":
            # The LLM may decide whether to transfer and how much, but the
            # destination is fixed by deterministic code. Never trust a model
            # response to choose where funds are sent.
            if target.lower() != emergency_safe.lower():
                logger.warning(
                    "Ignoring LLM transfer target %s; using emergency safe %s",
                    target,
                    emergency_safe,
                )
            target = emergency_safe
            if amount_wei < 0:
                amount_wei = 0
            if amount_wei > balance_wei:
                logger.warning(
                    "LLM requested %d wei but balance is %d, clamping",
                    amount_wei, balance_wei,
                )
                amount_wei = balance_wei

        else:
            # Default to HOLD for any unrecognised action
            action = "HOLD"
            amount_wei = 0
            target = ZERO_ADDRESS

        # ── 4. Compute actionHash (matches Vault contract) ──────────────
        if action != "SWAP":
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
            swap_calldata=swap_calldata,
            swap_calldata_hash=swap_calldata_hash,
            swap_amount_out_min=swap_amount_out_min,
        )

    def _build_demo_decision(
        self,
        *,
        action: str,
        user: str,
        balance_wei: int,
        transfer_bps: int,
    ) -> dict:
        """Build a deterministic demo decision without trusting prompt output."""
        normalized = action.upper()
        if normalized not in {"HOLD", "TRANSFER"}:
            raise ValueError("demo_action must be HOLD or TRANSFER")
        if normalized == "HOLD":
            return {
                "action": "HOLD",
                "amount_wei": 0,
                "target": ZERO_ADDRESS,
                "reasoning": "Demo override: keep funds in the vault.",
            }
        bps = max(0, min(transfer_bps, 10_000))
        amount_wei = balance_wei * bps // 10_000
        return {
            "action": "TRANSFER",
            "amount_wei": amount_wei,
            "target": user,
            "reasoning": (
                f"Demo override: transfer {bps / 100:.2f}% of the vault "
                "balance to the configured safe wallet."
            ),
        }

    def _build_demo_llm_response(self, prompt: str, parsed: dict) -> LLMResponse:
        response = json.dumps(parsed, separators=(",", ":"), sort_keys=True)
        canonical_input = (
            f"SYSTEM:{SYSTEM_PROMPT}\n"
            f"USER:{prompt}\n"
            f"MODEL:{self.ollama.model}"
        )
        input_hash = hashlib.sha256(canonical_input.encode("utf-8")).hexdigest()
        output_hash = hashlib.sha256(response.encode("utf-8")).hexdigest()
        return LLMResponse(
            model=self.ollama.model,
            prompt=prompt,
            response=response,
            input_hash="0x" + input_hash,
            output_hash="0x" + output_hash,
            elapsed_ms=0,
            eval_count=0,
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

    ollama = create_llm_client()
    if not ollama.health_check():
        print("ERROR: LLM provider is not reachable. Check tee-agent LLM env config.")
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
        mock_price="3500.00",
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
    if result.swap_calldata:
        print(f"Swap Calldata: {result.swap_calldata[:40]}...")
        print(f"Swap Hash:     {result.swap_calldata_hash}")
        print(f"Min USDC Out:  {result.swap_amount_out_min}")
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
