"""DexScreener + PancakeSwap Adapter — price, MCAP and pool data for BSC tokens.

Used by the KOL profiler to enrich trade records with MCAP-at-trade-time
estimates and current token metrics.

DexScreener API: https://docs.dexscreener.com/api/reference
PancakeSwap subgraph: https://thegraph.com/explorer/subgraphs/EsFMC5564n77u8EKc5WxaHCbz3pnJNr4SFkGFjxRWD8c
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_DSC_BASE = "https://api.dexscreener.com/latest/dex"
_TIMEOUT = 15.0
_CACHE: Dict[str, Any] = {}
_CACHE_TTL = 60  # seconds for price cache


@dataclass
class TokenMetrics:
    contract: str
    symbol: str
    name: str
    chain: str
    price_usd: float
    price_bnb: float          # approximate
    mcap_usd: float
    fdv_usd: float
    liquidity_usd: float
    volume_24h_usd: float
    price_change_1h_pct: float
    price_change_6h_pct: float
    price_change_24h_pct: float
    dex: str
    pair_address: str
    updated_at: int           # unix timestamp


@dataclass
class HistoricalMcap:
    """Approximate MCAP at a given timestamp using DexScreener OHLCV candles."""
    contract: str
    timestamp: int
    price_usd: float
    estimated_mcap_usd: float  # price_usd * circulating_supply (if available)


async def _dsc_get(path: str, params: Dict = None) -> Dict:
    url = f"{_DSC_BASE}/{path}"
    cache_key = f"{url}:{params}"
    cached = _CACHE.get(cache_key)
    if cached and time.time() - cached["ts"] < _CACHE_TTL:
        return cached["data"]

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params or {})
        resp.raise_for_status()
        data = resp.json()
        _CACHE[cache_key] = {"ts": time.time(), "data": data}
        return data


def _best_bsc_pair(pairs: List[Dict]) -> Optional[Dict]:
    """Pick the highest-liquidity BSC pair from DexScreener results."""
    bsc_pairs = [p for p in pairs if p.get("chainId") == "bsc"]
    if not bsc_pairs:
        return None
    return max(bsc_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))


async def get_token_metrics(contract: str) -> Optional[TokenMetrics]:
    """Fetch current price, MCAP, liquidity for a BSC token."""
    try:
        data = await _dsc_get(f"tokens/{contract}")
        pairs = data.get("pairs") or []
        pair = _best_bsc_pair(pairs)
        if not pair:
            return None

        base = pair.get("baseToken", {})
        info = pair.get("info", {})
        priceUsd = float(pair.get("priceUsd", 0) or 0)
        priceNative = float(pair.get("priceNative", 0) or 0)
        mc = pair.get("marketCap") or pair.get("fdv") or 0
        fdv = pair.get("fdv") or 0
        liq = (pair.get("liquidity") or {}).get("usd") or 0
        vol = (pair.get("volume") or {}).get("h24") or 0
        pc = pair.get("priceChange") or {}

        return TokenMetrics(
            contract=contract.lower(),
            symbol=base.get("symbol", ""),
            name=base.get("name", ""),
            chain="bsc",
            price_usd=priceUsd,
            price_bnb=priceNative,
            mcap_usd=float(mc),
            fdv_usd=float(fdv),
            liquidity_usd=float(liq),
            volume_24h_usd=float(vol),
            price_change_1h_pct=float(pc.get("h1", 0) or 0),
            price_change_6h_pct=float(pc.get("h6", 0) or 0),
            price_change_24h_pct=float(pc.get("h24", 0) or 0),
            dex=pair.get("dexId", ""),
            pair_address=pair.get("pairAddress", ""),
            updated_at=int(time.time()),
        )
    except Exception as e:
        logger.debug("DexScreener get_token_metrics failed for %s: %s", contract, e)
        return None


async def search_token(query: str, chain: str = "bsc") -> List[TokenMetrics]:
    """Search for tokens by name or symbol."""
    try:
        data = await _dsc_get("search", params={"q": query})
        pairs = data.get("pairs") or []
        results = []
        seen = set()
        for pair in pairs:
            if pair.get("chainId") != chain:
                continue
            contract = (pair.get("baseToken") or {}).get("address", "").lower()
            if contract in seen:
                continue
            seen.add(contract)
            base = pair.get("baseToken", {})
            priceUsd = float(pair.get("priceUsd", 0) or 0)
            mc = pair.get("marketCap") or pair.get("fdv") or 0
            liq = (pair.get("liquidity") or {}).get("usd") or 0
            vol = (pair.get("volume") or {}).get("h24") or 0
            pc = pair.get("priceChange") or {}
            results.append(TokenMetrics(
                contract=contract,
                symbol=base.get("symbol", ""),
                name=base.get("name", ""),
                chain=chain,
                price_usd=priceUsd,
                price_bnb=float(pair.get("priceNative", 0) or 0),
                mcap_usd=float(mc),
                fdv_usd=float(pair.get("fdv") or 0),
                liquidity_usd=float(liq),
                volume_24h_usd=float(vol),
                price_change_1h_pct=float(pc.get("h1", 0) or 0),
                price_change_6h_pct=float(pc.get("h6", 0) or 0),
                price_change_24h_pct=float(pc.get("h24", 0) or 0),
                dex=pair.get("dexId", ""),
                pair_address=pair.get("pairAddress", ""),
                updated_at=int(time.time()),
            ))
        return results[:10]
    except Exception as e:
        logger.debug("DexScreener search failed for %s: %s", query, e)
        return []


async def get_token_mcap(contract: str) -> float:
    """Quick helper — return current MCAP in USD, 0 if unavailable."""
    m = await get_token_metrics(contract)
    return m.mcap_usd if m else 0.0


async def get_ohlcv_candles(
    pair_address: str,
    timeframe: str = "1h",
    from_ts: int = 0,
    to_ts: int = 0,
    limit: int = 200,
) -> List[Dict]:
    """
    Fetch OHLCV candles for a pair.

    timeframe: 1m, 5m, 15m, 1h, 4h, 1d
    Returns list of {"timestamp", "open", "high", "low", "close", "volume"}
    """
    try:
        params: Dict[str, Any] = {"q": pair_address}
        # DexScreener candle endpoint (undocumented but stable)
        url = f"https://io.dexscreener.com/dex/chart/amm/v3/bsc/{pair_address}"
        params = {"res": timeframe, "cb": int(time.time())}
        if from_ts:
            params["from"] = from_ts
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()
        candles = data.get("bars") or []
        result = []
        for c in candles[-limit:]:
            result.append({
                "timestamp": c.get("t", 0),
                "open": float(c.get("o", 0)),
                "high": float(c.get("h", 0)),
                "low": float(c.get("l", 0)),
                "close": float(c.get("c", 0)),
                "volume": float(c.get("v", 0)),
            })
        return result
    except Exception as e:
        logger.debug("OHLCV fetch failed for %s: %s", pair_address, e)
        return []


async def estimate_mcap_at_timestamp(
    contract: str,
    target_ts: int,
) -> float:
    """
    Estimate MCAP at a historical timestamp by fetching nearest candle.
    Returns USD estimate, 0 if data unavailable.
    """
    metrics = await get_token_metrics(contract)
    if not metrics or not metrics.pair_address:
        return 0.0

    candles = await get_ohlcv_candles(
        pair_address=metrics.pair_address,
        timeframe="1h",
        from_ts=target_ts - 3600,
        to_ts=target_ts + 3600,
        limit=5,
    )
    if not candles:
        return 0.0

    # Find nearest candle
    nearest = min(candles, key=lambda c: abs(c["timestamp"] - target_ts))
    price_at_ts = nearest["close"]

    if metrics.mcap_usd > 0 and metrics.price_usd > 0:
        implied_supply = metrics.mcap_usd / metrics.price_usd
        return price_at_ts * implied_supply

    return 0.0


async def enrich_trades_with_mcap(trades: list) -> list:
    """
    Add mcap_usd to each Trade object where possible.
    Batches contract lookups to avoid hammering the API.
    """
    contracts = list({t.token_contract for t in trades})
    metrics_map: Dict[str, Optional[TokenMetrics]] = {}

    for i in range(0, len(contracts), 5):
        batch = contracts[i:i+5]
        results = await asyncio.gather(
            *[get_token_metrics(c) for c in batch],
            return_exceptions=True,
        )
        for contract, result in zip(batch, results):
            metrics_map[contract] = result if not isinstance(result, Exception) else None
        if i + 5 < len(contracts):
            await asyncio.sleep(0.5)

    for trade in trades:
        m = metrics_map.get(trade.token_contract)
        if m:
            trade.current_mcap_usd = m.mcap_usd
            trade.current_price_usd = m.price_usd
        else:
            trade.current_mcap_usd = 0.0
            trade.current_price_usd = 0.0

    return trades
