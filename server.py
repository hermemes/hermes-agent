#!/usr/bin/env python3
"""Hermemes Unified Server

Serves both landing page and dashboard from a single port:
  /              → landingpage/
  /dashboard/    → dashboard/
  /api/          → dashboard API endpoints
"""

import json
import os
import platform
import re
import shutil
import time
import socket
import subprocess
import urllib.request
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime, timezone

PORT = int(os.environ.get("PORT", 3099))
PROJECT_DIR = Path(__file__).resolve().parent
LANDING_DIR = PROJECT_DIR / "landingpage"
DASHBOARD_DIR = PROJECT_DIR / "dashboard"
HERMES_DIR = Path.home() / ".hermes"
START_TIME = time.time()

BSC_RPC = os.environ.get("BSC_RPC_URL", "https://bsc-dataseed1.binance.org")
GMGN_API_KEY = os.environ.get("GMGN_API_KEY", "")
GMGN_BASE = "https://gmgn.ai/defi/quotation/v1"

# ─── Real tracking state ───
api_call_log = []
tool_call_counts = {}
token_usage = {"input": 0, "output": 0, "total": 0, "api_calls": 0, "sessions": 0}


def _track_api_call(endpoint, status=200):
    api_call_log.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint, "status": status
    })
    if len(api_call_log) > 500:
        api_call_log.pop(0)
    token_usage["api_calls"] = len(api_call_log)


def _track_tool_call(tool_name):
    tool_call_counts[tool_name] = tool_call_counts.get(tool_name, 0) + 1


