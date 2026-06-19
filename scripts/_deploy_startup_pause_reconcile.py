#!/usr/bin/env python3
"""Deploy: hard startup PAUSED + chain reconcile loop. Restart bot paused."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from remote_deploy import (  # noqa: E402
    BUILD_VPS,
    HOST,
    KILL_STALE_BUILD,
    PROJ,
    ROOT,
    USER,
    load_password,
    run,
)


def run_out(c, cmd: str, t: int = 600) -> str:
    _, o, e = c.exec_command(cmd, timeout=t)
    return (o.read() + e.read()).decode(errors="replace").strip()


def main() -> int:
    uploads = [
        (ROOT / "trading-core/src/main.cpp", f"{PROJ}/trading-core/src/main.cpp"),
        (ROOT / "trading-core/src/risk/RiskManager.cpp", f"{PROJ}/trading-core/src/risk/RiskManager.cpp"),
        (ROOT / "scripts/live_lih_reconcile.py", f"{PROJ}/scripts/live_lih_reconcile.py"),
        (ROOT / "clob_trades.py", f"{PROJ}/clob_trades.py"),
        (ROOT / "dashboard_bridge.py", f"{PROJ}/dashboard_bridge.py"),
        (ROOT / "scripts/server_start_bot.sh", f"{PROJ}/scripts/server_start_bot.sh"),
    ]
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=load_password(), timeout=45)
    try:
        sftp = c.open_sftp()
        for local, remote in uploads:
            print(f"Upload {local.name} -> {remote}")
            sftp.put(str(local), remote)
        sftp.close()

        print("\n=== BUILD ===")
        run(c, KILL_STALE_BUILD, timeout=30)
        r = run(c, BUILD_VPS, timeout=900)
        if r != 0:
            print("BUILD FAILED", r)
            return 1
        print(run_out(c, f"ls -la '{PROJ}/build/trading-core'"))

        pause = json.dumps(
            {"control": "pause", "reason": "deploy — manual Web resume required"}
        )
        print("\n=== RESTART PAUSED ===")
        run_out(
            c,
            f"touch '{PROJ}/logs/STOP_TRADING' && "
            f"printf '%s' '{pause}' > '{PROJ}/logs/runtime_config.json' && "
            f"bash '{PROJ}/scripts/server_start_bot.sh'",
            t=60,
        )
        run_out(c, "sleep 8")

        print("\n=== VERIFY ===")
        print(run_out(c, f"test -f '{PROJ}/logs/STOP_TRADING' && echo STOP=yes || echo STOP=no"))
        print(
            run_out(
                c,
                "curl -s http://127.0.0.1:8081/api/config | python3 -c \"import sys,json; "
                "l=json.load(sys.stdin).get('live',{}); "
                "print('status', l.get('status'), '(3=paused)'); "
                "print('reason', l.get('statusReason','')); "
                "print('openCount', l.get('openCount')); "
                "print('riskMax', l.get('riskMaxConcurrentPositions'))\"",
            )
        )
        print(
            run_out(
                c,
                f"grep -a 'STARTUP PAUSED\\|Chain reconcile\\|manual Web resume' "
                f"'{PROJ}/logs/bridge.log' | tail -5",
            )
        )
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
