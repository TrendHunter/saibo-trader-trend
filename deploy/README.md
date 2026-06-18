# 部署指南

本项目有两种部署方式：**Docker（推荐）** 和 **服务器裸跑**。  
网络能直连 Binance / Polymarket 即可，**不需要额外代理**。

每个 bot 进程的持仓、流水、交易历史都在**进程内存**里，互不共享。多开时只要隔离：**端口、.env、日志目录、（有 Web 时）前端数据库**。

---

## 架构一览

```
┌─────────────────┐     WebSocket      ┌──────────────────┐
│  Next.js 前端    │ ◄─────────────── │ dashboard_bridge │
│  :3001          │   ws://bot:8080   │  + trading-core  │
└─────────────────┘                    └──────────────────┘
                                              ▲
                                         读 .env 策略/钱包
```

- **Bot 包**：C++ `trading-core` + Python `dashboard_bridge.py`（WS 默认 8080）
- **Web 包**：`frontend/`（Next.js，通过 `BOT_WS_URL` 连 bot）
- **仅跑 bot、不要 Web**：只启动 bridge 即可，用 `cli_dashboard.py` 或自建监控连 `ws://IP:8080`

---

## 方式一：Docker 部署

### 1. 单实例（一台服务器一套 bot + 仪表盘）

```bash
cd /opt/polymarket-bot
cp .env.example .env          # 编辑 LIH 策略、钱包（PAPER_MODE 已废弃，保持 false）
docker compose up -d --build

docker compose ps
docker compose logs -f bot
```

| 服务 | 容器内端口 | 宿主机默认映射 |
|------|------------|----------------|
| bot（WS） | 8080 | 8080 |
| frontend | 3001 | 3001 |

浏览器访问：`http://服务器IP:3001`（默认账号 `admin` / `admin`）。

改 `.env` 后：`bash server_start_bot.sh`（裸跑）或 `docker compose restart bot`（Docker）。

---

### 2. 多实例 Docker（多开、数据不串）

**一实例 = 一个 Compose 项目名 + 独立端口 + 独立 bot.env + 独立 logs + 独立前端库。**

```bash
# 准备两个实例目录
cp -r deploy/instances/example deploy/instances/bot-a
cp -r deploy/instances/example deploy/instances/bot-b

# bot-a/compose.env → BOT_HTTP_PORT=8080, FRONTEND_HTTP_PORT=3001
# bot-b/compose.env → BOT_HTTP_PORT=8081, FRONTEND_HTTP_PORT=3002
# 各自编辑 bot.env（实盘必须不同钱包）

docker compose build   # 镜像只需构建一次

docker compose -p bot-a \
  --env-file deploy/instances/bot-a/compose.env \
  -f docker-compose.multi.yml up -d

docker compose -p bot-b \
  --env-file deploy/instances/bot-b/compose.env \
  -f docker-compose.multi.yml up -d
```

| 必须隔离 | 原因 |
|----------|------|
| `-p` 项目名 | 容器、网络、数据卷前缀 |
| `BOT_HTTP_PORT` / `FRONTEND_HTTP_PORT` | 宿主机端口不能重复 |
| `bot.env` | 策略与钱包 |
| `logs/` | 日志目录 |
| 前端 `frontend-db` 卷 | 登录会话 |
| 实盘 `POLYMARKET_PRIVATE_KEY` | 同钱包多进程会重复下单 |

---

### 3. Docker 镜像打包带到服务器

**在能构建的机器上：**

```bash
docker compose build
docker save polymarket-cpp-bot:latest polymarket-cpp-frontend:latest | gzip > polymarket-images.tar.gz
```

**在服务器上：**

```bash
docker load < polymarket-images.tar.gz
# 拷贝项目里的 docker-compose*.yml、deploy/、.env，无需再编译 C++
docker compose up -d
```

或使用私有镜像仓库 `docker push` / `docker pull`。

---

## 方式二：VPS 裸跑（当前生产推荐）

