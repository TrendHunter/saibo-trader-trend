"use client";

import { useEffect, useMemo, useRef } from "react";
import { GlassCard, CardContent, CardHeader, CardTitle } from "@/components/shared/GlassCard";
import { createChart, ISeriesApi, LineSeries } from "lightweight-charts";
import { LineChart } from "lucide-react";
import type { DHOpportunity } from "@/hooks/useLiveState";

interface PmMarketPanelProps {
  opportunities: DHOpportunity[];
  dhSumTarget: number;
  dhMinDiscount: number;
  feeRate: number;
  timestamp: number;
  marketsScanned: number;
}

function dhNetDiscount(combined: number, feeRate: number): number {
  if (combined <= 0) return 0;
  return 1.0 - combined - combined * feeRate;
}

function shortQuestion(q: string): string {
  const m = q.match(/(Bitcoin|Ethereum|Solana|BTC|ETH|SOL)[^—-]*/i);
  return m ? m[0].trim() : q.slice(0, 36);
}

export function PmMarketPanel({
  opportunities,
  dhSumTarget,
  dhMinDiscount,
  feeRate,
  timestamp,
  marketsScanned,
}: PmMarketPanelProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const seriesRef = useRef<Record<string, ISeriesApi<"Line">>>({});

  const active = useMemo(
    () => opportunities.filter((o) => o.yesPrice > 0 && o.noPrice > 0 && o.combined > 0),
    [opportunities]
  );

  const bestByAsset = useMemo(() => {
    const map = new Map<string, DHOpportunity>();
    for (const o of active) {
      const prev = map.get(o.asset);
      if (!prev || (o.endDateTs ?? 0) < (prev.endDateTs ?? Infinity)) map.set(o.asset, o);
    }
    return map;
  }, [active]);

  useEffect(() => {
    if (!chartRef.current || chartRef.current.clientWidth === 0) return;

    const chart = createChart(chartRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "rgba(255,255,255,0.3)",
        fontFamily: "var(--font-jetbrains-mono)",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.02)" },
        horzLines: { color: "rgba(255, 255, 255, 0.02)" },
      },
      rightPriceScale: { borderColor: "rgba(255, 255, 255, 0.05)" },
      timeScale: { borderColor: "rgba(255, 255, 255, 0.05)" },
      width: chartRef.current.clientWidth,
      height: 200,
    });

    const colors: Record<string, string> = { btc: "#818cf8", eth: "#6366f1", sol: "#14b8a6" };
    for (const asset of ["btc", "eth", "sol"]) {
      seriesRef.current[asset] = chart.addSeries(LineSeries, {
        color: colors[asset] ?? "#94a3b8",
        lineWidth: 2,
        title: asset.toUpperCase(),
      });
    }

    const onResize = () => {
      if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth });
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
      seriesRef.current = {};
    };
  }, []);

  useEffect(() => {
    if (!timestamp) return;
    const time = Math.floor(timestamp / 1000) as never;
    for (const [asset, opp] of bestByAsset) {
      const s = seriesRef.current[asset];
      if (s && opp.combined > 0) s.update({ time, value: opp.combined });
    }
  }, [timestamp, bestByAsset]);

  return (
    <GlassCard>
      <CardHeader>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="font-heading text-lg font-semibold tracking-tight text-gradient flex items-center gap-2">
            <LineChart className="h-4 w-4" />
            实时行情（Polymarket）
          </CardTitle>
          <div className="text-[11px] font-mono text-white/40">
            扫描 {marketsScanned} 个市场 · 合价目标 ≤ {dhSumTarget.toFixed(2)}
          </div>
        </div>
        <p className="text-[11px] text-white/35 mt-2 leading-relaxed">
          DH 模式不连接 Binance。下方为 YES+NO 卖一合价；净折扣 ≥ {(dhMinDiscount * 100).toFixed(1)}% 且合价 ≤ {dhSumTarget} 时才会开仓。
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-3">
          {["btc", "eth", "sol"].map((asset) => {
            const o = bestByAsset.get(asset);
            const combined = o?.combined ?? 0;
            const net = combined > 0 ? dhNetDiscount(combined, feeRate) : 0;
            const ok = combined > 0 && combined <= dhSumTarget && net >= dhMinDiscount;
            return (
              <div key={asset} className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2.5">
                <div className="text-[10px] uppercase tracking-widest text-white/35">{asset}</div>
                <div className="font-mono text-lg text-white mt-1">
                  {combined > 0 ? combined.toFixed(3) : "—"}
                </div>
                <div className={`text-[10px] font-mono mt-1 ${ok ? "text-emerald-400" : "text-white/40"}`}>
                  {combined > 0 ? `净折扣 ${(net * 100).toFixed(2)}% · ${ok ? "可开仓" : "未达标"}` : "等待盘口…"}
                </div>
              </div>
            );
          })}
        </div>

        <div ref={chartRef} className="w-full h-[200px]" />

        <div className="overflow-x-auto rounded-lg border border-white/5">
          <table className="w-full text-[11px] font-mono">
            <thead>
              <tr className="text-white/35 border-b border-white/5">
                <th className="text-left py-2 px-3 font-medium">资产</th>
                <th className="text-right py-2 px-3 font-medium">YES</th>
                <th className="text-right py-2 px-3 font-medium">NO</th>
                <th className="text-right py-2 px-3 font-medium">合计</th>
                <th className="text-right py-2 px-3 font-medium">净折扣</th>
                <th className="text-right py-2 px-3 font-medium">状态</th>
              </tr>
            </thead>
            <tbody>
              {active.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-white/30">
                    暂无有效盘口数据，等待 Polymarket WebSocket 推送…
                  </td>
                </tr>
              ) : (
                active.map((o, i) => {
                  const net = dhNetDiscount(o.combined, feeRate);
                  const ok = o.combined <= dhSumTarget && net >= dhMinDiscount;
                  return (
                    <tr key={`${o.asset}-${o.endDateTs ?? i}`} className="border-b border-white/[0.03] text-white/70">
                      <td className="py-2 px-3">
                        <span className="uppercase text-white/90">{o.asset}</span>
                        <span className="block text-[9px] text-white/30 truncate max-w-[200px]" title={o.question}>
                          {shortQuestion(o.question)}
                        </span>
                      </td>
                      <td className="text-right py-2 px-3">{o.yesPrice.toFixed(3)}</td>
                      <td className="text-right py-2 px-3">{o.noPrice.toFixed(3)}</td>
                      <td className="text-right py-2 px-3">{o.combined.toFixed(3)}</td>
                      <td className="text-right py-2 px-3">{(net * 100).toFixed(2)}%</td>
                      <td className={`text-right py-2 px-3 ${ok ? "text-emerald-400" : "text-white/35"}`}>
                        {ok ? "达标" : "未达标"}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </GlassCard>
  );
}
