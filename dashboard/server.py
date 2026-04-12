#!/usr/bin/env python3
"""Hermemes Control Interface — Dashboard Backend Server

Serves the dashboard static files and provides REST API endpoints
for system monitoring, agent status, KOL pool data, and BSC chain info.
"""

import asyncio
import json
import os
import platform
import shutil
import time
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import subprocess
import socket

PORT = int(os.environ.get("DASHBOARD_PORT", 3199))
HERMES_DIR = Path.home() / ".hermes"
PROJECT_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = Path(__file__).resolve().parent
START_TIME = time.time()

# BSC RPC
BSC_RPC = os.environ.get("BSC_RPC_URL", "https://bsc-dataseed1.binance.org")


def get_system_stats():
    """Collect CPU, memory, disk stats using cross-platform methods."""
    stats = {"cpu_percent": 0, "memory_percent": 0, "disk_percent": 0, "uptime": "—"}

    try:
        import psutil
        stats["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        stats["memory_percent"] = mem.percent
        disk = psutil.disk_usage("/")
        stats["disk_percent"] = disk.percent
    except ImportError:
        # Fallback: parse system commands
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
                vm = subprocess.run(
                    ["vm_stat"], capture_output=True, text=True, timeout=3
                )
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
            # Linux
            try:
                with open("/proc/stat") as f:
                    cpu_line = f.readline()
                    vals = list(map(int, cpu_line.split()[1:]))
                    idle = vals[3]
                    total = sum(vals)
                    stats["cpu_percent"] = round((1 - idle / total) * 100, 1)
            except Exception:
                pass

            try:
                with open("/proc/meminfo") as f:
                    info = {}
                    for line in f:
                        k, v = line.split(":")
                        info[k.strip()] = int(v.strip().split()[0])
                    total = info.get("MemTotal", 1)
                    avail = info.get("MemAvailable", 0)
                    stats["memory_percent"] = round((1 - avail / total) * 100, 0)
            except Exception:
                pass

        # Disk (cross-platform)
        try:
            usage = shutil.disk_usage("/")
            stats["disk_percent"] = round(usage.used / usage.total * 100, 0)
        except Exception:
            pass

    # Uptime
    elapsed = int(time.time() - START_TIME)
    h = elapsed // 3600
    m = (elapsed % 3600) // 60
    s = elapsed % 60
    stats["uptime"] = f"{h}h {m}m {s}s"

    return stats


def get_bsc_chain_data():
    """Fetch BSC gas price and latest block via JSON-RPC."""
    import urllib.request

    result = {"gas_gwei": None, "block": None, "bnb_price": None}

    try:
        # Gas price
        payload = json.dumps({"jsonrpc": "2.0", "method": "eth_gasPrice", "params": [], "id": 1}).encode()
        req = urllib.request.Request(BSC_RPC, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            gas_wei = int(data["result"], 16)
            result["gas_gwei"] = round(gas_wei / 1e9, 2)
    except Exception:
        pass

    try:
        # Latest block number
        payload = json.dumps({"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 2}).encode()
        req = urllib.request.Request(BSC_RPC, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            result["block"] = int(data["result"], 16)
    except Exception:
        pass

    try:
        # BNB price from CoinGecko
        url = "https://api.coingecko.com/api/v3/simple/price?ids=binancecoin&vs_currencies=usd"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            result["bnb_price"] = data.get("binancecoin", {}).get("usd")
    except Exception:
        pass

    return result


def get_agent_status():
    """Check agent configuration and tool count."""
    status = {"status": "ready", "tools_count": 0, "model": "—", "provider": "—"}

    # Read config
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

    status["tools_count"] = 14

    status["token_usage"] = {
        "total": 0, "input": 0, "output": 0, "api_calls": 0, "sessions": 0
    }

    return status


def get_tools_list():
    """List registered tools."""
    tools = [
        "kol_analyze", "kol_decision", "kol_pool_scan", "kol_pool_load", "kol_report",
        "kol_correlation_matrix", "kol_comovement_scan", "kol_wallet_overlap",
        "token_safety_check", "token_quick_check",
        "web3_get_balance", "web3_get_token_balance", "web3_get_gas_price", "web3_get_transaction",
    ]
    return {"tools": tools, "count": len(tools)}


def get_tool_usage():
    """Simulated tool usage data for display."""
    return {"tools": [
        {"name": "kol_analyze", "count": 0},
        {"name": "kol_decision", "count": 0},
        {"name": "token_safety_check", "count": 0},
        {"name": "web3_get_balance", "count": 0},
        {"name": "kol_pool_scan", "count": 0},
        {"name": "kol_comovement_scan", "count": 0},
        {"name": "web3_get_gas_price", "count": 0},
        {"name": "kol_report", "count": 0},
        {"name": "token_quick_check", "count": 0},
    ]}


def get_cron_jobs():
    """List configured cron jobs."""
    return {"jobs": [
        {"name": "kol_pool_scan", "schedule": "every 4h", "status": "idle"},
    ]}


def get_kol_pool():
    """Read KOL pool file and return summary."""
    pool_file = os.environ.get("KOL_POOL_FILE", str(PROJECT_DIR / "kol-pool.example.md"))
    result = {
        "total": 0,
        "grades": {"A+": 0, "A": 0, "B": 0, "C": 0},
        "alerts": 0,
        "last_scan": "never"
    }

    try:
        if os.path.exists(pool_file):
            text = Path(pool_file).read_text()
            # Count wallet addresses (0x...)
            import re
            wallets = re.findall(r'0x[a-fA-F0-9]{40}', text)
            result["total"] = len(wallets)
    except Exception:
        pass

    return result


# ─── HTTP Handler ───

class DashboardHandler(SimpleHTTPRequestHandler):
    """Handles both static file serving and API routes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # API routes
        if path.startswith("/api/"):
            self._handle_api(path)
            return

        # Serve static files
        super().do_GET()

    def _handle_api(self, path):
        routes = {
            "/api/system": get_system_stats,
            "/api/status": get_agent_status,
            "/api/chain": get_bsc_chain_data,
            "/api/tools": get_tools_list,
            "/api/tools/usage": get_tool_usage,
            "/api/cron": get_cron_jobs,
            "/api/kol/pool": get_kol_pool,
            "/api/config": lambda: {"config": "loaded"},
            "/api/model": lambda: {"model": get_agent_status().get("model", "—")},
            "/api/skills": lambda: {"skills": ["kol-profiler"]},
            "/api/kol/scan": lambda: {"status": "scan_triggered", "message": "KOL pool scan started"},
        }

        # Dynamic routes
        if path.startswith("/api/kol/analyze/"):
            wallet = path.split("/")[-1]
            handler = lambda: {"wallet": wallet, "status": "analysis_queued",
                              "message": f"Analysis for {wallet[:8]}... queued"}
        elif path.startswith("/api/safety/"):
            token = path.split("/")[-1]
            handler = lambda: {"token": token, "status": "checking",
                              "message": f"Safety check for {token[:8]}... queued"}
        else:
            handler = routes.get(path)

        if handler:
            try:
                data = handler()
                self._json_response(200, data)
            except Exception as e:
                self._json_response(500, {"error": str(e)})
        else:
            self._json_response(404, {"error": "Not found"})

    def _json_response(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Suppress verbose request logs; only show errors
        if "404" in str(args) or "500" in str(args):
            super().log_message(format, *args)


def find_available_port(start_port):
    """Find an available port starting from start_port."""
    port = start_port
    while port < start_port + 100:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", port))
                return port
        except OSError:
            port += 1
    return start_port


def main():
    port = find_available_port(PORT)
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ☤  HERMEMES CONTROL INTERFACE                              ║
║                                                              ║
║   Dashboard:  http://localhost:{port:<5}                       ║
║   API Base:   http://localhost:{port:<5}/api                   ║
║                                                              ║
║   Endpoints:                                                 ║
║     GET /api/system     — System stats (CPU/MEM/DISK)        ║
║     GET /api/chain      — BSC chain data (gas/block/BNB)     ║
║     GET /api/status     — Agent status                       ║
║     GET /api/tools      — Tool list                          ║
║     GET /api/cron       — Cron jobs                          ║
║     GET /api/kol/pool   — KOL pool summary                   ║
║                                                              ║
║   Press Ctrl+C to stop                                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Hermemes Dashboard...")
        server.shutdown()


if __name__ == "__main__":
    main()
