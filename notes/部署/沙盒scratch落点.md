# 沙盒 scratch 落点（跨调用可写的临时目录）

文件名: 用户笔记/部署/沙盒scratch落点.md
摘要: `workspace-write` 下 `/tmp` 是**每次调用全新**的 tmpfs ⇒ 跨调用临时目录不存在。用 bwrap 的挂载顺序（later wins）把一个宿主子目录绑回去解决。含启动器侧守卫、**一处未解决的告知通路缺口**、以及实录的错账。
依赖: 补丁本体在 `补丁/sandbox-scratch/`；启动器改动在 `start-web.py`

---

## 一、要解决的问题

`workspace-write` 下 bwrap 执行 `--tmpfs /tmp`，官方 e2e 断言的语义是：

> workspace-write mounts an EPHEMERAL /tmp: **the write succeeds inside, the host /tmp stays untouched**

⇒ **沙盒里 `/tmp` 的寿命是"一次调用"**：`mkdir /tmp/foo` 下一次工具调用就看不见。

而**没有任何配置能加可写根**：`sandbox-policy` 的 `Config` 只有 `mode` / `workspaceRoot`；
`sandbox/src/roots.ts` 的 `writableRoots()` 是硬编码的 `{workspaceRoot, '/tmp', tmpdir()}`
（`roots.ts:54`）。⇒ 只能打补丁。

退而求其次往**用户工作区**挖 `.XXX-tmp` 是越界的：既进用户的文档树/备份/搜索，
又**绕过了 OS 本来替你管好的 tmpfs GC**。用户原话：

> 非专业项目目录造 `.XXX-tmp` 纯属随地大小便，还破坏操作系统的默认内存盘 GC 机制。
> 甚至我可以说，**如果你真的需要一个几小时或者一天以后还在的 tmp 目录，那就是需要建专业项目工作目录的时刻了。**

## 二、修法：利用 bwrap 的挂载顺序

bwrap **按 argv 顺序应用挂载，later wins**。所以在 `--tmpfs /tmp` **之后**再补一条
`--bind`，就能把宿主的一个子目录叠回不可丢的位置：

```diff
      args.push('--tmpfs', '/tmp')
      args.push('--bind', policy.workspaceRoot, policy.workspaceRoot)
+     if (policy.scratchRoot !== undefined) {
+       args.push('--bind', policy.scratchRoot, policy.scratchRoot)
+     }
```

**只放行这一个子目录**，`/tmp` 其余部分保持 per-call tmpfs —— 比"整个 `/tmp` 放行"精细，
且保留了 OS 的 GC 语义。

**设计取向：不把 `.dsh-tmp` 烤进源码**。沙盒只多认一个通用的 `scratchRoot` 配置字段，
落点由 deployment 给 ⇒ 换落点不用再动源码。

### 三处改动（一个整体）

| 文件 | 改动 |
|---|---|
| `sandbox/src/index.ts` | `SandboxExecutionPolicy` 加可选 `scratchRoot?: string` |
| `sandbox-local/src/profiles.ts` | `bwrapProfileArgs` 在 tmpfs 之后 bind 它 |
| `sandbox-policy/src/index.ts` | Config/schema/构造/`resolve()` 透传；`resolveScratchRoot()` 解析 + Win32 合法性检查 |

## 三、落点三层优先级

```
显式 config（profile 的 sandbox-policy.scratchRoot）
  ↓ 未设
DSH_SCRATCH_ROOT（启动器注入）
  ↓ 未设
平台默认：%TEMP%\.dsh-tmp（Windows）/ /tmp/.dsh-tmp（其余）
```

**为什么有 env 那一层**：scratch 目录必须**在任何沙盒调用之前就存在** —— 实测
`bwrap --bind <src>` 在 `<src>` 缺失时直接失败（`Can't find source path`，rc=1）
⇒ 沙盒里**每条命令全挂**。而"何时建目录"归启动器管（它拥有实例生命周期），
所以落点也从启动器传下去，两边不会漂。这与 `DSH_HOME` / `DSH_VERSION` 同一条既有通道
（启动器设 `os.environ` → DSH 主进程继承 → 它 spawn 的 bwrap 再继承；
**不经 MCP 管家的环境净化**）。`DSH_SCRATCH_ROOT` 不在 `dsh_instance_env.py` 的剥离清单里。

### Windows 口径

- 默认落点 `%TEMP%\.dsh-tmp`；`resolveScratchRoot()` **展开 `%VAR%` / `${VAR}` / `$VAR`**
  （`resolveWorkspaceRoot` 只查 `isAbsolute`，不展开）
- **Win32 传统 API 名字合法性检查**（仅 `win32`）：拒绝保留设备名（`CON` `PRN` `AUX` `NUL`
  `COM1..9` `LPT1..9`，大小写/带扩展名/带尾点尾空格**一律拒绝**）与以点或空格结尾的段。
  两类都是 POSIX 下合法、而 `CreateFileW` 打不开的名字。
