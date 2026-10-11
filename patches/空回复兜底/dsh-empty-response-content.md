# dsh-empty-response-content 补丁存档（空回复兜底）

> 让「只吐思考链、`finish=stop`」的退化响应变成**可重试的 `EMPTY_RESPONSE`**，
> 而不是一条静默落盘、界面上什么都不显示的空白回复。**两个适配器一起修**
> （DeepSeek Messages ＋ pi-ai）。
>
> **性质**：改官方源码（两处 `llm-*` 适配器），非插件。
> **归属**：与 `补丁/Markdown渲染/` 同属一份 patch 存档 —— 两份都修改基座检出源码，
> 由开机护栏 `guard_ui_patches` 按 `补丁/*/manifest.toml` 逐个重放。

---

## 一、状态

| 项 | 值 |
|---|---|
| 基座版本 | `0.2.0-rc.2`（2026-10-11 实施并构建通过） |
| 目标文件 | **4 个**：`llm-deepseek/src/translate.ts` ＋ 其 `tests/stream.spec.ts`；`llm-pi-ai/src/stream.ts` ＋ 其 `tests/convert.spec.ts` |
| 改动量 | Messages 侧 +21/−1；pi-ai 侧 +27/−9（含反转一条既有测试的意图） |
| 补丁文件 | `messages-adapter-0.2.0.patch`、`pi-ai-adapter-0.2.0.patch`（各含 src＋tests，`git apply` 原子重放） |
| 验证 | `tsc -b tsconfig.host.json` ✅ ／ 两个包 `tsdown` ✅ ／ **两包合计 31 files / 892 tests 全过** ✅ ／ 两个 `lib/index.js` 含新判据、旧判据消失 ✅ ／ 护栏 `[build]` 路径实跑 ✅ |
| 影响半径 | 构建后**只有两个文件**的 mtime 变化（两个包的 `lib/index.js`），335 个产物基线对比实测 |
| 真机生效 | **需重启**（`lib/` 在进程启动时装载，热改无效） |

---

## 二、现象：一场真实会话里的 13 次「回复被吞」

会话 `session-ec89256f-747d-42d9-8ce7-0f33241ea4cf`（153 轮，`deepseek-flash`＝Messages 路由，上下文峰值 ~505K、压缩 3 次）：

- **13 轮**的收尾步只产出 `reasoning` 块，**无 `text`、无 `tool-call`，`finish` 全是 `stop`**；
- 用户前后 **13 次**抱怨（「你的回复又被吞了」「又把回答吞在思考过程里了」「我回复呢。」），
  **每一次都恰好落在出事那一轮的下一轮**——一一对应；
- 另有 **7 轮** `interrupted: true`，那是用户自己按停，**形态不同，不计入**。

逐轮比例（收尾步中「被吞」的占比）：

| 轮段 | 收尾步 | 被吞 | 比例 |
|---|---|---|---|
| T1–T41 | 39 | 0 | 0 % |
| T42–T117 | 70 | 1 | 1.4 % |
| T118–T130 | 12 | 3 | 25 % |
| T131–T153 | 21 | 9 | **42.9 %** |

### 三条互相独立的证据：正文**从未生成**

1. **流里没有正文分片**。`assistant/message` 的 `stream` 只有
   `block-start(reasoning)` → `reasoning-chunks` → `block-end` → `usage` → `finish{stop}`；
   没有 `block-start(text)`，没有 `text-chunks`。`replayState.blocks` 也只有 `[{type:"reasoning"}]`。
2. **思考链的尾巴全是「好，写」**——计划排完了，正要写正文处断掉。例：
   `**好，写。** … **长度：中短。** … **好。**` ／ `**好，写。短，立刻。** **不调工具，没有新数字。**`
3. **token 账对得上**。以全会话 329 条带 usage 的消息估 token/字符比（≈0.546）反推：
   13 条的 `outputTokens` ÷「纯思考链预测值」= **0.94–1.11（合计 1.049）**
   ⇒ **一个 token 都没花在正文上**，不是「发出来了又被丢掉」。

