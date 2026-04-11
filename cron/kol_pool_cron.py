"""KOL Pool Cron Scanner — Hermemes automated BSC KOL pool monitoring.

This module is designed to be registered as a Hermes Agent Cron job.
It runs on a schedule (default every 4 hours), scans all wallets in the
KOL pool, detects new buy events, updates profiles, and sends alerts.

Usage — register via Hermes CLI or tell the agent:
    "每 4 小时扫描一次 kol-pool.md，有新买入立即推送 Telegram 告警"

Or register programmatically via the cron scheduler:
    from cron.kol_pool_cron import register_kol_cron_job
    register_kol_cron_job(interval_hours=4, pool_file="kol-pool.md")
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_STATE_FILE = Path(os.path.expanduser("~/.hermes/kol_pool_state.json"))
_ALERT_MIN_CONFIDENCE = float(os.getenv("KOL_ALERT_MIN_CONFIDENCE", "65"))
_ALERT_MIN_BNB = float(os.getenv("KOL_ALERT_MIN_BNB", "0.3"))


# ---------------------------------------------------------------------------
# State management — track last-seen tx per wallet to detect new activity
# ---------------------------------------------------------------------------

def _load_state() -> Dict[str, Any]:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state: Dict[str, Any]) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# New buy detection
# ---------------------------------------------------------------------------

@dataclass
class NewBuyAlert:
    wallet: str
    token_symbol: str
    token_contract: str
    bnb_amount: float
    tx_hash: str
    timestamp: int
    kol_grade: str
    confidence: float
    decision_text: str


async def _detect_new_buys(
    wallet: str,
    state: Dict[str, Any],
) -> List[NewBuyAlert]:
    """Compare latest trades against known state to find new buys."""
    from tools.bscscan_adapter import get_all_trades, fetch_bnb_balance
    from tools.bsc_kol_tool import _aggregate_positions, _build_profile, _decision_output

    last_ts = state.get(wallet, {}).get("last_trade_ts", 0)
    now = int(time.time())

    try:
        trades, bnb_balance = await asyncio.gather(
            get_all_trades(wallet, days=3),   # only look at last 3 days for freshness
            fetch_bnb_balance(wallet),
        )
    except Exception as e:
        logger.warning("Failed to fetch trades for %s: %s", wallet, e)
        return []

    new_buys = [
        t for t in trades
        if t.side == "buy"
        and t.timestamp > last_ts
        and t.bnb_value >= _ALERT_MIN_BNB
    ]

    if not new_buys:
        return []

    # Build full profile for decision
    try:
        all_trades, _ = await asyncio.gather(
            get_all_trades(wallet, days=90),
            asyncio.sleep(0),
        )
        positions = _aggregate_positions(all_trades)
        profile = _build_profile(wallet, all_trades, positions, bnb_balance, 90)
    except Exception as e:
        logger.warning("Profile build failed for %s: %s", wallet, e)
        return []

    alerts = []
    for trade in new_buys:
        decision = _decision_output(
            profile=profile,
            current_mcap_usd=getattr(trade, "current_mcap_usd", 0.0),
            kol_buy_bnb=trade.bnb_value,
            user_wallet_bnb=5.0,
            token_symbol=trade.token_symbol,
        )
        alerts.append(NewBuyAlert(
            wallet=wallet,
            token_symbol=trade.token_symbol,
            token_contract=trade.token_contract,
            bnb_amount=trade.bnb_value,
            tx_hash=trade.hash,
            timestamp=trade.timestamp,
            kol_grade=profile.kol_grade,
            confidence=profile.confidence_score,
            decision_text=decision,
        ))

    # Update state
    if trades:
        state.setdefault(wallet, {})["last_trade_ts"] = max(t.timestamp for t in trades)

    return alerts


def _format_alert(alert: NewBuyAlert) -> str:
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(alert.timestamp))
    return (
        f"🚨 Hermemes KOL 新买入警报\n"
        f"时间：{ts}\n"
        f"KOL：`{alert.wallet[:8]}...{alert.wallet[-4:]}`  [{alert.kol_grade}级 | 置信度 {alert.confidence:.0f}]\n"
        f"Token：**{alert.token_symbol}**  |  买入 {alert.bnb_amount:.3f} BNB\n"
        f"Tx：https://bscscan.com/tx/{alert.tx_hash}\n"
        f"\n{alert.decision_text}"
    )


# ---------------------------------------------------------------------------
# Main scan loop
# ---------------------------------------------------------------------------

async def run_scan(
    pool_file: str = "kol-pool.md",
    send_alerts: bool = True,
    alert_callback=None,
) -> Dict[str, Any]:
    """
    Full scan of the KOL pool.
    Returns summary dict with new alerts and updated profiles.

    alert_callback: async callable(message: str) — called for each new buy alert.
    """
    from tools.bsc_kol_tool import _load_kol_pool, _aggregate_positions, _build_profile
    from tools.bscscan_adapter import get_all_trades, fetch_bnb_balance

    wallets = _load_kol_pool(pool_file)
    if not wallets:
        return {"error": f"KOL pool file '{pool_file}' not found or empty"}

    state = _load_state()
    all_alerts: List[NewBuyAlert] = []
    profiles_updated = 0
    errors = []

    logger.info("Hermemes KOL Cron: scanning %d wallets from %s", len(wallets), pool_file)

    for w in wallets:
        addr = w["address"]
        try:
            new_buys = await _detect_new_buys(addr, state)
            all_alerts.extend(new_buys)

            # Update profile in state
            try:
                trades, bnb = await asyncio.gather(
                    get_all_trades(addr, days=30),
                    fetch_bnb_balance(addr),
                )
                positions = _aggregate_positions(trades)
                profile = _build_profile(addr, trades, positions, bnb, 30)
                state.setdefault(addr, {}).update({
                    "grade": profile.kol_grade,
                    "confidence": profile.confidence_score,
                    "win_rate_30d": profile.win_rate_30d,
                    "avg_roi": profile.avg_roi_multiple,
                    "last_updated": int(time.time()),
                })
                profiles_updated += 1
            except Exception as e:
                logger.debug("Profile update failed for %s: %s", addr, e)

        except Exception as e:
            errors.append({"wallet": addr, "error": str(e)[:100]})

        await asyncio.sleep(0.5)  # gentle rate limiting

    _save_state(state)

    # Send alerts
    if send_alerts and all_alerts and alert_callback:
        high_conf = [a for a in all_alerts if a.confidence >= _ALERT_MIN_CONFIDENCE]
        for alert in high_conf:
            try:
                msg = _format_alert(alert)
                await alert_callback(msg)
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning("Alert send failed: %s", e)

    summary = {
        "scan_time": time.strftime("%Y-%m-%d %H:%M UTC"),
        "wallets_scanned": len(wallets),
        "profiles_updated": profiles_updated,
        "new_buy_alerts": len(all_alerts),
        "high_confidence_alerts": len([a for a in all_alerts if a.confidence >= _ALERT_MIN_CONFIDENCE]),
        "errors": len(errors),
        "alerts": [
            {
                "wallet": a.wallet[:8] + "..." + a.wallet[-4:],
                "token": a.token_symbol,
                "bnb": a.bnb_amount,
                "grade": a.kol_grade,
                "confidence": a.confidence,
                "tx": a.tx_hash,
            }
            for a in all_alerts
        ],
    }

    logger.info(
        "Hermemes KOL Cron scan complete: %d wallets, %d new buys, %d errors",
        len(wallets), len(all_alerts), len(errors),
    )
    return summary


def run_scan_sync(pool_file: str = "kol-pool.md") -> str:
    """Synchronous entry point — called by Hermes Cron scheduler."""
    try:
        result = asyncio.run(run_scan(pool_file=pool_file, send_alerts=False))
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Cron job registration helper
# ---------------------------------------------------------------------------

def register_kol_cron_job(
    interval_hours: int = 4,
    pool_file: str = "kol-pool.md",
    platforms: Optional[List[str]] = None,
) -> str:
    """
    Register the KOL pool scanner as a Hermes Cron job.

    This function is called by the agent when the user requests automated scanning.
    Returns the cron expression and job description for confirmation.

    interval_hours: how often to scan (1, 2, 4, 6, 8, 12, 24)
    pool_file: path to kol-pool.md
    platforms: list of platforms to send alerts to (e.g. ["telegram", "discord"])
    """
    valid_intervals = {1, 2, 4, 6, 8, 12, 24}
    if interval_hours not in valid_intervals:
        interval_hours = 4

    cron_expr = f"0 */{interval_hours} * * *"

    job_description = (
        f"Hermemes KOL Pool Scanner — 每 {interval_hours} 小时扫描 {pool_file} 中所有钱包，"
        f"检测新买入事件并更新 KOL 画像。"
        f"{'推送到 ' + ', '.join(platforms) if platforms else '（未配置推送平台）'}"
    )

    config = {
        "cron": cron_expr,
        "name": "hermemes_kol_scan",
        "description": job_description,
        "pool_file": pool_file,
        "alert_platforms": platforms or [],
        "min_confidence_to_alert": _ALERT_MIN_CONFIDENCE,
        "min_bnb_to_alert": _ALERT_MIN_BNB,
        "command": f"python -c \"from cron.kol_pool_cron import run_scan_sync; print(run_scan_sync('{pool_file}'))\"",
    }

    return json.dumps(config, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI entry point (for testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    pool_file = sys.argv[1] if len(sys.argv) > 1 else "kol-pool.md"
    print(f"Running KOL pool scan on {pool_file}...")
    result = run_scan_sync(pool_file)
    print(result)
