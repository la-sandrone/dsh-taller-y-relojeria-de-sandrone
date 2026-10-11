# [Bug] Firefox 专属：内在对象判定用了单行 native-code 字符串比较，导致**正在流式输出的会话彻底无法打开**

> 初稿 · 2026-10-03 · 待提交到 https://github.com/deepseek-ai/deepseek-harness/discussions

---

## TL;DR

**在 Firefox 上**，只要一个会话**正在流式生成正文**，去打开它（或切回它）就会永久卡在「载入历史…」，
直到这一轮任务结束才恢复。

根因是一处**跨引擎不成立的字符串比较**：

```ts
// packages/util/values/src/index.ts:20  hasIntrinsicConstructor()
Function.prototype.toString.call(constructor) === `function ${name}() { [native code] }`
```

**SpiderMonkey（Firefox）的原生函数源码是【多行】的**，V8/JSC 才是单行。
于是这个比较在 Firefox 上**对每一个内建构造函数都返回 false**，
`isIntrinsicObjectPrototype` / `hasPlainObjectPrototype` / `hasPlainArrayPrototype` **全线判假**
→ **任何普通对象或数组都过不了 `snapshotJsonValue`** → `snapshotChunk` 抛错 → 会话装配中断。

---

## 环境

- `@deepseek-ai/dsh` **0.1.7-rc.2**（源码检出 + `tsx` 直跑）
- Node **v26.10.0**
- **Firefox 157.0 / Windows x64**
  `Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101 Firefox/157.0`
- `dsh web --port 9007`
- 已装浏览器扩展（控制台可见 `content-script.js`、`installHook.js.map`），但**与本 bug 无关**——见下方"已证伪"

## 复现

1. 在会话 **A** 里发起一个会产生**长回复**的请求，让它开始**流式吐字**
2. 在 A 吐字期间，切到另一个会话，再**切回 A**
3. A 永久卡在「载入历史…」，控制台出现下方异常
4. 等 A 这一轮结束，再打开 A → 恢复正常

> 在 Firefox 上这是**确定性**的（只要目标会话存在在途助手流）；
> 之所以看起来随机，是因为"打开的那一刻它是否正在流式"不固定。

## 报错

```
Sidebar Session opening failed: TypeError: Assistant stream raw chunk must be a lossless JSON object
    validateRecord  assistant-stream.ts:498
Caused by: TypeError: Assistant stream chunk must be losslessly JSON-serializable
    snapshotChunk   assistant-stream.ts:90
```

## 根因

### 出问题的比较

`packages/util/values/src/index.ts:17-27`

```ts
function hasIntrinsicConstructor(prototype: object, name: 'Array' | 'Object'): boolean {
  const descriptor = Object.getOwnPropertyDescriptor(prototype, 'constructor')
  const constructor: unknown = descriptor?.value
  if (typeof constructor !== 'function') return false
  try {
    return constructor.name === name
      && constructor.prototype === prototype
      && Function.prototype.toString.call(constructor) === `function ${name}() { [native code] }`
  } catch {
    return false
  }
}
```

### 两个引擎的格式不一样

```js
// Chrome / Edge / Safari (V8 / JSC) —— 单行
'function Object() { [native code] }'

// Firefox (SpiderMonkey) —— 多行，带换行与四空格缩进
'function Object() {\n    [native code]\n}'
```

### 实测确认（Firefox 157.0 / Windows x64）

```js
Function.prototype.toString.call(Object) === 'function Object() { [native code] }'
// → false      ← 本 bug
```

**Edge 154 / Windows x64** 上同一条表达式为 **`true`**：

```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0
```

最直观的指纹是对 `toString` **自身**取源码——同一个表达式，两个引擎给出不同格式：

```js
// Firefox —— 多行
'function toString() {\n    [native code]\n}'

// Edge    —— 单行
'function toString() { [native code] }'
```


### 传染链

