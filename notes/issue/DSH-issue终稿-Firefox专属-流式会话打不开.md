# [Bug][Firefox 专属] 内在对象判定用了单行 native-code 字符串比较，导致**正在流式输出的会话彻底无法打开**

> 拟定提交至 https://github.com/deepseek-ai/deepseek-harness/discussions

---

## 摘要

**在 Firefox 上**，只要一个会话**正在流式生成正文**，去打开它（或切回它）就会永久卡在「载入历史…」，
直到这一轮任务结束才恢复。控制台报：

```
TypeError: Assistant stream raw chunk must be a lossless JSON object
Caused by: TypeError: Assistant stream chunk must be losslessly JSON-serializable
```

根因是一处**跨引擎不成立的字符串比较**（`packages/util/values/src/index.ts:25`）：

```ts
Function.prototype.toString.call(constructor) === `function ${name}() { [native code] }`
```

**SpiderMonkey（Firefox）的原生函数源码是【多行】的**，只有 V8 / JSC 才是单行。
于是这个比较在 Firefox 上**对每一个内建构造函数都返回 `false`**，
`isIntrinsicObjectPrototype` → `hasPlainObjectPrototype` → `hasPlainArrayPrototype` **全线判假**，
最终 `snapshotJsonValue` **对任何对象或数组都返回 `undefined`** —— 而会话装配没有降级机制，
一次判假就直接把整个会话打掉。

---

## 环境

| | |
|---|---|
| `@deepseek-ai/dsh` | **0.1.7-rc.2**（源码检出 + `tsx` 直跑） |
| Node | **v26.10.0** |
| 出问题的浏览器 | **Firefox 157.0 / Windows x64**<br>`Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101 Firefox/157.0` |
| 对照浏览器 | **Edge 154 / Windows x64**<br>`Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0` |
| 启动方式 | `dsh web --port 9007` |

---

## 复现步骤

1. 在会话 **A** 里发起一个会产生**长回复**的请求，让它开始**流式吐字**
2. 在 A 还在吐字期间，切到另一个会话，再**切回 A**
3. A 永久卡在「载入历史…」，控制台出现上面的异常
4. 等 A 这一轮结束，再打开 A → **恢复正常**

> **在 Firefox 上这是确定性的**：只要目标会话存在"在途助手流"，必然触发。
> 之所以看起来随机，是因为"打开它的那一刻，它是否正在流式输出"不固定。

---

## 根因

### 出问题的比较

`packages/util/values/src/index.ts:18-28`

> 下文所有行号均以 **0.1.7-rc.2** 为基准；master 上因改动可能已有少量偏移，请以函数名与代码内容为准。

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

### 两个引擎给出的源码格式不一样

```js
// V8（Chrome / Edge）/ JSC（Safari）—— 单行
'function Object() { [native code] }'

// SpiderMonkey（Firefox）—— 多行，带换行 + 四空格缩进
'function Object() {\n    [native code]\n}'
```

### 实测 A/B（同一条表达式，两个引擎）

```js
Function.prototype.toString.call(Object) === 'function Object() { [native code] }'
// Firefox 157.0 → false      ← 本 bug
// Edge    154   → true
```

最直观的指纹是对 `toString` **自身**取源码：

```js
// Firefox —— 多行
'function toString() {\n    [native code]\n}'

// Edge    —— 单行
'function toString() { [native code] }'
```

### 传染链

```
hasIntrinsicConstructor(prototype, 'Object')   === false   ← Firefox 上恒定
  └─ isIntrinsicObjectPrototype()              === false
      └─ hasPlainObjectPrototype()             === false
          └─ walkJsonValue()              return undefined
              └─ snapshotJsonValue()      return undefined
                  └─ snapshotChunk()      throw TypeError
                      └─ validateRecord() throw "raw chunk must be a lossless JSON object"
                          └─ expandAssistantStream()
                              └─ ClientAssistantStream.replace()   ← 会话装配中断
```

数组同理：`hasPlainArrayPrototype`（`:37`）同样依赖 `hasIntrinsicConstructor(prototype, 'Array')`。

### 在 Node 上复现（不需要装 Firefox）

