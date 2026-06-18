# 实盘 LIH 下单函数调用链

前提：`LIH_ENABLED=true`，`LIVE_LIH_DRY_RUN=false`，`USE_PYTHON_CLOB=true`（默认）。

---

## 1. 总调用树（Leg1 真下单）

```text
main()                                                          [main.cpp]
└─ while (true) 主循环 ~250ms
   ├─ router.refresh_rest_book(tokens)                           [OrderRouter.cpp]  ← 检测/簿缓存
   └─ try_lih_evaluate()                                        [main.cpp λ]
      └─ LegInHedgeDetector::evaluate(now_ms, risk_manager)       [LegInHedgeDetector.cpp]
         ├─ quote_for(market)                                   [LegInHedgeDetector.cpp]
         │  ├─ StateStore::get_detection_ask()                  [StateStore.cpp]
         │  ├─ StateStore::get_mirror_quote()                    [StateStore.cpp]  (LIH_USE_MIRROR)
         │  └─ StateStore::get_token_price()                     [StateStore.cpp]
         ├─ RiskManager::can_open_lih_leg(...)                  [RiskManager.cpp]   ← 检测阶段预检
         └─ return LegInAction { OpenLeg1 | CompleteHedge | ... }

      └─ execute_lih_action(act, now_sec)                       [main.cpp λ]
         └─ OrderRouter::submit_lih_action(act, now_sec)     [OrderRouter.cpp]

               ┌─ OpenLeg1 ─────────────────────────────────────────────┐
               ├─ OrderRouter::fetch_book_ask_info(token_id)            │
               │  └─ OrderRouter::fetch_book_object(token_id)           │  REST CLOB /book
               │     └─ OrderRouter::parse_book_asks()                    │
               ├─ resize_for_ask_book()                                 │  [OrderRouter.cpp 匿名]
               ├─ OrderRouter::leg_meets_minimum()                     │
               ├─ RiskManager::can_open_lih_leg(...)                    │  ← 执行前再检
               ├─ RiskManager::try_begin_lih_leg1(asset, window)       │  ← inflight 加锁
               │
               ├─ OrderRouter::execute_dh_leg_buy(tok, px, sh, neg)     │
               │  ├─ OrderRouter::build_order()                          │
               │  ├─ OrderRouter::pick_signer().sign_order()           │  EIP-712
               │  └─ OrderRouter::execute_rest_order(..., reg=false)     │
               │     └─ OrderRouter::execute_via_clob_bridge()         │
               │        └─ HTTP POST 127.0.0.1:8081/internal/clob/order │
               │           └─ dashboard_bridge.ConfigHTTPHandler.do_POST [dashboard_bridge.py]
               │              └─ clob_live.post_fak_order()             [clob_live.py]
               │                 ├─ _client() → ClobClient              [py_clob_client_v2]
               │                 ├─ client.create_and_post_order(FAK)     → Polymarket CLOB API
               │                 └─ _normalize_result()                  │
               │                    ├─ _poll_order_fill()                │
               │                    │  └─ client.get_order(order_id)     │
               │                    └─ _activity_fill_for_token()        │
               │                       └─ clob_trades.fetch_user_trades() │
               │
               ├─ [fill 不足] OrderRouter::resolve_clob_fill()           │
               │  └─ HTTP POST /internal/clob/resolve                    │
               │     └─ clob_live.resolve_order_fill()                   [clob_live.py]
               │        ├─ _poll_order_fill()                          │
               │        └─ _activity_fill_for_token()                    │
               │
               ├─ [pending_fill / 有 order_id 未确认] → return false      │  保持 inflight
               ├─ [真失败 无 order_id]                                   │
               │  └─ RiskManager::end_lih_leg1_inflight()              │
               └─ [成交]                                                 │
                  └─ RiskManager::register_lih_open_leg1()              │  内存持仓 + 扣款
                     └─ persistence::save_live_lih_state()             │  [main.cpp 回调]
                        └─ RiskManager::export_live_lih_state()        [LiveStateStore.cpp]
```

**并行触发**（同样进入 `try_lih_evaluate`）：

```text
PolymarketFeed::on_read()
└─ process_message()
   └─ update_ws_book_ask() / update_token_price()
      └─ tick_callback_(token_id)
         └─ try_lih_evaluate()                    [main.cpp]
```

---

## 2. 时序图（Leg1 成功路径）

