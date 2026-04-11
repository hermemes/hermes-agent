"""four.meme Adapter — early BSC meme token launch data.

four.meme is the primary BSC meme launchpad. This adapter fetches:
- Token launch timestamps (to compute KOL entry timing after launch)
- Initial liquidity and bonding curve parameters
- Token creator / deployer address
- Current bonding curve progress (% to graduation)
- Token metadata (name, symbol, description, socials)

four.meme API base: https://four.meme
Also uses BSC RPC to query the four.meme factory contract directly
for on-chain launch data when the API is unavailable.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_FOUR_MEME_API = "https://four.meme/meme-api"
_FOUR_MEME_WEB  = "https://four.meme"
_BSC_RPC = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org")
_TIMEOUT = 15.0

# four.meme factory contract on BSC (creates bonding curve tokens)
FOUR_MEME_FACTORY = "0x5c952063c7fc8610fffed69d5a7b8c236d1b0085"
# four.meme router (used for token purchases on bonding curve)
FOUR_MEME_ROUTER  = "0x5c952063c7fc8610fffed69d5a7b8c236d1b0085"

# Topic for TokenCreated event in four.meme factory
TOKEN_CREATED_TOPIC = "0x9f4a58d1d78c8e8b2b00ea4e04bc5d1df10e84a44c39cba94fcd9a22aea26f5a"


@dataclass
class FourMemeToken:
    contract: str
    symbol: str
    name: str
    description: str
    creator: str           # deployer wallet
    launch_ts: int         # unix timestamp of token creation
    initial_supply: float
    initial_liquidity_bnb: float
    bonding_curve_pct: float   # 0–100, progress to DEX graduation
    graduated: bool            # True = moved to PancakeSwap
    graduation_ts: int         # 0 if not yet graduated
    market_cap_usd: float
    holders: int
    socials: Dict[str, str] = field(default_factory=dict)
    image_url: str = ""


@dataclass
class KOLEntryTiming:
    """How quickly after launch a KOL entered a token."""
    wallet: str
    token_contract: str
    token_symbol: str
    launch_ts: int
    first_buy_ts: int
    hours_after_launch: float
    is_pre_graduation: bool   # bought before DEX graduation
    bonding_curve_pct_at_entry: float  # estimated


async def _api_get(path: str, params: Dict = None) -> Dict:
    """Call four.meme API endpoint."""
    url = f"{_FOUR_MEME_API}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params or {}, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": _FOUR_MEME_WEB,
        })
        if resp.status_code == 200:
            return resp.json()
        return {}


async def _rpc_call(method: str, params: list) -> Any:
    """Raw BSC JSON-RPC call."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(_BSC_RPC, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        return data.get("result")


async def get_token_launch_info(contract: str) -> Optional[FourMemeToken]:
    """
    Fetch launch metadata for a four.meme token.

    Tries four.meme API first, falls back to on-chain event logs.
    """
    contract = contract.strip().lower()

    # --- Try four.meme API ---
    try:
        data = await _api_get(f"v1/token/info", params={"address": contract})
        token_data = data.get("data") or data.get("token") or data
        if token_data and token_data.get("address", "").lower() == contract:
            return _parse_api_token(token_data)
    except Exception as e:
        logger.debug("four.meme API failed for %s: %s", contract, e)

    # --- Fallback: on-chain log scan for TokenCreated event ---
    try:
        return await _get_token_from_logs(contract)
    except Exception as e:
        logger.debug("On-chain fallback failed for %s: %s", contract, e)
        return None


def _parse_api_token(d: Dict) -> FourMemeToken:
    socials = {}
    for key in ("twitter", "telegram", "website", "discord"):
        val = d.get(key) or d.get(f"social_{key}")
        if val:
            socials[key] = val

    launch_ts = int(d.get("createTime", 0) or d.get("launch_time", 0) or 0)
    if launch_ts > 10**12:
        launch_ts //= 1000  # ms → s

    grad_ts = int(d.get("graduationTime", 0) or 0)
    if grad_ts > 10**12:
        grad_ts //= 1000

    return FourMemeToken(
        contract=d.get("address", "").lower(),
        symbol=d.get("symbol", ""),
        name=d.get("name", ""),
        description=d.get("description", ""),
        creator=d.get("creator", "").lower(),
        launch_ts=launch_ts,
        initial_supply=float(d.get("initialSupply", 0) or 0),
        initial_liquidity_bnb=float(d.get("initialLiquidity", 0) or 0),
        bonding_curve_pct=float(d.get("progress", 0) or d.get("bondingCurvePct", 0) or 0),
        graduated=bool(d.get("graduated") or d.get("isGraduated") or grad_ts > 0),
        graduation_ts=grad_ts,
        market_cap_usd=float(d.get("marketCap", 0) or 0),
        holders=int(d.get("holders", 0) or 0),
        socials=socials,
        image_url=d.get("imageUrl", "") or d.get("logo", ""),
    )


