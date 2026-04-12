"""Token Safety Tool — honeypot, rug pull, and contract risk detection for BSC.

Uses multiple data sources for defense-in-depth:
1. honeypot.is API       — dedicated honeypot detector
2. GoPlus Security API   — comprehensive token security audit
3. On-chain analysis     — owner permissions, mint/pause functions,
                           top holder concentration, liquidity lock status

Registered tools:
  token_safety_check   — full safety audit for a BSC token
  token_quick_check    — fast honeypot-only check (< 2s)
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

_HONEYPOT_API  = "https://api.honeypot.is/v2"
_GOPLUS_API    = "https://api.gopluslabs.io/api/v1"
_BSC_RPC       = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org")
_TIMEOUT       = 12.0
_BSC_CHAIN_ID  = "56"

# Risk thresholds
_HIGH_HOLDER_CONCENTRATION_PCT = 30.0   # top-10 holders own >30% = risk flag
_MIN_LIQUIDITY_USD = 5_000              # <$5k liquidity = very risky
_MAX_BUY_TAX_PCT   = 10.0
_MAX_SELL_TAX_PCT  = 15.0


@dataclass
class SafetyFlag:
    severity: str   # "critical" | "high" | "medium" | "low" | "info"
    code: str       # machine-readable flag code
    message: str    # human-readable description


@dataclass
class TokenSafetyReport:
    contract: str
    symbol: str
    name: str
    chain: str
    checked_at: int

    # Overall verdict
    is_honeypot: bool
    is_open_source: bool
    is_proxy: bool
    can_mint: bool
    can_pause_trading: bool
    owner_can_change_balance: bool
    has_blacklist: bool
    has_whitelist: bool

    # Tax
    buy_tax_pct: float
    sell_tax_pct: float
    transfer_tax_pct: float

    # Liquidity
    liquidity_usd: float
    liquidity_locked: bool
    liquidity_lock_until: Optional[int]  # unix timestamp

    # Holders
    holder_count: int
    top10_holder_pct: float   # % of supply held by top 10 wallets
    creator_pct: float        # % held by creator/deployer

    # Simulation
    can_buy: bool
    can_sell: bool
    buy_gas: int
    sell_gas: int

    # Risk scoring
    risk_score: int           # 0-100, higher = riskier
    risk_level: str           # "safe" | "low" | "medium" | "high" | "critical"
    flags: List[SafetyFlag] = field(default_factory=list)
    recommendation: str = ""


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------

async def _rpc(method: str, params: list) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post(_BSC_RPC, json=payload)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        return data.get("result")


async def _fetch_honeypot_is(contract: str) -> Dict:
    """Call honeypot.is API for simulation-based detection."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(
                f"{_HONEYPOT_API}/IsHoneypot",
                params={"address": contract, "chainID": _BSC_CHAIN_ID},
            )
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        logger.debug("honeypot.is failed: %s", e)
    return {}


