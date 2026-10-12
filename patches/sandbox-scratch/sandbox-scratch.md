# 沙盒 scratch 落点（per-instance 跨调用可写目录）

文件名: 补丁/sandbox-scratch/sandbox-scratch.md
摘要: 让 `workspace-write` 沙盒拥有一个**跨调用存活**的 scratch 目录 —— 由 bwrap 在
      `--tmpfs /tmp` 之后 bind 回宿主一个子目录；其余 `/tmp` 保持每次全新。
依赖: 无（补丁本体见同目录 manifest.toml 与 *.patch）

## 要解决的问题

`workspace-write` 下 bwrap 执行 `--tmpfs /tmp`，官方 e2e 断言的语义是：

> workspace-write mounts an EPHEMERAL /tmp: **the write succeeds inside, the host /tmp stays untouched**

⇒ **`/tmp` 在沙盒里寿命为零**（一次调用即没）。于是：

- 沙盒内 `mkdir /tmp/foo`，**下一次工具调用就看不见**
- 想"跨调用缓存中间结果"在 `workspace-write` 下**不可能**
- 退而求其次往**用户工作区**挖 `.XXX-tmp` 是越界的：既进用户的文档树/备份/搜索，
  又**绕过了 OS 本来替你管好的 tmpfs GC**

同时，官方**没有**"追加可写根"的配置：`sandbox-policy` 的 `Config` 只有
`mode` / `workspaceRoot`；`writableRoots()` 是硬编码的
`{workspaceRoot, '/tmp', tmpdir()}`。⇒ 只能打补丁。

## 修法

bwrap **按 argv 顺序应用挂载，later wins**。所以只要在 `--tmpfs /tmp`
**之后**再补一条 `--bind`，就能把宿主的一个子目录叠回不可丢的位置：

```diff
      args.push('--tmpfs', '/tmp')
      args.push('--bind', policy.workspaceRoot, policy.workspaceRoot)
+     if (policy.scratchRoot !== undefined) {
+       args.push('--bind', policy.scratchRoot, policy.scratchRoot)
+     }
```

**只放行这一个子目录**，`/tmp` 其余部分保持 per-call tmpfs —— 比"整个 `/tmp` 放行"
精细得多，且保留了 OS 的 GC 语义。

### 实测（本机 bwrap 0.13.0）

| | 容器内 `/tmp` | 宿主 |
|---|---|---|
| 仅 `--tmpfs /tmp` | 空（每次全新） | 不受影响 |
| `--tmpfs /tmp` **后**再 `--bind <host> /tmp` | 见宿主内容 | 容器内写入**落到宿主** ✓ |

跨进程验证：第 1 次 bwrap 写 `scratch/persist.txt` 与 `/tmp/gone.txt`；
第 2 次 bwrap（新进程）→ `persist.txt` **仍在**，`gone.txt` **没了**。预期行为。

## 改了什么（三处，一个整体）

| 文件 | 改动 |
|---|---|
| `packages/sandbox/sandbox/src/index.ts` | `SandboxExecutionPolicy` 加可选字段 `scratchRoot?: string` |
| `packages/sandbox/sandbox-local/src/profiles.ts` | `bwrapProfileArgs` 在 tmpfs 之后 bind 它 |
| `packages/sandbox/sandbox-policy/src/index.ts` | Config/schema/构造/`resolve()` 透传；`resolveScratchRoot()` 解析 + Win32 合法性检查；policy context 加说明句 |

### 设计取向：不把 `.dsh-tmp` 烤进源码

源码里**没有** `.dsh-tmp` 字面量 —— 沙盒只多认一个**通用**的 `scratchRoot` 配置字段，
落点由 deployment 配置（profile 的 `sandbox-policy` 段）给。好处：换落点不用再动源码。

### Windows 口径

- 默认落点是 **`%TEMP%\.dsh-tmp`**（Windows）/ `/tmp/.dsh-tmp`（其余）
- `resolveScratchRoot()` **展开 `%VAR%` / `${VAR}` / `$VAR`**（`resolveWorkspaceRoot`
  只查 `isAbsolute`，不展开）
- **Win32 传统 API 名字合法性检查**：`process.platform === 'win32'` 时拒绝
  - 保留设备名（大小写、带扩展名、带尾点/尾空格**一律拒绝**）：`CON` `PRN` `AUX` `NUL`
    `COM1..9` `LPT1..9`
  - 以点或空格结尾的段
  这两类都是 POSIX 下合法、而 `CreateFileW` 之类的传统 Win32 API **打不开**的名字。
  在**解析期**拒绝 ⇒ 把"agent 第一次写入悄悄落到不可用的地方"变成**开机就报错**。

  ⚠️ **检查必须在 `%VAR%` 展开之后**（实现里就是这个顺序，别挪）：
  配置写 `%TEMP%\CON\scratch` 时，要检查的是展开后的 `<C盘>:\...\Temp\CON\scratch`
  —— 那个 `CON` 段才是 Win32 API 真正会撞上的东西。若把检查挪到展开**之前**，
  展开产物里的非法段就整个漏过去了，而这个改动在只看代码时**看不出来**
  （两种顺序都"检查了路径"）。

