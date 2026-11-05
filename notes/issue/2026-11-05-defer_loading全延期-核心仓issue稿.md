# Issue 稿（投 `deepseek-ai/deepseek-harness`）：`defer_loading` 投影可产出「全延期」请求，会话永久 400

文件名: 用户笔记/issue/2026-11-05-defer_loading全延期-核心仓issue稿.md
摘要: 工具面中途变过形态的会话（132 原生 ↔ 1 个 run_code），在官方模型下必定 400；根因是 `projectToolUpdates()` 的 `addition-only` 分支可把基线工具删空，只剩一个被标延期的迟到工具。建议投影层保证至少一个 immediate 声明。
状态: **已作废**（2026-11-05）—— 该仓 `has_issues: false`，只有 Discussions，且同案已有 5 条（#8683 / #10163 / #10749 / #11475）。改投 `#11475` 的短评论，见 `2026-11-05-defer_loading-评论稿-11475.md`

目标: https://github.com/deepseek-ai/deepseek-harness/issues/new
查重: 该仓 `defer_loading` / `deferred` / `All tools cannot be deferred` 三搜均 0 命中（2026-11-05）

---

**标题**

`Session permanently 400: tool projection can emit an all-deferred request (defer_loading), because addition-only drops every baseline tool`

**Environment**

- DSH `v0.2.2-rc.1`（tag `dsh-v0.2.2-rc.1`），自建 profile（web），5 个 agent preset，10 个 MCP
- provider：官方账户模型（`deepseek-flash` / `deepseek-v4.1-flash`）；PTC 已按 `tool-executor-ptc` 启用

**Actual**

打开该会话即整轮失败，无任何工具执行：

```
tools: at least one tool must have defer_loading=false. All tools cannot be deferred.
  (INVALID_REQUEST 400, request_id: 158191bb-3e30-46e0-ae84-d19941636ce7)
```

**Evidence**（同一会话 `request/header` 逐条解出）

| 事件 | 模型 | tools |
|---|---|---|
| `request/header` `seq 11` | `deepseek-flash` | **132** 个原生工具 |
| `request/header` `seq 2728` | `deepseek-v4.1-flash` | **1**：`run_code` |
| `assistant/attempt` `seq 2716`（turn 81 / step 1） | — | 400，见上 `request_id` |

**Expected**

会话可继续；或至少失败时说明是「基线与当前工具面不相交」这一具体原因，而不是抛一个 provider 原文错误。

**Analysis**（`packages/llm/llm/src/content.ts`，`toolDeclarations()` / `projectToolUpdates()`）

1. `declarations` 以历史基线为底（本例 132 个原生工具）
2. 后来才出现的 `run_code` 写入时被标 `deferLoading: true`
3. `addition-only` 分支删除**所有当前不活跃**的名字 ⇒ 只剩那个迟到且延期的 `run_code`
4. ⇒ 请求里没有一个是 `defer_loading=false` ⇒ 服务端按不变量拒绝

反向同理：基线 `run_code`（PTC）的会话切到 native 70 个工具时，全部工具都算「中途新增」，同样全延期（社区已有同案，见下）。

**Suggested fix**

投影结束后若 `declarations` 全部为 `deferLoading: true`，至少保留一个 immediate 声明（例如 `run_code` 本身，或最近一次常驻工具），或在 `turn/end` 给出显式诊断「该会话基线与当前工具面不相交」。

**Related reports**（不同仓，同一不变量）

- `zhu1090093659/dsh-web#1947` —— 反向方向（PTC 基线 → native 70 工具）必 400；协作者回「下次发版修复」，但那是修 `liangshen` 的 `presentAs` 退化，未触及本投影
- `BotHarness/DeepSeekBot#3137` —— 新会话被全延期堵死；期望即「host 应至少保留一个常驻工具」
- `microsoft/vscode#311946` —— 只挂 MCP 工具时同样全延期

**Why it is provider-specific**

`defer_loading` 只由官方 provider 适配器发出（`packages/llm/llm-deepseek/src/serialize.ts:165`）。自定义 `openai-completions` 端点的 `toolUpdate` 为 `undefined`，`content.ts:433-434` 会剥掉该标记 ⇒ 同一会话换自定义端点即可继续。可据此判定「不是会话数据损坏」。
