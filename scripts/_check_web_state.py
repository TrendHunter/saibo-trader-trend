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

_, out, _ = client.exec_command(
    f"curl -s http://127.0.0.1:8081/api/config", timeout=20
)
raw = out.read().decode("utf-8", errors="replace")
try:
    cfg = json.loads(raw)
    live = cfg.get("live") or {}
    print("openCount:", live.get("openCount"))
    print("openPositions field:", live.get("openPositions"))
    print("liveLihDryRun:", live.get("liveLihDryRun"))
    ops = live.get("openPositions") or live.get("positionList") or []
    print("positions:", len(ops))
    for p in ops:
        print(" -", p.get("asset"), p.get("question", "")[:60], "endDateTs=", p.get("endDateTs"))
except Exception as e:
    print("api parse error", e, raw[:500])

_, out, _ = client.exec_command(f"cat '{PROJ}/logs/live_state.json'", timeout=20)
doc = json.loads(out.read().decode() or "{}")
opens = doc.get("open_lih_positions") or {}
print(f"\nlive_state open={len(opens)} closed={len(doc.get('closed_lih_positions') or [])}")
print(f"total_lih_trades={doc.get('total_lih_trades')} lih_pnl={doc.get('lih_pnl')}")
for k in opens:
    v = opens[k]
    print(" open", k, v.get("market_question", "")[:50])

client.close()
