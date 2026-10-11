# DSH 升级铁律（硬性规定）

> 起因：2026-09-25 定案 —— `ERR_SSL_SSL/TLS_ALERT_BAD_RECORD_MAC` → `ERR_HTTP2_INVALID_SESSION`
> 这条**黏性故障由 HTTP/2 触发**（undici v8 起 `allowH2` 默认 `true`）。
> 完整证据（含 22:0 的 A/B 对照）：`tools/H1-AB-RESULTS.md`。

---

## 铁律 1：任何 DSH 升级，必须显式钉死 HTTP/1.1

**任何**升级（换 `DSH_VERSION`、换 Node、换 undici、重装依赖）之后，
**必须先确认 `force-h1` 在这一版上真的生效**，才允许正常使用。

理由不是"以防万一"——是**已知会复发**：

- undici v8 默认 `allowH2 = true`（官方 v7→v8 迁移文档明说）
- H2 session 一旦因一次 TLS 抖动被销毁，undici **会继续复用它** → 之后每一发都是毫秒级秒失败 → **只能重启**
- DSH 侧相关代码在 0.1.5-rc.2 → 0.1.7-rc.2 **逐字节未改**，依赖仍是 `undici@^8.10.0`
  → **升级不会自愈，只会让"路径失效"变成一个更隐蔽的坑**

## 铁律 2：升级后必须跑完这份核对表（**缺一不可**）

```bash
cd $HARNESS

# ① 臂开关在位？（应为 on）
cat tools/h1-mode                       # 期望: on

# ② 【最关键】宿主进程里 force-h1 真的生效了？
grep '"event":"force-h1"' _scratch/fetch-trace.log | tail -3
#   ✅ 期望: "applied":true  且 argv 指向 …/apps/cli/src/bin.ts
#   ❌ 若见 "applied":false,"reason":"undici-unresolved" → H1 没生效，H2 已回来，故障必复发
#   ❌ 若见 "applied":false,"reason":"mode=off"          → 臂被切成了 off

# ③ 飞行记录仪在跑？（应有心跳）
grep -c '"event":"heartbeat"' _scratch/fetch-trace.log

# ④ 运维守护在跑？（由 start-web.sh 拉起）
tail -3 _scratch/ops-daemon.log

# ⑤ 端到端：发一条消息，确认 LLM 正常，且库里能看到对应记录
mariadb --defaults-extra-file=_scratch/trace-db.cnf -e "
SELECT ts,event,pid,h1_forced,body_bytes,cause_code
FROM test_db.dsh_transport_log ORDER BY id DESC LIMIT 10;"
```

**任一项不符合 → 先修好再干活。** 尤其 ②。

## 铁律 3：升级后禁止把 `UND_ERR_SOCKET` 当回归

H1 之下抖动仍然存在（一次 `UND_ERR_SOCKET: other side closed` 属正常范围，**一发就过**）。
**判据是"黏不黏"，不是"有没有"**：

| 症状 | 含义 | 处置 |
|---|---|---|
| 单发 `UND_ERR_SOCKET`，重试即过 | 抖动，H1 已正确应对 | 无需处理 |
| `BAD_RECORD_MAC` 或连续 `INVALID_SESSION` | **H1 没生效**，回去查铁律 2 的 ② | 修 force-h1 的 undici 解析 |

---

## 已知的升级坑（本文件落笔时发现并已修）

`tools/dsh-force-h1.mjs` 原先用**硬编码版本目录**解析 undici：

```
原始代码研究/v0.1.5-rc.2/packages/util/http-proxy/package.json
```

**换版本即失效**（目录名不存在 → `loadUndici()` 返回 undefined → H1 静默失效）。
已改为**动态解析**：先读 `DSH_VERSION` 拼路径，再 glob `原始代码研究/*/` 兜底。
—— 但**别以为修完就一劳永逸**：铁律 2 的 ② 就是为这一类"静默失效"准备的。

## 后续（升级完成后做，二选一）

| 方案 | 说明 | 评价 |
|---|---|---|
| **插件（推荐）** | 写一个 cordis 插件，加载时安装 `allowH2:false` 的全局 dispatcher（社区已有先例：`dsh-fetch-timeouts` 就是这么接管全局 dispatcher 的） | **跨版本存活**，不跟源码冲突，升级零维护 |
| 补丁 | 改 `packages/util/http-proxy/src/install.ts`，让"无代理策略"时也装 `allowH2:false` 的直连 Agent | 侵入源码，每次升级要重新打 |

**在插件做出来之前，`tools/dsh-force-h1.mjs` 这个 preload 就是临时的"补丁"**，
它不改源码、跨版本有效，**但依赖铁律 2 的 ② 来确认它还活着**。