把 V8 的单行形式改写成 SpiderMonkey 的多行形式，即可在 CI 里复现。完整 preload 只有 12 行：

```js
// sm-patch.mjs
const realToString = Function.prototype.toString
const NATIVE_SINGLE_LINE = /^(.*) \{ \[native code\] \}$/s

Function.prototype.toString = function toString() {
  const source = realToString.call(this)
  const match = NATIVE_SINGLE_LINE.exec(source)
  if (match === null) return source
  return match[1] + ' {\n    [native code]\n}'
}
```

对照结果（`packages/util/values/lib/index.js`）：

| 判定 | V8（原生） | 模拟 SpiderMonkey |
|---|---|---|
| `Function.prototype.toString.call(Object)` 与期望串相等 | `true` | **`false`** |
| `hasIntrinsicConstructor(Object.prototype, 'Object')` | `true` | **`false`** |
| `hasIntrinsicConstructor(Array.prototype, 'Array')` | `true` | **`false`** |
| `isJsonValue({ a: 1 })` | `true` | **`false`** |
| `isJsonValue([1, 2, 3])` | `true` | **`false`** |
| `isJsonValue({ type: 'block-start', index: 0, blockType: 'reasoning' })` | `true` | **`false`** |
| `isJsonValue('hi')` / `isJsonValue(42)` / `isJsonValue(null)` | `true` | `true` |
| `snapshotJsonValue({ a: 1 })` | 对象 | **`undefined`** |

> 注意最后一行：**连 `{type:'block-start', index:0, blockType:'reasoning'}` 这种完全正常的记录都判 `false`** ——
> 它正是把会话装配炸掉的那条数据。

---

## 为什么只有「正在流式输出」的会话中招

```ts
// packages/api/session-controller/src/client/sessions/assistant-stream.ts:66
const opening = baseline?.activeAttempt
if (opening !== undefined) {
  for (const [index, member] of expandAssistantStream(
    opening.stream as unknown as readonly AssistantStreamRecord[],   // ← 盲转型，无边界校验
  ).entries()) { ... }
}
```

`expandAssistantStream` **只在存在在途助手流时**被调用；host 侧 `snapshot()`
（`packages/api/session-controller/src/assistant-stream.ts:84`）也只在 `activeAttempt !== undefined` 时附带该字段。

⇒ 只有"正在流式输出"的会话会走到这个校验点。
⇒ 任务一结束，`activeAttempt` 退休，快照不再包含该字段，于是"自己就好了"。

---

## 这不是性能问题（实测数据）

**卡住那一刻 host 侧实测**（`HTTP GET /`，探针每 3 秒采样）：

```
时刻        HTTP(s)   状态码   ESTAB  CLOSE_WAIT  node CPU
18:41:59    0.0028    401      6      0           0%
18:42:02    0.0013    401      6      0           0%
```

host **1.3 毫秒、0% CPU**。

**同一轮运行中，`session/follow` 首帧大小反复出现 1.4–1.9 MB，而对应会话全部正常打开。**
⇒ 帧大小与 host 负载都不是触发器。

---

## 已证伪的假设（对照实验矩阵）

以下每一条都单独实测过，**都不是成因**。列在这里是为了省掉"你试过 X 吗"的往返：

| 假设 | 实验 | 结果 |
|---|---|---|
| CPU 满载 | 纯 CPU 负载 100 秒（零磁盘写入） | 不触发 |
| 工作区持续写盘 | 每 0.14 秒写一次工作区文件，共 700 次 | 不触发 |
| 首帧太大 | 空闲时打开 2.77 MB 首帧的会话 | 秒开 |
| 两个会话同时在跑 | 双会话并发、目标会话空闲 | 不触发 |
| 目标会话在跑（但无正文流） | 目标会话卡在工具调用里 | 不触发 |
| 渲染进程内存累积 | 连续打开多个大会话，`about:processes` 内存不涨甚至回落 | 不触发 |
| mux 断线不自动重连（#7677） | 探针监测 `open` 后 6 秒无响应 | 未触发 |
| 主线程被占死 | `setInterval` 漂移法监测 | 无 >500 ms 卡顿 |
| **帧载荷里含非法值** | **扫整帧 10 万+ 节点，找 `NaN`/`±Infinity`/`-0`/`undefined`/非普通对象** | **零违规——线缆数据本来就是干净的** |
| 浏览器扩展改写了 `Function.prototype.toString` | 实测 `Function.prototype.toString.toString()` 仍是 native | **不是扩展，是引擎格式差异** |

