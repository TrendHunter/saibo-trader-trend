#!/bin/bash
# Next.js dashboard (bare metal, survives SSH disconnect)
set -e
ROOT="/opt/polymarket-bot"
cd "$ROOT/frontend"
mkdir -p prisma/data "$ROOT/logs"

export DATABASE_URL="${DATABASE_URL:-file:./prisma/data/dev.db}"
export BOT_WS_URL="${BOT_WS_URL:-ws://127.0.0.1:8080}"
export BOT_API_URL="${BOT_API_URL:-http://127.0.0.1:8081}"
export PORT="${PORT:-3001}"
export HOSTNAME=0.0.0.0
export NEXTAUTH_URL="${NEXTAUTH_URL:-http://127.0.0.1:3001}"
export NEXTAUTH_SECRET="${NEXTAUTH_SECRET:-change-me-in-production}"
export AUTH_USERNAME="${AUTH_USERNAME:-admin}"
export AUTH_PASSWORD="${AUTH_PASSWORD:-admin}"
export AUTH_TRUST_HOST=true

npm ci --no-audit --no-fund
npx prisma generate
npx prisma db push
if [ ! -f prisma/data/dev.db ]; then npx tsx prisma/seed.ts 2>/dev/null || true; fi

npm run build

pkill -f "next-server" 2>/dev/null || true
pkill -f "$ROOT/frontend" 2>/dev/null || true
sleep 2
setsid -f -- npm run start >> "$ROOT/logs/frontend.log" 2>&1
sleep 6
ss -tlnp | grep ":${PORT}" || true
pgrep -af "next|node.*${PORT}" || true
