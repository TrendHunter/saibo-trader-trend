#!/usr/bin/env python3
"""Step 2: small live LIH — preflight, LIVE_LIH_DRY_RUN=false, restart, verify."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from remote_deploy import HOST, PROJ, ROOT, USER, load_password, run  # noqa: E402


def run_out(client: paramiko.SSHClient, cmd: str, timeout: int = 180) -> str:
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    combined = (stdout.read() + stderr.read()).decode(errors="replace").strip()
    print(f"\n>>> {cmd}\n{combined}\n")
    return combined


def revert_shadow(client: paramiko.SSHClient) -> None:
    run_out(
        client,
        f"grep -q '^LIVE_LIH_DRY_RUN=' '{PROJ}/.env' && "
        f"sed -i 's/^LIVE_LIH_DRY_RUN=.*/LIVE_LIH_DRY_RUN=true/' '{PROJ}/.env' || "
        f"echo 'LIVE_LIH_DRY_RUN=true' >> '{PROJ}/.env'",
    )
    run(client, f"bash '{PROJ}/server_start_bot.sh'", timeout=120)


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=load_password(), timeout=45)

    uploads = [
        (ROOT / "prelive_lih_check.py", f"{PROJ}/prelive_lih_check.py"),
        (ROOT / "live_preflight.py", f"{PROJ}/live_preflight.py"),
        (ROOT / "start_bot.py", f"{PROJ}/start_bot.py"),
    ]

    try:
        sftp = client.open_sftp()
        for local, remote in uploads:
            print(f"Upload {local.name}")
            sftp.put(str(local), remote)
        sftp.close()

        ts = int(time.time())
        env_cmds = (
            f"sed -i 's/^#POLYMARKET_PRIVATE_KEY=/POLYMARKET_PRIVATE_KEY=/' '{PROJ}/.env'; "
            f"grep -q '^LIVE_LIH_DRY_RUN=' '{PROJ}/.env' && "
            f"sed -i 's/^LIVE_LIH_DRY_RUN=.*/LIVE_LIH_DRY_RUN=false/' '{PROJ}/.env' || "
            f"echo 'LIVE_LIH_DRY_RUN=false' >> '{PROJ}/.env'; "
            f"sed -i 's/^DH_ENABLE_5M_ETH=.*/DH_ENABLE_5M_ETH=false/' '{PROJ}/.env'; "
            f"sed -i 's/^DH_ENABLE_15M=.*/DH_ENABLE_15M=false/' '{PROJ}/.env'; "
            f"grep -q '^LIVE_TRADES_BASELINE_TS=' '{PROJ}/.env' && "
            f"sed -i 's/^LIVE_TRADES_BASELINE_TS=.*/LIVE_TRADES_BASELINE_TS={ts}/' '{PROJ}/.env' || "
            f"echo 'LIVE_TRADES_BASELINE_TS={ts}' >> '{PROJ}/.env'; "
            f"grep -q '^START_SKIP_PRELIVE=' '{PROJ}/.env' && "
            f"sed -i 's/^START_SKIP_PRELIVE=.*/START_SKIP_PRELIVE=true/' '{PROJ}/.env' || "
            f"echo 'START_SKIP_PRELIVE=true' >> '{PROJ}/.env'; "
            f"rm -f '{PROJ}/logs/STOP_TRADING'"
        )
        run_out(client, env_cmds)
        run_out(
            client,
            f"grep -E '^(LIVE_LIH_DRY_RUN|DH_ENABLE_5M|RISK_MAX_CONCURRENT|LIH_LEG1_SHARES|LIVE_TRADES)' "
            f"'{PROJ}/.env'",
        )
        key_line = run_out(
            client,
            f"grep 'POLYMARKET_PRIVATE_KEY' '{PROJ}/.env' | sed 's/=.*/=***REDACTED***/' | head -1",
        )
        if "POLYMARKET_PRIVATE_KEY=" not in key_line or key_line.strip().startswith("#"):
            print("FATAL: private key not uncommented")
            revert_shadow(client)
            return 1

        bal = run_out(client, f"cd '{PROJ}' && .venv/bin/python fetch_balance.py")
        try:
            balance = float(bal.splitlines()[-1].strip())
            print(f"Balance: ${balance:.2f}")
            if balance < 10:
                print("FATAL: balance below LIH_MIN_BALANCE")
                revert_shadow(client)
                return 1
        except ValueError:
            print("WARN: could not parse balance")

        pf = run(client, f"cd '{PROJ}' && .venv/bin/python start_bot.py --preflight-only", timeout=120)
        if pf != 0:
            print("FATAL: preflight failed — reverting to shadow")
            revert_shadow(client)
            return 1

        pl = run(
            client,
            f"cd '{PROJ}' && .venv/bin/python prelive_lih_check.py --allow-live --since-baseline",
            timeout=120,
        )
        if pl != 0:
            print("FATAL: prelive failed — reverting to shadow")
            revert_shadow(client)
            return 1

        run(client, f"bash '{PROJ}/server_start_bot.sh'", timeout=120)
        time.sleep(20)

        procs = run_out(client, "pgrep -af 'start_bot|trading-core' || echo NONE")
        if "trading-core" not in procs:
            print("FATAL: bot not running after start")
            revert_shadow(client)
            return 1

        boot = run_out(
            client,
            f"grep -aE 'Starting Core|LIH dry-run|Mode: LIVE|LIVE_LIH_DRY_RUN|reconcile' "
            f"'{PROJ}/logs/bridge.log' | tail -12",
        )
        if "dry-run: off" not in boot.lower() and "dry_run=false" not in boot.lower():
            tail = run_out(client, f"tail -30 '{PROJ}/logs/bridge.log'")
            if "dry-run: on" in tail.lower() or "shadow" in tail.lower():
                print("FATAL: still in shadow mode after go-live")
                return 1

        api = run_out(
            client,
            "curl -s http://127.0.0.1:8081/api/config | python3 -c \"import sys,json; "
            "l=json.load(sys.stdin).get('live',{}); "
            "print('dryRun', l.get('liveLihDryRun')); "
            "print('status', l.get('status'), l.get('statusReason','')); "
            "print('openCount', l.get('openCount')); "
            "print('balance', l.get('balance'))\"",
        )
        if "dryRun False" not in api and "dryRun false" not in api.lower():
            print("WARN: API still shows dryRun — check manually")

        print("\n=== STEP 2 GO-LIVE: STARTED ===")
        print("LIVE_LIH_DRY_RUN=false | BTC 5m only | key stays in .env for CLOB signing")
        print("Monitor: python scripts/live_monitor.py")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
