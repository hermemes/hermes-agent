"""KOL Correlation & Co-movement Analyzer.

Detects coordinated buying patterns across the KOL pool:
- Which KOLs are buying the same tokens in the same time window (共振)
- Wallet-to-wallet correlation matrix (pairwise token overlap)
- "Smart money convergence" alerts when 3+ KOLs enter the same token

Registered tools:
  kol_correlation_matrix  — pairwise correlation for all KOL pool wallets
  kol_comovement_scan     — find tokens bought by multiple KOLs recently
  kol_wallet_overlap      — compare two wallets' trading overlap
"""

import asyncio
import json
import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from tools.bscscan_adapter import Trade, get_all_trades
from tools.registry import registry

logger = logging.getLogger(__name__)

_COMOVEMENT_WINDOW_HOURS = 24   # tokens bought within this window are "co-moves"
_MIN_BNB_FOR_SIGNAL = 0.2       # ignore dust trades


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class WalletPairOverlap:
    wallet_a: str
    wallet_b: str
    shared_tokens: List[str]
    shared_symbols: List[str]
    jaccard_similarity: float    # |intersection| / |union|
    time_correlation: float      # 0-1: how often they buy within same 24h window
    total_tokens_a: int
    total_tokens_b: int


@dataclass
class ComovementSignal:
    token_contract: str
    token_symbol: str
    buyers: List[str]            # wallets that bought this token
    buyer_grades: List[str]      # KOL grades of each buyer
    earliest_buy_ts: int
    latest_buy_ts: int
    window_hours: float          # spread of buys in hours
    total_bnb_combined: float
    signal_strength: float       # 0-100, higher = more notable


