"""
redeem_positions.py — On-chain CTF redeem for resolved Polymarket markets.

Called by the C++ core after live DH expiry. Prints one JSON line to stdout:
  {"success": true, "tx_hash": "0x...", "message": "..."}

Requires: POLYMARKET_PRIVATE_KEY, web3
"""
from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv


def redeem_positions(condition_id: str) -> dict:
    load_dotenv()

    cid = (condition_id or "").strip()
    if not cid:
        return {"success": False, "tx_hash": None, "message": "condition_id required"}

    paper = os.getenv("PAPER_MODE", "true").strip().lower()
    if paper in ("true", "1", "yes"):
        return {"success": True, "tx_hash": None, "message": "Paper mode — skipped"}

    pk = os.getenv("POLYMARKET_PRIVATE_KEY", "").strip()
    if not pk:
        return {"success": False, "tx_hash": None, "message": "POLYMARKET_PRIVATE_KEY missing"}
    if not pk.startswith("0x"):
        pk = "0x" + pk

    try:
        from web3 import Web3
        from web3.middleware import geth_poa_middleware
    except ImportError:
        return {
            "success": False,
            "tx_hash": None,
            "message": "web3 not installed — add web3>=6.0.0,<8.0.0 to requirements.txt",
        }

    CTF_CONTRACT = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
    USDC_ADDRESS = "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359"
    RPC_URLS = [
        "https://polygon-rpc.com",
        "https://rpc.ankr.com/polygon",
        "https://polygon-bor-rpc.publicnode.com",
        "https://1rpc.io/matic",
    ]
    REDEEM_SELECTOR = "0x01b7037c"

    cid_clean = cid[2:] if cid.startswith("0x") else cid
    cid_bytes32 = cid_clean.zfill(64).lower()
    parent_collection_id = "0" * 64
    collateral_bytes32 = "0" * 24 + USDC_ADDRESS[2:].lower()
    array_offset = 32 * 4
    array_length = 2

    encoded = (
        collateral_bytes32
        + parent_collection_id
        + cid_bytes32
        + hex(array_offset)[2:].zfill(64)
        + hex(array_length)[2:].zfill(64)
        + hex(1)[2:].zfill(64)
        + hex(2)[2:].zfill(64)
    )
    data = REDEEM_SELECTOR + encoded

    last_exc: Exception | None = None
    for rpc_url in RPC_URLS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 15}))
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)

            account = w3.eth.account.from_key(pk)
            wallet_address = account.address

            nonce = w3.eth.get_transaction_count(wallet_address)
            gas_price = w3.eth.gas_price

            tx = {
                "to": CTF_CONTRACT,
                "data": data,
                "value": 0,
                "gas": 200_000,
                "gasPrice": gas_price,
                "nonce": nonce,
                "chainId": 137,
            }

            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if not receipt.get("status"):
                raise RuntimeError(f"Tx reverted: {tx_hash.hex()}")

            return {
                "success": True,
                "tx_hash": tx_hash.hex(),
                "message": f"Redeemed {cid[:18]} via {rpc_url}",
            }
        except Exception as exc:
            last_exc = exc
            continue

    return {
        "success": False,
        "tx_hash": None,
        "message": str(last_exc) if last_exc else "All RPC endpoints failed",
    }


if __name__ == "__main__":
    condition = sys.argv[1] if len(sys.argv) > 1 else ""
    out = redeem_positions(condition)
    print(json.dumps(out))
    sys.exit(0 if out.get("success") else 1)
