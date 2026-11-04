# 给 #6935 的评论草稿

> 目标：https://github.com/deepseek-ai/deepseek-harness/discussions/6935
> 用途：补充「国内链路也中招」的证据，支持 OP 的建议。

---

## 补充一条不同地域的证据：纯国内链路同样中招

上面这条 case 走的是 `opencode.ai`（跨境）。这里补一个**纯国内链路**的对照——说明这**不是「出口链路差」的问题**，而是 h2 会话复用的结构性缺陷。

### 环境

- DSH `0.2.1-rc.2`
- 中国移动（国内 ISP）
- **直连 DeepSeek 官方 API**（`api.deepseek.com`，国内服务器）
- Node 内置 fetch（undici v8，`allowH2` 默认 `true`）

### 症状形状完全一致

- 聊几条消息后，连接挂住一会儿
- 之后每次请求 **1–2 ms 内失败**，**无 DNS 查询、无 TCP 建连**
- `ERR_HTTP2_INVALID_SESSION`
- **只能重启 `dsh` 恢复**

和你贴的 before 表格逐项对得上。

### 关键点：这不是跨境问题

你的 case 很容易被读成「出口链路差」。但**国内 API + 国内 ISP 同样复现**，说明触发条件是：

> **链路在 TLS/传输层抖一下 + 客户端继续复用已死的 h2 会话**

链路质量只决定「多久抖一次」，**不是根因**。这也解释了为什么换 provider 没用——只要对端 h2-capable，同样的毒化就会发生。

### 本地缓解（已跑了数月）

按你的方案装了全局 dispatcher，用 `NODE_OPTIONS` 的 preload 注入：

```js
const { Agent, setGlobalDispatcher } = await import('undici')
setGlobalDispatcher(new Agent({ allowH2: false }))
```

结果和你测的一致：

- `ERR_HTTP2_INVALID_SESSION` 不再出现
- 底层连接**照样会断**（`UND_ERR_SOCKET: other side closed`），但每次都退化成**单次可重试的请求失败**
- **不需要重启进程**

代价：HTTP/1.1 没有多路复用，并发请求多时会多开连接。对 agent 这种「同时一两个在飞」的负载，实测无感。

### 支持你的建议，并想强调一点

在 `@deepseek-ai/dsh-http-proxy` 的直接（无代理）路径里装 `allowH2: false`，或至少暴露一个开关。

**想强调的不是性能，是故障性质**：

> 这个 bug 的表现形式是「**进程级不可恢复**」。

用户看到的不是「网络慢」，是「**聊几句就得重启，一重启正在跑的会话就没了**」。这个代价远大于 HTTP/1.1 少掉的并发收益。而且**用户几乎不可能自己诊断出来**——现象是 `fetch failed`，得挖到 `error.cause` 才看得见 `ERR_HTTP2_INVALID_SESSION`。

一个默认值就能把这个「只能重启」的故障降级成「自动重试」，成本收益比很明显。

---

## 发布提示

1. 上面 `---` 之间的内容（含）直接粘
2. 链接：https://github.com/deepseek-ai/deepseek-harness/discussions/6935
3. 发完可以把 URL 记进 `用户笔记/升级/DSH-0.2.2-alpha.2-调研.md` 的「相关」里
