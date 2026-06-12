"use client";

import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { PageContainer } from "@/components/shared/PageContainer";
import { PageHeader } from "@/components/shared/PageHeader";
import { DemoBanner } from "@/components/shared/DemoBanner";
import { GlassCard, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/shared/GlassCard";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { SlidersHorizontal } from "lucide-react";
import { useState } from "react";

export default function StrategiesPage() {
  const [dumpHedgeEnabled, setDumpHedgeEnabled] = useState(true);

  return (
    <DashboardLayout>
      <PageContainer>
        <PageHeader
          title="策略配置"
          description="当前仅运行 DH（结构对冲）策略。"
          icon={SlidersHorizontal}
        />

        <DemoBanner hint="策略参数读取自 .env，重启 bot 后生效。此页控件不会写入核心。" />

        <GlassCard>
          <CardHeader>
            <CardTitle className="font-heading text-lg font-semibold tracking-tight text-gradient">对冲套利检测器 (DH)</CardTitle>
            <CardDescription className="text-white/40 text-[13px] leading-relaxed">
              扫描 Polymarket 5m/15m Up-Down 市场，当 YES + NO 合价低于 $1.00 时同时买入双腿，锁定结构利润。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <Label htmlFor="dump-hedge" className="flex flex-col space-y-1">
                <span className="font-semibold text-white/90 text-[14px]">启用检测器</span>
                <span className="font-normal text-white/40 text-[12px] tracking-wide">
                  在 Polymarket 订单簿更新时评估机会（纸面/实盘由 PAPER_MODE 控制）。
                </span>
              </Label>
              <Switch id="dump-hedge" checked={dumpHedgeEnabled} onCheckedChange={setDumpHedgeEnabled} />
            </div>

            <div className="bg-white/5 p-4 rounded-xl border border-white/10">
              <h4 className="text-[11px] font-medium tracking-widest uppercase text-white/40 mb-3">当前参数（.env）</h4>
              <ul className="text-[13px] space-y-2.5">
                <li className="flex justify-between">
                  <span className="text-white/50">标的 / 窗口</span>
                  <span className="font-mono text-white/90">BTC·ETH·SOL 5m + BTC·ETH 15m</span>
                </li>
                <li className="flex justify-between">
                  <span className="text-white/50">合价目标</span>
                  <span className="font-mono text-white/90">DH_SUM_TARGET ≤ 0.95</span>
                </li>
                <li className="flex justify-between">
                  <span className="text-white/50">最小折价</span>
                  <span className="font-mono text-white/90">DH_MIN_DISCOUNT ≥ 3%</span>
                </li>
              </ul>
            </div>
          </CardContent>
        </GlassCard>
      </PageContainer>
    </DashboardLayout>
  );
}