@dataclass
class CorrelationMatrix:
    wallets: List[str]
    pairs: List[WalletPairOverlap]
    generated_at: int
    lookback_days: int


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _jaccard(set_a: Set[str], set_b: Set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union > 0 else 0.0


def _time_correlation(
    trades_a: List[Trade],
    trades_b: List[Trade],
    window_seconds: int = 86400,
) -> float:
    """
    Fraction of wallet_a's buy days where wallet_b also bought
    within the same ±window_seconds period.
    """
    buys_a = [t for t in trades_a if t.side == "buy" and t.bnb_value >= _MIN_BNB_FOR_SIGNAL]
    buys_b = [t for t in trades_b if t.side == "buy" and t.bnb_value >= _MIN_BNB_FOR_SIGNAL]

    if not buys_a or not buys_b:
        return 0.0

    ts_b = [t.timestamp for t in buys_b]
    correlated = 0
    for ta in buys_a:
        for tb in ts_b:
            if abs(ta.timestamp - tb) <= window_seconds:
                correlated += 1
                break

    return correlated / len(buys_a)


def _compute_pair_overlap(
    wallet_a: str,
    trades_a: List[Trade],
    wallet_b: str,
    trades_b: List[Trade],
) -> WalletPairOverlap:
    tokens_a = {
        t.token_contract: t.token_symbol
        for t in trades_a
        if t.side == "buy" and t.bnb_value >= _MIN_BNB_FOR_SIGNAL
    }
    tokens_b = {
        t.token_contract: t.token_symbol
        for t in trades_b
        if t.side == "buy" and t.bnb_value >= _MIN_BNB_FOR_SIGNAL
    }

    shared_contracts = set(tokens_a.keys()) & set(tokens_b.keys())
    shared_symbols = [tokens_a[c] for c in shared_contracts]
    jaccard = _jaccard(set(tokens_a.keys()), set(tokens_b.keys()))
    time_corr = _time_correlation(trades_a, trades_b)

    return WalletPairOverlap(
        wallet_a=wallet_a,
        wallet_b=wallet_b,
        shared_tokens=list(shared_contracts),
        shared_symbols=shared_symbols,
        jaccard_similarity=round(jaccard, 4),
        time_correlation=round(time_corr, 4),
        total_tokens_a=len(tokens_a),
        total_tokens_b=len(tokens_b),
    )


def _comovement_signals(
    wallet_trades: Dict[str, List[Trade]],
    window_hours: int = _COMOVEMENT_WINDOW_HOURS,
    min_wallets: int = 2,
    kol_grades: Optional[Dict[str, str]] = None,
) -> List[ComovementSignal]:
    """
    Find tokens bought by ≥ min_wallets KOLs within window_hours of each other.
    """
    kol_grades = kol_grades or {}
    window_s = window_hours * 3600

    # token_contract → list of (wallet, timestamp, bnb_value)
    token_buyers: Dict[str, List[Tuple[str, int, float]]] = defaultdict(list)

    for wallet, trades in wallet_trades.items():
        for t in trades:
            if t.side == "buy" and t.bnb_value >= _MIN_BNB_FOR_SIGNAL:
                token_buyers[t.token_contract].append(
                    (wallet, t.timestamp, t.bnb_value, t.token_symbol)
                )

    signals = []
    for contract, entries in token_buyers.items():
        if len({e[0] for e in entries}) < min_wallets:
            continue

        # Sort by time and find clusters
        entries.sort(key=lambda e: e[1])
        symbol = entries[0][3]
        earliest = entries[0][1]
        latest = entries[-1][1]
        window_actual = (latest - earliest) / 3600

        if window_actual > window_hours:
            continue

        wallets = list({e[0] for e in entries})
        grades = [kol_grades.get(w, "?") for w in wallets]
        total_bnb = sum(e[2] for e in entries)

        # Signal strength: more wallets + higher grades + smaller window = stronger
        grade_bonus = sum({"A+": 20, "A": 15, "B": 10, "C": 5, "?": 0}.get(g, 0) for g in grades)
        wallet_bonus = len(wallets) * 15
        time_bonus = max(0, 20 - window_actual)  # tighter window = stronger
        strength = min(100.0, wallet_bonus + grade_bonus + time_bonus)

        signals.append(ComovementSignal(
            token_contract=contract,
            token_symbol=symbol,
            buyers=wallets,
            buyer_grades=grades,
            earliest_buy_ts=earliest,
            latest_buy_ts=latest,
            window_hours=round(window_actual, 2),
            total_bnb_combined=round(total_bnb, 4),
            signal_strength=round(strength, 1),
        ))

    return sorted(signals, key=lambda s: s.signal_strength, reverse=True)


# ---------------------------------------------------------------------------
# KOL pool loader (reuse from bsc_kol_tool)
# ---------------------------------------------------------------------------

def _load_kol_pool(filepath: str = "kol-pool.md"):
    from tools.bsc_kol_tool import _load_kol_pool as _inner
    return _inner(filepath)


# ---------------------------------------------------------------------------
# Async handlers
# ---------------------------------------------------------------------------

async def _handle_correlation_matrix(
    pool_file: str,
    days: int,
    max_wallets: int,
) -> str:
    wallets = _load_kol_pool(pool_file)
    if not wallets:
        return f"❌ 找不到 KOL 池文件 '{pool_file}'"

    wallets = wallets[:max_wallets]
    addrs = [w["address"] for w in wallets]

    # Fetch all trade histories in parallel (batched to avoid rate limits)
    all_trades: Dict[str, List[Trade]] = {}
    for i in range(0, len(addrs), 5):
        batch = addrs[i:i+5]
        results = await asyncio.gather(
            *[get_all_trades(addr, days=days) for addr in batch],
            return_exceptions=True,
        )
        for addr, result in zip(batch, results):
            if isinstance(result, Exception):
                all_trades[addr] = []
            else:
                all_trades[addr] = result
        if i + 5 < len(addrs):
            await asyncio.sleep(1.0)

    # Compute all pairs
    pairs = []
    for i, wa in enumerate(addrs):
        for wb in addrs[i+1:]:
            pair = _compute_pair_overlap(wa, all_trades[wa], wb, all_trades[wb])
            if pair.jaccard_similarity > 0 or pair.time_correlation > 0:
                pairs.append(pair)

    pairs.sort(key=lambda p: p.jaccard_similarity + p.time_correlation, reverse=True)

    output = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M UTC"),
        "wallets": len(addrs),
        "lookback_days": days,
        "top_correlated_pairs": [
            {
                "wallet_a": p.wallet_a[:8] + "..." + p.wallet_a[-4:],
                "wallet_b": p.wallet_b[:8] + "..." + p.wallet_b[-4:],
                "shared_tokens": len(p.shared_tokens),
                "shared_symbols": p.shared_symbols[:10],
                "jaccard": f"{p.jaccard_similarity*100:.1f}%",
                "time_correlation": f"{p.time_correlation*100:.1f}%",
            }
            for p in pairs[:20]
        ],
        "total_pairs": len(pairs),
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


async def _handle_comovement_scan(
    pool_file: str,
    days: int,
    window_hours: int,
    min_wallets: int,
) -> str:
    wallets = _load_kol_pool(pool_file)
    if not wallets:
        return f"❌ 找不到 KOL 池文件 '{pool_file}'"

    addrs = [w["address"] for w in wallets[:50]]

    # Load grades from state if available
    kol_grades: Dict[str, str] = {}
    try:
        import json as _json
        from pathlib import Path
        state_path = Path.home() / ".hermes" / "kol_pool_state.json"
        if state_path.exists():
            state = _json.loads(state_path.read_text())
            for addr in addrs:
                kol_grades[addr] = state.get(addr, {}).get("grade", "?")
    except Exception:
        pass

    # Fetch trades
    all_trades: Dict[str, List[Trade]] = {}
    for i in range(0, len(addrs), 5):
        batch = addrs[i:i+5]
        results = await asyncio.gather(
            *[get_all_trades(addr, days=days) for addr in batch],
            return_exceptions=True,
        )
        for addr, result in zip(batch, results):
            all_trades[addr] = [] if isinstance(result, Exception) else result
        if i + 5 < len(addrs):
            await asyncio.sleep(0.8)

    signals = _comovement_signals(all_trades, window_hours=window_hours,
                                  min_wallets=min_wallets, kol_grades=kol_grades)

    since_ts = int(time.time()) - days * 86400
    recent = [s for s in signals if s.earliest_buy_ts >= since_ts]

    output = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M UTC"),
        "wallets_scanned": len(addrs),
        "lookback_days": days,
        "window_hours": window_hours,
        "min_wallets_threshold": min_wallets,
        "comovement_signals": [
            {
                "token": s.token_symbol,
                "contract": s.token_contract,
                "buyers": len(s.buyers),
                "buyer_grades": s.buyer_grades,
                "buyer_wallets": [f"{w[:8]}...{w[-4:]}" for w in s.buyers],
                "window_hours": s.window_hours,
                "total_bnb": s.total_bnb_combined,
                "signal_strength": s.signal_strength,
                "earliest": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(s.earliest_buy_ts)),
                "latest": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(s.latest_buy_ts)),
            }
            for s in recent[:30]
        ],
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


