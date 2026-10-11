# 建议：把 `0.2.0-rc.1` 的这条修复补进 release notes（Firefox 下「正在流式输出的会话无法打开」）

> 拟定提交至 https://github.com/deepseek-ai/deepseek-harness/discussions

---

## 一句话

`0.2.0-rc.1` 实际修复了一个**「Firefox 上，正在流式输出的会话永久卡在『载入历史…』」**的问题
（`@deepseek-ai/dsh-util-values` 的内在对象判定），**但 release notes 里没有任何一条提到它**。

建议补一条。理由是：**受影响的人搜不到，而定位它的成本极高。**

---

## 为什么这条 note 值得补

1. **症状伪装成性能问题。** 表现是"卡在载入历史"、'会话越多越容易触发'，任何人第一反应都会去查
   分页、帧大小、主线程阻塞、服务端负载——**没人会往"引擎的原生函数源码字符串格式"想**。

2. **定位成本极高。** 我们为此做了**十组对照实验**（CPU 负载、磁盘写入、帧大小、双会话并发、
   内存累积、mux 重连、主线程卡顿、整帧扫描……）才排除掉全部错误方向，最终落到那条字符串比较上。

3. **0.1.x 用户仍在踩。** 修复从 `0.2.0-rc.1` 开始，但 `0.1.7-rc.2 → 0.2.0-rc.1` 之间的
   notes 里**一个字都没有**，用户完全无从知道"该升级就能解决"。

4. **这是一个「跨引擎假设」类问题，值得被记住。** 同一类写法（用字符串格式判定内建对象）
   在 V8 之外必然失效，而这类问题很难被日常开发发现。

---

## 修复本身（供核对）

```ts
// 0.1.7-rc.2 —— 硬编码单行格式（V8 能过，SpiderMonkey 必挂）
&& Function.prototype.toString.call(constructor) === `function ${name}() { [native code] }`

// 0.2.0-rc.1 起 —— 拿"引擎自己对真内建函数的输出"当基准，与引擎无关
&& Function.prototype.toString.call(constructor)
   === Function.prototype.toString.call(name === 'Array' ? Array : Object)
```

文件：`packages/util/values/src/index.ts` → `hasIntrinsicConstructor()`

**逐 tag 验证**（直接取各 tag 源码核对）：

| tag | `? Array : Object` 基准法 | 状态 |
|---|---|---|
| `dsh-v0.1.7-rc.2` | 无 | ❌ 未修复 |
| `dsh-v0.2.0-rc.1` | 有 | ✅ 已修复 |
| `dsh-v0.2.0-rc.2` | 有 | ✅ 已修复 |
| `dsh-v0.2.1-alpha.1` | 有 | ✅ 已修复 |

---

## 建议补的 release note 文案（可直接粘贴）

**中文 · 加在 `0.2.0-rc.1` 的「🐛 问题修复」下：**

> 修复 Firefox 下「正在流式输出的会话无法打开、界面一直停在『载入历史…』」的问题。原因是内在对象判定用了固定单行格式的原生函数源码串做比较，而 Firefox（SpiderMonkey）的原生函数源码是多行格式，导致该判定在 Firefox 上对所有内建构造函数恒为假。

**English · under "🐛 Bug Fixes":**

> Fix sessions stuck on "Loading history…" in Firefox while the session is actively streaming. The intrinsic-object check compared against a hard-coded single-line native-function source string, but SpiderMonkey renders native functions multi-line, so the check always failed on Firefox.

> （若希望更简短，可只保留第一句；「原因」半句可省。）

---

## 附带建议：为这类写法加跨引擎回归覆盖

这次的根因是**引擎行为差异**，而日常开发与 CI 都在 V8 上跑 —— 这类 bug 天然逃得掉。
我们附一个 **12 行的 preload**，把 V8 的单行形式伪装成 SpiderMonkey 的多行形式，**不需要安装 Firefox**：

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

用法：

```
NODE_OPTIONS='--import ./sm-patch.mjs' pnpm vitest run --pool=forks packages/util/values
```

（`--pool=forks` 是为了让 `NODE_OPTIONS` 的 preload 进入子进程；默认的 worker 线程池不一定生效。）

**效果对照**（直接在真实模块 `packages/util/values/lib/index.js` 上跑）：

| 判定 | V8（原生） | 伪装成 SpiderMonkey |
|---|---|---|
| `hasIntrinsicConstructor(Object.prototype, 'Object')` | `true` | **`false`** |
| `hasIntrinsicConstructor(Array.prototype, 'Array')` | `true` | **`false`** |
| `isJsonValue({ a: 1 })` | `true` | **`false`** |
| `isJsonValue([1, 2, 3])` | `true` | **`false`** |
| `isJsonValue('hi')` / `isJsonValue(42)` / `isJsonValue(null)` | `true` | `true` |
| `snapshotJsonValue({ a: 1 })` | 对象 | **`undefined`** |

> 在这个伪装下，**任何对象或数组都过不了"无损 JSON"判定**——正是线上症状的直接来源。

---

## 参考：完整根因（附，供想深挖的人）

<details>
<summary>展开</summary>

**症状**：Firefox 下，只要一个会话**正在流式生成正文**，去打开它（或切回它）就永久卡在「载入历史…」，
直到这一轮任务结束才恢复。控制台报：

```
TypeError: Assistant stream raw chunk must be a lossless JSON object
Caused by: TypeError: Assistant stream chunk must be losslessly JSON-serializable
```

**因果链**：

```
Function.prototype.toString.call(constructor) === 'function Object() { [native code] }'
  → SpiderMonkey 返回多行 'function Object() {\n    [native code]\n}'  ⇒ false
    → hasIntrinsicConstructor()        === false
      → isIntrinsicObjectPrototype()   === false
        → hasPlainObjectPrototype()    === false
          → walkJsonValue()            return undefined
            → snapshotJsonValue()      return undefined
              → snapshotChunk()        throw TypeError
                → validateRecord()     throw "raw chunk must be a lossless JSON object"
                  → expandAssistantStream()
                    → ClientAssistantStream.replace()   ← 会话装配中断
```

**为什么只有"正在流式输出"的会话中招**：`expandAssistantStream` 只在存在在途助手流
（`baseline.activeAttempt !== undefined`）时被调用。任务一结束该 attempt 退休，于是"自己就好了"。

**确证（一条命令，Firefox 控制台）**：

```js
Function.prototype.toString.call(Object) === 'function Object() { [native code] }'
// Firefox → false    Chrome / Edge → true
```

**已排除的方向**（均单独实测）：CPU 满载、磁盘持续写入、首帧过大（1.4–2.9 MB 的帧对应的会话全部正常打开）、
双会话并发、渲染进程内存累积、mux 不重连（#7677）、主线程阻塞（无 >500 ms 卡顿）、
**线缆载荷含非法值（整帧扫描 10 万+ 节点，零违规）**、浏览器扩展改写 `toString`（实测仍为 native）。

**卡住那一刻 host 侧实测**：`HTTP GET /` **1.3 ms**、node CPU **0%** —— 与性能无关。

</details>

---

## 小结

- **不是请求修 bug** —— 它在 `0.2.0-rc.1` 已经修好了
- **是请求补一条 release note** —— 让搜"Firefox 会话打不开"的人能搜到
- **外加一个可落地的回归覆盖方案** —— 12 行 preload，跑在现有 CI 上

影响面其实很小（`0.1.x` 且用 Firefox 的用户），但**定位成本与可见度问题很大**，所以这条 note 的性价比很高。
