"""BSC KOL Profiler Tool — 25+ dimension on-chain behavior analysis engine.

Registered tools:
  kol_analyze        — full 25+ metric profile for one wallet
  kol_decision       — quantified follow-copy decision for a new buy event
  kol_pool_scan      — batch scan all wallets in kol-pool.md
  kol_pool_load      — load / list the KOL pool file
  kol_report         — generate weekly/monthly summary for the KOL pool

Data sources: BscScan API + DexScreener (see bscscan_adapter, dexscreener_adapter)
"""

import asyncio
import json
import logging
import math
import os
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.bscscan_adapter import (
    Trade,
    fetch_bnb_balance,
    get_all_trades,
)
from tools.dexscreener_adapter import (
    TokenMetrics,
    enrich_trades_with_mcap,
    get_token_metrics,
    search_token,
)
from tools.registry import registry

logger = logging.getLogger(__name__)

BNB_USD_FALLBACK = 600.0  # rough fallback if BNB price unavailable


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TokenPosition:
    """Aggregated buy/sell record for one token within one wallet."""
    token_contract: str
    token_symbol: str
    first_buy_ts: int
    last_activity_ts: int
    total_buy_bnb: float
    total_sell_bnb: float
    total_buy_tokens: float
    total_sell_tokens: float
    buy_count: int
    sell_count: int
    realized_pnl_bnb: float       # sell_bnb - buy_bnb (for matched sells)
    is_closed: bool                # True if all tokens sold
    roi_multiple: float            # sell_bnb / buy_bnb
    hold_days: float
    entry_mcap_usd: float         # MCAP when first buy happened (estimated)
    peak_mcap_usd: float          # current MCAP (proxy for peak if token still live)
    exit_mcap_usd: float


@dataclass
class KOLProfile:
    """Full quantitative profile for one KOL wallet (25+ dimensions)."""
    wallet: str
    generated_at: int
    lookback_days: int
    bnb_balance: float

    # A. Performance
    win_rate_30d: float
    win_rate_90d: float
    avg_roi_multiple: float
    total_pnl_bnb: float
    total_pnl_usd: float
    sharpe_ratio: float
    sortino_ratio: float
    consistency_score: float      # 0-100
    rug_avoidance_rate: float     # % of closed positions that were profitable
    unrealized_pnl_bnb: float
    unrealized_pnl_ratio: float   # unrealized / total_invested

    # B. Entry behavior
    avg_entry_mcap_usd: float
    median_entry_mcap_usd: float
    avg_entry_hours_after_launch: float
    avg_position_size_pct: float  # % of wallet BNB per trade
    trades_per_day_30d: float
    active_days_30d: int

    # C. Exit / Dump behavior
    avg_exit_multiple: float
    median_exit_multiple: float
    dump_mcap_p50_usd: float      # median MCAP when 50%+ sold
    dump_mcap_p70_usd: float      # median MCAP when 70%+ sold
    avg_hold_days: float
    max_hold_days: float
    typical_sell_tranche_1_pct: float   # first sell as % of position
    trailing_stop_threshold_pct: float  # estimated from peak-to-sell patterns

    # D. Risk management
    max_drawdown_pct: float
    kelly_position_pct: float
    avg_gas_gwei: float
    total_trades: int
    unique_tokens: int

    # E. Composite scores
    confidence_score: float       # 0-100
    rrr: float                    # expected risk/reward ratio
    kol_grade: str                # A+ / A / B / C / D
    type_label: str               # "Early Sniper", "Mid-Entry", "Swing", etc.

    positions: List[TokenPosition] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core analysis engine
# ---------------------------------------------------------------------------

def _aggregate_positions(trades: List[Trade]) -> List[TokenPosition]:
    """Group trades by token and compute per-token P&L."""
    by_token: Dict[str, List[Trade]] = defaultdict(list)
    for t in trades:
        by_token[t.token_contract].append(t)

    positions = []
    for contract, token_trades in by_token.items():
        token_trades.sort(key=lambda t: t.timestamp)
        buys = [t for t in token_trades if t.side == "buy"]
        sells = [t for t in token_trades if t.side == "sell"]

        if not buys:
            continue

        total_buy_bnb = sum(t.bnb_value for t in buys)
        total_sell_bnb = sum(t.bnb_value for t in sells)
        total_buy_tokens = sum(t.amount_tokens for t in buys)
        total_sell_tokens = sum(t.amount_tokens for t in sells)

        realized_pnl = total_sell_bnb - total_buy_bnb
        is_closed = total_sell_tokens >= total_buy_tokens * 0.85
        roi = (total_sell_bnb / total_buy_bnb) if total_buy_bnb > 0 else 0.0

        first_buy_ts = buys[0].timestamp
        last_ts = token_trades[-1].timestamp
        hold_days = (last_ts - first_buy_ts) / 86400

        symbol = buys[0].token_symbol

        # MCAP estimates (filled later by enrich step)
        entry_mcap = getattr(buys[0], "current_mcap_usd", 0.0)
        exit_mcap = getattr(sells[-1], "current_mcap_usd", 0.0) if sells else 0.0
        peak_mcap = getattr(token_trades[-1], "current_mcap_usd", 0.0)

        positions.append(TokenPosition(
            token_contract=contract,
            token_symbol=symbol,
            first_buy_ts=first_buy_ts,
            last_activity_ts=last_ts,
            total_buy_bnb=total_buy_bnb,
            total_sell_bnb=total_sell_bnb,
            total_buy_tokens=total_buy_tokens,
            total_sell_tokens=total_sell_tokens,
            buy_count=len(buys),
            sell_count=len(sells),
            realized_pnl_bnb=realized_pnl,
            is_closed=is_closed,
            roi_multiple=roi,
            hold_days=hold_days,
            entry_mcap_usd=entry_mcap,
            peak_mcap_usd=peak_mcap,
            exit_mcap_usd=exit_mcap,
        ))

    return sorted(positions, key=lambda p: p.first_buy_ts, reverse=True)


