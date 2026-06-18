# 实盘就绪清单 (Live Readiness)

当前主策略为 **LIH（分腿对冲）**，默认 **实盘 LIVE**。上线前用 **`LIVE_LIH_DRY_RUN=true`** 做 shadow（只验簿、不下单），通过后再设 `false` 小资金试跑。

---

## 1. 环境与密钥

| 步骤 | 命令 / 配置 | 通过标准 |
|------|-------------|----------|
| Shadow 观察 | `LIVE_LIH_DRY_RUN=true`，跑数小时+ | 日志有 `[LIVE LIH SHADOW] LEG1/HEDGE`，无同 slot 重复 LEG1 |
| 钱包鉴权 | `python derive_and_update_keys.py` | `.env` 写入 `POLY_API_*` |
| 私钥 / Funder | `POLYMARKET_PRIVATE_KEY`、`POLYMARKET_FUNDER`、`POLYMARKET_SIGNER` | 非占位符；代理钱包 signer ≠ funder |
| 余额 | `python fetch_balance.py` | 非零 USDC/pUSD |
| 自检 | `python live_preflight.py` | 全部 OK |
| LIH prelive | `python prelive_lih_check.py` | 无 duplicate slot（真下单前） |

---

## 2. Shadow vs 实盘

| | Shadow `LIVE_LIH_DRY_RUN=true` | 实盘 `LIVE_LIH_DRY_RUN=false` |
|--|-------------------------------|-------------------------------|
| CLOB 下单 | 否 | 是 |
| 余额 | 链上真实余额 | 同左 |
| 到期 | 结构结算 + 可选 `AUTO_REDEEM` | 同左 |
| 用途 | 验信号 / 日志 / prelive | 真钱 |

---

## 3. LIH 实盘流程（已实现）

1. Leg1：便宜边 ask ≤ `LIH_LEG1_MAX_PRICE`
2. Hedge：合价 ≤ `LIH_TARGET_COMBINED`
3. Pending 成交轮询 + 部分成交接受
4. 到期结构结算 → `AUTO_REDEEM` 链上 redeem
5. `LIH_PAUSE_AFTER_ROUND` 可每局自动 pause

---

## 4. 首次实盘建议

1. **极小资金**（$20–50 USDC + EOA 上少量 POL 作 redeem gas）
2. `LIVE_LIH_DRY_RUN=false`，`AUTO_REDEEM=true`，`LIH_PAUSE_AFTER_ROUND=true`
3. 盯日志：`[LIH LIVE] LEG1` / `HEDGE` / `CLOSED` / `AUTO-REDEEM OK`
4. Polymarket 网页核对持仓与日志一致
5. 单轮验证：`python scripts/_watch_test_round.py --enable-live --expect-assets btc`

---

## 5. 紧急停止

```bash
python scripts/_emergency_stop_entries.py   # VPS
# 或 Web 暂停 + RISK_MAX_CONCURRENT_POSITIONS=0
pkill -f dashboard_bridge.py; pkill -f trading-core   # 本地
```

---

## 6. 故障排查

| 现象 | 可能原因 |
|------|----------|
| `REDEEM FAIL` | RPC 超时、EOA 无 POL、市场未 finalize |
| `HEDGE uncertain fill` / pending timeout | 流动性不足；窗口内可能单腿到期 |
| `leg1 in-flight` / `slot busy` 卡下一窗 | 应已被 scrub 清理；查 `[LIH] scrub` 日志 |
| 余额与链上不符 | redeem 未成功或 API 同步延迟 |
| 不开 leg1 | 无 cheap leg、余额 < `LIH_MIN_BALANCE_USDC`、已 pause、session 满 |

---

**结论：** 先 shadow → 小资金单轮 → 人工盯盘通过后再加大规模。详见 [docs/LIVE_SETUP.md](../docs/LIVE_SETUP.md) 与根 [README.md](../README.md)。
