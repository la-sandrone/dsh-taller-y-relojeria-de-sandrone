# defer 全延期兜底（声明集全延期时至少留一个可加载项）

文件名: 补丁/defer全延期兜底/defer全延期兜底.md
摘要: 会话基线是旧工具面、而中途工具面变化时，`projectToolUpdates()` 会产出全延期声明集 ⇒ 服务端 400 ⇒ 该会话永久不可用。本补丁在投影后兜一层：全延期就至少留一个可加载声明。
状态: 已应用（2026-11-05，检出 `v0.2.2-rc.1`，src 与 lib 都已改）；由开机护栏按 manifest 重放

---

## 现象

```
tools: at least one tool must have defer_loading=false. All tools cannot be deferred.
  (INVALID_REQUEST 400)
```

该会话此后**每一轮都失败**（不是偶发），界面上表现为「工具已更新 · 新增 1 个，移除 131 个」之后立即失败。

## 机制（四步，逐条对应源码）

1. 会话基线（`history.tools`）是当年的工具面：132 个原生工具；
2. 工具面在中途变了（0.2.2 打开 PTC ⇒ 面只剩 `run_code`）；
3. loop 追加 `request/header{reason:'change'|'resume'}` + `developer/message` 的 `tool-removal`/`tool-addition`
   —— 注意 `change`/`resume` **都不会重开声明系列**（只有 `series`/`startsSeries`/同名定义变化会）；
4. 投影（`packages/llm/llm/src/content.ts`）：`tool-removal` 把基线那 131 个删掉，
   活下来的 `run_code` 是 addition ⇒ 被标 `deferLoading: true` ⇒ **整份 tools 全延期**。

## 实测现场

| 会话 | 位置 | 证据 |
|---|---|---|
| 「整理素材（2）」`session-f0435754-…` | turn 433 / step 1 | `request_id 044bcbc1-22bb-4c1b-b17e-73129d3f7dab` |
| 「整理素材（2）（失败现场备份3）」`session-654d7a73-…` | turn 433 / step 1 | `request_id b54bce8…`；header `reason=resume tools=1` |

两者都是**旧会话在 0.2.2 上重开**时炸的；`0.2.1` home 里的同名副本停在同一轮且正常结束。

## 修法

在 `projectToolUpdates()` 取到 `declarations` 之后、投影消息之前插入一段兜底：

```ts
if (declarations.size > 0
  && [...declarations.values()].every(declaration => declaration.deferLoading === true)) {
  const loadableNames = new Set((tools ?? []).map(tool => tool.name))
  const loadable = [...declarations.values()].find(d => loadableNames.has(d.name))
    ?? [...declarations.values()][0]
  if (loadable !== undefined) {
    const { deferLoading: _deferred, ...immediate } = loadable
    declarations.set(loadable.name, immediate)
  }
}
```

**优先级是有意的**：先找「当前活跃工具」（模型这轮真能用上的），找不到才退回第一个。

## 验证

拿**真实的** `lib/index.js` 跑失败形状（基线 132 + `run_code` 作为 addition、活跃面只有 `run_code`）：

```
投影结果: 1 条 | 延期 0 | 全延期? false
保留的可加载项: [ 'run_code' ]
```

## 为什么不靠插件（三条都试过、都失败）

| 路子 | 失败点 |
|---|---|
| 在 `llm/stream` 里改 options | 那份 options 是 `Object.freeze`（`agent.ts:733-741`），严格模式下赋值抛异常 |
| 被拒后重派发 | waterfall 的 `next()` 只能调一次，第二次抛 `next() called multiple times` |
| 在 `agent/pre-step` 追 `request/header{reason:'series'}` | `ctx.tools.schemas(agent)` 返回的是**注册表**（155~158），不是执行器呈现的 1 个 ⇒ 反而制造 158 条 removal |

## 边界（重要）

- 这是**兜底不是修复**：请求变合法、会话可用，但「投影会全延期」这个事实没变；
- 上游若自行修好（投影后强制保留一个 immediate 声明），本补丁**应当删除**（删目录即可）；
- 代价：全延期时会把一个工具从「延期」降级为「立即加载」，多一份 schema 的开销，可忽略。