```mermaid
sequenceDiagram
    participant Loop as main 主循环
    participant Det as LegInHedgeDetector
    participant RM as RiskManager
    participant OR as OrderRouter
    participant Bridge as dashboard_bridge
    participant Clob as clob_live
    participant API as Polymarket CLOB

    Loop->>Det: evaluate(now_ms, rm)
    Det->>Det: quote_for(market)
    Det->>RM: can_open_lih_leg (预检)
    Det-->>Loop: LegInAction OpenLeg1

    Loop->>OR: submit_lih_action(act)
    OR->>OR: fetch_book_ask_info (REST)
    OR->>RM: can_open_lih_leg
    OR->>RM: try_begin_lih_leg1 (inflight)

    OR->>OR: execute_dh_leg_buy
    OR->>OR: execute_rest_order
    OR->>Bridge: POST /internal/clob/order
    Bridge->>Clob: post_fak_order
    Clob->>API: create_and_post_order FAK
    API-->>Clob: order_id + status
    Clob->>Clob: _normalize_result / poll
    Clob-->>Bridge: {success, size_shares, order_id}
    Bridge-->>OR: HTTP 200 JSON

    alt fill 为 0 但有 order_id
        OR->>OR: resolve_clob_fill
        OR->>Bridge: POST /internal/clob/resolve
        Bridge->>Clob: resolve_order_fill
        Clob-->>OR: 补查结果
    end

    OR->>RM: register_lih_open_leg1
    Loop->>Loop: save_live_lih_state
```

---

## 3. 按 Action 类型的执行分叉

调用链在 `OrderRouter::submit_lih_action` 的 `switch (act.kind)` 处分叉：

| Kind | 关键调用 | 成交登记 |
|------|----------|----------|
| **OpenLeg1** | `try_begin_lih_leg1` → `execute_dh_leg_buy` ×1 | `register_lih_open_leg1` |
| **CompleteHedge** | `try_begin_lih_rebalance` → `execute_dh_leg_buy` ×1 | `register_lih_add_leg` |
| **HeavyDilute** | 同上（买重腿 token） | `register_lih_add_leg` |
| **ScalePaired** | `execute_dh_leg_buy` YES → `execute_dh_leg_buy` NO | `register_lih_add_paired` |
| **DilutePaired** | 同上 | `register_lih_add_paired` |

**Paired 失败回滚**：

```text
NO leg 失败
└─ OrderRouter::execute_unwind_sell(yes_token)
   └─ execute_rest_order(SELL)
      └─ execute_via_clob_bridge → post_fak_order(side=SELL)
```

---

## 4. Shadow 路径（`LIVE_LIH_DRY_RUN=true`）

在 `submit_lih_action` 内，**不调用** `execute_dh_leg_buy`：

```text
OrderRouter::submit_lih_action
├─ fetch_book_ask_info + 风控 + inflight 锁
└─ live_lih_dry_run_
   ├─ register_lih_open_leg1 / register_lih_add_*  (debit_balance=false)
   └─ shadow() → spdlog + push_telemetry  "[LIVE LIH SHADOW]"
```

---

## 5. 成交确认三分支

`execute_dh_leg_buy` 返回后（Leg1 / Hedge 单腿）：

```text
LegFillResult fill = execute_dh_leg_buy(...)

├─ A. fill.success && size >= min
│     └─ register_lih_*  → save_live_lih_state
│
├─ B. fill.pending_fill || (有 order_id && !success)
│     └─ return false（保持 inflight，不 end_*，不 register）
│
└─ C. 无 order_id 且失败
      └─ end_lih_leg1_inflight / end_lih_rebalance_inflight
```

---

## 6. 直连 CLOB 分支（`USE_PYTHON_CLOB=false`）

```text
execute_rest_order
└─ [不走 bridge]
   └─ HTTP POST https://clob.polymarket.com/order
      ├─ OrderRouter::generate_hmac_signature()
      └─ boost::beast SSL write/read
```

当前 VPS 默认走 Python bridge。

---

## 7. 文件索引

| 函数 | 文件 |
|------|------|
| `main` / `try_lih_evaluate` / `execute_lih_action` | `trading-core/src/main.cpp` |
| `LegInHedgeDetector::evaluate` / `quote_for` | `trading-core/src/signals/LegInHedgeDetector.cpp` |
| `submit_lih_action` / `execute_dh_leg_buy` / `execute_via_clob_bridge` / `resolve_clob_fill` | `trading-core/src/exec/OrderRouter.cpp` |
| `can_open_lih_leg` / `try_begin_lih_leg1` / `register_lih_*` | `trading-core/src/risk/RiskManager.cpp` |
| `do_POST` `/internal/clob/*` | `dashboard_bridge.py` |
| `post_fak_order` / `resolve_order_fill` | `clob_live.py` |
| `save_live_lih_state` | `trading-core/src/state/LiveStateStore.cpp` |

更完整的业务说明见 [LIVE_LIH_ORDER_FLOW.md](./LIVE_LIH_ORDER_FLOW.md)。
