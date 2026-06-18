#!/usr/bin/env python3
import json
import sys
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from remote_deploy import HOST, PROJ, USER, load_password, run

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=load_password(), timeout=15)

_, out, _ = client.exec_command(f"cat '{PROJ}/logs/live_state.json'", timeout=30)
raw = out.read().decode("utf-8", errors="replace")
doc = json.loads(raw)
opens = doc.get("open_lih_positions") or {}
print(f"open slots in file: {len(opens)}")
for k, v in opens.items():
    print(" ", k, "dryRun=", v.get("is_shadow"), "shadow=", v.get("is_shadow"), "q=", (v.get("market_question") or "")[:50])

for cmd in [
    f"grep -E '^(LIVE_LIH_DRY_RUN|LIVE_LIH_RECONCILE)' '{PROJ}/.env'",
    f"tail -40 '{PROJ}/logs/serverbot.log' 2>/dev/null || tail -40 '{PROJ}/serverbot.log' 2>/dev/null || echo no log",
]:
    print(">>>", cmd)
    print(run(client, cmd, timeout=30))
client.close()