与线上一致：`/opt/polymarket-bot`，Bot 用 `server_start_bot.sh`，Web 用 `server_start_web.sh` + `web.env`。完整步骤见根目录 **[README.md](../README.md#vps-裸跑部署当前生产与服务器一致)**。

### 环境依赖

| 组件 | 版本建议 |
|------|----------|
| OS | Linux x86_64 |
| Python | 3.9+（venv 在 `.venv/`） |
| Node.js | 20+ |
| 构建 | gcc/clang、cmake、conan；**~1GB 内存 VPS 用 `build-lowmem.sh`** |

---

### 1. Bot

```bash
cd /opt/polymarket-bot
cp .env.example .env && vi .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 derive_and_update_keys.py
bash build-lowmem.sh          # 或 ./build.sh（内存充足时）
bash server_start_bot.sh      # 后台：start_bot.py → bridge + trading-core
```

日志：`logs/bridge.log`、`logs/bot.log`。HTTP API 默认 `127.0.0.1:8081`，WS `0.0.0.0:8080`（建议防火墙禁止公网访问 8080/8081）。

---

### 2. Web 仪表盘（与服务器相同流程）

Bot 必须先起来。Web 配置与 bot **分离**：

```bash
cd /opt/polymarket-bot
cp web.env.example web.env
# 必填：AUTH_USERNAME、AUTH_PASSWORD、NEXTAUTH_URL=http://<公网IP>:3001

bash server_start_web.sh      # 首次 / 改 frontend 后：npm ci + build + 启动 + watchdog cron
# 日常快速重启（不编译）：
bash server_restart_web.sh
```

| 文件 | 作用 |
|------|------|
| `web.env` | 登录账号、NEXTAUTH、BOT_WS_URL / BOT_API_URL |
| `scripts/web_run.sh` | 启动 Next（standalone，低内存 heap） |
| `scripts/web_watchdog.sh` | cron 检测 :3001，挂掉则 restart |
| `logs/frontend.log` | Web 运行日志 |

浏览器：`http://服务器IP:3001`。

**从本地推送 Web：** `python scripts/remote_deploy.py web`

---

### 3. 裸跑多实例

每个实例**单独目录**（或同目录不同 `.env` + 不同端口），例如：

**实例 A**（`/opt/bot-a`）：

```bash
cd /opt/bot-a
cp /opt/polymarket-bot/build/trading-core ./build/   # 或各自 build
cp bot.env .env
WS_PORT=8080 nohup python3 dashboard_bridge.py >> logs/bridge.log 2>&1 &
```

**实例 A 前端**：

```bash
BOT_WS_URL=ws://127.0.0.1:8080 PORT=3001 DATABASE_URL=file:./prisma/data-a/dev.db npm run start
```

**实例 B**：`WS_PORT=8081`，前端 `PORT=3002`，`BOT_WS_URL=ws://127.0.0.1:8081`，**另一份** `bot.env` 与 prisma 目录。

---

### 4. systemd 托管（裸跑 Bot 示例）

见 `deploy/systemd/polymarket-bot@.service.example`，可按实例名启用：

```bash
sudo cp deploy/systemd/polymarket-bot@.service.example /etc/systemd/system/polymarket-bot@.service
# 编辑 WorkingDirectory、EnvironmentFile 指向 deploy/instances/bot-a/
sudo systemctl enable --now polymarket-bot@bot-a
```

---

## 端口与安全建议

| 端口 | 服务 | 建议 |
|------|------|------|
| 8080+ | bot WebSocket | 仅本机或内网；前端通过 `BOT_WS_URL` 访问 |
| 3001+ | Web 仪表盘 | 可对公网，建议 Nginx + HTTPS + 强密码 |

防火墙示例：只放行 `3001`，不放行 `8080` 到公网。

---

## 运行模式（纸面已移除）

| 模式 | 配置 | 说明 |
|------|------|------|
| **实盘** | `PAPER_MODE=false`（默认） | 真实 CLOB 下单 |
| **Shadow** | `LIVE_LIH_DRY_RUN=true` | 只验证信号，不下单 |
| ~~纸面~~ | ~~`PAPER_MODE=true`~~ | 已移除；核心会忽略 |

实盘必须填 `POLYMARKET_PRIVATE_KEY`；多实例 **必须不同钱包**。到期结算 + 可选 `AUTO_REDEEM`。

**上实盘前：** [LIVE_READINESS.md](./LIVE_READINESS.md)（部分内容仍提及纸面，以本表为准）。

---

## 常用命令速查

**Docker 单实例**

```bash
docker compose up -d
docker compose logs -f bot
docker compose restart bot
docker compose down
```

**Docker 多实例**

```bash
docker compose -p bot-a -f docker-compose.multi.yml --env-file deploy/instances/bot-a/compose.env logs -f bot
docker compose -p bot-a -f docker-compose.multi.yml down
```

**裸跑（VPS 生产）**

```bash
bash build-lowmem.sh && bash server_start_bot.sh     # bot
bash server_start_web.sh                             # web（首次 / 改代码）
bash server_restart_web.sh                           # web 快速重启
```

---

## 文件说明

| 文件 | 用途 |
|------|------|
| `docker-compose.yml` | 单实例 Docker |
| `docker-compose.multi.yml` | 多实例 Docker 模板 |
| `deploy/instances/*/compose.env` | 实例端口、NEXTAUTH |
| `deploy/instances/*/bot.env` | 策略与钱包（挂载进容器或裸跑 `.env`） |
| `web.env.example` | Web 登录 / NEXTAUTH / BOT_WS_URL |
| `server_start_bot.sh` / `server_start_web.sh` | VPS 后台启动脚本 |
| `build-lowmem.sh` | 低内存 VPS 编译 C++ |
| `dashboard_bridge.py` | Bot 入口（含 WS 服务） |