- ⚠️ **检查必须在 `%VAR%` 展开之后**（实现里就是这个顺序，别挪）：配置写
  `%TEMP%\CON\scratch` 时要检查的是展开后的 `...\Temp\CON\scratch`。挪到展开前，
  展开产物里的非法段就漏过去了 —— 而且**只看代码看不出来**（两种顺序都"检查了路径"）。
- **Windows 分支不猜**：`TEMP` / `TMP` 都没设就 fail-loud，**不**回退到
  `~\AppData\Local\Temp`。实测理由：本机 `%TEMP%` 被有意重定向到 **ImDisk 内存盘**
  （`<R盘>:\TEMP`），而回退猜测会静默落到 **C: 的 SSD** —— 正是用户特意挪开的盘。

## 四、启动器侧（`start-web.py`）

- `scratch_root()` —— 平台口径；**显式覆盖优先**（环境里已有 `DSH_SCRATCH_ROOT` 就用它）
- `build_instance_env()` 里 `os.environ["DSH_SCRATCH_ROOT"] = scratch_root()`
  （**在环境净化之前**，与 `DSH_HOME` 同类）
- `guard_scratch_root()` —— 开机 `mkdir -p` **+ 探针测写**，任一失败即拒绝开机
  （fail-loud）。**不清空**：寿命交给平台（tmpfs 重启即清 + systemd-tmpfiles），
  开机清一次反而与插入/绑定抢时序。

> ⚠️ **探针测写不能省**：`mkdir` 成功 **≠** 写得进去 —— 目录「已存在但只读 / 属他人 /
> 挂在只读介质上」时 `exist_ok=True` 会**静默返回**，而 bwrap 的 `--bind` 照样成功
> （目录存在）⇒ 失败推迟到 agent 第一次写入才暴露，散落在几百次调用里。
> 这正是 `沙盒外写操作准入.md` 那条「唯一无条件、与 policy 无关的纪律：探针测写」要挡的情形。
> （实测：只 `mkdir` 的版本在只读目录上**通过**了。）

## 五、说明句到不了 agent —— 已修（走 persona + 变量）

设计里有一条"告诉 agent"：`renderPolicyContext` 的 `workspace-write` 分支会带上
scratch 路径 + **寿命不保证** + **任何人可读（别写敏感信息）**。

**实测发现它没生效。** `system/message`（21K 字符）里：

| 检查 | 结果 |
|---|---|
| 含「你当前运行的模型是」 | **True** |
| 含「DSH file policy」 | **False** |
| 含「scratch」 | **False** |

**根因**（`core/system-prompt/src/index.ts:614/633`）：

```ts
contexts: runtimeContextSuppressed ? [] : [...],   // ← context 全清空
variables,                                         // ← variables 不受影响
```

你们 **5 个 preset 全是 `includeRuntimeContext: false`**（`cordis.patch.yml` 768/1690/2454/3236/3989）
⇒ **`systemPrompt.context()` 这条通路整个是死的**，`sandbox:policy`（含我的 scratch 段）
一律被清空。这解释了模型身份为什么活下来 —— 它走的是 **persona 段 + `{{model}}` 变量**，不是 context。

**修法**（同日完成）：走 persona + 变量那条活路。因为 plugin 的 `apply()` 与本 preset
的 persona 在**同一 scope**，变量名对得上就能插值。

- **插件**：并入 `patches/0.1.7-agent-presets/cwd-fallback.mjs`（用户定：这类功能都放这），
  加文件头 §7 + 常量 `RUNTIME_PLACEHOLDER` + 三个变量注册：
  `{{session_id}}`（`context.agent?.session.id`）、
  `{{dsh_version}}`（`process.env.DSH_VERSION`）、
  `{{scratch_dir}}`（`process.env.DSH_SCRATCH_ROOT`）。
  后两者与启动器同源（启动器设 → 主进程继承 → 插件读 → bwrap 再继承），不会漂。
- **persona**：5 个 preset 各加「# 运行环境」段（紧随「# 模型身份」之后），
  引用这三个变量 + scratch 的两条硬约束（寿命不保证 / 任何本机用户可读）。
  会话 id 与版本号是**排查"莫名其妙"故障的第一手线索**，故一并送进去。

⚠️ **变量名有硬约束**（踩过，见错账 #7）：框架要求 `^[a-z][a-z0-9_]*$` —— **不允许大写**。

**验证**（重启前能做的都做了）：把 persona 里**所有** `{{...}}` 抽出来逐个核对
名字合法性与是否已注册 ⇒ `cwd` / `model` / `session_id` / `dsh_version` / `scratch_dir`
全部通过；YAML 结构可解析（剥 `!!js` 后）。

✅ **重启后实测确认**（`session-ce05d9ba-5322-4dd7-a85a-8fc50efaaa47` 的 `system/message`）：