### System Prompt 里给模型的说明

`renderPolicyContext` 的 `workspace-write` 分支会带上：

- scratch 目录的绝对路径，以及"跨调用存活"这一点
- **WORLD-READABLE**：平台临时区对每个本地用户都可穿越，新目录取进程 umask（实测 `755`），
  ⇒ 明令**不得**写密钥/凭据/个人数据/内部地址
- **寿命不保证**：重启或平台 temp cleaner 都会清掉 ⇒ 要长存的东西该落**专业项目目录**

> 措辞刻意是**泛指"每个本地用户"**而不是"同一实例的其他会话"：宿主 `/tmp` 是 `1777`，
> 泄漏面就是整台机器。窄化边界会让模型低估风险 —— 那比笼统更糟。

## 落点是怎么确定的（三层优先级）

```
显式 config（profile 的 sandbox-policy.scratchRoot）
  ↓ 未设
DSH_SCRATCH_ROOT（启动器注入）
  ↓ 未设
平台默认：%TEMP%\.dsh-tmp（Windows）/ /tmp/.dsh-tmp（其余）
```

**为什么要 env 那一层**：scratch 目录必须**在任何沙盒调用之前就存在** ——
实测 `bwrap --bind <src>` 在 `<src>` 缺失时直接失败（`Can't find source path`，rc=1）
⇒ 沙盒里**每条命令全挂**。而"何时建目录"归启动器管（它拥有实例生命周期），
所以把落点也从启动器传下去，两边就不会漂。这与 `DSH_HOME` / `DSH_VERSION`
同一条既有通道（启动器设 `os.environ` → DSH 主进程继承 → 它 spawn 的 bwrap 再继承；
**不经 MCP 管家的环境净化**）。

⚠️ 这是**实现细节不是用户旋钮**：部署该在 config 里写落点；env 那一层是启动器
的接线。`DSH_SCRATCH_ROOT` 不在 `dsh_instance_env.py` 的剥离清单里，故能活过净化。

## 启动器侧（`start-web.py`，本地改动，不在补丁里）

- `scratch_root()` —— 平台口径（`os.name == "nt"` ⇒ `%TEMP%\.dsh-tmp`）。
  **显式覆盖优先**：环境里已有 `DSH_SCRATCH_ROOT` 就用它 —— 否则守卫报错里那句
  「设 `DSH_SCRATCH_ROOT=…` 再启动」就是空话（会被无条件覆盖掉）。
  **Windows 分支不猜**：`TEMP` / `TMP` 都没设就 fail-loud，**不**回退到
  `~\AppData\Local\Temp`。理由是实测的：本机 `%TEMP%` 被有意重定向到
  **ImDisk 内存盘**（`<R盘>:\TEMP`），而回退猜测会静默落到 **C: 的 SSD** ——
  正是用户特意挪开的盘。**落错地方还不报错，比拒绝启动糟得多。**
- `build_instance_env()` 里 `os.environ["DSH_SCRATCH_ROOT"] = scratch_root()`
  （**在环境净化之前**，与 `DSH_HOME` 同类）
- `guard_scratch_root()` —— 开机 `mkdir -p` **+ 探针测写**，任一失败即拒绝开机（fail-loud）。
  ⚠️ **探针测写不能省**：`mkdir` 成功 **≠** 写得进去 —— 目录「已存在但只读 / 属他人 /
  挂在只读介质上」时 `exist_ok=True` 会**静默返回**，而 bwrap 的 `--bind` 照样成功
  （目录存在）⇒ 失败推迟到 agent 第一次写入才暴露，散落在几百次调用里。
  这正是 `用户笔记/部署/沙盒外写操作准入.md` 那条
  「唯一无条件、与 policy 无关的纪律：探针测写」要挡的情形。
  （实测：只 `mkdir` 的版本在只读目录上**通过**了。）
  刻意不"用到再建"：失败点集中在开机一处，比散落在几百次调用里好定位。
  **不清空**：寿命交给平台（tmpfs 重启即清 + systemd-tmpfiles），
  开机清一次反而与插入/绑定抢时序。

## 版本升级立即排查清单

1. 开机护栏 `guard_ui_patches` 是否报漂移（`guards/ui_patches.txt`）
2. 三处结构是否还在（见 `manifest.toml` 的 `must_contain`）
3. 上游是否已自带等价能力 ⇒ 若是，**删掉本目录**
4. 重打后回读：三个 `lib/index.js` 含 `scratchRoot`、`tsc -b` rc=0、
   profile 的 `scratchRoot` 已填、真机验证跨调用可见