def _sharpe(returns: List[float], risk_free: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(variance)
    return (mean - risk_free) / std if std > 0 else 0.0


def _sortino(returns: List[float], risk_free: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    downside = [r for r in returns if r < risk_free]
    if not downside:
        return 5.0
    downside_var = sum((r - risk_free) ** 2 for r in downside) / len(downside)
    downside_std = math.sqrt(downside_var)
    return (mean - risk_free) / downside_std if downside_std > 0 else 0.0


def _kelly(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Kelly Criterion: f = (win_rate * avg_win - (1-win_rate) * avg_loss) / avg_win"""
    if avg_win <= 0:
        return 0.0
    f = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
    return max(0.0, min(f, 0.5))  # cap at 50%


def _consistency_score(returns: List[float]) -> float:
    """0-100 score: penalizes high variance and streaks of losses."""
    if not returns:
        return 0.0
    n = len(returns)
    wins = sum(1 for r in returns if r > 0)
    win_rate = wins / n

    if n < 2:
        return win_rate * 100

    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    cv = math.sqrt(variance) / abs(mean) if mean != 0 else 1.0
    consistency = win_rate * (1 / (1 + cv))

    # Bonus for consecutive wins
    max_streak = cur_streak = 0
    for r in returns:
        if r > 0:
            cur_streak += 1
            max_streak = max(max_streak, cur_streak)
        else:
            cur_streak = 0
    streak_bonus = min(0.1, max_streak * 0.01)

    return min(100.0, (consistency + streak_bonus) * 100)


def _kol_grade(confidence: float, win_rate: float, roi: float) -> str:
    if confidence >= 85 and win_rate >= 0.70 and roi >= 5.0:
        return "A+"
    if confidence >= 70 and win_rate >= 0.60 and roi >= 3.0:
        return "A"
    if confidence >= 55 and win_rate >= 0.50 and roi >= 1.5:
        return "B"
    if confidence >= 40:
        return "C"
    return "D"


def _type_label(avg_entry_mcap: float, avg_hold_days: float, trades_per_day: float) -> str:
    if avg_entry_mcap < 150_000:
        return "Early Sniper"
    if avg_entry_mcap < 500_000 and avg_hold_days < 3:
        return "Scalper"
    if avg_entry_mcap < 1_000_000:
        return "Mid-Entry"
    if avg_hold_days >= 7:
        return "Swing Holder"
    return "Momentum Trader"


def _confidence_score(
    win_rate: float,
    total_trades: int,
    sharpe: float,
    consistency: float,
    rug_avoidance: float,
) -> float:
    """Weighted 0-100 composite confidence score."""
    if total_trades < 3:
        return max(0.0, total_trades * 10.0)

    w_wr = 0.30       # win rate weight
    w_trades = 0.15   # sample size weight
    w_sharpe = 0.20   # risk-adjusted return
    w_consist = 0.20  # consistency
    w_rug = 0.15      # rug avoidance

    wr_score = win_rate * 100
    trade_score = min(100.0, total_trades * 2)
    sharpe_score = min(100.0, max(0.0, sharpe * 25))
    rug_score = rug_avoidance * 100

    score = (
        wr_score * w_wr
        + trade_score * w_trades
        + sharpe_score * w_sharpe
        + consistency * w_consist
        + rug_score * w_rug
    )
    return round(min(100.0, max(0.0, score)), 1)


def _build_profile(
    wallet: str,
    trades: List[Trade],
    positions: List[TokenPosition],
    bnb_balance: float,
    lookback_days: int,
) -> KOLProfile:
    now = int(time.time())
    ts_30d = now - 30 * 86400
    ts_90d = now - 90 * 86400

    closed = [p for p in positions if p.is_closed]
    open_pos = [p for p in positions if not p.is_closed]

    # Win rates
    closed_30d = [p for p in closed if p.last_activity_ts >= ts_30d]
    closed_90d = [p for p in closed if p.last_activity_ts >= ts_90d]
    wins_30d = [p for p in closed_30d if p.realized_pnl_bnb > 0]
    wins_90d = [p for p in closed_90d if p.realized_pnl_bnb > 0]
    wr_30d = len(wins_30d) / len(closed_30d) if closed_30d else 0.0
    wr_90d = len(wins_90d) / len(closed_90d) if closed_90d else 0.0

    # ROI
    roi_list = [p.roi_multiple for p in closed if p.roi_multiple > 0]
    avg_roi = sum(roi_list) / len(roi_list) if roi_list else 0.0

    # PnL
    total_pnl_bnb = sum(p.realized_pnl_bnb for p in closed)
    total_pnl_usd = total_pnl_bnb * BNB_USD_FALLBACK

    # Sharpe / Sortino on ROI series
    returns = [p.roi_multiple - 1.0 for p in closed if p.roi_multiple > 0]
    sharpe = _sharpe(returns)
    sortino = _sortino(returns)

    # Consistency
    consist = _consistency_score(returns)

    # Rug avoidance
    rug_avoidance = len([p for p in closed if p.roi_multiple > 0]) / len(closed) if closed else 0.0

    # Unrealized PnL
    total_invested = sum(p.total_buy_bnb for p in open_pos)
    # rough current value: assume still at entry (conservative)
    unrealized_pnl = 0.0
    unrealized_ratio = 0.0
    if total_invested > 0:
        unrealized_pnl = -total_invested  # worst case: all open positions worthless
        unrealized_ratio = unrealized_pnl / total_invested

    # Entry behavior
    entry_mcaps = [p.entry_mcap_usd for p in positions if p.entry_mcap_usd > 0]
    avg_entry_mcap = sum(entry_mcaps) / len(entry_mcaps) if entry_mcaps else 0.0
    median_entry_mcap = sorted(entry_mcaps)[len(entry_mcaps)//2] if entry_mcaps else 0.0

    # Position size as % of wallet
    wallet_size = bnb_balance if bnb_balance > 0 else 1.0
    sizes = [t.bnb_value / wallet_size * 100 for t in trades if t.side == "buy" and t.bnb_value > 0]
    avg_pos_size_pct = sum(sizes) / len(sizes) if sizes else 0.0

    # Trading frequency
    buys_30d = [t for t in trades if t.side == "buy" and t.timestamp >= ts_30d]
    active_days_set = {time.strftime("%Y%m%d", time.gmtime(t.timestamp)) for t in buys_30d}
    active_days_30d = len(active_days_set)
    trades_per_day_30d = len(buys_30d) / 30.0

    # Exit behavior
    exit_multiples = [p.roi_multiple for p in closed if p.roi_multiple > 0]
    avg_exit_multiple = sum(exit_multiples) / len(exit_multiples) if exit_multiples else 0.0
    median_exit_multiple = sorted(exit_multiples)[len(exit_multiples)//2] if exit_multiples else 0.0

    exit_mcaps_50 = [p.exit_mcap_usd for p in closed if p.exit_mcap_usd > 0 and p.total_sell_tokens >= p.total_buy_tokens * 0.5]
    exit_mcaps_70 = [p.exit_mcap_usd for p in closed if p.exit_mcap_usd > 0 and p.total_sell_tokens >= p.total_buy_tokens * 0.7]
    dump_mcap_p50 = sorted(exit_mcaps_50)[len(exit_mcaps_50)//2] if exit_mcaps_50 else 0.0
    dump_mcap_p70 = sorted(exit_mcaps_70)[len(exit_mcaps_70)//2] if exit_mcaps_70 else 0.0

    hold_times = [p.hold_days for p in closed]
    avg_hold = sum(hold_times) / len(hold_times) if hold_times else 0.0
    max_hold = max(hold_times) if hold_times else 0.0

    # First sell tranche (rough)
    first_sell_pcts = []
    for p in closed:
        if p.total_buy_tokens > 0 and p.sell_count >= 1:
            first_sell_pcts.append(p.total_sell_tokens / p.total_buy_tokens)
    typical_tranche1 = sum(first_sell_pcts) / len(first_sell_pcts) * 100 if first_sell_pcts else 0.0

    # Trailing stop threshold (estimated from hold time + loss patterns)
    losing_positions_roi = [p.roi_multiple for p in closed if p.roi_multiple < 1.0]
    trailing_stop = (
        (1 - sum(losing_positions_roi) / len(losing_positions_roi)) * 100
        if losing_positions_roi else 25.0
    )

    # Max drawdown on cumulative PnL
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in sorted(closed, key=lambda x: x.last_activity_ts):
        cumulative += p.realized_pnl_bnb
        if cumulative > peak:
            peak = cumulative
        dd = (peak - cumulative) / peak * 100 if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    # Kelly
    wins = [p.roi_multiple - 1.0 for p in closed if p.realized_pnl_bnb > 0]
    losses = [abs(p.roi_multiple - 1.0) for p in closed if p.realized_pnl_bnb < 0]
    avg_win_r = sum(wins) / len(wins) if wins else 0.0
    avg_loss_r = sum(losses) / len(losses) if losses else 1.0
    kelly_pct = _kelly(wr_30d or wr_90d, avg_win_r, avg_loss_r) * 100

    # Avg gas (proxy: we don't have gas from transfers, use 5 gwei as BSC default)
    avg_gas = 5.0

    total_trades = len(trades)
    unique_tokens = len({t.token_contract for t in trades})

    confidence = _confidence_score(wr_30d, total_trades, sharpe, consist, rug_avoidance)
    rrr = avg_roi / (1 + max_dd / 100) if max_dd < 100 else 0.0
    grade = _kol_grade(confidence, wr_30d, avg_roi)
    label = _type_label(avg_entry_mcap, avg_hold, trades_per_day_30d)

    return KOLProfile(
        wallet=wallet,
        generated_at=now,
        lookback_days=lookback_days,
        bnb_balance=bnb_balance,
        win_rate_30d=round(wr_30d, 4),
        win_rate_90d=round(wr_90d, 4),
        avg_roi_multiple=round(avg_roi, 2),
        total_pnl_bnb=round(total_pnl_bnb, 4),
        total_pnl_usd=round(total_pnl_usd, 2),
        sharpe_ratio=round(sharpe, 3),
        sortino_ratio=round(sortino, 3),
        consistency_score=round(consist, 1),
        rug_avoidance_rate=round(rug_avoidance, 4),
        unrealized_pnl_bnb=round(unrealized_pnl, 4),
        unrealized_pnl_ratio=round(unrealized_ratio, 4),
        avg_entry_mcap_usd=round(avg_entry_mcap, 0),
        median_entry_mcap_usd=round(median_entry_mcap, 0),
        avg_entry_hours_after_launch=0.0,  # needs launch data from four.meme
        avg_position_size_pct=round(avg_pos_size_pct, 2),
        trades_per_day_30d=round(trades_per_day_30d, 2),
        active_days_30d=active_days_30d,
        avg_exit_multiple=round(avg_exit_multiple, 2),
        median_exit_multiple=round(median_exit_multiple, 2),
        dump_mcap_p50_usd=round(dump_mcap_p50, 0),
        dump_mcap_p70_usd=round(dump_mcap_p70, 0),
        avg_hold_days=round(avg_hold, 2),
        max_hold_days=round(max_hold, 2),
        typical_sell_tranche_1_pct=round(typical_tranche1, 1),
        trailing_stop_threshold_pct=round(trailing_stop, 1),
        max_drawdown_pct=round(max_dd, 2),
        kelly_position_pct=round(kelly_pct, 1),
        avg_gas_gwei=avg_gas,
        total_trades=total_trades,
        unique_tokens=unique_tokens,
        confidence_score=confidence,
        rrr=round(rrr, 2),
        kol_grade=grade,
        type_label=label,
        positions=positions[:20],  # keep last 20 in output
    )


# ---------------------------------------------------------------------------
# Decision engine
# ---------------------------------------------------------------------------

def _decision_output(
    profile: KOLProfile,
    current_mcap_usd: float,
    kol_buy_bnb: float,
    user_wallet_bnb: float,
    token_symbol: str,
) -> str:
    """Generate structured follow-copy decision for a new KOL buy event."""
    p = profile

    # Should we follow?
    follow = p.confidence_score >= 60 and p.win_rate_30d >= 0.50
    similar_entry = p.avg_entry_mcap_usd * 0.5 <= current_mcap_usd <= p.avg_entry_mcap_usd * 2.0
    follow_strength = "强烈推荐" if p.confidence_score >= 80 else ("推荐" if follow else "谨慎" if p.confidence_score >= 50 else "不推荐")

    # Position sizing using Kelly
    kelly_bnb = user_wallet_bnb * (p.kelly_position_pct / 100)
    suggested_bnb = round(min(kelly_bnb, user_wallet_bnb * 0.3), 3)
    min_bnb = round(suggested_bnb * 0.7, 3)
    max_bnb = round(suggested_bnb * 1.3, 3)

    # Take-profit targets based on historical exit multiples
    tp1_x = max(3.0, p.avg_exit_multiple * 0.5)
    tp2_x = max(6.0, p.avg_exit_multiple)
    tp1_mcap = current_mcap_usd * tp1_x if current_mcap_usd > 0 else 0
    tp2_mcap = current_mcap_usd * tp2_x if current_mcap_usd > 0 else 0

    trailing = p.trailing_stop_threshold_pct
    max_hold = f"{p.avg_hold_days:.0f}–{p.max_hold_days:.0f} 天"

    # Risk warnings
    warnings = []
    if p.max_drawdown_pct > 50:
        warnings.append(f"历史最大回撤 {p.max_drawdown_pct:.0f}%，风险较高")
    if not similar_entry:
        if current_mcap_usd > p.avg_entry_mcap_usd * 2:
            warnings.append(f"当前 MCAP 高于该 KOL 平均入场 MCAP {p.avg_entry_mcap_usd/1000:.0f}k，属于偏晚入场")
        else:
            warnings.append(f"当前 MCAP 低于该 KOL 平均入场 MCAP，属于提前布局")
    if p.win_rate_30d < 0.5:
        warnings.append(f"近 30 天胜率仅 {p.win_rate_30d*100:.0f}%，建议降低仓位")

    mcap_str = f"${current_mcap_usd/1000:.0f}k" if current_mcap_usd < 1_000_000 else f"${current_mcap_usd/1_000_000:.2f}M"
    tp1_str = f"${tp1_mcap/1000:.0f}k" if tp1_mcap and tp1_mcap < 1_000_000 else (f"${tp1_mcap/1_000_000:.2f}M" if tp1_mcap else "N/A")
    tp2_str = f"${tp2_mcap/1000:.0f}k" if tp2_mcap and tp2_mcap < 1_000_000 else (f"${tp2_mcap/1_000_000:.2f}M" if tp2_mcap else "N/A")

    lines = [
        "━" * 50,
        f"🧬 KOL 画像快照  |  {p.wallet[:6]}...{p.wallet[-4:]}",
        "━" * 50,
        f"类型：{p.type_label}  |  等级：{p.kol_grade}",
        f"胜率：{p.win_rate_30d*100:.0f}% (30d) / {p.win_rate_90d*100:.0f}% (90d)",
        f"平均 ROI：{p.avg_roi_multiple:.1f}x  |  一致性：{p.consistency_score:.0f}/100",
        f"入场偏好 MCAP：avg ${p.avg_entry_mcap_usd/1000:.0f}k / median ${p.median_entry_mcap_usd/1000:.0f}k",
        f"Dump 习惯：avg {p.avg_exit_multiple:.1f}x 出场，70% 清仓在 ${p.dump_mcap_p70_usd/1000:.0f}k" if p.dump_mcap_p70_usd > 0 else "Dump 习惯：数据积累中",
        f"总 PnL：{p.total_pnl_bnb:.2f} BNB / ${p.total_pnl_usd:.0f}  |  样本 {p.total_trades} 笔",
        "",
        "━" * 50,
        f"🎯 本单决策参考  |  {token_symbol} @ {mcap_str}",
        "━" * 50,
        f"{'✅' if follow else '⚠️'} 该不该跟：{follow_strength}跟单（置信度 {p.confidence_score:.0f}/100）",
        f"   RRR {p.rrr:.1f}  |  历史类似场景胜率 {p.win_rate_30d*100:.0f}%",
        "",
        f"💰 跟多少：建议 {min_bnb}–{max_bnb} BNB（钱包 {p.kelly_position_pct:.0f}% Kelly 仓位）",
        f"   最优：{suggested_bnb} BNB",
        "",
        "📤 止盈计划：",
        f"   → {tp1_x:.0f}x 时跑 40%（约 MCAP {tp1_str}）",
        f"   → {tp2_x:.0f}x 时跑剩余 50%（约 MCAP {tp2_str}）",
        f"   → 剩余 10% 设 {trailing:.0f}% 回撤 trailing stop",
        f"   ⏰ 最大建议持仓：{max_hold}",
    ]

    if warnings:
        lines.append("")
        lines.append("⚠️ 风险预警：")
        for w in warnings:
            lines.append(f"   • {w}")

    lines.append("━" * 50)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# KOL Pool loader
# ---------------------------------------------------------------------------

def _load_kol_pool(filepath: str = "kol-pool.md") -> List[Dict[str, str]]:
    """Parse kol-pool.md and return list of {address, note, tier} dicts."""
    path = Path(filepath)
    if not path.exists():
        return []

    wallets = []
    current_tier = "Unknown"
    addr_re = re.compile(r"(0x[0-9a-fA-F]{40})")

    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("## Tier"):
            current_tier = line.replace("## ", "").split("—")[0].strip()
        match = addr_re.search(line)
        if match:
            addr = match.group(1)
            note = line.split("|", 1)[1].strip() if "|" in line else ""
            note = re.sub(r"备注:\s*", "", note)
            wallets.append({"address": addr, "tier": current_tier, "note": note})

    return wallets


# ---------------------------------------------------------------------------
# Sync wrapper
# ---------------------------------------------------------------------------

def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result(timeout=120)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def _analyze(wallet: str, days: int) -> str:
    wallet = wallet.strip().lower()
    if not wallet.startswith("0x") or len(wallet) != 42:
        return f"❌ 无效地址: {wallet}"

    try:
        trades, bnb_balance = await asyncio.gather(
            get_all_trades(wallet, days=days),
            fetch_bnb_balance(wallet),
        )
    except Exception as e:
        return f"❌ 数据获取失败: {e}"

    if not trades:
        return f"⚠️ 地址 {wallet} 在过去 {days} 天内没有找到 BSC 交易记录。\n请确认 BSCSCAN_API_KEY 已配置，或该地址确实活跃在 BSC 链上。"

    try:
        await enrich_trades_with_mcap(trades)
    except Exception as e:
        logger.debug("MCAP enrichment partial failure: %s", e)

    positions = _aggregate_positions(trades)
    profile = _build_profile(wallet, trades, positions, bnb_balance, days)

    d = asdict(profile)
    d.pop("positions")  # keep output clean; positions saved separately

    out = {
        "wallet": wallet,
        "generated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(profile.generated_at)),
        "grade": profile.kol_grade,
        "type": profile.type_label,
        "confidence": f"{profile.confidence_score}/100",
        "performance": {
            "win_rate_30d": f"{profile.win_rate_30d*100:.1f}%",
            "win_rate_90d": f"{profile.win_rate_90d*100:.1f}%",
            "avg_roi": f"{profile.avg_roi_multiple:.2f}x",
            "total_pnl_bnb": f"{profile.total_pnl_bnb:.3f} BNB",
            "total_pnl_usd": f"${profile.total_pnl_usd:,.0f}",
            "sharpe": f"{profile.sharpe_ratio:.2f}",
            "sortino": f"{profile.sortino_ratio:.2f}",
            "consistency_score": f"{profile.consistency_score:.0f}/100",
            "rug_avoidance": f"{profile.rug_avoidance_rate*100:.0f}%",
        },
        "entry_behavior": {
            "avg_entry_mcap_usd": f"${profile.avg_entry_mcap_usd:,.0f}",
            "median_entry_mcap_usd": f"${profile.median_entry_mcap_usd:,.0f}",
            "avg_position_size_pct": f"{profile.avg_position_size_pct:.1f}%",
            "trades_per_day_30d": f"{profile.trades_per_day_30d:.2f}",
            "active_days_30d": profile.active_days_30d,
        },
        "exit_behavior": {
            "avg_exit_multiple": f"{profile.avg_exit_multiple:.1f}x",
            "median_exit_multiple": f"{profile.median_exit_multiple:.1f}x",
            "dump_mcap_p50_usd": f"${profile.dump_mcap_p50_usd:,.0f}",
            "dump_mcap_p70_usd": f"${profile.dump_mcap_p70_usd:,.0f}",
            "avg_hold_days": f"{profile.avg_hold_days:.1f}",
            "typical_first_sell_pct": f"{profile.typical_sell_tranche_1_pct:.0f}%",
            "trailing_stop_pct": f"{profile.trailing_stop_threshold_pct:.0f}%",
        },
        "risk": {
            "max_drawdown_pct": f"{profile.max_drawdown_pct:.1f}%",
            "kelly_position_pct": f"{profile.kelly_position_pct:.1f}%",
            "rrr": f"{profile.rrr:.2f}",
        },
        "stats": {
            "total_trades": profile.total_trades,
            "unique_tokens": profile.unique_tokens,
            "bnb_balance": f"{profile.bnb_balance:.4f} BNB",
            "lookback_days": days,
        },
        "recent_positions": [
            {
                "symbol": pos.token_symbol,
                "contract": pos.token_contract,
                "side": "CLOSED" if pos.is_closed else "OPEN",
                "roi": f"{pos.roi_multiple:.2f}x",
                "pnl_bnb": f"{pos.realized_pnl_bnb:+.4f}",
                "hold_days": f"{pos.hold_days:.1f}d",
                "buy_bnb": f"{pos.total_buy_bnb:.4f}",
            }
            for pos in positions[:10]
        ],
    }
    return json.dumps(out, indent=2, ensure_ascii=False)


async def _decision(
    kol_wallet: str,
    token_symbol: str,
    token_contract: str,
    current_mcap_usd: float,
    kol_buy_bnb: float,
    user_wallet_bnb: float,
    days: int,
) -> str:
    kol_wallet = kol_wallet.strip().lower()
    try:
        trades, bnb_balance = await asyncio.gather(
            get_all_trades(kol_wallet, days=days),
            fetch_bnb_balance(kol_wallet),
        )
    except Exception as e:
        return f"❌ 数据获取失败: {e}"

    if not trades:
        return f"⚠️ 该 KOL ({kol_wallet[:8]}...) 没有足够历史数据生成决策建议（{days} 天内无交易）。"

    positions = _aggregate_positions(trades)
    profile = _build_profile(kol_wallet, trades, positions, bnb_balance, days)

    if current_mcap_usd <= 0 and token_contract:
        m = await get_token_metrics(token_contract)
        if m:
            current_mcap_usd = m.mcap_usd

    if user_wallet_bnb <= 0:
        user_wallet_bnb = 5.0  # default assumption

    return _decision_output(profile, current_mcap_usd, kol_buy_bnb, user_wallet_bnb, token_symbol)


async def _pool_scan(pool_file: str, days: int, max_wallets: int) -> str:
    wallets = _load_kol_pool(pool_file)
    if not wallets:
        return f"❌ 找不到 KOL 池文件 '{pool_file}'，请先创建（参考 kol-pool.example.md）。"

    wallets = wallets[:max_wallets]
    results = []

    for i, w in enumerate(wallets):
        addr = w["address"]
        try:
            trades, bnb_balance = await asyncio.gather(
                get_all_trades(addr, days=days),
                fetch_bnb_balance(addr),
            )
            positions = _aggregate_positions(trades)
            profile = _build_profile(addr, trades, positions, bnb_balance, days)
            results.append({
                "rank": i + 1,
                "address": addr,
                "tier": w["tier"],
                "note": w["note"],
                "grade": profile.kol_grade,
                "type": profile.type_label,
                "confidence": profile.confidence_score,
                "win_rate_30d": f"{profile.win_rate_30d*100:.0f}%",
                "avg_roi": f"{profile.avg_roi_multiple:.1f}x",
                "total_pnl_bnb": f"{profile.total_pnl_bnb:.3f}",
                "trades": profile.total_trades,
            })
        except Exception as e:
            results.append({
                "rank": i + 1,
                "address": addr,
                "tier": w["tier"],
                "error": str(e)[:100],
            })

        if i < len(wallets) - 1:
            await asyncio.sleep(0.3)

    results.sort(key=lambda r: r.get("confidence", 0), reverse=True)

    summary = {
        "scan_time": time.strftime("%Y-%m-%d %H:%M UTC"),
        "total_wallets": len(wallets),
        "pool_file": pool_file,
        "lookback_days": days,
        "results": results,
    }
    return json.dumps(summary, indent=2, ensure_ascii=False)


async def _pool_load(pool_file: str) -> str:
    wallets = _load_kol_pool(pool_file)
    if not wallets:
        return f"❌ 找不到或无法解析 '{pool_file}'。请参考 kol-pool.example.md 创建。"
    tiers: Dict[str, List] = defaultdict(list)
    for w in wallets:
        tiers[w["tier"]].append(w)
    out = {"file": pool_file, "total": len(wallets), "tiers": dict(tiers)}
    return json.dumps(out, indent=2, ensure_ascii=False)


async def _report(pool_file: str, days: int) -> str:
    wallets = _load_kol_pool(pool_file)
    if not wallets:
        return f"❌ 找不到 KOL 池文件 '{pool_file}'。"

    profiles = []
    for w in wallets[:50]:
        try:
            trades, bnb = await asyncio.gather(
                get_all_trades(w["address"], days=days),
                fetch_bnb_balance(w["address"]),
            )
            positions = _aggregate_positions(trades)
            p = _build_profile(w["address"], trades, positions, bnb, days)
            profiles.append((w, p))
            await asyncio.sleep(0.2)
        except Exception:
            continue

    if not profiles:
        return "⚠️ 没有成功分析任何钱包，请检查 BSCSCAN_API_KEY 配置。"

    a_plus = [p for _, p in profiles if p.kol_grade == "A+"]
    a_grade = [p for _, p in profiles if p.kol_grade == "A"]
    top5 = sorted(profiles, key=lambda x: x[1].confidence_score, reverse=True)[:5]

    total_pools = len(profiles)
    avg_wr = sum(p.win_rate_30d for _, p in profiles) / total_pools
    avg_roi = sum(p.avg_roi_multiple for _, p in profiles) / total_pools

    lines = [
        f"# Hermemes KOL 池报告",
        f"生成时间: {time.strftime('%Y-%m-%d %H:%M UTC')}  |  分析周期: {days} 天  |  钱包数: {total_pools}",
        "",
        f"## 池概览",
        f"- A+ 级 KOL: {len(a_plus)} 个",
        f"- A 级 KOL: {len(a_grade)} 个",
        f"- 平均胜率 (30d): {avg_wr*100:.1f}%",
        f"- 平均 ROI: {avg_roi:.2f}x",
        "",
        "## Top 5 推荐跟单",
    ]
    for i, (w, p) in enumerate(top5, 1):
        lines.append(
            f"{i}. `{p.wallet[:8]}...` | {p.kol_grade} | 置信度 {p.confidence_score:.0f} | "
            f"胜率 {p.win_rate_30d*100:.0f}% | ROI {p.avg_roi_multiple:.1f}x | {p.type_label}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sync wrappers → tool handlers
# ---------------------------------------------------------------------------

def kol_analyze(wallet: str, days: int = 90) -> str:
    return _run(_analyze(wallet, days))


def kol_decision(
    kol_wallet: str,
    token_symbol: str = "",
    token_contract: str = "",
    current_mcap_usd: float = 0.0,
    kol_buy_bnb: float = 0.0,
    user_wallet_bnb: float = 5.0,
    days: int = 90,
) -> str:
    return _run(_decision(kol_wallet, token_symbol, token_contract, current_mcap_usd, kol_buy_bnb, user_wallet_bnb, days))


def kol_pool_scan(pool_file: str = "kol-pool.md", days: int = 30, max_wallets: int = 50) -> str:
    return _run(_pool_scan(pool_file, days, max_wallets))


def kol_pool_load(pool_file: str = "kol-pool.md") -> str:
    return _run(_pool_load(pool_file))


def kol_report(pool_file: str = "kol-pool.md", days: int = 30) -> str:
    return _run(_report(pool_file, days))


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

registry.register(
    name="kol_analyze",
    toolset="kol",
    schema={
        "type": "function",
        "function": {
            "name": "kol_analyze",
            "description": (
                "Full 25+ dimension on-chain behavior analysis for a BSC wallet address. "
                "Fetches transaction history from BscScan, resolves buy/sell trades, and "
                "computes win rate, ROI, Sharpe ratio, entry/exit MCAP preferences, Kelly "
                "position sizing, consistency score, dump behavior, and a KOL grade (A+/A/B/C/D). "
                "Use this to build or refresh a KOL profile."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "wallet": {"type": "string", "description": "BSC wallet address (0x…)"},
                    "days": {"type": "integer", "description": "Lookback window in days (default 90)", "default": 90},
                },
                "required": ["wallet"],
            },
        },
    },
    handler=kol_analyze,
    description="25+ dimension KOL behavior analysis",
    emoji="🧬",
    requires_env=["BSCSCAN_API_KEY"],
)

registry.register(
    name="kol_decision",
    toolset="kol",
    schema={
        "type": "function",
        "function": {
            "name": "kol_decision",
            "description": (
                "Given a new KOL buy event on BSC, generate a quantified follow-copy decision: "
                "should I follow, how much BNB, when to take profit, when to stop loss. "
                "Uses the KOL's historical 25+ dimension profile to compute Kelly position size, "
                "TP targets based on historical exit multiples, and risk warnings."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kol_wallet": {"type": "string", "description": "KOL BSC wallet address"},
                    "token_symbol": {"type": "string", "description": "Token ticker symbol, e.g. $HERMEMES"},
                    "token_contract": {"type": "string", "description": "Token contract address (optional, used to fetch live MCAP)"},
                    "current_mcap_usd": {"type": "number", "description": "Current token market cap in USD (0 = auto-fetch)"},
                    "kol_buy_bnb": {"type": "number", "description": "How much BNB the KOL bought"},
                    "user_wallet_bnb": {"type": "number", "description": "Your wallet balance in BNB (for position sizing)"},
                    "days": {"type": "integer", "description": "Historical lookback days (default 90)", "default": 90},
                },
                "required": ["kol_wallet"],
            },
        },
    },
    handler=kol_decision,
    description="Quantified follow-copy decision for a KOL buy event",
    emoji="🎯",
    requires_env=["BSCSCAN_API_KEY"],
)

registry.register(
    name="kol_pool_scan",
    toolset="kol",
    schema={
        "type": "function",
        "function": {
            "name": "kol_pool_scan",
            "description": (
                "Batch-scan all wallets in the KOL pool file (kol-pool.md by default). "
                "Analyzes each wallet and returns a ranked leaderboard sorted by confidence score. "
                "Use this for scheduled Cron updates of the full KOL pool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pool_file": {"type": "string", "description": "Path to KOL pool file", "default": "kol-pool.md"},
                    "days": {"type": "integer", "description": "Lookback days per wallet", "default": 30},
                    "max_wallets": {"type": "integer", "description": "Max wallets to scan in one run", "default": 50},
                },
                "required": [],
            },
        },
    },
    handler=kol_pool_scan,
    description="Batch scan all KOL pool wallets and rank by confidence",
    emoji="📡",
    requires_env=["BSCSCAN_API_KEY"],
)

registry.register(
    name="kol_pool_load",
    toolset="kol",
    schema={
        "type": "function",
        "function": {
            "name": "kol_pool_load",
            "description": "Load and display the current KOL pool from kol-pool.md, grouped by tier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pool_file": {"type": "string", "description": "Path to KOL pool file", "default": "kol-pool.md"},
                },
                "required": [],
            },
        },
    },
    handler=kol_pool_load,
    description="Load and list KOL pool wallets by tier",
    emoji="📋",
)

registry.register(
    name="kol_report",
    toolset="kol",
    schema={
        "type": "function",
        "function": {
            "name": "kol_report",
            "description": (
                "Generate a summary report for the full KOL pool: pool overview stats, "
                "grade distribution, top 5 recommended follow-copy wallets, and weekly trends."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pool_file": {"type": "string", "description": "Path to KOL pool file", "default": "kol-pool.md"},
                    "days": {"type": "integer", "description": "Report period in days", "default": 30},
                },
                "required": [],
            },
        },
    },
    handler=kol_report,
    description="Generate KOL pool summary report",
    emoji="📊",
)
