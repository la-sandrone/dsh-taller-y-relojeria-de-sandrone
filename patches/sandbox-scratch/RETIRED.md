# 已退役：sandbox-scratch（2026-11-04）

**这个补丁不再需要了 —— 上游 0.2.2 用同一设计思路实现了它。**

本目录**保留为存档**，不是可用的补丁说明；`manifest.toml` 与三个 `.patch` 只对 0.2.0 基线有意义。

## 它当年解决什么

`workspace-write` 下 bwrap 执行 `--tmpfs /tmp` ⇒ **沙盒里的 `/tmp` 寿命只有一次调用**，
跨调用临时目录不存在。往用户工作区挖 `.XXX-tmp` 又越界（进备份、进全文搜索、绕过 OS 的 tmpfs GC）。

补丁的做法：不把路径烤进源码，而是给 `sandbox-policy` 加一个 `scratchRoot` 字段，
在 `--tmpfs /tmp` **之后**再 `--bind` 一次（bwrap 按 argv 顺序应用，later wins）⇒
**只有这一颗子目录跨调用存活**，`/tmp` 其余保持每次全新。

## 上游怎么取代它

0.2.2 的 `sandbox-policy` 新增 `additionalWritableRoots: string[]`（多根列表，**落点由 deployment 给**——
与当年的设计取向一致），bwrap 后端对每个根 `--bind`，顺序同样在 `--tmpfs /tmp` 之后：

```
packages/sandbox/sandbox-local/src/profiles.ts:19-21   --tmpfs /tmp  →  逐个 --bind root root
packages/sandbox/sandbox/src/roots.ts:84               workspaceWritableRoots = [workspaceRoot, ...additionalWritableRoots]
```

所以配置一条就等价：

```yaml
- id: sandbox-policy
  config:
    mode: !!js process.env.DSH_PERMISSION_MODE ?? 'workspace-write'
    workspaceRoot: !!js process.cwd()
    additionalWritableRoots:
      - /tmp/.dsh-tmp
```

上游还多给三样（我们当年没有）：

1. **每次调用校验**：不存在 / 不是目录 / 是符号链接 ⇒ `SANDBOX_INVALID_ROOT`，命令启动前就拦；
2. **多根列表**（不止一颗子目录）；
3. `read-only` 下**明确不授予**（`roots.ts:84` 对非 `workspace-write` 直接返回空集）。

## 配套（仍然有效）

启动器侧的守卫本来就没失效，而且**默认落点正好是这个**：

- `start-web.py` 的 `scratch_root()` 默认返回 `/tmp/.dsh-tmp`（可被 `DSH_SCRATCH_ROOT` 覆盖）；
- `guard_scratch_root()` 开机 `mkdir` + **探针测写**（只 mkdir 不测写会漏掉「存在但写不进」），建不出来就拒绝开机。

System Prompt 也已同步：各 preset 都写明「未获 `danger-full-access` 时，草稿一律写 `/tmp/.dsh-tmp/`」。

## 为什么留在这里而不是删掉

它是**判据的来源**：为什么要有跨调用草稿区、为什么不挖工作区、为什么用挂载顺序而不是改策略，
这三条结论在 0.2.1 时代是被实测逼出来的。删掉文件，结论就只剩结论。
