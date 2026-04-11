"""Binance Web3 / EVM-Compatible Chain Tool

Provides read-only on-chain data tools for Ethereum-compatible networks.
Supports Ethereum, BSC (Binance Smart Chain), Polygon, Arbitrum, and Base.

Uses the Binance Web3 Connect EVM-Compatible Provider pattern — JSON-RPC
calls over HTTPS, no wallet private key needed for read operations.

Registered tools:
- ``web3_get_balance``      — native token balance (ETH / BNB / MATIC…)
- ``web3_get_token_balance``— ERC-20 token balance for an address
- ``web3_get_gas_price``    — current network gas price
- ``web3_get_transaction``  — details of a transaction by hash

No extra dependencies — uses httpx which is already a project dependency.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Network configuration
# ---------------------------------------------------------------------------

_NETWORKS: Dict[str, Dict[str, Any]] = {
    "ethereum": {
        "name": "Ethereum Mainnet",
        "chain_id": 1,
        "rpc": os.getenv("ETH_RPC_URL", "https://eth.llamarpc.com"),
        "symbol": "ETH",
        "explorer": "https://etherscan.io",
    },
    "bsc": {
        "name": "BNB Smart Chain",
        "chain_id": 56,
        "rpc": os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org"),
        "symbol": "BNB",
        "explorer": "https://bscscan.com",
    },
    "polygon": {
        "name": "Polygon",
        "chain_id": 137,
        "rpc": os.getenv("POLYGON_RPC_URL", "https://polygon.llamarpc.com"),
        "symbol": "MATIC",
        "explorer": "https://polygonscan.com",
    },
    "arbitrum": {
        "name": "Arbitrum One",
        "chain_id": 42161,
        "rpc": os.getenv("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc"),
        "symbol": "ETH",
        "explorer": "https://arbiscan.io",
    },
    "base": {
        "name": "Base",
        "chain_id": 8453,
        "rpc": os.getenv("BASE_RPC_URL", "https://mainnet.base.org"),
        "symbol": "ETH",
        "explorer": "https://basescan.org",
    },
}

# ERC-20 minimal ABI selectors (keccak256 first 4 bytes)
_ERC20_BALANCE_OF_SELECTOR = "0x70a08231"  # balanceOf(address)
_ERC20_DECIMALS_SELECTOR = "0x313ce567"    # decimals()
_ERC20_SYMBOL_SELECTOR = "0x95d89b41"      # symbol()

_TIMEOUT = 15.0


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

async def _rpc(network: str, method: str, params: list) -> Any:
    """Make a single JSON-RPC call and return the ``result`` field."""
    cfg = _NETWORKS.get(network)
    if not cfg:
        raise ValueError(f"Unknown network '{network}'. Choose: {', '.join(_NETWORKS)}")

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(cfg["rpc"], json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"RPC error: {data['error']}")
        return data["result"]


def _hex_to_int(hex_val: str) -> int:
    if not hex_val or hex_val == "0x":
        return 0
    return int(hex_val, 16)


def _wei_to_native(wei: int, decimals: int = 18) -> float:
    return wei / (10 ** decimals)


def _pad_address(addr: str) -> str:
    """Pad an Ethereum address to 32 bytes for ABI encoding."""
    addr = addr.lower().replace("0x", "")
    return "0x" + addr.zfill(64)


def _decode_uint256(hex_data: str) -> int:
    if not hex_data or hex_data == "0x":
        return 0
    return int(hex_data, 16)


def _decode_string(hex_data: str) -> str:
    """Decode an ABI-encoded string from a hex eth_call result."""
    try:
        if not hex_data or hex_data == "0x":
            return ""
        raw = bytes.fromhex(hex_data[2:])
        # ABI string: offset(32), length(32), data
        if len(raw) < 64:
            return raw.rstrip(b"\x00").decode("utf-8", errors="replace")
        length = int.from_bytes(raw[32:64], "big")
        return raw[64:64 + length].decode("utf-8", errors="replace")
    except Exception:
        return hex_data


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def _handle_get_balance(address: str, network: str = "bsc") -> str:
    """Get native token balance for ``address`` on ``network``."""
    address = address.strip()
    network = network.strip().lower()

    cfg = _NETWORKS.get(network)
    if not cfg:
        return f"❌ Unknown network '{network}'. Available: {', '.join(_NETWORKS)}"

    try:
        raw = await _rpc(network, "eth_getBalance", [address, "latest"])
        wei = _hex_to_int(raw)
        amount = _wei_to_native(wei)
        block_raw = await _rpc(network, "eth_blockNumber", [])
        block = _hex_to_int(block_raw)

        return json.dumps({
            "address": address,
            "network": cfg["name"],
            "chain_id": cfg["chain_id"],
            "balance_wei": str(wei),
            "balance": f"{amount:.8f} {cfg['symbol']}",
            "block": block,
            "explorer": f"{cfg['explorer']}/address/{address}",
        }, indent=2)
    except Exception as e:
        return f"❌ Failed to get balance: {e}"


async def _handle_get_token_balance(
    address: str,
    token_contract: str,
    network: str = "bsc",
) -> str:
    """Get ERC-20 token balance for ``address`` on ``network``."""
    address = address.strip()
    token_contract = token_contract.strip()
    network = network.strip().lower()

    cfg = _NETWORKS.get(network)
    if not cfg:
        return f"❌ Unknown network '{network}'. Available: {', '.join(_NETWORKS)}"

    try:
        balance_data = _ERC20_BALANCE_OF_SELECTOR + _pad_address(address)[2:]
        raw_balance = await _rpc(network, "eth_call", [
            {"to": token_contract, "data": balance_data}, "latest"
        ])

        raw_decimals = await _rpc(network, "eth_call", [
            {"to": token_contract, "data": _ERC20_DECIMALS_SELECTOR}, "latest"
        ])
        raw_symbol = await _rpc(network, "eth_call", [
            {"to": token_contract, "data": _ERC20_SYMBOL_SELECTOR}, "latest"
        ])

        balance_raw = _decode_uint256(raw_balance)
        decimals = _decode_uint256(raw_decimals) or 18
        symbol = _decode_string(raw_symbol) or "TOKEN"
        balance = _wei_to_native(balance_raw, decimals)

        return json.dumps({
            "address": address,
            "token_contract": token_contract,
            "network": cfg["name"],
            "chain_id": cfg["chain_id"],
            "symbol": symbol,
            "decimals": decimals,
            "balance_raw": str(balance_raw),
            "balance": f"{balance:.8f} {symbol}",
            "explorer": f"{cfg['explorer']}/token/{token_contract}?a={address}",
        }, indent=2)
    except Exception as e:
        return f"❌ Failed to get token balance: {e}"


async def _handle_get_gas_price(network: str = "bsc") -> str:
    """Get current gas price and base fee on ``network``."""
    network = network.strip().lower()
    cfg = _NETWORKS.get(network)
    if not cfg:
        return f"❌ Unknown network '{network}'. Available: {', '.join(_NETWORKS)}"

    try:
        raw = await _rpc(network, "eth_gasPrice", [])
        wei = _hex_to_int(raw)
        gwei = wei / 1e9

        result: Dict[str, Any] = {
            "network": cfg["name"],
            "chain_id": cfg["chain_id"],
            "gas_price_wei": str(wei),
            "gas_price_gwei": f"{gwei:.4f} Gwei",
        }

        try:
            latest = await _rpc(network, "eth_getBlockByNumber", ["latest", False])
            if latest and "baseFeePerGas" in latest:
                base_fee = _hex_to_int(latest["baseFeePerGas"])
                result["base_fee_gwei"] = f"{base_fee / 1e9:.4f} Gwei"
                result["suggested_priority_fee_gwei"] = f"{max(0.1, (wei - base_fee) / 1e9):.4f} Gwei"
        except Exception:
            pass

        return json.dumps(result, indent=2)
    except Exception as e:
        return f"❌ Failed to get gas price: {e}"


async def _handle_get_transaction(tx_hash: str, network: str = "bsc") -> str:
    """Get details of a transaction by hash on ``network``."""
    tx_hash = tx_hash.strip()
    network = network.strip().lower()

    cfg = _NETWORKS.get(network)
    if not cfg:
        return f"❌ Unknown network '{network}'. Available: {', '.join(_NETWORKS)}"

    try:
        tx = await _rpc(network, "eth_getTransactionByHash", [tx_hash])
        if not tx:
            return f"❌ Transaction {tx_hash} not found on {cfg['name']}"

        receipt = None
        try:
            receipt = await _rpc(network, "eth_getTransactionReceipt", [tx_hash])
        except Exception:
            pass

        value_wei = _hex_to_int(tx.get("value", "0x0"))
        gas_price_wei = _hex_to_int(tx.get("gasPrice", "0x0"))
        gas_used = _hex_to_int(receipt.get("gasUsed", "0x0")) if receipt else None
        status = None
        if receipt:
            status_raw = _hex_to_int(receipt.get("status", "0x1"))
            status = "success" if status_raw == 1 else "failed"

        result: Dict[str, Any] = {
            "hash": tx_hash,
            "network": cfg["name"],
            "from": tx.get("from"),
            "to": tx.get("to"),
            "value": f"{_wei_to_native(value_wei):.8f} {cfg['symbol']}",
            "gas_price_gwei": f"{gas_price_wei / 1e9:.4f} Gwei",
            "block": _hex_to_int(tx.get("blockNumber", "0x0")) if tx.get("blockNumber") else "pending",
            "status": status or "pending",
            "explorer": f"{cfg['explorer']}/tx/{tx_hash}",
        }
        if gas_used is not None:
            fee_wei = gas_used * gas_price_wei
            result["fee"] = f"{_wei_to_native(fee_wei):.8f} {cfg['symbol']}"
            result["gas_used"] = gas_used

        return json.dumps(result, indent=2)
    except Exception as e:
        return f"❌ Failed to get transaction: {e}"


# ---------------------------------------------------------------------------
# Sync wrappers
# ---------------------------------------------------------------------------

def _sync(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=30)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def web3_get_balance(address: str, network: str = "bsc") -> str:
    return _sync(_handle_get_balance(address, network))


def web3_get_token_balance(address: str, token_contract: str, network: str = "bsc") -> str:
    return _sync(_handle_get_token_balance(address, token_contract, network))


def web3_get_gas_price(network: str = "bsc") -> str:
    return _sync(_handle_get_gas_price(network))


def web3_get_transaction(tx_hash: str, network: str = "bsc") -> str:
    return _sync(_handle_get_transaction(tx_hash, network))


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

from tools.registry import registry  # noqa: E402

_NETWORKS_ENUM = list(_NETWORKS.keys())

registry.register(
    name="web3_get_balance",
    toolset="web3",
    schema={
        "type": "function",
        "function": {
            "name": "web3_get_balance",
            "description": (
                "Get the native token balance (ETH, BNB, MATIC…) for an Ethereum-compatible "
                "wallet address. Supports Ethereum, BSC (Binance Smart Chain), Polygon, "
                "Arbitrum, and Base. Returns balance in both wei and human-readable format."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Ethereum-compatible wallet address (0x…)",
                    },
                    "network": {
                        "type": "string",
                        "enum": _NETWORKS_ENUM,
                        "description": "Network to query. Default: bsc",
                        "default": "bsc",
                    },
                },
                "required": ["address"],
            },
        },
    },
    handler=web3_get_balance,
    description="Get native token balance on EVM chains",
    emoji="💰",
)

registry.register(
    name="web3_get_token_balance",
    toolset="web3",
    schema={
        "type": "function",
        "function": {
            "name": "web3_get_token_balance",
            "description": (
                "Get the ERC-20 token balance for a wallet address on an EVM-compatible chain. "
                "Automatically reads the token's symbol and decimals from the contract."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Wallet address to check (0x…)",
                    },
                    "token_contract": {
                        "type": "string",
                        "description": "ERC-20 token contract address (0x…)",
                    },
                    "network": {
                        "type": "string",
                        "enum": _NETWORKS_ENUM,
                        "description": "Network to query. Default: bsc",
                        "default": "bsc",
                    },
                },
                "required": ["address", "token_contract"],
            },
        },
    },
    handler=web3_get_token_balance,
    description="Get ERC-20 token balance on EVM chains",
    emoji="🪙",
)

registry.register(
    name="web3_get_gas_price",
    toolset="web3",
    schema={
        "type": "function",
        "function": {
            "name": "web3_get_gas_price",
            "description": (
                "Get the current gas price and base fee on an EVM-compatible chain. "
                "Useful for estimating transaction costs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "network": {
                        "type": "string",
                        "enum": _NETWORKS_ENUM,
                        "description": "Network to query. Default: bsc",
                        "default": "bsc",
                    },
                },
                "required": [],
            },
        },
    },
    handler=web3_get_gas_price,
    description="Get current gas price on EVM chains",
    emoji="⛽",
)

registry.register(
    name="web3_get_transaction",
    toolset="web3",
    schema={
        "type": "function",
        "function": {
            "name": "web3_get_transaction",
            "description": (
                "Get details of a transaction by its hash on an EVM-compatible chain. "
                "Returns sender, recipient, value, gas fee, block, and status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tx_hash": {
                        "type": "string",
                        "description": "Transaction hash (0x…)",
                    },
                    "network": {
                        "type": "string",
                        "enum": _NETWORKS_ENUM,
                        "description": "Network to query. Default: bsc",
                        "default": "bsc",
                    },
                },
                "required": ["tx_hash"],
            },
        },
    },
    handler=web3_get_transaction,
    description="Get EVM transaction details by hash",
    emoji="🔍",
)