### ⛔ 两个看起来像判据、实际站不住的量

| 猜想 | 实测 |
|---|---|
| 「思考太长才会这样」 | 被吞的思考链中位数 **3,354** 字，正常的 **4,035** 字——**被吞的更短** |
| 「上下文太大才会这样」 | 被吞中位 305K、正常中位 317K，**重叠**；505K 时犯过一次，319K 时也正常出过正文 |

⇒ 与上游若干报告的结论一致：**概率性退化，不是硬阈值**。要抓它只能抓**形状**（见下）。

---

## 三、根因：一条判据，两个适配器各犯一次

### ① 守卫问错了问题（两处）

```ts
// ① packages/llm/llm-deepseek/src/translate.ts（0.2.0-rc.2 第 149 行；0.1.7-rc.2 同为 149 行）
if (blocks.size === 0 && reason.kind === 'stop') throw new LlmError('DeepSeek Messages returned no content', 'EMPTY_RESPONSE')
//    ↑ blocks 是「开过的块」的 Map —— thinking 块也入表（startBlock()）⇒ blocks.size === 1 ⇒ 永不触发
```

```ts
// ② packages/llm/llm-pi-ai/src/stream.ts（mapStopReason 的 case 'stop'）
if (message.content.length === 0) { … EMPTY_RESPONSE … }
//    ↑ content 是块**数组** —— [thinking] 长度是 1 ⇒ 数组非空即算「有内容」⇒ 永不触发
```

而 `packages/llm/llm/src/error.ts` 里随常量发布的理由原文写着：
*「…instead of yielding an empty assistant message, because an empty message **silently ends the turn with nothing for the user or the loop to act on**.」*
—— 只吐 reasoning 的一轮，效果**正是**这个。**理由与措辞在这个形状上分岔了，而抵达代码的是措辞。**

### ⚠️ pi-ai 那处更隐蔽：它有**把错误行为写成契约的测试**

```ts
// packages/llm/llm-pi-ai/tests/convert.spec.ts（补丁前）
it('keeps a thinking-only stop successful (any block counts as content)', () => {
  expect(mapStopReason(assistant({ stopReason: 'stop', content: [{ type: 'thinking', thinking: 'mull' }] })))
    .toEqual({ kind: 'stop' })
})
```

也就是说：**它不是漏了，是被断言过的**（测试名连理由都写出来了：「any block counts as content」）。
所以修补必须**连带反转这条测试的意图**——否则测试全绿，而 bug 还在。
这条也解释了它为什么长期没人报：**绿是假的**。

### ② 重试链路是好的，只是永远唤不醒

`EMPTY_RESPONSE` 是默认**可重试码的第一位**（`packages/llm/llm/src/retry-policy.ts`）；
那条真实会话的 retry 策略键实测为
`["normal",5,["EMPTY_RESPONSE","RATE_LIMIT","SERVER","TIMEOUT","TRANSPORT"],500,10000,0.1]`，
且该会话**真的重试了 9 次**——全是 `TRANSPORT`。**机制活着，只是这个形状永远走不到那儿。**

### ③ 循环与 UI 把空消息当正常收尾

```ts
// packages/core/agent-loop/src/agent.ts：没有 tool call 就收工，不检查有没有可见正文
if (toolCalls.length === 0) return { kind: 'completed' }
```

```ts
// packages/client/ui-chat/src/client/contract/assistant-content.ts —— 客户端侧判据**本来就是对的**
if (block.kind === 'reasoning' || block.kind === 'tool-call') return false
if (block.kind === 'text') return block.text.trim() !== ''
```

⇒ 纯 reasoning 步 `answerStep = null` ⇒ 没有正文节点可渲染，只剩思考行。

> **一句话**：同一个仓库里「什么算回复」的正确判据早已存在（客户端那一份），
> 但**终止判定与重试触发那一层没问这个问题**。

---

## 四、判定逻辑（关键设计）

