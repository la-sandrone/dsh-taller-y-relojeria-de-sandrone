# dsh-old-session-toolface-guard（**观察者**，不是修复器）

> **状态：修复职能已退役（2026-11-05）。** 真正的修复是**源码级补丁**：
> `patches/defer全延期兜底/` —— 它让 `projectToolUpdates()` 在「全部延期」时至少保留一个可加载声明。
> 本插件保留的唯一职责：把每次 `llm/stream` 的决策写进 `<home>/logs/toolface-guard.log`，供下次排查。

## 它观察什么

`defer_loading` 全延期导致的 400：

```
tools: at least one tool must have defer_loading=false. All tools cannot be deferred.
```

**机制**（`packages/llm/llm/src/content.ts`）：会话基线是旧工具面（例：132 个原生工具），工具面中途变了（PTC ⇒ 只剩 `run_code`），
loop 追加 `request/header{reason:'change'|'resume'}` + `tool-removal`/`tool-addition`；
投影时 removal 删光基线、剩下的 `run_code` 是 deferred addition ⇒ 整份声明集全延期 ⇒ 服务端拒绝，**该会话此后每轮都失败**。

**关键**：`reason:'change'` 与 `resume` 都**不会**重开声明系列（只有 `series` / `startsSeries` / 同名定义变化会），所以旧会话在工具面变化后重开必然踩上。

## 三条被证伪的修复路线（别再试）

| 路线 | 死因 |
|---|---|
| 在 `llm/stream` 里改 `options` | 那份 options 是 `Object.freeze`（`core/agent-loop/src/agent.ts:733-741`），严格模式下赋值抛异常 —— 只会静默无操作 |
| 被拒后重派发 | waterfall 的 `next()` 只能调一次，第二次抛 `next() called multiple times` |
| 在 `agent/pre-step` 追加 `request/header{reason:'series'}` | `ctx.tools.schemas(agent)` 返回的是**工具注册表**（155~158 个），不是执行器呈现的面（1 个）⇒ 反而每步制造上百条 `tool-removal`，把正常会话也污染 |

## 配置

```yaml
- id: old-session-toolface-guard
  config:
    repairMode: observe      # 只写诊断。series/restore/reset/append 是上面那三条死路，留作对照，别打开
    dryRun: false
```

## 诊断日志

`<home>/logs/toolface-guard.log`，每次 `llm/stream` 一行 JSON（1 MB 后清空重来），字段：

| 字段 | 含义 |
|---|---|
| `k` | `observe` / `skip` / `series` / `series-skip` / `series-error` |
| `base` | 会话历史基线的工具数（`toolHistory.tools`） |
| `adds` | 中途新增段数（`toolHistory.updates`） |
| `active` | 本次请求的工具数 |
| `seeded` | 是否 fork/种子会话（fork 的 `createdAt` 是分叉时刻，不能用来判断「老会话」） |
| `createdAt` | 会话创建时刻（毫秒） |

## 边界

- 不注册工具、不写会话、不改请求；只做纯对象运算 + 一行日志。
- 任何内部异常 **fail-open**（原样放行）。