```
# 运行环境

- **会话 id**：`session-ce05d9ba-5322-4dd7-a85a-8fc50efaaa47`   ← 与实际会话一致
- **DeepSeek Harness 版本**：`v0.2.0-rc.2`
- **沙盒 scratch 目录**：`/tmp/.dsh-tmp`
```

⇒ **缺口闭合**：说明句确实进了模型上下文。
附带结论：**「persona 段 + 变量」这条通路可用** —— 以后凡是要让模型看见运行时信息
（而 `systemPrompt.context()` 被 `includeRuntimeContext: false` 清空）的场合，都走这条。

## 六、实测结果（2026-10-12，真机 workspace-write、真 bwrap）

| 检查 | 结果 |
|---|---|
| 工作区外写 `/mnt/e` | **拒**（`只读文件系统`）✓ |
| scratch `/tmp/.dsh-tmp/x` 跨调用 | **在** ✓ |
| 普通 `/tmp/y` 跨调用 | **没了** ✓（per-call 语义保住） |
| 工作区内写 | 在 ✓ |
| 沙盒内写入落宿主 | ✓（宿主侧可见） |
| 沙盒内 `ls -A /tmp` | **只有 `.dsh-tmp`** ← 设计意图的直观体现 |
| 沙盒 PID | `2`（`--unshare-pid` 特征） |

## 七、错账（诚实记）

| # | 错 | 教训 |
|---|---|---|
| 1 | 三个文件打成一整份 `.patch`，而清单里三个 `[[target]]` 都指向它 | 逐 target 重放时第二、三次必失败 —— **`[[target]].patch` 必须一 target 一件**。不修的话**下次开机才炸**，而那时已经重启过了 |
| 2 | `_read_maybe_zstd` 的回退路径拿 `os.path.getsize`（**压缩后**字节）当读多少的上限 | 在「解压输出 == 压缩大小」处**静默截断**（实测 4,352,964 → 952,956 B）。两个数字都看起来合理 ⇒ 只有**独立比对原始字节**才抓得到 |
| 3 | `guard_scratch_root` 只 `mkdir`、不测写 | 只读目录上**通过了** —— 我自己读过、引用过 `沙盒外写操作准入.md` 那条「探针测写」，**然后没照办** |
| 4 | `build_instance_env` 里 `DSH_SCRATCH_ROOT` 无条件覆盖 | 我报错文案里写的「设 `DSH_SCRATCH_ROOT=…` 再启动」成了**空话**（会被覆盖掉） |
| 5 | 断言 `ntpath.expanduser` 只认正斜杠 | **错**：`seps = '\\/'` 两个都认，原写法本来就能跑。把"顺手清理"说成"修 bug"是夸大 |
| 6 | 首次 `.patch` 用 grep 验证 `lib` 是否更新 | `tsc -b` 返回 0、`tsbuildinfo` 更新，但 **`lib/index.js` 的 mtime 纹丝不动** —— 这两个包的 `outDir` 是 `lib/types`（只出 `.d.ts`），真正被 import 的 `lib/index.js` 是 **`tsdown` 打的包**。只跑 tsc 等于没生效 |
| 7 | 新变量起名 `sessionId` / `dshVersion` / `scratchDir`（驼峰） | 框架的 `VARIABLE_NAME = /^[a-z][a-z0-9_]*$/` **不允许大写**，而且**注册时（`system-prompt:538`）与引用解析时（`:346`）两处都会抛** ⇒ 直接重启的话**所有会话都建不起来**。改成 snake_case 才对。**教训**：给框架加名字前，先把它的**命名/校验契约**读出来，别照自己的习惯起名 |

> 第 3、5 两条是同一族：**把"我以为的机制"当成机制**。第 3 条尤其典型 ——
> 用户的 `Application Data` 直觉（"**没发 dir 但能穿过去写**"）把它引了出来：
> 「存在」不等于「可用」。

## 八、版本升级立即排查清单

1. 开机护栏 `guard_ui_patches` 是否报漂移（`guards/ui_patches.txt`）
2. 三处结构是否还在（见 `补丁/sandbox-scratch/manifest.toml` 的 `must_contain`）
3. 上游是否已自带等价能力 ⇒ 若是，**删掉 `补丁/sandbox-scratch/` 整个目录**
4. 重打后回读：三个 `lib/index.js` 含 `scratchRoot`、`tsc -b` rc=0、
   启动器 `DSH_SCRATCH_ROOT` 已注入、真机验证「scratch 跨调用可见 + 其余 /tmp 不可见」

---

**注**：本文件的写入走的是**文件系统 MCP 工具**而不是 bash —— 因为当时会话已在
`workspace-write` 下，bash 写 `~` 会被沙盒拒（实测 `只读文件系统`）。
这正好是 `沙盒外写操作准入.md` 第 2 条（「沙盒外一律走 MCP 文件工具」）的现场例证。