修法只有一句：**把「有没有块」换成「有没有产出可交付内容」**。但**几个候选写法都是错的**：

| 写法 | 判定后果 |
|---|---|
| `blocks.size === 0`（Messages 原） | 纯 reasoning 轮**不算空** ⇒ 本 bug |
| `message.content.length === 0`（pi-ai 原） | 同上，且**被测试固化为契约** |
| `some(b => type === 'text')` | tool-call 轮**被判成空** ⇒ 把正常的工作中轮次打成错误并重试 |
| `assistantStreamHasVisibleContent`（导出工具） | **两个方向都错**：它把 reasoning 算作可见（同一个 bug），又把 tool-call 算作不可见 |
| ✅ `tool-call \|\| (text && 非空白)` | 只认「读者或循环能作用的东西」 |

客户端那份 `hasAssistantReplyContent`（**排除** reasoning **与 tool-call**）也**不能直接复用**——
它的语义是「这一轮有没有给读者的回复」，而这里要问的是「**这一轮有没有交付任何东西**」，
两者的 tool-call 判定**恰好相反**。这也是这个改动值得单独一个补丁、而不是「顺手复用现成判据」的原因。

### 两个适配器的块形状不同，判据要各写各的（不能照抄）

| 适配器 | 块类型 | 文本字段 | 工具调用标记 |
|---|---|---|---|
| DeepSeek Messages | `{type:'text'}` / `{type:'reasoning'}` / `{type:'tool-call'}` | `text` | `type === 'tool-call'` |
| pi-ai | `TextContent{type:'text'}` / `ThinkingContent{type:'thinking'}` / `ToolCall{type:'toolCall'}` | `text`（thinking 的是 `thinking`） | `type === 'toolCall'`（**驼峰**） |

刻意**保留** `reason.kind === 'stop'` / `case 'stop':` 这个前提：

- `max-tokens`：模型把预算烧在思考上、正文为空——UI 有**专门的呈现**（不是静默），
  且重试大概率仍会烧满，属于另一个问题域，**不在本补丁**；
- `error` / `aborted`：本来就走错误/中断路径；
- pi-ai 的 `toolUse` 分支：原样不动（见第五节边界 1）。

---

## 五、边界（有意为之，勿当 bug）

1. **pi-ai 的 `toolUse` 标签未加校验。** 若某 provider 把「只吐思考链」的响应标成
   `stopReason: 'toolUse'`，本补丁仍会把它当 `tool-calls` 放过去（随后 `agent.ts` 发现零工具调用
   → 同样是静默收尾）。**未观测到这种 provider 行为**，故不动——要覆盖它会把「标签」与
   「内容」两件事混在一起，语义上更冒险。
2. **不动 README。** 仓库用 `README.i18n.yaml` 记「英中段落哈希对」，改单侧需跑
   `pnpm run verify-translation-pairing --write` 重录。补丁一碰它就得**每个版本重算哈希**，
   不可重放——留作上游若采纳时同步修改（两处文案：
   `llm-deepseek/README.md` 的「a terminal `stop` with no content blocks becomes `EMPTY_RESPONSE`」
   → 「…that delivered neither non-blank text nor a tool call…」；
   `llm-pi-ai` 的 `mapStopReason` 文档注释已随补丁一起改，见下）。
   ⚠️ 注意 pi-ai 的 `mapStopReason` 还有一份**函数级文档注释**在 `src/stream.ts` 里，
   **它已包含在补丁内**（属于源码，不是 README）。
3. **不动客户端。** 客户端的 `hasAssistantReplyContent` 本来就是对的，问题不在它。
4. **不改 `agent.ts` 的收尾逻辑。** 守卫修好后，空轮次在适配器层就变成可重试错误，
   循环根本不会看到它；改循环是第二道防线，且会波及所有 provider，本次不动。

---

## 六、构建

