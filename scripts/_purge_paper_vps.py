#!/usr/bin/env python3
"""Remove legacy state files and clear stale open positions on VPS."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from remote_deploy import HOST, PROJ, USER, load_password, run


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=load_password(), timeout=30)

    live_path = f"{PROJ}/logs/live_state.json"
    steps = [
        f"rm -f '{PROJ}/logs/paper_state.json' '{PROJ}/logs/paper_state.json.tmp' "
        f"'{PROJ}/paper_state.json' 2>/dev/null; echo legacy files removed",
        f"grep -q '^LIVE_LIH_DRY_RUN=' '{PROJ}/.env' && "
        f"sed -i 's/^LIVE_LIH_DRY_RUN=.*/LIVE_LIH_DRY_RUN=true/' '{PROJ}/.env' || "
        f"echo 'LIVE_LIH_DRY_RUN=true' >> '{PROJ}/.env'",
        f"grep -q '^LIVE_LIH_RECONCILE_ON_START=' '{PROJ}/.env' && "
        f"sed -i 's/^LIVE_LIH_RECONCILE_ON_START=.*/LIVE_LIH_RECONCILE_ON_START=false/' '{PROJ}/.env' || "
        f"echo 'LIVE_LIH_RECONCILE_ON_START=false' >> '{PROJ}/.env'",
        f"test -f '{live_path}' && cp '{live_path}' '{live_path}.bak-pre-purge' || true",
    ]
    for step in steps:
        print(run(client, step))

    # Clear open_lih in live_state — keep closed history
    _, out, _ = client.exec_command(f"cat '{live_path}' 2>/dev/null || echo '{{}}'", timeout=30)
    raw = out.read().decode("utf-8", errors="replace").strip()
    try:
        doc = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        doc = {}
    if doc:
        open_before = len(doc.get("open_lih_positions") or {})
        doc["open_lih_positions"] = {}
        doc["lih_session_legs_used"] = 0
        cleaned = json.dumps(doc, separators=(",", ":"))
        sftp = client.open_sftp()
        with sftp.file(live_path, "w") as f:
            f.write(cleaned)
        sftp.close()
        print(f"live_state: cleared {open_before} open LIH slot(s), session reset")
    else:
        print("live_state: no file or empty — skip")

    run(client, "pkill -f trading-core || true; pkill -f start_bot.py || true; sleep 2")
    run(client, f"bash '{PROJ}/server_start_bot.sh'")
    run(client, "sleep 12")
    print(run(client, "pgrep -af 'start_bot|trading-core' || true"))
    print(
        run(
            client,
            f"curl -s http://127.0.0.1:8081/api/config | python3 -c "
            "\"import sys,json; l=json.load(sys.stdin).get('live',{}); "
            "print('openCount', l.get('openCount'), 'dryRun', l.get('liveLihDryRun')); "
            "print('ops', l.get('openPositions'))\"",
        )
    )
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
