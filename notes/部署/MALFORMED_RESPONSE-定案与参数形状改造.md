# MALFORMED_RESPONSE 定案与 mcp-calculator 参数形状改造

文件名: 用户笔记/部署/MALFORMED_RESPONSE-定案与参数形状改造.md
摘要: 「本轮运行失败 DeepSeek Messages stream: tool input is invalid JSON MALFORMED_RESPONSE」的根因，
      与两项处置：mcp-calculator 参数形状改造（**已上线**）、DSH 补丁 A+B（**待实施，明确记在此处**）。
依赖: ../tools/scan-session-errors.py, ../tools/list-malformed-calls.py,
      ../tools/analyze-malformed-calls.py, ../tools/dump-session-stream.py
      ../原始代码研究/v0.2.0-rc.2/packages/llm/llm-deepseek/src/translate.ts（补丁 A 的落点）
      ../原始代码研究/v0.2.0-rc.2/packages/core/tools/src/schema.ts（补丁 B 的落点）
      发布仓 <挂载e>:/公开发布项目/mcp-cronopios

---

## 一、症状

会话里极频繁出现，且**整轮被打死**（连合法的兄弟工具调用、已生成的正文一起丢）：

```
本轮运行失败DeepSeek Messages stream: tool input is invalid JSON MALFORMED_RESPONSE
```

## 二、根因（2026-10-12 定案）

**不是网络、不是代理、不是 DSH 的解析 bug** —— 是 **`deepseek-v4-flash` 自己在工具调用参数里写出了不合法的 JSON**。

模型想传「一串公式」，而当时的 schema（`calculate(expression: str, ...)`）只给**一个字符串**的位置，
于是它自作主张改写成 JSON 数组，并掉了引号：

```json
{"exprs 当时的形状": "……"}
{"expression": [g1, g2, g3], "vars": {...}}      ← 裸标识符，非法 JSON
{"expression": [1000*1.5e11/2.99e8, 4.4+41.2]}   ← 裸算式，非法 JSON
{"ids": 1397,1795, "text": "…"}                  ← 漏方括号
```

**JSON 里没有「裸标识符/裸算式」这种值**，所以这串在 `JSON.parse` 处就死了。
更糟的是死法：DSH 在流末（`message_stop`）校验失败即抛，**整轮作废**。

### 为什么会这样死：DSH 自己内部不自洽

| 位置 | 处置 |
|---|---|
| `core/agent-loop/src/tool-calls.ts:104` | 注释原文 **「preserving invalid JSON as text」** —— catch 后把原始串当入参交下去 |
| `acp/acp/src/updates.ts:104` | **「Preserve malformed model output as opaque input」** |
| `core/tools/src/schema.ts:597` | 校验失败 → `ToolArgsError` → 落成 **isError 工具结果**（回合继续） |
| `llm/llm/src/assembler.ts:136` | `max-tokens` 路径**优雅丢弃** tool-call |
| **`llm-deepseek/src/translate.ts:160`** | **硬抛** `MALFORMED_RESPONSE` ⇒ 前面几条全都轮不到 |

**⇒ 上游整套是按「非法 JSON 是预期输入」设计的，只有 translate.ts 那一处是叛徒。**

### 官方侧（上游缺陷，不是我们的）

