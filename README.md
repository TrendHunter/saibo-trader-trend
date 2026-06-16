# POLYMARKET ARBITRAGE BOT — C++ HIGH-PERFORMANCE CORE

> Polymarket **5m / 15m Up-Down** windows (BTC, ETH, SOL). Primary strategy: **LIH (Leg-In Hedge)** — buy the cheap leg first, hedge toward a target combined price.

[![C++](https://img.shields.io/badge/C++-20-blue)](https://isocpp.org)
[![Polygon](https://img.shields.io/badge/Network-Polygon_Mainnet-purple)](https://polygon.technology)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## What This Bot Does

| Mode | Strategy | Notes |
|------|----------|-------|
| **Paper** (`PAPER_MODE=true`) | LIH | Official CLOB books + depth simulation |
| **Live** (`PAPER_MODE=false`) | LIH | CLOB FAK orders via `clob_live.py` bridge |
| **Legacy** | Dump Hedge (DH) | Archived — see [`archive/dh-only/`](archive/dh-only/) |

### LIH flow (one round)

1. **Leg1** — when ask ≤ `LIH_LEG1_MAX_PRICE` (default **0.45**), buy the cheaper side (Up or Down).
2. **Hedge** — when `heavy_avg + light_ask ≤ LIH_TARGET_COMBINED` (default **0.95**), buy the other side to balance.
3. **Pause** — with `LIH_PAUSE_AFTER_ROUND=true`, bot auto-pauses after leg1+hedge complete or window settlement. Click **Resume** on the web dashboard to start the next round (session counter resets).

### Conservative live defaults

| Setting | Default | Meaning |
|---------|---------|---------|
| `LIH_ONE_SLOT_GLOBAL` | `true` | Only one asset/window slot at a time |
| `LIH_SESSION_MAX_LEGS` | `2` | Max 2 live legs per round (leg1 + hedge) |
| `LIH_LEG1_MIN_SECONDS_REMAINING` | `30` | No new leg1 in the last 30s of a window |
| `LIH_MIN_BALANCE_USDC` | `10` | Block leg1 if wallet below $10 |
| `LIH_PAUSE_AFTER_ROUND` | `true` | Auto-pause after each round for manual review |

---

## Architecture

```
start_bot.py              # Entry: preflight + dashboard_bridge + spawns trading-core
dashboard_bridge.py       # HTTP API + WebSocket → Next.js frontend
clob_live.py              # Live CLOB order bridge (fill polling + activity fallback)
clob_trades.py            # Fetch user trades from Polymarket activity API

trading-core/
├── src/main.cpp                    # Event loop, runtime config, LIH orchestration
├── src/signals/LegInHedgeDetector  # Leg1 entry + rebalance / hedge logic
├── src/exec/OrderRouter.cpp        # Paper + live order execution
├── src/risk/RiskManager.cpp        # Positions, session legs, pause/resume
├── src/state/StateStore.cpp        # WS payload: openPositions, balance, telemetry
└── src/feeds/                      # Polymarket WS + Gamma + optional Binance

frontend/                 # Next.js dashboard (positions, risk, history, control)
scripts/
├── remote_deploy.py      # VPS deploy (modes: pause-after-round, live-monitor, …)
├── live_lih_reconcile.py # Rebuild open LIH positions from chain when fills missed
└── live_monitor.py       # Poll VPS status + tail LIH logs
```

**Web positions** come from C++ `RiskManager` memory → WebSocket (`openPositions`). If live fills are not registered (`Bridge fill … x 0.00`), the dashboard shows 0 even when the chain has positions. Run `live_lih_reconcile.py` or wait for the 60s maintenance reconcile in `dashboard_bridge.py`.

---

## Quick Start

### 1. Configure

```bash
cp .env.example .env
# Edit: POLYMARKET_PRIVATE_KEY, POLYMARKET_FUNDER, POLYMARKET_SIGNER
```

Key switches:

```bash
PAPER_MODE=true          # paper first; false for live
LIH_ENABLED=true         # primary strategy (default)
LIVE_LIH_DRY_RUN=true    # live shadow only (no real orders) until you set false
LIH_TARGET_COMBINED=0.95
LIH_PAUSE_AFTER_ROUND=true
```

### 2. Build (Linux / VPS)

```bash
./build.sh
```

Windows (PowerShell):

```powershell
pip install conan cmake ninja
conan profile detect --force
conan install trading-core --output-folder=build --build=missing -c tools.cmake.cmaketoolchain:generator=Ninja
cmake --preset conan-release -S trading-core
cmake --build build --config Release
```

### 3. Run

```bash
python start_bot.py          # bot + dashboard bridge
# Web UI: see scripts/server_start_web.sh or docker compose
```

Paper preflight (optional):

```bash
python prelive_lih_check.py
```

---

## Live Ops

| Task | Command |
|------|---------|
| Deploy to VPS | `python scripts/remote_deploy.py pause-after-round` |
| Monitor VPS | `python scripts/live_monitor.py` |
| Reconcile positions | `python scripts/live_lih_reconcile.py` |
| Prune expired slots | `python scripts/prune_live_lih.py` |

After each live round the bot pauses. On the web dashboard: **Resume** → new round (session 0/2). **Pause** → emergency stop.

---

## 部署

| 方式 | 说明 | 文档 |
|------|------|------|
| **Docker 单实例** | `docker compose up -d --build` | 下文 |
| **Docker 多实例** | 多开 bot，端口/配置/数据隔离 | [deploy/README.md](deploy/README.md) |
| **服务器裸跑** | systemd 管进程 | [deploy/README.md](deploy/README.md) |

### Docker 单实例

```bash
cp .env.example .env
# Set LIH_ENABLED=true, PAPER_MODE as needed
docker compose up -d --build
# Dashboard http://<host>:3001  (default admin/admin)
# Bot WebSocket on host :8080
```

多实例、裸跑编译与 systemd：见 **[deploy/README.md](deploy/README.md)**。

---

## Disclaimer

This software is for educational and experimental use. Prediction market trading involves significant financial risk. Validate with paper trading before live capital. You are solely responsible for any losses.
