# 操作陷阱：在这个工作区跑 `node` 会触发取证 preload

**日期**：2026-10-11
**发现经过**：给 `tools/` 里的 `_scratch` 引用改落点时，用 `node --check` 做语法检查，输出里混进了一行不相干的东西。

## 现象

```
$ node --check tools/dsh-force-h1.mjs
[dsh-force-h1] 已强制 HTTP/1.1 (allowH2=false) pid=102027   ← 这是 preload 的输出，不是语法检查的
```

`node --check` **本该只解析不执行**，但它仍然执行了 —— 因为 `NODE_OPTIONS` 里挂着 harness 的取证 preload：

```
NODE_OPTIONS = --import .../tools/dsh-fetch-trace.mjs --import .../tools/dsh-force-h1.mjs
```

**任何 `node` 进程都会先加载它们**，与本意无关。

## 两个后果

1. **输出被污染**：多出一行 `[dsh-force-h1] 已强制 HTTP/1.1 …`（带 pid）。
   在脚本里 grep 语法检查结果时，这行会造成误判。
2. ⚠️ **preload 会往取证日志写东西**：`dsh-fetch-trace.mjs` 的落点是
   `DSH_TRACE_LOG`，**没设时回落到 `草稿纸与垃圾桶/fetch-trace.log`**（见
   `用户笔记/部署/草稿区与运行数据的落点判定.md`）。
   ⇒ 一次语法检查会在草稿区留下一个"匿名进程"的取证文件。

## 处置

**只对临时性的 node 调用**（语法检查、一次性脚本）清空即可：

```bash
NODE_OPTIONS= node --check tools/dsh-force-h1.mjs        # 干净
NODE_OPTIONS= node -e 'console.log(1)'
```

⚠️ **不要**对整个 DSH 实例或启动器清空它 —— 那两个 preload 正是干活的：
`dsh-force-h1.mjs` 是 H1 强制臂、`dsh-fetch-trace.mjs` 是取证日志的来源。
**它们被执行是设计，不是 bug**；陷阱只在于"我以为我在跑一个无关的 node"。

## 自查

```bash
echo "${NODE_OPTIONS:-（未设）}"     # 看到两个 --import 就说明挂着
```
