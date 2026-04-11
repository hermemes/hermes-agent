"""BscScan API Adapter — BSC transaction history for KOL profiling.

Fetches normal transactions, BEP-20 token transfers, and internal
transactions for a given BSC wallet address.

Set BSCSCAN_API_KEY in env. Free tier supports 5 req/s, 100k req/day.
Docs: https://docs.bscscan.com/
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://api.bscscan.com/api"
_TIMEOUT = 20.0
_MAX_RETRIES = 3
_RETRY_DELAY = 1.5

# PancakeSwap v2 Router — used to detect swap transactions
PANCAKE_ROUTER_V2 = "0x10ed43c718714eb63d5aa57b78b54704e256024e"
PANCAKE_ROUTER_V3 = "0x13f4ea83d0bd40e75c8222255bc855a974568dd4"
FOUR_MEME_ROUTER  = "0x5c952063c7fc8610fffed69d5a7b8c236d1b0085"

SWAP_ROUTERS = {
    PANCAKE_ROUTER_V2.lower(),
    PANCAKE_ROUTER_V3.lower(),
    FOUR_MEME_ROUTER.lower(),
}

WBNB = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"


@dataclass
class RawTransaction:
    hash: str
    block: int
    timestamp: int
    from_addr: str
    to_addr: str
    value_bnb: float
    gas_used: int
    gas_price_gwei: float
    is_error: bool
    method_id: str


@dataclass
class TokenTransfer:
    hash: str
    block: int
    timestamp: int
    from_addr: str
    to_addr: str
    token_contract: str
    token_symbol: str
    token_name: str
    token_decimals: int
    amount: float


@dataclass
class Trade:
    """A single resolved buy or sell event for a token."""
    hash: str
    timestamp: int
    wallet: str
    token_contract: str
    token_symbol: str
    side: str              # "buy" or "sell"
    amount_tokens: float
    bnb_value: float       # approximate BNB spent/received
    token_decimals: int
    router: str            # which DEX router was used


def _api_key() -> str:
    key = os.getenv("BSCSCAN_API_KEY", "")
    if not key:
        logger.warning("BSCSCAN_API_KEY not set — rate limits apply (1 req/5s)")
    return key


async def _get(params: Dict[str, Any], retries: int = _MAX_RETRIES) -> Dict:
    params["apikey"] = _api_key()
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()
                if data.get("status") == "1":
                    return data
                msg = data.get("message", "")
                if "rate limit" in msg.lower() or data.get("result") == "Max rate limit reached":
                    await asyncio.sleep(_RETRY_DELAY * (attempt + 1))
                    continue
                # "No transactions found" is a valid empty result
                if "No transactions" in msg or data.get("result") == [] or data.get("result") == "":
                    return {"status": "0", "result": [], "message": msg}
                logger.debug("BscScan non-1 status: %s | %s", data.get("status"), msg)
                return data
        except httpx.HTTPError as e:
            if attempt < retries - 1:
                await asyncio.sleep(_RETRY_DELAY * (attempt + 1))
            else:
                raise RuntimeError(f"BscScan request failed: {e}") from e
    return {"status": "0", "result": []}


async def fetch_normal_transactions(
    address: str,
    days: int = 90,
    max_records: int = 1000,
) -> List[RawTransaction]:
    """Fetch normal (BNB-value) transactions for a wallet."""
    since_ts = int(time.time()) - days * 86400
    params = {
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "sort": "desc",
        "offset": max_records,
        "page": 1,
    }
    data = await _get(params)
    txs = []
    for t in data.get("result", []) or []:
        ts = int(t.get("timeStamp", 0))
        if ts < since_ts:
            continue
        txs.append(RawTransaction(
            hash=t["hash"],
            block=int(t.get("blockNumber", 0)),
            timestamp=ts,
            from_addr=t.get("from", "").lower(),
            to_addr=t.get("to", "").lower(),
            value_bnb=int(t.get("value", 0)) / 1e18,
            gas_used=int(t.get("gasUsed", 0)),
            gas_price_gwei=int(t.get("gasPrice", 0)) / 1e9,
            is_error=t.get("isError", "0") == "1",
            method_id=t.get("methodId", "0x"),
        ))
    return txs


async def fetch_token_transfers(
    address: str,
    days: int = 90,
    max_records: int = 2000,
) -> List[TokenTransfer]:
    """Fetch BEP-20 token transfer events for a wallet."""
    since_ts = int(time.time()) - days * 86400
    params = {
        "module": "account",
        "action": "tokentx",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "sort": "desc",
        "offset": max_records,
        "page": 1,
    }
    data = await _get(params)
    transfers = []
    for t in data.get("result", []) or []:
        ts = int(t.get("timeStamp", 0))
        if ts < since_ts:
            continue
        decimals = int(t.get("tokenDecimal", 18))
        raw_amount = int(t.get("value", 0))
        amount = raw_amount / (10 ** decimals) if decimals >= 0 else raw_amount
        transfers.append(TokenTransfer(
            hash=t["hash"],
            block=int(t.get("blockNumber", 0)),
            timestamp=ts,
            from_addr=t.get("from", "").lower(),
            to_addr=t.get("to", "").lower(),
            token_contract=t.get("contractAddress", "").lower(),
            token_symbol=t.get("tokenSymbol", "UNKNOWN"),
            token_name=t.get("tokenName", ""),
            token_decimals=decimals,
            amount=amount,
        ))
    return transfers


async def fetch_bnb_balance(address: str) -> float:
    """Get current BNB balance for a wallet."""
    params = {
        "module": "account",
        "action": "balance",
        "address": address,
        "tag": "latest",
    }
    data = await _get(params)
    result = data.get("result", "0")
    return int(result) / 1e18 if result else 0.0


async def resolve_trades(
    address: str,
    token_transfers: List[TokenTransfer],
    normal_txs: List[RawTransaction],
) -> List[Trade]:
    """
    Match token transfers with normal BNB transactions to infer trades.

    Logic:
    - Token IN to wallet + BNB OUT from wallet in same tx → BUY
    - Token OUT from wallet + BNB IN to wallet in same tx → SELL
    - Token IN from a known router without BNB move → assume swap buy
    """
    addr = address.lower()
    bnb_by_hash: Dict[str, float] = {}
    for tx in normal_txs:
        if tx.is_error:
            continue
        if tx.from_addr == addr:
            bnb_by_hash[tx.hash] = -tx.value_bnb
        elif tx.to_addr == addr:
            bnb_by_hash[tx.hash] = tx.value_bnb

    trades: List[Trade] = []
    seen_hashes: Dict[str, str] = {}

    for transfer in token_transfers:
        contract = transfer.token_contract
        if contract.lower() == WBNB.lower():
            continue

        is_receive = transfer.to_addr == addr
        is_send = transfer.from_addr == addr

        if not (is_receive or is_send):
            continue

        bnb_val = abs(bnb_by_hash.get(transfer.hash, 0.0))
        tx_hash = transfer.hash

        key = f"{tx_hash}:{contract}"
        if key in seen_hashes:
            continue
        seen_hashes[key] = "1"

        side = "buy" if is_receive else "sell"

        # Detect which router
        router = "unknown"
        for tx in normal_txs:
            if tx.hash == tx_hash:
                if tx.to_addr in SWAP_ROUTERS:
                    router = tx.to_addr
                break

        trades.append(Trade(
            hash=tx_hash,
            timestamp=transfer.timestamp,
            wallet=addr,
            token_contract=contract,
            token_symbol=transfer.token_symbol,
            side=side,
            amount_tokens=transfer.amount,
            bnb_value=bnb_val,
            token_decimals=transfer.token_decimals,
            router=router,
        ))

    trades.sort(key=lambda t: t.timestamp)
    return trades


async def get_all_trades(address: str, days: int = 90) -> List[Trade]:
    """High-level: fetch and resolve all trades for a wallet."""
    transfers, normal_txs = await asyncio.gather(
        fetch_token_transfers(address, days=days),
        fetch_normal_transactions(address, days=days),
    )
    return await resolve_trades(address, transfers, normal_txs)