```
hasIntrinsicConstructor(..., 'Object')  === false   （Firefox 恒定）
  └─ isIntrinsicObjectPrototype()       === false   （恒定）
      └─ hasPlainObjectPrototype()      === false   （恒定）
          └─ walkJsonValue()            return undefined
              └─ snapshotJsonValue()    return undefined
                  └─ snapshotChunk()    throw TypeError
                      └─ validateRecord()  throw  ← "raw chunk must be a lossless JSON object"
                          └─ expandAssistantStream()
                              └─ ClientAssistantStream.replace()  ← 会话装配中断
```

数组同理：`hasPlainArrayPrototype` 依赖 `hasIntrinsicConstructor(prototype, 'Array')`，在 Firefox 上同样为 false。

**⇒ 在 Firefox 上，任何对象/数组都过不了这一关。** 例如实测到的这条完全正常的记录：

```json
{"type":"chunk","time":1791028796775,"chunk":{"type":"block-start","index":0,"blockType":"reasoning"}}
```

在 V8 上通过，在 SpiderMonkey 上必然失败。

## 为什么只有"正在流式输出"的会话中招

```ts
// packages/api/session-controller/src/client/sessions/assistant-stream.ts:59
const opening = baseline?.activeAttempt
if (opening !== undefined) {
  for (const [index, member] of expandAssistantStream(
    opening.stream as unknown as readonly AssistantStreamRecord[],   // ← 盲转型，无边界校验
  ).entries()) { ... }
}
```

`expandAssistantStream` **只在存在在途助手流时**被调用（host 侧 `snapshot()` 也只在
`activeAttempt !== undefined` 时附带 `assistantStream`）。
⇒ 只有"正在流式输出"的会话会走到这个校验点；跑完、空闲、卡在工具调用里的会话都不走。
⇒ 任务一结束，`activeAttempt` 退休，快照不再包含该字段，于是"自己好了"。

## 已证伪的假设（对照实验矩阵）

下面每一条都单独实测过，**都不是成因**：

| 假设 | 实验 | 结果 |
|---|---|---|
| CPU 满载 | 纯 CPU 负载 100s（零磁盘写入） | 不触发 |
| 工作区持续写盘 | 每 0.14s 写一次，共 700 次 | 不触发 |
| 帧太大 | 空闲时打开 2.77 MB 首帧的会话 | 秒开 |
| 两个会话同时在跑 | 双会话并发、目标空闲 | 不触发 |
| 页面寿命 / 内存累积 | 连续开多个大会话，`about:processes` 内存不涨甚至回落 | 不触发 |
| mux 断线不重连（#7677） | 探针监测 `open` 后 6s 无响应 | 未触发 |
| 主线程被占死 | `setInterval` 漂移法 | 无 >500ms 卡顿 |
| **帧载荷里有坏值** | **扫整帧 100k+ 节点** | **零违规——线缆数据本来就是干净的** |
| 浏览器扩展改写 `Function.prototype.toString` | 实测 `toString.toString()` 仍是 native | **不是扩展，是引擎差异** |

**卡住那一刻 host 侧实测**（`HTTP GET /`）：

```
时刻        HTTP(s)   状态码   ESTAB  CLOSE_WAIT  node CPU
18:41:59    0.0028    401      6      0           0%
18:42:02    0.0013    401      6      0           0%
```

⇒ host **1.3 毫秒、0% CPU**；同一次运行中 1.4–1.9 MB 的首帧反复出现而对应会话正常打开
⇒ **帧大小与 host 负载都不是成因。**

## 建议修复

1. **把跨引擎的字符串比较改对**（最小改动）：

```ts
const source = Function.prototype.toString.call(constructor).replace(/\s+/g, ' ')
return constructor.name === name
  && constructor.prototype === prototype
  && source === `function ${name}() { [native code] }`
```

2. **但更该改的是它的"权力"。** 现在 `snapshotJsonValue` 既是校验器又是闸门：
   它判假就**中断整个会话装配**，没有降级、没有重试、没有错误态。
   应当降级为"丢弃这一条记录 / 标记该 attempt 不可用"，而不是"这个会话不可用"。

3. **给 UI 一个真正的错误态。** `openState` 目前实际落在"永久 loading"上，
   用户看不到"这次没能打开，原因是什么"。

