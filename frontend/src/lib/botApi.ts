const BOT_API_URL = process.env.BOT_API_URL || "http://127.0.0.1:8081";
const BOT_API_TOKEN = process.env.BOT_API_TOKEN || "";

export type BotConfig = Record<string, string>;

export interface AuditEvent {
  ts: number;
  type: string;
  user?: string;
  patch?: Record<string, string>;
  action?: string;
  reason?: string;
}

async function botFetch(path: string, init?: RequestInit) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (BOT_API_TOKEN) {
    headers["X-Bot-Api-Token"] = BOT_API_TOKEN;
  }
  const res = await fetch(`${BOT_API_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Bot API error ${res.status}`);
  }
  return data;
}

export async function fetchBotConfig() {
  return botFetch("/api/config") as Promise<{ config: BotConfig; live: Record<string, unknown> }>;
}

export async function updateBotConfig(
  patch: Record<string, string | number>,
  user: string,
  options?: { action?: "pause" | "resume" | "reset_kill"; reason?: string }
) {
  const normalized: Record<string, string> = {};
  for (const [k, v] of Object.entries(patch)) {
    if (v === undefined || v === null) continue;
    const text = String(v).trim();
    if (!text || text === "undefined" || text === "NaN") {
      throw new Error(`无效参数 ${k}`);
    }
    normalized[k] = text;
  }
  if (!Object.keys(normalized).length && !options?.action) {
    throw new Error("没有可保存的配置项");
  }
  const body: Record<string, unknown> = { user };
  if (Object.keys(normalized).length) body.patch = normalized;
  if (options?.action) {
    body.action = options.action;
    if (options.reason) body.reason = options.reason;
  }
  return botFetch("/api/config", {
    method: "POST",
    body: JSON.stringify(body),
  }) as Promise<{ ok: boolean; applied: Record<string, string>; action?: string | null }>;
}

export type TradingMode = "stopped" | "shadow" | "live";

export async function setTradingMode(mode: TradingMode, user: string) {
  if (mode === "stopped") {
    return updateBotConfig({}, user, { action: "pause", reason: "Web: 停止新开仓" });
  }
  if (mode === "shadow") {
    return updateBotConfig({ LIVE_LIH_DRY_RUN: "true" }, user, {
      action: "resume",
      reason: "Web: Shadow 运行",
    });
  }
  return updateBotConfig({ LIVE_LIH_DRY_RUN: "false" }, user, {
    action: "resume",
    reason: "Web: 实盘运行",
  });
}

export async function botControl(action: "pause" | "resume" | "reset_kill", user: string, reason?: string) {
  return botFetch("/api/control", {
    method: "POST",
    body: JSON.stringify({ action, user, reason }),
  });
}

export async function fetchAuditEvents() {
  return botFetch("/api/audit") as Promise<{ events: AuditEvent[] }>;
}

export async function fetchPreflight() {
  return botFetch("/api/preflight") as Promise<{ preflight: Record<string, unknown> }>;
}

export async function fetchClobTrades(limit = 200) {
  return botFetch(`/api/clob/trades?limit=${limit}`) as Promise<{
    trades: Array<Record<string, unknown>>;
    count: number;
  }>;
}
