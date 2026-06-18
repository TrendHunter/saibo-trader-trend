# Polymarket LIH Bot — C++ 交易核心

Polymarket **5m / 15m Up-Down** 市场（BTC / ETH / SOL）自动交易。主策略 **LIH（Leg-In Hedge）**：先买便宜边，再对冲到目标合价。

[![C++](https://img.shields.io/badge/C++-20-blue)](https://isocpp.org)
[![Polygon](https://img.shields.io/badge/Network-Polygon-purple)](https://polygon.technology)

> 遗留 **Dump Hedge** 已归档：[`archive/dh-only/`](archive/dh-only/)（设 `LIH_ENABLED=false` 可恢复 DH-only）。**纸面模式已移除**，仅保留 `LIVE_LIH_DRY_RUN` 做 shadow 验证。

---

## 策略逻辑（一局）

```
扫描盘口 → leg1（ask ≤ 0.45）→ 登记持仓 → 对冲（heavy_avg + light_ask ≤ 0.95）→ 结算 / 自动 redeem / 自动暂停
```

| 阶段 | 条件 | 说明 |
|------|------|------|
| **Leg1** | 某侧 ask ≤ `LIH_LEG1_MAX_PRICE`（默认 0.45） | 买 Up 或 Down 中更便宜的一侧 |
| **对冲** | `已买边均价 + 对面 ask ≤ LIH_TARGET_COMBINED`（默认 **0.95**） | 买对面配平 |
| **结算** | 市场到期 | `AUTO_REDEEM=true` 时自动链上 redeem |
| **暂停** | `LIH_PAUSE_AFTER_ROUND=true` | leg1+对冲完成或窗口结算后自动 PAUSE；Web 点「恢复」开下一局（session 清零） |

保守实盘默认：全局单槽（`LIH_ONE_SLOT_GLOBAL`）、每局最多 2 腿（leg1+对冲）、余额低于 $10 不开 leg1、窗口最后 30s 不开新 leg1。

### Leg1 / 对冲锁（不留尾巴）

`RiskManager` 维护 leg1 in-flight 与 rebalance 锁。Round 结束或异常路径主动释放；**`scrub_lih_inflight_locks`** 在主循环与 `LegInHedgeDetector::evaluate` 入口周期性清理（120s TTL），避免上一局结束后卡死下一窗口。

---

## 技术栈

| 层级 | 技术 | 作用 |
|------|------|------|
| **交易核心** | C++20 · CMake · Conan · Boost · spdlog · OpenSSL | 行情、LIH 检测、风控、下单编排 |
| **Python 桥接** | asyncio · py-clob-client | `dashboard_bridge.py` WS + HTTP API、`clob_live.py` 实盘下单、reconcile / redeem |
| **Web 仪表盘** | Next.js 16 · Prisma/SQLite · NextAuth | 实时持仓/余额、暂停恢复、风控参数、历史 |
| **部署** | VPS 裸跑 · Docker · `remote_deploy.py` | 当前生产为 VPS 裸跑（见下） |

**设计原则**：C++ 核心与 bot HTTP API（`:8081`）仅监听本机；公网只暴露 Next.js（`:3001`）。

---

## 架构

```
浏览器 → Next.js :3001 (web.env)
              │  服务端 proxy
              ▼
dashboard_bridge.py  WS :8080  HTTP :8081  (.env)
    │  spawn
    ▼
trading-core (C++)
    ├── LegInHedgeDetector / RiskManager / OrderRouter
    ├── clob_live.py → Polymarket CLOB
    └── redeem_positions.py → AUTO_REDEEM
```

---

## 运行模式

| 模式 | 配置 | 说明 |
|------|------|------|
| **实盘 LIVE** | `PAPER_MODE=false`（默认） | 真实 CLOB 下单 |
| **Shadow** | `LIVE_LIH_DRY_RUN=true` | 只打日志、不下单，验证信号 |
| ~~纸面~~ | ~~`PAPER_MODE=true`~~ | **已移除**；C++ 读到 `true` 会 warn 并忽略 |

钱包与策略在根目录 **`.env`**；Web 登录与公网 URL 在 **`web.env`**（见 [`web.env.example`](web.env.example)）。

---

## VPS 裸跑部署（当前生产，与服务器一致）

默认路径 **`/opt/polymarket-bot`**。Bot 与 Web **分开启动**，Web 用 `web.env` + 启动脚本（低内存 VPS 友好）。

### 1. 首次安装 Bot

```bash
cd /opt/polymarket-bot
git pull
cp .env.example .env          # 填 POLYMARKET_PRIVATE_KEY / FUNDER / SIGNER
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 derive_and_update_keys.py   # 写入 POLY_API_* 到 .env

# ~1GB 内存 VPS 用低内存编译
bash build-lowmem.sh

# 后台启动 bot（bridge + trading-core）
bash server_start_bot.sh
# 日志: logs/bridge.log  logs/bot.log
```

`.env` 关键项：`LIH_ENABLED=true`、`LIVE_LIH_DRY_RUN=false`、`AUTO_REDEEM=true`、`HTTP_BIND=127.0.0.1`。

改 C++ 后必须 **重新 `build-lowmem.sh` 并 `server_start_bot.sh`** 才生效。

### 2. 首次安装 Web 仪表盘

```bash
cd /opt/polymarket-bot
cp web.env.example web.env
# 编辑 AUTH_USERNAME / AUTH_PASSWORD / NEXTAUTH_URL=http://<公网IP>:3001

bash server_start_web.sh
# 内部: npm ci → prisma → npm run build → scripts/web_run.sh → web watchdog cron
# 日志: logs/frontend.log
```

| 脚本 | 用途 |
|------|------|
| `server_start_web.sh` | **全量**：依赖安装 + build + 启动（改 frontend 代码后跑这个） |
| `server_restart_web.sh` | **快速重启**：不 npm ci / 不 build（日常或 watchdog 用） |
| `scripts/web_run.sh` | 启动 Next（优先 standalone，192MB heap） |
| `scripts/web_watchdog.sh` | cron 每 3 分钟检查端口，挂了就 `server_restart_web.sh` |

浏览器：`http://<服务器IP>:3001`（凭 `web.env` 里的账号密码）。

### 3. 端口与安全

| 端口 | 服务 | 暴露 |
|------|------|------|
| 8080 | Bot WebSocket | **仅 127.0.0.1** |
| 8081 | Bot HTTP API | **仅 127.0.0.1** |
| 3001 | Next.js Web | 可对公网（建议 HTTPS + 强密码） |

防火墙：放行 `3001`，**不要**把 8080/8081 暴露到公网。

### 4. 从本地 Windows 推送部署

在开发机配置 `.deploy.local`（SSH 密码，已 gitignore），然后：

```bash
# 推代码 + 编译 + 重启 bot
python scripts/remote_deploy.py

# 仅部署 / 重建 Web
python scripts/remote_deploy.py web

# 仅重启 bot（不编译）
python scripts/_restart_bot_only.py
```

C++ / Python 策略改动：**必须**走 `remote_deploy.py` 或手动上传后在 VPS 上 `build-lowmem.sh`。本地监控脚本（如 `_watch_test_round.py`）只 SSH 观测，不会自动同步代码。

---

## 本地开发

```bash
cp .env.example .env
./build.sh
python start_bot.py
```

Windows：`./start_windows.ps1` 或见 `build.sh` 注释。

前端开发（`frontend/`）：

```bash
npm run dev
npx prisma db push && npx tsx prisma/seed.ts
```

---

## 运维命令

| 任务 | 命令 |
|------|------|
| VPS 全量部署 bot | `python scripts/remote_deploy.py` |
| VPS 部署 Web | `python scripts/remote_deploy.py web` |
| 重启 bot | `python scripts/_restart_bot_only.py` |
| 实盘前检查 | `python scripts/_preflight_live_test.py` |
| 单轮 live 验证 | `python scripts/_watch_test_round.py --enable-live --expect-assets btc` |
| 连开 N 局 | `python scripts/_watch_test_round.py --enable-live --rounds 2 --max-wait 1200` |
| 紧急停开仓 | `python scripts/_emergency_stop_entries.py` |
| 链上持仓补录 | `python scripts/live_lih_reconcile.py` |

5m slug：`{asset}-updown-5m-{unix_ts}`，`ts = (now // 300) * 300`。币种开关：`DH_ENABLE_5M_BTC=true` 等。

---

## Docker 部署（可选）

单机：`docker compose up -d --build` → `:3001` 仪表盘。多实例见 [deploy/README.md](deploy/README.md)。

与 VPS 裸跑二选一；**当前线上用的是裸跑 + `server_start_*` 脚本**，不是 Docker。

---

## 目录速查

| 路径 | 说明 |
|------|------|
| `.env.example` | Bot 策略 / 钱包 / LIH 参数 |
| `web.env.example` | Web 登录 / NEXTAUTH / BOT_WS_URL |
| `server_start_bot.sh` | VPS 后台启动 bot |
| `server_start_web.sh` | VPS 全量 Web 安装 + 启动 |
| `build-lowmem.sh` | 低内存 VPS 编译 C++ |
| `trading-core/src/risk/RiskManager.*` | 风控、in-flight 锁、session |
| `scripts/remote_deploy.py` | 本地 → VPS SSH 部署 |
| `scripts/_watch_test_round.py` | 单轮 / 多轮 live 测试监控 |

---

## 免责声明

仅供学习与研究。预测市场交易有风险，请先用 shadow 或小资金单轮验证，实盘自负盈亏。