4. **边界上补真校验。** 目前两处都是盲转型，没有任何一方验过：

```ts
// host   · session-controller/src/assistant-stream.ts:91
stream: this.activeAttempt.stream.snapshot() as unknown as readonly JsonValue[],
// client · api/session-controller/src/client/sessions/assistant-stream.ts:80
opening.stream as unknown as readonly AssistantStreamRecord[],
```

5. **建议加一条跨引擎的 CI 覆盖**：这类"用 `Function.prototype.toString` 的字符串格式
   判定内建对象"的写法，在 V8 之外必然失效。至少在 SpiderMonkey 上跑一遍
   `@deepseek-ai/dsh-util-values` 的用例。

## ⚠️ 影响面可能远不止这一条症状

同一个谓词在 **Firefox 上是全线失真**的：`snapshotJsonValue` / `isJsonValue` 只要走到
对象或数组，就必然返回"不是无损 JSON"。

我们能观察到的，只是**最先炸、且炸得最响的那一条**——因为**会话装配没有降级机制**，
一次判假就直接崩掉整个会话。

**其他调用点很可能只是静默降级了**，所以这个 bug 才能在 Firefox 上潜伏至今
（本项目显然有相当数量的 Firefox 用户）。建议顺带审计 `snapshotJsonValue` /
`isJsonValue` 的**全部调用点**，尤其是：

- 工具参数与工具结果的 JSON 校验
- 上下文与种子事件的校验
- 任何把返回的 `undefined` / `false` 当作**正常分支**而不是失败的"验证"——
  那类地方不会报错，只会悄悄降级

## 与现存讨论的关系

| 现有 | 关系 |
|---|---|
| #7677「Firefox 特有：会话历史在'载入历史…'处无限卡住」 | **同一引擎维度的另一个侧面**，但根因不同（那份是 mux 不重连） |
| #6978「AI 回复中打开会话卡在载入历史」 | **症状相同**；那份只有 AI 推断，本报告给出可复现的跨引擎字符串比较 |
| #4513 分页按消息数 | **无关**（帧大小已被证伪为触发器） |
| #1550 / #4416 冷历史物化拖垮服务 | **无关**（卡住时 host 1.3 ms） |

---

## English summary

**Firefox-only. A session that is actively streaming cannot be opened** — it stays on
"Loading history…" until that turn finishes.

`packages/util/values/src/index.ts:20` decides whether a constructor is intrinsic by
comparing `Function.prototype.toString.call(constructor)` against a **single-line**
string:

```ts
Function.prototype.toString.call(constructor) === `function ${name}() { [native code] }`
```

V8/JSC render native functions on one line, but **SpiderMonkey renders them multi-line**:

```js
Function.prototype.toString.call(Object)
// Chrome/Edge: 'function Object() { [native code] }'
// Firefox:     'function Object() {\n    [native code]\n}'
```

Verified on Firefox 157.0 / Windows x64:

```js
Function.prototype.toString.call(Object) === 'function Object() { [native code] }'
// → false
```

Consequently `isIntrinsicObjectPrototype` → `hasPlainObjectPrototype` → `hasPlainArrayPrototype`
all return **false for every value on Firefox**, so `walkJsonValue` rejects **every object and
array** as "not losslessly JSON-serializable". `snapshotChunk` then throws, `validateRecord`
wraps and rethrows, and `ClientAssistantStream.replace()` aborts the whole session assembly.

This only fires when the target session has an in-flight assistant attempt, because
`expandAssistantStream` is called exclusively on `baseline.activeAttempt` — which is why it
looks random and why it heals itself once the turn ends.

The wire payload is clean (a full-frame scan of 100k+ nodes found zero violations) and the
host is healthy (1.3 ms HTTP, 0% CPU at the moment of failure) — the defect is a
**string-format assumption about the JavaScript engine**, not about data.

Fixes: normalize whitespace in the comparison; stop letting one failed record abort the whole
session assembly; give the UI a real error state instead of a permanent "loading"; replace the
`as unknown as` blind casts at both transport boundaries with real validation; and add
SpiderMonkey coverage for engine-sensitive predicates.
