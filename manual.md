# Polymarket LIH Bot — Operations Manual

> **Note:** This file is a legacy English ops cheat sheet. For current LIH live deployment (VPS + Web), see root [README.md](../README.md) and [deploy/README.md](../deploy/README.md).

---

## 1. Overview

- **Stack:** C++20 `trading-core` + Python `dashboard_bridge.py` + optional Next.js dashboard
- **Strategy:** LIH (Leg-In Hedge) — leg1 cheap side, then hedge to target combined price
- **Modes:** Live (`LIVE_LIH_DRY_RUN=false`) or shadow (`LIVE_LIH_DRY_RUN=true`)

---

## 2. Prerequisites (Linux VPS)

```bash
sudo apt-get update && sudo apt-get install -y build-essential cmake libssl-dev python3-venv nodejs npm
```

---

## 3. Configuration

```bash
cp .env.example .env
# Required: POLYMARKET_PRIVATE_KEY, POLYMARKET_FUNDER, POLYMARKET_SIGNER
python3 derive_and_update_keys.py
```

Web dashboard (separate file):

```bash
cp web.env.example web.env
# AUTH_USERNAME, AUTH_PASSWORD, NEXTAUTH_URL
```

---

## 4. Build & Run (VPS production)

```bash
bash build-lowmem.sh
bash server_start_bot.sh
bash server_start_web.sh    # first time / after frontend changes
```

---

## 5. Monitoring

```bash
tail -f logs/bot.log
tail -f logs/bridge.log
tail -f logs/frontend.log
python3 status_bot.py --live
```

---

## 6. Management

| Task | Command |
|------|---------|
| Stop bot | `pkill -f dashboard_bridge.py; pkill -f trading-core` |
| Restart bot | `bash server_start_bot.sh` |
| Restart web | `bash server_restart_web.sh` |
| Emergency stop entries | `python scripts/_emergency_stop_entries.py` |
| Switch to shadow | Set `LIVE_LIH_DRY_RUN=true` in `.env` and restart |

---

## 7. Before going live

1. Run shadow for several hours (`LIVE_LIH_DRY_RUN=true`)
2. `python live_preflight.py` — all checks OK
3. Small balance test round: `python scripts/_watch_test_round.py --enable-live`
4. Verify positions on Polymarket website match logs
