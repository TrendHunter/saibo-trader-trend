# 前端仪表盘

Next.js 16 仪表盘，通过 WebSocket 订阅 bot 实时状态。

## 启动（裸跑）

Bot 需先运行（`python start_bot.py` 或 Docker bot 服务）。

```bash
cd frontend
npm ci
npx prisma generate
export DATABASE_URL="file:./prisma/data/dev.db"
npx prisma db push && npx prisma db seed

export BOT_WS_URL="ws://127.0.0.1:8080"
export BOT_API_URL="http://127.0.0.1:8081"
export PORT=3001
export NEXTAUTH_URL="http://127.0.0.1:3001"
export NEXTAUTH_SECRET="随机长字符串"
npm run build && npm run start
```

浏览器：`http://localhost:3001`

## 技术栈

Next.js · React · Tailwind · NextAuth · Prisma (SQLite) · WebSocket (`useLiveState`)

## 说明

- 持仓/余额来自 bot WS，不直连 Polymarket
- 暂停/恢复通过 `BOT_API_URL` 写入 `logs/runtime_config.json`
- 项目总览见根目录 [README.md](../README.md)