- **deepseek-ai/DeepSeek-V3#1541** —— 标题逐字命中：`v4-flash emits unquoted enum literals in
  forced tool_call arguments (invalid JSON)`。跨端点复现 ⇒ 判定「**模型 token 流，不是适配器**」；
  坏窗口内 **40–60%** 失败率；随时间波动；**重试成串失败**；坏响应照常计费。
  **状态：被 stale bot 冻结，未修。**
- **deepseek-ai/DeepSeek-V3#1069** —— strict 模式 `/beta` 返回坏 JSON（同类不同症状）。
- **vllm-project/vllm#47449** —— 定性最干脆：
  **「expected model misbehavior, not a server fault；OpenAI 流式契约本就允许 `arguments` 非法，客户端负责校验」**。

## 三、证据链（可复现）

主战场 `session-b86d4978-c873-4870-8b26-95c877dce087`：116 turns / 592 次 tool-call / **9 轮被打死**。

**决定性证据**：`assistant/attempt` 事件保存了**完整流**，含 `tool-call-chunks` 的
**原始 token 分片**。turn 35 的分片原文：

```
["{", "\"", "ids", "\"", ": ", "139", "7", ",", "179", "5", ", ", "\"", "text", …]
```

⇒ **引号真的不在分片里** —— 是模型自己吐的，不是 DSH 拼接错。（`tools/dump-session-stream.py`）

跨会话语料（0.1.7 + 0.2.0 两个 home，298 个会话）：

```
turn/end 错误 134；其中 MALFORMED_RESPONSE 28
去重后 21 个坏参数，分布在 7 个会话
涉及工具：mcp-calculator 26 / draftpad_write 4 / draftpad_amend 1   （未去重口径）
```

## 四、处置一（**已做**）：mcp-calculator 参数形状改造

**判据（来自语料，不是猜）**：

| 位置 | 样本量 | 失手 |
|---|---|---|
| 代码型内容**在键后面**（值位） | 几百次 | **0** |
| **非代码型**数组（如 `tags`） | 很多 | **0** |
| 代码型内容**在数组里** | 18 | **18** |

⇒ 失手的是**「数组 ＋ 代码型内容」这个交叉位**。原因：写对象的值时模型刚写完带引号的键，
处在「引号模式」；写数组元素时前面是 `[` 或 `,`，**没有任何东西提示这里要引号**
——而 Python 的列表恰恰就是「去掉引号的 JSON 数组」。

**修法不是加容错，是把内容挪到那一格永远不会掉引号的位置**：

```
calculate(exprs: dict, dps: int = 50)
  {"exprs": {"C": "3.74e28", "P": "140e15", "tau_s": "C/P/3.15576e7"}}
```

- 「一串东西」用多个键表达；字面量与公式没有区别
- 顺带消掉了 `vars` + `expression` 两分，以及「这条该放哪个」这个**决策点**
  （决策点正是模型即兴发挥的地方）
- 依赖图用**标准库 `graphlib`**（零新增依赖，PEP723 头未动）；成环报出环的路径
- 参数标注是**裸 `dict`**，刻意不写 `dict[str, str]`：
  后者生成 `additionalProperties={"type":"string"}`，而 DSH 的 JSON schema 子集
  **只收布尔形式**（`json-schema.ts`：`additionalProperties must be a boolean`），
  schema 形式会被静默忽略。裸 `dict` → `{"type":"object","additionalProperties":true}`，
  与旧版 `vars` 同形（已在线跑数月的形状）。

**验证阶梯**：worker `--selftest` **45/45** ／ 端到端 12 例 ／ 工具 JSON schema 实测在子集内 ／
cronopios `functional_test.py`（**真起 stdio MCP 发 JSON-RPC**）**5/5** ／ `smoke_test.py` **6/6** ／
重启后实调 4 例（含值漏引号时给出带正确写法的提示）。

**落点**：`<挂载d>:/DataServices/MCP/mcp-calculator/{worker.py,mcp_calculator.py,INDEX.md}`
（旧版备份 `*.bak-exprs-20261012-235346`）＋ 发布仓 `servers/`、`DESIGN.md §2.4`、
`tests/functional_test.py`。

## 五、处置二（**待实施**）：DSH 补丁 A + B

> ⚠️ **本节的目的是"稍后再修"时不必重新推导。动手前先跑第 0 条那几项检查。**

### A（必修）· 不再致命

**落点**：`原始代码研究/v0.2.0-rc.2/packages/llm/llm-deepseek/src/translate.ts:155-163`

删掉整块：

```ts
if (reason.kind !== 'max-tokens') {
  for (const { content } of blocks.values()) {
    if (content.type !== 'tool-call') continue
    let parsed: unknown
    try { parsed = JSON.parse(content.arguments) } catch (_invalidProviderToolJson) { return malformed('tool input is invalid JSON') }
    object(parsed)
  }
}
```

换成一段说明注释（讲清为何此处不该致命、下游契约在哪）。

**依据**：`parsed` 在 `object(parsed)` 之后**再没被用过** —— 那个循环的唯一作用就是校验，
删掉不改变任何数据流。

**效果**：坏入参的块照常流到工具层 → 落成 `isError` 结果 → **回合存活、兄弟调用照跑、
模型看得见失败能自己改**。

### B（诊断）· 让失败自解释

把「模型入参根本不是 JSON」这一情形的失败文案，从 `invalid arguments: must be object`
改成带上原文（**有界截断**），例如：

```
invalid arguments: must be object; the model's arguments were not valid JSON
(received: {"ids": 1397,1795, "text": …})
```

这才是直接回答「错误现场是啥意思、怎么错的」。候选落点：`packages/core/tools/src/schema.ts`
的 `ToolArgsError` 构造处（仅当 `typeof args === 'string'` 时追加，避免影响既有精确文案断言）。

### ❌ 明确**不做**：替模型补引号的自动修复

曾设计过一整套「插入式修复 + schema 裁决 + 留痕」，**决定不做**。理由：
形状改造之后，能被安全修复的残余已经很小，而**猜错的修复是静默的错误执行**（比失败危险）。
落成失败结果 + 让模型自己改，是更安全的等价收益。

### 第 0 条 · 动手前要跑的检查（尚未跑）

1. `llm-deepseek/src/serialize.ts` + `replay.ts`：坏 `arguments` 如何**回传给 provider**
   （若处理不当，崩溃只是从本轮挪到下一轮 —— 最致命的一条）
2. 修复/诊断代码的落点与 schema 可达性
3. stderr 与会话日志的写法（会话事件类型能否承载任意 payload）
4. `补丁/空回复兜底/messages-adapter-0.2.0.patch` 的实际 hunk 范围
   —— 它也改 `translate.ts` 且与 154 行**紧邻**，两份 patch 打同一文件相邻行会因上下文重叠硬失败；
   若合并，倾向**合成一份 patch、一个 hunk**
5. 既有测试 `llm-deepseek/tests/stream.spec.ts:78` 断言的是**旧行为**
   （`rejects.toMatchObject({ code: 'MALFORMED_RESPONSE' })`）—— 必须**反转**它，否则绿是假的
6. 0.1.7 检出里同处代码在 `translate.ts:155`（**不是 0.2.0 回归，是老行为**）

## 六、取证工具（已归位 `tools/`）

| 工具 | 回答什么 |
|---|---|
| `tools/scan-session-errors.py <home…>` | **面**：死过多少轮、哪个码、哪个工具最常被写坏（**量前后对照的尺子**） |
| `tools/list-malformed-calls.py <home…>` | **点**：一行一案，坏在哪一格、解析器报什么、失败点前后原文 |
| `tools/analyze-malformed-calls.py <log>` | **整轮展开**：好参数会不会连坐合法兄弟（带 call id，可 grep 证明它没跑过） |
| `tools/dump-session-stream.py <log> <seq>` | **token 分片级证据**（后两个直接吃 `.jsonl.zst`，不必手工解压） |

**改造前的基线**：`MALFORMED_RESPONSE` **28 次**（其中 calculator 26 次）。跑一段时间后重跑
`scan-session-errors.py` 对照 —— **这是本次唯一能用数字验收的改动**。

## 七、残留与未验证

- 上游 #1541 称 Anthropic 兼容端点会把坏参数**静默丢弃为 `input: {}`**（那样 DSH 反而不报错，
  因为 `JSON.parse("{}")` 通过）。**但我们实测拿到的是原始坏分片**。不一致，**未验证**。
- 长中文正文里的转义问题（`Unterminated string`，1–2 例）**与形状无关**，本次改造治不了，
  只能靠补丁 A 的"不致命"+ B 的"诊断"兜。
- 只扫了两个 home 的 298 个会话；其它实例 home 未扫。
- `additionalProperties` 那条是读上游源码 + 实测 schema 得出的；**未经真机"注册期"验证**
  （`mcp-client/tools.ts` 对入口 schema 不做断言，故理论上不会注册失败）。