async def _handle_wallet_overlap(
    wallet_a: str,
    wallet_b: str,
    days: int,
) -> str:
    trades_a, trades_b = await asyncio.gather(
        get_all_trades(wallet_a, days=days),
        get_all_trades(wallet_b, days=days),
    )
    pair = _compute_pair_overlap(wallet_a, trades_a, wallet_b, trades_b)

    output = {
        "wallet_a": wallet_a,
        "wallet_b": wallet_b,
        "lookback_days": days,
        "jaccard_similarity": f"{pair.jaccard_similarity*100:.1f}%",
        "time_correlation": f"{pair.time_correlation*100:.1f}%",
        "shared_tokens": len(pair.shared_tokens),
        "shared_symbols": pair.shared_symbols,
        "total_tokens_a": pair.total_tokens_a,
        "total_tokens_b": pair.total_tokens_b,
        "interpretation": (
            "高度相关（共振明显）" if pair.jaccard_similarity > 0.3
            else "中等相关" if pair.jaccard_similarity > 0.15
            else "低相关（独立决策为主）"
        ),
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Sync wrappers
# ---------------------------------------------------------------------------

def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result(timeout=180)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def kol_correlation_matrix(pool_file: str = "kol-pool.md", days: int = 30, max_wallets: int = 30) -> str:
    return _run(_handle_correlation_matrix(pool_file, days, max_wallets))


def kol_comovement_scan(pool_file: str = "kol-pool.md", days: int = 7, window_hours: int = 24, min_wallets: int = 2) -> str:
    return _run(_handle_comovement_scan(pool_file, days, window_hours, min_wallets))


def kol_wallet_overlap(wallet_a: str, wallet_b: str, days: int = 30) -> str:
    return _run(_handle_wallet_overlap(wallet_a, wallet_b, days))


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

registry.register(
    name="kol_correlation_matrix",
    toolset="kol",
    schema={
        "type": "function",
        "function": {
            "name": "kol_correlation_matrix",
            "description": (
                "Compute pairwise trading correlation for all wallets in the KOL pool. "
                "Returns Jaccard similarity (shared token overlap) and time-correlation "
                "(how often two KOLs buy within 24h of each other). Useful for identifying "
                "coordinated wallets or KOLs that consistently move together."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pool_file": {"type": "string", "default": "kol-pool.md"},
                    "days": {"type": "integer", "default": 30, "description": "Lookback days"},
                    "max_wallets": {"type": "integer", "default": 30, "description": "Max wallets to compare"},
                },
                "required": [],
            },
        },
    },
    handler=kol_correlation_matrix,
    description="Pairwise KOL wallet trading correlation matrix",
    emoji="🔗",
    requires_env=["BSCSCAN_API_KEY"],
)

