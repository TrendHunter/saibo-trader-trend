#!/usr/bin/env python3
import sys
import time
from pathlib import Path
import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from remote_deploy import HOST, PROJ, USER, load_password

RID = sys.argv[1] if len(sys.argv) > 1 else "LIH-btc-1781807712094"


def ro(c, cmd, t=60):
    _, o, e = c.exec_command(cmd, timeout=t, get_pty=True)
    return (o.read() + e.read()).decode(errors="replace").strip()


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=load_password(), timeout=60)
    tr = c.get_transport()
    if tr:
        tr.set_keepalive(20)
    try:
        for i in range(24):
            api = ro(
                c,
                "curl -s -m 8 http://127.0.0.1:8081/api/config | python3 -c \"import sys,json; "
                "l=json.load(sys.stdin).get('live',{}); print(l.get('openCount'),l.get('status'),"
                "l.get('statusReason',''),round(l.get('balance',0),2))\"",
            )
            closed = ro(c, f"grep -a 'CLOSED {RID}' '{PROJ}/bot.log' | tail -1")
            redeem = ro(
                c,
                f"grep -aE 'AUTO-REDEEM|REDEEM' '{PROJ}/bot.log' | grep -a '{RID}' | tail -3",
            )
            print(f"[{i}] open/status/reason/bal: {api.splitlines()[-1] if api else '?'}")
            if closed:
                print(f"CLOSED: {closed}")
                print(f"REDEEM:\n{redeem or '(none yet)'}")
                break
            time.sleep(15)
        else:
            print("still open after 6min")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