async def _get_token_from_logs(contract: str) -> Optional[FourMemeToken]:
    """
    Scan BSC event logs for four.meme factory TokenCreated events
    and find the creation block/timestamp for this contract.
    """
    params = {
        "fromBlock": "0x1A00000",  # ~mid 2023, when four.meme launched
        "toBlock": "latest",
        "address": FOUR_MEME_FACTORY,
        "topics": [TOKEN_CREATED_TOPIC],
    }
    logs = await _rpc_call("eth_getLogs", [params])
    if not logs:
        return None

    for log in logs:
        # Token address is usually in the data or topics[1]
        topics = log.get("topics", [])
        data = log.get("data", "")
        # Check if this log references our contract
        contract_in_topics = any(contract[2:].lower() in t.lower() for t in topics if t)
        contract_in_data = contract[2:].lower() in data.lower()
        if not (contract_in_topics or contract_in_data):
            continue

        block_hex = log.get("blockNumber", "0x0")
        block_num = int(block_hex, 16)

        # Get block timestamp
        block_data = await _rpc_call("eth_getBlockByNumber", [block_hex, False])
        ts = int(block_data.get("timestamp", "0x0"), 16) if block_data else 0

        return FourMemeToken(
            contract=contract,
            symbol="",
            name="",
            description="",
            creator="",
            launch_ts=ts,
            initial_supply=0.0,
            initial_liquidity_bnb=0.0,
            bonding_curve_pct=0.0,
            graduated=False,
            graduation_ts=0,
            market_cap_usd=0.0,
            holders=0,
        )

    return None


async def search_recent_launches(limit: int = 20, sort: str = "new") -> List[FourMemeToken]:
    """
    Fetch recently launched tokens on four.meme.

    sort: "new" (newest first) | "trending" | "graduating" (close to DEX graduation)
    """
    sort_map = {"new": "createTime", "trending": "volume", "graduating": "progress"}
    sort_field = sort_map.get(sort, "createTime")

    try:
        data = await _api_get("v1/token/list", params={
            "sortBy": sort_field,
            "order": "desc",
            "limit": limit,
            "chain": "bsc",
        })
        items = data.get("data", {}).get("list") or data.get("tokens") or []
        return [_parse_api_token(t) for t in items]
    except Exception as e:
        logger.debug("four.meme search_recent_launches failed: %s", e)
        return []


async def get_tokens_by_creator(creator_wallet: str) -> List[FourMemeToken]:
    """Fetch all tokens deployed by a given wallet on four.meme."""
    creator_wallet = creator_wallet.strip().lower()
    try:
        data = await _api_get("v1/token/list", params={
            "creator": creator_wallet,
            "limit": 50,
            "chain": "bsc",
        })
        items = data.get("data", {}).get("list") or data.get("tokens") or []
        return [_parse_api_token(t) for t in items]
    except Exception as e:
        logger.debug("four.meme get_tokens_by_creator failed: %s", e)
        return []


async def compute_entry_timing(
    wallet: str,
    trades: list,  # List[Trade] from bscscan_adapter
    days: int = 90,
) -> List[KOLEntryTiming]:
    """
    For each token the KOL bought, compute how many hours after
    four.meme launch they entered.

    trades: resolved Trade list from bscscan_adapter.get_all_trades()
    Returns list of KOLEntryTiming, one per unique token.
    """
    buys = [t for t in trades if t.side == "buy"]
    # Group by token, take first buy
    first_buys: Dict[str, Any] = {}
    for trade in sorted(buys, key=lambda t: t.timestamp):
        if trade.token_contract not in first_buys:
            first_buys[trade.token_contract] = trade

    results = []
    for contract, trade in list(first_buys.items())[:30]:  # cap at 30
        try:
            token_info = await get_token_launch_info(contract)
            if not token_info or token_info.launch_ts == 0:
                continue

            hours_after = (trade.timestamp - token_info.launch_ts) / 3600
            if hours_after < 0:
                continue  # data inconsistency

            results.append(KOLEntryTiming(
                wallet=wallet,
                token_contract=contract,
                token_symbol=trade.token_symbol,
                launch_ts=token_info.launch_ts,
                first_buy_ts=trade.timestamp,
                hours_after_launch=round(hours_after, 2),
                is_pre_graduation=not token_info.graduated or (
                    token_info.graduation_ts > 0
                    and trade.timestamp < token_info.graduation_ts
                ),
                bonding_curve_pct_at_entry=token_info.bonding_curve_pct
                if hours_after < 24 else 0.0,
            ))
            await asyncio.sleep(0.2)
        except Exception as e:
            logger.debug("Entry timing failed for %s: %s", contract, e)

    return results


def avg_hours_after_launch(timings: List[KOLEntryTiming]) -> float:
    """Return average hours-after-launch across all timings."""
    if not timings:
        return 0.0
    return sum(t.hours_after_launch for t in timings) / len(timings)


def pre_graduation_rate(timings: List[KOLEntryTiming]) -> float:
    """Fraction of entries made before DEX graduation (0.0–1.0)."""
    if not timings:
        return 0.0
    return sum(1 for t in timings if t.is_pre_graduation) / len(timings)