registry.register(
    name="kol_comovement_scan",
    toolset="kol",
    schema={
        "type": "function",
        "function": {
            "name": "kol_comovement_scan",
            "description": (
                "Scan the KOL pool for co-movement signals: tokens where multiple KOLs "
                "bought within the same time window. Returns ranked signals by strength — "
                "higher strength means more KOLs, better grades, and tighter time clustering. "
                "Use for 'smart money convergence' detection."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pool_file": {"type": "string", "default": "kol-pool.md"},
                    "days": {"type": "integer", "default": 7, "description": "Lookback days"},
                    "window_hours": {"type": "integer", "default": 24, "description": "Max hours between first and last buy to count as co-movement"},
                    "min_wallets": {"type": "integer", "default": 2, "description": "Minimum number of KOLs that must buy the same token"},
                },
                "required": [],
            },
        },
    },
    handler=kol_comovement_scan,
    description="Detect tokens multiple KOLs bought in the same time window",
    emoji="⚡",
    requires_env=["BSCSCAN_API_KEY"],
)

registry.register(
    name="kol_wallet_overlap",
    toolset="kol",
    schema={
        "type": "function",
        "function": {
            "name": "kol_wallet_overlap",
            "description": (
                "Compare trading overlap between two specific BSC wallets. "
                "Returns shared tokens, Jaccard similarity, and time-correlation. "
                "Useful for checking if a new wallet is highly correlated with a known KOL."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "wallet_a": {"type": "string", "description": "First BSC wallet address"},
                    "wallet_b": {"type": "string", "description": "Second BSC wallet address"},
                    "days": {"type": "integer", "default": 30},
                },
                "required": ["wallet_a", "wallet_b"],
            },
        },
    },
    handler=kol_wallet_overlap,
    description="Compare trading overlap between two BSC wallets",
    emoji="🔗",
    requires_env=["BSCSCAN_API_KEY"],
)