**运行时装的是 `lib/`，不是 `src/`**（`package.json` 的 `main`/`exports` 都指 `lib/index.js`）
⇒ 只改 src 不重建 = **看着改了、其实没生效**。这是本补丁最阴的失败模式，所以构建是**必需**步骤。

```bash
cd ~/deepseek-harness/原始代码研究/$DSH_VERSION
pnpm exec tsc -b tsconfig.host.json
pnpm exec tsdown --env.DSH_BUILD_FACE host \
  --filter @deepseek-ai/dsh-llm-deepseek --filter @deepseek-ai/dsh-llm-pi-ai
```

### ⚠️ 故意**不**走 `pnpm run build:lib:host`

那句 `build:lib:host` 末尾嵌套着 `pnpm --filter @deepseek-ai/dsh-desktop run bundle`，
2026-09-26 实测它命中另一个 pnpm（11.7.0）**整条链中断**，client 半区只留下 `types/`
没有 `index.js`，随后 `build:web` 才以 Rollup 报错暴露。本补丁只需要 host 半区里的**两个包**，
所以直接点名命令，把风险面缩到最小，顺带避开无关的 desktop bundle。

### ⚠️ `--filter` 只吃**精确相等**，不吃正则；但**可以重复传**

实测 `--filter dsh-llm-deepseek` 与 `--filter "/llm-deepseek$/"` 都得到
`Error: No valid configuration found.`（rc=1，**硬失败，不会静默空跑**——这点是好事，
但意味着过滤器写错会直接把构建拦死）。必须写全名；**重复传 `--filter` 有效**：
两个包在同一次运行里一起构建完成（实测 11.5s，两个 `Build complete`）。

### 验收（五条，缺一不可）

```bash
# ① 两个产物里真的换了判据
grep -c "no answer content" packages/llm/llm-deepseek/lib/index.js   # 期望 1
grep -c "no answer content" packages/llm/llm-pi-ai/lib/index.js      # 期望 1
grep -c "returned no content"        packages/llm/llm-deepseek/lib/index.js   # 期望 0
grep -c "with no content"            packages/llm/llm-pi-ai/lib/index.js      # 期望 0
# ② 行为（源码层，比 grep 强）
pnpm exec vitest run packages/llm/llm-deepseek/tests/ packages/llm/llm-pi-ai/tests/
#   期望 31 files / 892 passed
# ③ 影响半径：只有那两个 lib/index.js 的 mtime 变化（先记录基线再比）
find packages apps vendor -maxdepth 4 -name index.js -path "*/lib/*" -printf '%T@ %p\n' | sort
# ④ 木桶完整性（对照基线，别只看"构建成功"）
ls apps/web/dist/index.html                           # 必须存在（824 B）
find packages -maxdepth 3 -name lib -type d | wc -l   # 0.2.0-rc.2 实测 316（同量级）
# ⑤ 护栏视角
python3 tools/dsh-ui-patches.py --checkout 原始代码研究/$DSH_VERSION   # 期望 rc=0、两处「已在位」
```

---

## 七、升级核对清单

升到新版本后，以下十项由开机护栏自动核对（`[verify]`），**不通过就不打补丁并大声报**；
人工只需在护栏报「上游漂移」时按 `manifest.toml` 的 `[on_drift].hint` 处置。

- Messages 侧：`message_stop` 分支仍在；`reason.kind === 'stop'` 与 `'EMPTY_RESPONSE'` 成对；
  `case 'thinking':` 仍在；测试锚点 `refuses unsupported response content…` 仍在。
- pi-ai 侧：`mapStopReason(` 仍导出；`case 'stop':` 仍在；`EMPTY_RESPONSE_CODE` 仍用；
  测试锚点 `classifies a completed stop with no content as an EMPTY_RESPONSE error` 与
  `describe('mapStopReason / mapUsage'` 仍在。

**护栏跑的是「已打上也必须成立」的断言**——这是本清单最容易被写错的地方：
`[verify]` 每次开机都跑，且跑在「该不该打」之前；若断言只在补丁前成立，
状态良好的树会被误报成漂移，**补丁反而永远打不回去**。