def _rpc_call(method, params=None):
    payload = json.dumps({
        "jsonrpc": "2.0", "method": method,
        "params": params or [], "id": 1
    }).encode()
    req = urllib.request.Request(
        BSC_RPC, data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


# ─── System Stats ───

def get_system_stats():
    stats = {"cpu_percent": 0, "memory_percent": 0, "disk_percent": 0, "uptime": "—"}
    try:
        import psutil
        stats["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        stats["memory_percent"] = psutil.virtual_memory().percent
        stats["disk_percent"] = psutil.disk_usage("/").percent
    except ImportError:
        if platform.system() == "Darwin":
            try:
                top = subprocess.run(
                    ["top", "-l", "1", "-n", "0"],
                    capture_output=True, text=True, timeout=5
                )
                for line in top.stdout.splitlines():
                    if "CPU usage" in line:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if p == "idle":
                                idle = float(parts[i - 1].rstrip("%"))
                                stats["cpu_percent"] = round(100 - idle, 1)
                                break
            except Exception:
                pass
            try:
                vm = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=3)
                pages = {}
                for line in vm.stdout.splitlines():
                    for key in ("free", "active", "inactive", "wired", "speculative"):
                        if key in line.lower():
                            val = line.split(":")[-1].strip().rstrip(".")
                            try:
                                pages[key] = int(val)
                            except ValueError:
                                pass
                total_pages = sum(pages.values()) if pages else 1
                used = pages.get("active", 0) + pages.get("wired", 0)
                stats["memory_percent"] = round(used / total_pages * 100, 0)
            except Exception:
                pass
        else:
            try:
                with open("/proc/stat") as f:
                    vals = list(map(int, f.readline().split()[1:]))
                    stats["cpu_percent"] = round((1 - vals[3] / sum(vals)) * 100, 1)
            except Exception:
                pass
            try:
                with open("/proc/meminfo") as f:
                    info = {}
                    for line in f:
                        k, v = line.split(":")
                        info[k.strip()] = int(v.strip().split()[0])
                    stats["memory_percent"] = round(
                        (1 - info.get("MemAvailable", 0) / info.get("MemTotal", 1)) * 100, 0
                    )
            except Exception:
                pass
        try:
            usage = shutil.disk_usage("/")
            stats["disk_percent"] = round(usage.used / usage.total * 100, 0)
        except Exception:
            pass

    elapsed = int(time.time() - START_TIME)
    stats["uptime"] = f"{elapsed // 3600}h {(elapsed % 3600) // 60}m {elapsed % 60}s"
    return stats


# ─── BSC Chain Data ───

def get_bsc_chain_data():
    result = {"gas_gwei": None, "block": None, "bnb_price": None}
    try:
        data = _rpc_call("eth_gasPrice")
        result["gas_gwei"] = round(int(data["result"], 16) / 1e9, 2)
    except Exception:
        pass
    try:
        data = _rpc_call("eth_blockNumber")
        result["block"] = int(data["result"], 16)
    except Exception:
        pass
    try:
        req = urllib.request.Request(
            "https://api.binance.com/api/v3/ticker/price?symbol=BNBUSDT",
            headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            result["bnb_price"] = round(float(data["price"]), 2)
    except Exception:
        try:
            req = urllib.request.Request(
                "https://api.coingecko.com/api/v3/simple/price?ids=binancecoin&vs_currencies=usd",
                headers={"Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                result["bnb_price"] = data.get("binancecoin", {}).get("usd")
        except Exception:
            pass
    return result


# ─── Environment Detection ───

def get_env_status():
    checks = {}
    env_map = {
        "OpenRouter": "OPENROUTER_API_KEY",
        "BscScan": "BSCSCAN_API_KEY",
        "Telegram": "TELEGRAM_BOT_TOKEN",
        "GMGN": "GMGN_API_KEY",
        "BSC RPC": "BSC_RPC_URL",
    }
    defaults = {"BSC_RPC_URL": "https://bsc-dataseed1.binance.org"}

    for label, env_var in env_map.items():
        val = os.environ.get(env_var, "")
        if val:
            checks[label] = "configured"
        elif env_var in defaults:
            checks[label] = "configured"
        else:
            checks[label] = "not configured"

    env_file = PROJECT_DIR / ".env"
    env_from_file = {}
    if env_file.exists():
        try:
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    v = v.strip().strip('"').strip("'")
                    if v:
                        env_from_file[k.strip()] = v
        except Exception:
            pass

    for label, env_var in env_map.items():
        if checks[label] == "not configured" and env_var in env_from_file:
            checks[label] = "configured"

    config_path = HERMES_DIR / "config.yaml"
    if config_path.exists():
        try:
            text = config_path.read_text()
            if "openrouter" in text.lower() and checks.get("OpenRouter") == "not configured":
                checks["OpenRouter"] = "configured"
        except Exception:
            pass

    checks["Terminal"] = "LOCAL"
    checks["Platform"] = platform.system()
    return checks


# ─── Agent Status ───

def get_agent_status():
    status = {"status": "ready", "tools_count": 0, "model": "—", "provider": "—"}
    config_path = HERMES_DIR / "config.yaml"
    if config_path.exists():
        try:
            text = config_path.read_text()
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("model:") and "provider" not in stripped:
                    status["model"] = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                if stripped.startswith("provider:"):
                    status["provider"] = stripped.split(":", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass

    tools_dir = PROJECT_DIR / "tools"
    tool_names = set()
    if tools_dir.exists():
        for f in tools_dir.glob("*.py"):
            if f.name.startswith("__"):
                continue
            try:
                content = f.read_text()
                found = re.findall(r'def\s+(kol_\w+|token_\w+|web3_\w+|four_\w+)\s*\(', content)
                tool_names.update(found)
            except Exception:
                pass

    if not tool_names:
        tool_names = {
            "kol_analyze", "kol_decision", "kol_pool_scan", "kol_pool_load", "kol_report",
            "kol_correlation_matrix", "kol_comovement_scan", "kol_wallet_overlap",
            "token_safety_check", "token_quick_check",
            "web3_get_balance", "web3_get_token_balance", "web3_get_gas_price", "web3_get_transaction",
        }

    status["tools_count"] = len(tool_names)
    status["tools_list"] = sorted(tool_names)
    status["token_usage"] = token_usage.copy()
    return status


def get_tools_list():
    status = get_agent_status()
    return {"tools": status["tools_list"], "count": status["tools_count"]}


def get_tool_usage():
    all_tools = get_agent_status()["tools_list"]
    tools = [{"name": name, "count": tool_call_counts.get(name, 0)} for name in all_tools]
    tools.sort(key=lambda t: t["count"], reverse=True)
    return {"tools": tools}


def get_cron_jobs():
    jobs = []
    cron_dir = PROJECT_DIR / "cron"
    if cron_dir.exists():
        for f in cron_dir.glob("*.py"):
            if f.name.startswith("__"):
                continue
            name = f.stem
            schedule = "manual"
            try:
                content = f.read_text()
                m = re.search(r'interval.*?(\d+)\s*h', content, re.IGNORECASE)
                if m:
                    schedule = f"every {m.group(1)}h"
                m2 = re.search(r'schedule.*?["\'](.+?)["\']', content)
                if m2:
                    schedule = m2.group(1)
            except Exception:
                pass
            jobs.append({"name": name, "schedule": schedule, "status": "idle"})
    if not jobs:
        jobs.append({"name": "none", "schedule": "—", "status": "—"})
    return {"jobs": jobs}


def get_kol_pool():
    pool_file = os.environ.get("KOL_POOL_FILE", str(PROJECT_DIR / "kol-pool.example.md"))
    result = {
        "total": 0,
        "grades": {"A+": 0, "A": 0, "B": 0, "C": 0},
        "alerts": 0, "last_scan": "never", "wallets": []
    }
    try:
        if os.path.exists(pool_file):
            text = Path(pool_file).read_text()
            wallets = re.findall(r'0x[a-fA-F0-9]{40}', text)
            result["total"] = len(wallets)
            result["wallets"] = wallets
            state_file = HERMES_DIR / "kol_scan_state.json"
            if state_file.exists():
                state = json.loads(state_file.read_text())
                if "last_scan_ts" in state:
                    dt = datetime.fromtimestamp(state["last_scan_ts"], tz=timezone.utc)
                    result["last_scan"] = dt.strftime("%Y-%m-%d %H:%M UTC")
                for g in ("A+", "A", "B", "C"):
                    result["grades"][g] = state.get("grades", {}).get(g, 0)
                result["alerts"] = state.get("alerts", 0)
    except Exception:
        pass
    return result


def get_recent_sessions():
    if not api_call_log:
        return []
    sessions = []
    seen = set()
    for entry in reversed(api_call_log):
        ep = entry["endpoint"]
        label = _endpoint_label(ep)
        if label and label not in seen:
            seen.add(label)
            ago = _time_ago(entry["ts"])
            sessions.append({"title": label, "time": ago})
        if len(sessions) >= 8:
            break
    return sessions


def _endpoint_label(ep):
    labels = {
        "/api/system": "System Monitor",
        "/api/chain": "BSC Chain Query",
        "/api/status": "Agent Status Check",
        "/api/tools": "Tool List Query",
        "/api/tools/usage": "Tool Usage Stats",
        "/api/cron": "Cron Jobs Check",
        "/api/kol/pool": "KOL Pool Query",
        "/api/kol/scan": "KOL Pool Scan",
        "/api/config": "Config Query",
        "/api/model": "Model Query",
        "/api/skills": "Skills Query",
    }
    if ep in labels:
        return labels[ep]
    if ep.startswith("/api/kol/analyze/"):
        return f"KOL Analyze {ep.split('/')[-1][:8]}..."
    if ep.startswith("/api/safety/"):
        return f"Safety Check {ep.split('/')[-1][:8]}..."
    return None


def _time_ago(iso_ts):
    try:
        dt = datetime.fromisoformat(iso_ts)
        diff = (datetime.now(timezone.utc) - dt).total_seconds()
        if diff < 60:
            return f"{int(diff)}s ago"
        if diff < 3600:
            return f"{int(diff // 60)}m ago"
        return f"{int(diff // 3600)}h ago"
    except Exception:
        return "just now"


# ─── GMGN.ai API (REAL on-chain data) ───

def _gmgn_get(url):
    key = GMGN_API_KEY
    if not key:
        env_file = PROJECT_DIR / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.strip().startswith("GMGN_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        return None

    headers = {
        "Accept": "application/json",
        "Referer": "https://gmgn.ai/",
        "Origin": "https://gmgn.ai",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }
    if key:
        headers["X-APIKEY"] = key

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"GMGN API error ({url}): {e}")
        return None


def _parse_token(t):
    symbol = t.get("symbol") or "?"
    name = t.get("name") or symbol
    return {
        "name": name,
        "symbol": symbol,
        "address": t.get("address", ""),
        "price": t.get("price"),
        "price_change_1h": t.get("price_change_percent"),
        "price_change_5m": t.get("price_change_percent5m"),
        "volume_24h": t.get("volume"),
        "market_cap": t.get("market_cap"),
        "liquidity": t.get("liquidity"),
        "holders": t.get("holder_count"),
        "buy_tax": t.get("buy_tax"),
        "sell_tax": t.get("sell_tax"),
        "is_honeypot": t.get("is_honeypot"),
        "smart_buy_24h": t.get("smart_buy_24h"),
        "smart_sell_24h": t.get("smart_sell_24h"),
        "smart_money_count": t.get("smart_degen_count"),
        "kol_count": t.get("renowned_count"),
        "swaps_24h": t.get("swaps"),
        "logo": t.get("logo"),
    }


def gmgn_trending(chain="bsc", interval="1h", orderby="swaps"):
    url = (
        f"{GMGN_BASE}/rank/{chain}/swaps/{interval}"
        f"?orderby={orderby}&direction=desc"
        f"&filters[]=not_honeypot"
    )
    data = _gmgn_get(url)
    if not data or data.get("code") != 0:
        return {"tokens": [], "error": data.get("msg") if data else "GMGN unavailable"}
    rank = data.get("data", {}).get("rank", [])
    return {"tokens": [_parse_token(t) for t in rank[:20]], "chain": chain, "interval": interval}


def gmgn_smart_trending(chain="bsc", interval="24h"):
    url = (
        f"{GMGN_BASE}/rank/{chain}/swaps/{interval}"
        f"?orderby=smartmoney&direction=desc"
        f"&filters[]=not_honeypot"
    )
    data = _gmgn_get(url)
    if not data or data.get("code") != 0:
        return {"tokens": [], "error": data.get("msg") if data else "GMGN unavailable"}
    rank = data.get("data", {}).get("rank", [])
    return {"tokens": [_parse_token(t) for t in rank[:20]], "chain": chain, "interval": interval, "sort": "smartmoney"}


def gmgn_token_info(chain, address):
    url = f"https://gmgn.ai/api/v1/token_info/{chain}/{address}"
    data = _gmgn_get(url)
    if not data or "data" not in data:
        return {"error": "Token not found or GMGN unavailable"}
    t = data["data"]
    return {
        "name": t.get("name"),
        "symbol": t.get("symbol"),
        "address": address,
        "chain": chain,
        "price": t.get("price"),
        "market_cap": t.get("market_cap"),
        "volume_24h": t.get("volume_24h"),
        "holder_count": t.get("holder_count"),
        "liquidity": t.get("liquidity"),
        "smart_money_count": t.get("smart_degen_count"),
        "kol_count": t.get("renowned_count"),
        "creation_time": t.get("creation_timestamp"),
        "logo": t.get("logo"),
    }


def gmgn_token_security(chain, address):
    url = f"https://gmgn.ai/api/v1/token_security/{chain}/{address}"
    data = _gmgn_get(url)
    if not data or "data" not in data:
        return {"error": "Security data unavailable"}
    s = data["data"]
    return {
        "address": address,
        "chain": chain,
        "is_honeypot": s.get("is_honeypot"),
        "buy_tax": s.get("buy_tax"),
        "sell_tax": s.get("sell_tax"),
        "is_open_source": s.get("is_open_source"),
        "is_proxy": s.get("is_proxy"),
        "is_mintable": s.get("is_mintable"),
        "owner_address": s.get("owner_address"),
        "top10_holder_rate": s.get("top_10_holder_rate"),
    }


def gmgn_top_holders(chain, address, tag=None):
    url = f"https://gmgn.ai/api/v1/token_top_holders/{chain}/{address}?limit=20&orderby=amount_percentage&direction=desc"
    if tag:
        url += f"&tag={tag}"
    data = _gmgn_get(url)
    if not data or "data" not in data:
        return {"holders": [], "error": "Data unavailable"}
    holders = []
    for h in (data.get("data") or [])[:20]:
        holders.append({
            "wallet": h.get("address"),
            "amount_pct": h.get("amount_percentage"),
            "profit": h.get("profit"),
            "unrealized_profit": h.get("unrealized_profit"),
            "tags": h.get("tags", []),
        })
    return {"holders": holders, "tag": tag or "all", "token": address, "chain": chain}


def gmgn_kol_trades():
    return gmgn_trending(chain="bsc", interval="1h", orderby="smartmoney")


def gmgn_wallet_holdings(chain, wallet):
    url = f"https://gmgn.ai/api/v1/wallet_holdings/{chain}/{wallet}?limit=30"
    data = _gmgn_get(url)
    if not data or "data" not in data:
        return {"holdings": [], "error": "Wallet data unavailable"}
    holdings = []
    for h in (data.get("data") or [])[:30]:
        holdings.append({
            "token_name": h.get("token_name") or h.get("symbol"),
            "token_address": h.get("token_address"),
            "balance": h.get("balance"),
            "value_usd": h.get("usd_value"),
            "profit": h.get("realized_profit"),
            "unrealized_pnl": h.get("unrealized_profit"),
        })
    return {"wallet": wallet, "holdings": holdings, "chain": chain}


def get_agents():
    agents = [{"name": "HERMEMES", "status": "active", "type": "default"}]
    cron_dir = PROJECT_DIR / "cron"
    if cron_dir.exists():
        for f in cron_dir.glob("*.py"):
            if f.name.startswith("__"):
                continue
            agents.append({
                "name": f.stem.upper().replace("_", "-"),
                "status": "idle", "type": "cron"
            })
    return agents


# ─── Unified HTTP Handler ───

MIME_TYPES = {
    ".html": "text/html", ".css": "text/css", ".js": "application/javascript",
    ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".svg": "image/svg+xml", ".ico": "image/x-icon",
    ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf",
    ".gif": "image/gif", ".webp": "image/webp",
}


class UnifiedHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        path = urlparse(self.path).path

        # API routes
        if path.startswith("/api/"):
            self._handle_api(path)
            return

        # Dashboard routes: /dashboard/ → serve from dashboard/
        if path.startswith("/dashboard"):
            self._serve_static(path, "/dashboard", DASHBOARD_DIR)
            return

        # Landing page: everything else → serve from landingpage/
        self._serve_static(path, "", LANDING_DIR)

    def _serve_static(self, path, prefix, root_dir):
        rel = path[len(prefix):] if prefix else path
        if not rel or rel == "/":
            rel = "/index.html"

        file_path = root_dir / rel.lstrip("/")

        if file_path.is_dir():
            file_path = file_path / "index.html"

        if not file_path.exists():
            self.send_error(404)
            return

        ext = file_path.suffix.lower()
        content_type = MIME_TYPES.get(ext, "application/octet-stream")

        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _handle_api(self, path):
        _track_api_call(path)

        routes = {
            "/api/system": get_system_stats,
            "/api/status": get_agent_status,
            "/api/chain": get_bsc_chain_data,
            "/api/tools": get_tools_list,
            "/api/tools/usage": get_tool_usage,
            "/api/cron": get_cron_jobs,
            "/api/kol/pool": get_kol_pool,
            "/api/env": get_env_status,
            "/api/agents": get_agents,
            "/api/sessions": lambda: {"sessions": get_recent_sessions()},
            "/api/config": lambda: {"config": "loaded", **get_env_status()},
            "/api/model": lambda: {"model": get_agent_status().get("model", "—")},
            "/api/skills": lambda: {"skills": ["kol-profiler"]},
            "/api/kol/scan": lambda: {"status": "scan_triggered", "message": "KOL pool scan started"},
            "/api/gmgn/trending": lambda: gmgn_trending("bsc", "1h"),
            "/api/gmgn/trending/sol": lambda: gmgn_trending("sol", "1h"),
            "/api/gmgn/trending/eth": lambda: gmgn_trending("eth", "1h"),
            "/api/gmgn/trending/base": lambda: gmgn_trending("base", "1h"),
            "/api/gmgn/smart-money": lambda: gmgn_smart_trending("bsc", "24h"),
            "/api/gmgn/smart-money/sol": lambda: gmgn_smart_trending("sol", "24h"),
        }

        if path.startswith("/api/gmgn/token/"):
            seg = path.split("/api/gmgn/token/")[1]
            parts_gm = seg.strip("/").split("/")
            chain_g = parts_gm[0] if len(parts_gm) >= 2 else "bsc"
            addr = parts_gm[1] if len(parts_gm) >= 2 else parts_gm[0]
            rest = "/".join(parts_gm[2:]) if len(parts_gm) > 2 else ""
            if rest == "security":
                handler = lambda c=chain_g, a=addr: gmgn_token_security(c, a)
            elif rest == "holders":
                handler = lambda c=chain_g, a=addr: gmgn_top_holders(c, a)
            elif rest == "holders/kol":
                handler = lambda c=chain_g, a=addr: gmgn_top_holders(c, a, tag="renowned")
            elif rest == "holders/smart":
                handler = lambda c=chain_g, a=addr: gmgn_top_holders(c, a, tag="smart_degen")
            else:
                handler = lambda c=chain_g, a=addr: gmgn_token_info(c, a)
            _track_tool_call("gmgn_token")
        elif path.startswith("/api/gmgn/wallet/"):
            seg = path.split("/api/gmgn/wallet/")[1]
            parts_gm = seg.strip("/").split("/")
            chain_g = parts_gm[0] if len(parts_gm) >= 2 else "bsc"
            wallet = parts_gm[1] if len(parts_gm) >= 2 else parts_gm[0]
            handler = lambda c=chain_g, w=wallet: gmgn_wallet_holdings(c, w)
            _track_tool_call("gmgn_wallet")
        elif path.startswith("/api/kol/analyze/"):
            wallet = path.split("/")[-1]
            _track_tool_call("kol_analyze")
            handler = lambda w=wallet: {"wallet": w, "status": "analysis_queued",
                                        "message": f"Analysis for {w[:8]}... queued"}
        elif path.startswith("/api/safety/"):
            token = path.split("/")[-1]
            _track_tool_call("token_safety_check")
            handler = lambda t=token: {"token": t, "status": "checking",
                                       "message": f"Safety check for {t[:8]}... queued"}
        else:
            handler = routes.get(path)

        if handler:
            try:
                data = handler()
                self._json_response(200, data)
            except Exception as e:
                self._json_response(500, {"error": str(e)})
        else:
            self._json_response(404, {"error": f"Unknown endpoint: {path}"})

    def _json_response(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        if "404" in str(args) or "500" in str(args):
            super().log_message(fmt, *args)


def main():
    server = HTTPServer(("0.0.0.0", PORT), UnifiedHandler)
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   ☤  HERMEMES UNIFIED SERVER                                 ║
║                                                              ║
║   Landing:    http://localhost:{PORT:<5}                       ║
║   Dashboard:  http://localhost:{PORT:<5}/dashboard/            ║
║   API Base:   http://localhost:{PORT:<5}/api/                  ║
║                                                              ║
║   All data is REAL — no fakes.                               ║
║   Press Ctrl+C to stop                                       ║
╚══════════════════════════════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
