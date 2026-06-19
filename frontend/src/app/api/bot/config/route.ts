import { NextResponse } from "next/server";
import { requireSession } from "@/lib/auth";
import { validateAuditReason, validateAuditUser } from "@/lib/inputSecurity";
import { fetchBotConfig, updateBotConfig, fetchAuditEvents } from "@/lib/botApi";

export const dynamic = "force-dynamic";

export async function GET() {
  const session = await requireSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  try {
    const data = await fetchBotConfig();
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Bot unreachable" }, { status: 502 });
  }
}

export async function POST(req: Request) {
  const session = await requireSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  try {
    const body = await req.json();
    const user = validateAuditUser(session.user?.email || "web");
    const reason = body.reason ? validateAuditReason(String(body.reason)) : undefined;
    const actionRaw = String(body.action || "").toLowerCase();
    const action =
      actionRaw === "pause" || actionRaw === "resume" || actionRaw === "reset_kill"
        ? actionRaw
        : undefined;
    const patch =
      body.patch && typeof body.patch === "object" && !Array.isArray(body.patch)
        ? (body.patch as Record<string, string | number>)
        : undefined;

    if (patch || action) {
      const result = await updateBotConfig(patch ?? {}, user, { action, reason });
      return NextResponse.json(result);
    }
    return NextResponse.json({ error: "patch or action required" }, { status: 400 });
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Update failed" }, { status: 502 });
  }
}