**两个 target 共用同一套断言**：任一项不成立 ⇒ 两份都不打（fail-closed）。
这是刻意的：宁可这次不打，也不要打出一份行为错误的补丁。两份 patch 之间**互不牵连**
（各自一次 `git apply`，原子），所以其中一份漂移时另一份仍能落盘。

---

## 八、回滚

```bash
cd ~/deepseek-harness/原始代码研究/$DSH_VERSION
git checkout -- \
  packages/llm/llm-deepseek/src/translate.ts packages/llm/llm-deepseek/tests/stream.spec.ts \
  packages/llm/llm-pi-ai/src/stream.ts packages/llm/llm-pi-ai/tests/convert.spec.ts
# 再跑一次第六节那两条构建命令，然后重启
```

或直接删掉 `补丁/空回复兜底/` 目录（护栏下次开机不再处理它），再手工回滚源码。

---

## 九、上游状态（截至 2026-10-11）

**同一个根因在 DSH 仓库被反复独立报告过至少 8 条 discussion**（Issue 未开放）：

| 讨论 | 日期 | 要点 |
|---|---|---|
| #5113 | 08-30 | 最早：reasoning-only stop 被判 completed，隔离复现 25/25 |
| #5466 | 09-03 | 序列化侧缺兜底，会把整会话毒死（另一个层） |
| #6218 | 09-10 | 直指：守卫数的是 `order.length`，把 reasoning 算进去了 |
| #6431 | 09-12 | 同根因 + UI 层实证（`answerStep = null`） |
| #6532 | 09-13 | 论证最完整；社区对照 master 逐行核实并给出修法：`order.some(b => b.kind === 'tool-call' \|\| (b.kind === 'text' && b.text.trim()))` |
| #7529 | 09-22 | 「我询问你好，他只思考并不会回答」，附 `blockIsVisible` 佐证 |
| #8553 | 10-01 | 同为 `deepseek-flash`；给出量化判据 `usage.output == usage.reasoning` |
| #9006 | 10-06 | 同根因复查报告 |

厂商侧（答案落进 `reasoning_content`）：`deepseek-ai/DeepSeek-V3` 的 #1673（v4-pro / V4.1-Flash，
`finish_reason:"stop"` + `content` 空 + 完整答案在 `reasoning_content`，45 次复现 13 次）、
#1453（两通道全空）、#1610（思考吃光预算）、#1670（网页版同形）。
另一个 harness 的同款：`earendil-works/pi#9266`（同模型、`thinking high`、`maxTokens: 384000`，
症状描述为 "thinking finished, no reply"，并指出**重试可 100% 恢复**）。

**本文实施当天（2026-10-11）核对上游 master：Messages 侧判据、`agent.ts` 收尾逻辑、
以及 pi-ai 的 `mapStopReason` 与那条 `keeps a thinking-only stop successful` 测试，
均逐字未改。**

> 上报建议：这条修补的特别之处在于 —— **pi-ai 侧必须先反转一条既有测试的意图**。
> 所以它不是「补一个漏判」，而是「**改一条被断言过的契约**」，报告里要把这条单列，
> 否则维护者只会看到"测试从绿变绿"。

---

## 十、为什么这里是源码补丁，而不是插件

`llm/stream` 瀑布是一个可用的插件缝（`LlmRuntime.stream()` → `streamWithRegistration()`），
挂在那里能**一次覆盖所有 provider**，且零构建。之所以选源码补丁：

- **修在正确的层**：这个 bug 就在这两道守卫里，改它就是改它；
- **升级自动化已经存在**：`补丁/` + 开机护栏（预存件 → 自动重放 → 漂移大声报），
  版本耦合的成本已经付过一次（`Markdown渲染/`），再加一份边际成本极低；
- **上游可采纳**：改动小、带回归测试、有清晰的边界声明。

代价（已知并接受）：需要两条构建命令（tsc ＋ 一次 tsdown 两个 filter）。
