#!/usr/bin/env python3
"""Post Step-2 verification: logs, API, trade history."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from remote_deploy import HOST, PROJ, USER, load_password  # noqa: E402


def run_out(c, cmd, t=90):
    _, o, e = c.exec_command(cmd, timeout=t)
    return (o.read() + e.read()).decode(errors="replace").strip()


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=load_password(), timeout=45)
    try:
        sections = [
            ("ENV", f"grep -E '^(LIVE_LIH_DRY_RUN|DH_ENABLE_5M)' '{PROJ}/.env'"),
            (
                "ROUND_LOG",
                f"grep -aE 'LIH LIVE|LIVE EXEC|Bridge fill|pending|CRITICAL|invalid signature|REJECTED' "
                f"'{PROJ}/bot.log' | tail -30",
            ),
            (
                "API",
                "curl -s http://127.0.0.1:8081/api/config | python3 -c \"import sys,json; "
                "d=json.load(sys.stdin); l=d.get('live',{}); "
                "print('dryRun', l.get('liveLihDryRun')); "
                "print('openCount', l.get('openCount')); "
                "print('session', l.get('lihSessionLegsUsed'), '/', l.get('lihSessionMaxLegs')); "
                "th=l.get('tradeHistory') or []; print('tradeHistory', len(th)); "
                "[print(' ', t) for t in th[-5:]]; "
                "ops=l.get('openPositions') or []; "
                "[print('pos', p) for p in ops]\"",
            ),
            (
                "LIVE_STATE",
                f"cd '{PROJ}' && .venv/bin/python -c \"import json,os; "
                "p='logs/live_state.json'; "
                "d=json.load(open(p)) if os.path.isfile(p) else {{}}; "
                "print('open', len(d.get('open_lih_positions',{{}}))); "
                "print('closed', len(d.get('closed_lih_positions',[]))); "
                "print('total_trades', d.get('total_lih_trades',0))\"",
            ),
            ("BALANCE", f"cd '{PROJ}' && .venv/bin/python fetch_balance.py 2>&1 | tail -3"),
            (
                "HEDGED",
                f"grep -a 'LIH-btc-1781698814991' '{PROJ}/bot.log' | tail -20",
            ),
            (
                "RECON",
                f"grep -aE 'reconcile|recon' '{PROJ}/bot.log' '{PROJ}/logs/bridge.log' 2>/dev/null | tail -25",
            ),
            (
                "REGISTER",
                f"grep -aE 'register_lih|OPENED|CLOSED' '{PROJ}/bot.log' | tail -20",
            ),
            ("LIVE_STATE_RAW", f"head -80 '{PROJ}/logs/live_state.json' 2>/dev/null || echo missing"),
        ]
        for title, cmd in sections:
            print(f"\n=== {title} ===")
            print(run_out(c, cmd))
    finally:
        c.close()


if __name__ == "__main__":
    main()