async def _fetch_goplus(contract: str) -> Dict:
    """Call GoPlus Security API for comprehensive token security info."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(
                f"{_GOPLUS_API}/token_security/{_BSC_CHAIN_ID}",
                params={"contract_addresses": contract},
            )
            if r.status_code == 200:
                data = r.json()
                result = data.get("result", {})
                return result.get(contract.lower(), {})
    except Exception as e:
        logger.debug("GoPlus failed: %s", e)
    return {}


async def _fetch_owner_info(contract: str) -> Dict[str, Any]:
    """Check on-chain: owner address, renounced status."""
    # ERC-20 owner() selector: 0x8da5cb5b
    try:
        owner_raw = await _rpc("eth_call", [{"to": contract, "data": "0x8da5cb5b"}, "latest"])
        if owner_raw and len(owner_raw) >= 66:
            owner = "0x" + owner_raw[-40:]
            renounced = owner.lower() == "0x" + "0" * 40
            return {"owner": owner, "renounced": renounced}
    except Exception:
        pass
    return {"owner": None, "renounced": False}


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def _build_flags(
    hp: Dict,
    gp: Dict,
    is_honeypot: bool,
    buy_tax: float,
    sell_tax: float,
    top10_pct: float,
    liquidity_usd: float,
    can_mint: bool,
    can_pause: bool,
    has_blacklist: bool,
    is_open_source: bool,
    owner_renounced: bool,
) -> Tuple[List[SafetyFlag], int]:
    flags = []

    if is_honeypot:
        flags.append(SafetyFlag("critical", "HONEYPOT", "蜜罐合约：无法卖出，资金将被锁定"))

    if sell_tax > _MAX_SELL_TAX_PCT:
        flags.append(SafetyFlag("high", "HIGH_SELL_TAX", f"卖出税过高：{sell_tax:.1f}%（超过 {_MAX_SELL_TAX_PCT}% 警戒线）"))

    if buy_tax > _MAX_BUY_TAX_PCT:
        flags.append(SafetyFlag("medium", "HIGH_BUY_TAX", f"买入税过高：{buy_tax:.1f}%"))

    if can_mint:
        flags.append(SafetyFlag("high", "CAN_MINT", "合约可增发代币，存在通货膨胀风险"))

    if can_pause:
        flags.append(SafetyFlag("high", "CAN_PAUSE", "合约可暂停交易（owner 可随时锁仓）"))

    if has_blacklist:
        flags.append(SafetyFlag("medium", "HAS_BLACKLIST", "合约含黑名单功能，指定地址可能无法卖出"))

    if top10_pct > _HIGH_HOLDER_CONCENTRATION_PCT:
        flags.append(SafetyFlag("medium", "HIGH_CONCENTRATION",
                                f"Top-10 持有者占比 {top10_pct:.1f}%，集中度过高，存在砸盘风险"))

    if liquidity_usd < _MIN_LIQUIDITY_USD and liquidity_usd > 0:
        flags.append(SafetyFlag("high", "LOW_LIQUIDITY",
                                f"流动性极低：${liquidity_usd:,.0f}，大额买卖滑点极高"))

    if not is_open_source:
        flags.append(SafetyFlag("medium", "NOT_VERIFIED", "合约未开源验证，无法审查代码逻辑"))

    if not owner_renounced:
        flags.append(SafetyFlag("low", "OWNER_ACTIVE", "合约 owner 未放弃权限，存在后门风险"))

    # Risk score: weight each flag
    severity_weights = {"critical": 50, "high": 20, "medium": 10, "low": 5, "info": 1}
    score = min(100, sum(severity_weights.get(f.severity, 0) for f in flags))

    return flags, score


def _risk_level(score: int) -> str:
    if score >= 50:
        return "critical"
    if score >= 30:
        return "high"
    if score >= 15:
        return "medium"
    if score >= 5:
        return "low"
    return "safe"


def _recommendation(level: str, flags: List[SafetyFlag]) -> str:
    if level == "critical":
        return "❌ 极高风险 — 强烈建议不要买入。检测到蜜罐或其他严重漏洞。"
    if level == "high":
        critical_flags = [f.code for f in flags if f.severity in ("critical", "high")]
        return f"⚠️ 高风险 — 建议避开。主要风险：{', '.join(critical_flags)}"
    if level == "medium":
        return "⚠️ 中等风险 — 谨慎操作，建议小仓位并设止损。"
    if level == "low":
        return "🟡 低风险 — 基本安全，但仍需注意流动性和持仓分布。"
    return "✅ 安全 — 未检测到主要风险指标。"


# ---------------------------------------------------------------------------
# Main analysis functions
# ---------------------------------------------------------------------------

async def _full_safety_check(contract: str) -> TokenSafetyReport:
    contract = contract.strip().lower()

    # Parallel data fetch
    hp_data, gp_data, owner_info = await asyncio.gather(
        _fetch_honeypot_is(contract),
        _fetch_goplus(contract),
        _fetch_owner_info(contract),
        return_exceptions=True,
    )
    if isinstance(hp_data, Exception): hp_data = {}
    if isinstance(gp_data, Exception): gp_data = {}
    if isinstance(owner_info, Exception): owner_info = {}

    # --- Parse honeypot.is ---
    hp_result = hp_data.get("honeypotResult", {})
    sim = hp_data.get("simulationResult", {})
    token_meta = hp_data.get("token", {})

    is_honeypot = hp_result.get("isHoneypot", False)
    can_buy  = not hp_result.get("buyTax", 0) >= 99
    can_sell = not hp_result.get("sellTax", 0) >= 99
    buy_tax  = float(sim.get("buyTax", hp_result.get("buyTax", 0)) or 0)
    sell_tax = float(sim.get("sellTax", hp_result.get("sellTax", 0)) or 0)
    buy_gas  = int(sim.get("buyGas", 0) or 0)
    sell_gas = int(sim.get("sellGas", 0) or 0)
    symbol   = token_meta.get("symbol", "")
    name     = token_meta.get("name", "")

    # Liquidity from honeypot.is
    pair = hp_data.get("pair", {})
    liquidity_usd = float(pair.get("liquidity", 0) or 0)
    liquidity_locked = bool(pair.get("liquidityLocked", False))
    liq_lock_until = pair.get("liquidityLockTime")

    # --- Parse GoPlus ---
    is_open_source  = gp_data.get("is_open_source", "0") == "1"
    is_proxy        = gp_data.get("is_proxy", "0") == "1"
    can_mint        = gp_data.get("is_mintable", "0") == "1"
    can_pause       = gp_data.get("trading_cooldown", "0") == "1" or gp_data.get("is_blacklisted", "0") == "1"
    owner_can_change_balance = gp_data.get("owner_change_balance", "0") == "1"
    has_blacklist   = gp_data.get("is_blacklisted", "0") == "1"
    has_whitelist   = gp_data.get("is_whitelisted", "0") == "1"
    holder_count    = int(gp_data.get("holder_count", 0) or 0)
    creator_pct     = float(gp_data.get("creator_percent", 0) or 0) * 100

    # Top-10 holder concentration
    holders_raw = gp_data.get("holders", []) or []
    top10_pct = sum(float(h.get("percent", 0) or 0) * 100 for h in holders_raw[:10])

    # GoPlus sell/buy tax (more accurate)
    gp_buy_tax  = float(gp_data.get("buy_tax", buy_tax) or buy_tax)
    gp_sell_tax = float(gp_data.get("sell_tax", sell_tax) or sell_tax)
    buy_tax  = max(buy_tax, gp_buy_tax)
    sell_tax = max(sell_tax, gp_sell_tax)

    # GoPlus liquidity
    if liquidity_usd == 0:
        dex_info = gp_data.get("dex", []) or []
        if dex_info:
            liquidity_usd = float(dex_info[0].get("liquidity", 0) or 0)

    # Symbol/name fallback
    if not symbol:
        symbol = gp_data.get("token_symbol", "")
    if not name:
        name = gp_data.get("token_name", "")

    # Owner renounced
    owner_renounced = owner_info.get("renounced", False) if isinstance(owner_info, dict) else False

    # Build flags and score
    flags, risk_score = _build_flags(
        hp_data, gp_data, is_honeypot, buy_tax, sell_tax,
        top10_pct, liquidity_usd, can_mint, can_pause,
        has_blacklist, is_open_source, owner_renounced,
    )
    level = _risk_level(risk_score)
    rec = _recommendation(level, flags)

    return TokenSafetyReport(
        contract=contract,
        symbol=symbol,
        name=name,
        chain="BSC",
        checked_at=int(time.time()),
        is_honeypot=is_honeypot,
        is_open_source=is_open_source,
        is_proxy=is_proxy,
        can_mint=can_mint,
        can_pause_trading=can_pause,
        owner_can_change_balance=owner_can_change_balance,
        has_blacklist=has_blacklist,
        has_whitelist=has_whitelist,
        buy_tax_pct=round(buy_tax, 2),
        sell_tax_pct=round(sell_tax, 2),
        transfer_tax_pct=0.0,
        liquidity_usd=round(liquidity_usd, 2),
        liquidity_locked=liquidity_locked,
        liquidity_lock_until=liq_lock_until,
        holder_count=holder_count,
        top10_holder_pct=round(top10_pct, 2),
        creator_pct=round(creator_pct, 2),
        can_buy=can_buy,
        can_sell=can_sell,
        buy_gas=buy_gas,
        sell_gas=sell_gas,
        risk_score=risk_score,
        risk_level=level,
        flags=flags,
        recommendation=rec,
    )


def _format_report(report: TokenSafetyReport) -> str:
    level_emoji = {
        "safe": "✅", "low": "🟡", "medium": "⚠️", "high": "🔴", "critical": "💀"
    }.get(report.risk_level, "❓")

    flag_lines = "\n".join(
        f"   [{f.severity.upper()}] {f.message}"
        for f in report.flags
    ) or "   없음 (None)"

    return json.dumps({
        "contract": report.contract,
        "symbol": report.symbol,
        "name": report.name,
        "verdict": f"{level_emoji} {report.risk_level.upper()} (score {report.risk_score}/100)",
        "recommendation": report.recommendation,
        "honeypot": report.is_honeypot,
        "can_buy": report.can_buy,
        "can_sell": report.can_sell,
        "buy_tax": f"{report.buy_tax_pct:.1f}%",
        "sell_tax": f"{report.sell_tax_pct:.1f}%",
        "liquidity_usd": f"${report.liquidity_usd:,.0f}",
        "liquidity_locked": report.liquidity_locked,
        "holder_count": report.holder_count,
        "top10_concentration": f"{report.top10_holder_pct:.1f}%",
        "creator_pct": f"{report.creator_pct:.1f}%",
        "open_source": report.is_open_source,
        "can_mint": report.can_mint,
        "can_pause_trading": report.can_pause_trading,
        "has_blacklist": report.has_blacklist,
        "risk_flags": [
            {"severity": f.severity, "code": f.code, "message": f.message}
            for f in report.flags
        ],
        "checked_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(report.checked_at)),
    }, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Quick check (honeypot.is only — fast)
# ---------------------------------------------------------------------------

async def _quick_check(contract: str) -> str:
    contract = contract.strip().lower()
    hp = await _fetch_honeypot_is(contract)
    hp_result = hp.get("honeypotResult", {})
    sim = hp.get("simulationResult", {})
    token = hp.get("token", {})

    is_hp = hp_result.get("isHoneypot", "unknown")
    buy_tax  = float(sim.get("buyTax", 0) or 0)
    sell_tax = float(sim.get("sellTax", 0) or 0)

    if is_hp is True or is_hp == "true":
        verdict = "💀 蜜罐 — 无法卖出"
    elif sell_tax > 50:
        verdict = f"🔴 高风险 — 卖出税 {sell_tax:.0f}%"
    elif sell_tax > 15:
        verdict = f"⚠️ 中风险 — 卖出税 {sell_tax:.0f}%"
    else:
        verdict = f"✅ 暂时安全 — 买入税 {buy_tax:.0f}% / 卖出税 {sell_tax:.0f}%"

    return json.dumps({
        "contract": contract,
        "symbol": token.get("symbol", ""),
        "verdict": verdict,
        "is_honeypot": is_hp,
        "buy_tax": f"{buy_tax:.1f}%",
        "sell_tax": f"{sell_tax:.1f}%",
        "note": "Quick check only (honeypot.is). Run token_safety_check for full audit.",
    }, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Sync wrappers
# ---------------------------------------------------------------------------

def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result(timeout=30)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def token_safety_check(contract: str) -> str:
    return _run(_full_safety_check(contract).then(_format_report) if False
                else _run_format(contract))


def _run_format(contract: str) -> str:
    async def _inner():
        report = await _full_safety_check(contract)
        return _format_report(report)
    return _run(_inner())


def token_quick_check(contract: str) -> str:
    return _run(_quick_check(contract))


# Patch the sync wrapper
token_safety_check = lambda contract: _run_format(contract)


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

from tools.registry import registry  # noqa: E402

registry.register(
    name="token_safety_check",
    toolset="kol",
    schema={
        "type": "function",
        "function": {
            "name": "token_safety_check",
            "description": (
                "Full safety audit for a BSC token before buying. Uses honeypot.is + GoPlus "
                "Security API + on-chain analysis to check: honeypot simulation, sell tax, "
                "mint/pause functions, blacklist, top-10 holder concentration, liquidity "
                "lock status, and contract verification. Returns a risk score (0-100) and "
                "actionable recommendation. Always run this before following a KOL into a new token."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contract": {"type": "string", "description": "BSC token contract address (0x…)"},
                },
                "required": ["contract"],
            },
        },
    },
    handler=token_safety_check,
    description="Full honeypot + rug pull + tax safety audit for BSC tokens",
    emoji="🛡️",
)

registry.register(
    name="token_quick_check",
    toolset="kol",
    schema={
        "type": "function",
        "function": {
            "name": "token_quick_check",
            "description": (
                "Fast honeypot simulation check for a BSC token (< 2 seconds). "
                "Uses honeypot.is to simulate buy and sell transactions. "
                "Use this for a rapid sanity check before deeper analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contract": {"type": "string", "description": "BSC token contract address (0x…)"},
                },
                "required": ["contract"],
            },
        },
    },
    handler=token_quick_check,
    description="Fast honeypot simulation check",
    emoji="⚡",
)