---

## ⚠️ 影响面可能远不止这一条症状

同一个谓词在 **Firefox 上是全线失真**的：`snapshotJsonValue` / `isJsonValue` 只要走到对象或数组，
就必然返回"不是无损 JSON"。

我们能观察到的，只是**最先炸、且炸得最响的那一条**——因为**会话装配没有降级机制**，一次判假就整个崩掉。

**其他调用点很可能只是静默降级了**，所以这个 bug 才能在 Firefox 上潜伏至今。
建议顺带审计 `snapshotJsonValue` / `isJsonValue` 的**全部调用点**，尤其是：

- 工具参数与工具结果的 JSON 校验
- 上下文与种子事件的校验
- 任何把返回的 `undefined` / `false` 当作**正常分支**而不是失败的"验证"——那类地方不会报错，只会悄悄降级

---

## 修复建议

**1. 把跨引擎的字符串比较改对**（最小改动）：

```ts
const source = Function.prototype.toString.call(constructor).replace(/\s+/g, ' ')
return constructor.name === name
  && constructor.prototype === prototype
  && source === `function ${name}() { [native code] }`
```

**2. 但更该改的是它的"权力"。** 目前 `snapshotJsonValue` 既是校验器又是闸门：
它判假就**中断整个会话装配**，没有降级、没有重试、没有错误态。
应当降级为"丢弃这一条记录 / 标记该 attempt 不可用"，而不是"这个会话不可用"。

**3. 给 UI 一个真正的错误态。** `openState` 目前实际落在"永久 loading"，用户看不到"这次没能打开，原因是什么"。

**4. 边界上补真校验。** 目前两处都是盲转型，没有任何一方验过：

```ts
// host   · packages/api/session-controller/src/assistant-stream.ts:95
stream: this.activeAttempt.stream.snapshot() as unknown as readonly JsonValue[],
// client · packages/api/session-controller/src/client/sessions/assistant-stream.ts:80
opening.stream as unknown as readonly AssistantStreamRecord[],
```

**5. 加跨引擎 CI 覆盖。** 凡是用 `Function.prototype.toString` 的**字符串格式**去判定内建对象的写法，
在 V8 之外必然失效。可用的复现手段：

```
NODE_OPTIONS='--import ./sm-patch.mjs' pnpm vitest run --pool=forks packages/util/values
```

（`sm-patch.mjs` 即上文那 12 行 preload；`--pool=forks` 是为了让 `NODE_OPTIONS` 的 preload 进入子进程。）

---

## 与现存讨论的关系

| 现有 | 关系 |
|---|---|
| **#7677**「Firefox 特有：会话历史在"载入历史…"处无限卡住」 | **同为 Firefox 维度**，但根因不同（那份定位到 mux 不自动重连）。两条都值得修 |
| **#6978**「AI 回复中打开会话卡在载入历史」 | **症状相同**；那份只有 AI 推断，本报告给出可复现的跨引擎字符串比较与确证命令 |
| #4513 分页按消息数、chunk 行展开 | **无关**（帧大小已被证伪为触发器） |
| #1550 / #4416 冷历史物化拖垮整个 Web 服务 | **无关**（卡住时 host 1.3 ms） |

---

## 最小验证（一条命令）

在 Firefox 的控制台里跑：

```js
Function.prototype.toString.call(Object) === 'function Object() { [native code] }'
```

- **Firefox → `false`**（本 bug）
- Chrome / Edge → `true`

**在 Firefox 上这一条为 `false`，就足以证明本报告。**

---

*本报告中的每一项数字都来自实测：浏览器控制台、host 侧 CPU profile 与 HTTP 延迟采样、
会话日志的字节画像、以及上面对照实验矩阵中的九次独立实验。*
