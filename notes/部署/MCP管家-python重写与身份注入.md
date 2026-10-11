# MCP 管家 python 重写与实例身份注入（2026-10-08）

**一句话**：`wrap/mcp-stdio.sh`（bash，109 行 `case`，15 个分支）→
`<挂载d>:/DataServices/MCP/mcp启动器.py` + `mcp服务.toml`；
并补上一条**断掉的链路**：MCP 服务从此知道**自己在伺候哪个实例**。

---

## 一、为什么换

用户口径（原话）：

> 「bash 只适合干一件事：**source 完了 exec**。再复杂就不要让 bash 干了。」

这不是教条 —— 本项目**已经用同一条规则迁过两次**（`start-web.sh` → `start-web.py`；
`dsh-instance-env.sh` → `dsh_instance_env.py`）。MCP 管家是**最后一个 bash 钉子**。

顺带交代一条**不构成理由**的东西：15 个分支里那 10 处重复的
`source ~/ai-services/bin/activate` + `exec python3 …` —— **那是分派表，不是样板** ✗
（每行是一条**独立事实**，不是同一算法的拷贝）。**不要**拿"去重"当换语言的理由。

## 二、设计定案

| 项 | 定案 | 为什么 |
|---|---|---|
| 清单 | `mcp服务.toml`（**数据**） | 加服务 = 加一节，不碰代码；注释承载"为什么" |
| 执行器 | `mcp启动器.py`（**通用**） | 不含任何服务专属逻辑 |
| 变量 | `${NAME}`，**单趟、只能向后引用** | 语法上不可能成环（比"检测环"强） |
| 预制菜 | `${_DP0_}` = 管家自己所在目录 | `%~dp0` 的 Linux 转世（用户点名保留） |
| `cmd` | **完整 argv**（绝对路径优先） | `--dump` 与真实 `exec` 逐字节相同，无拼接逻辑 |
| `cwd` | **每服务显式** | 旧脚本 8/15 不设 cwd ⟹ 跑在"客户端碰巧的目录"里 ✗ |
| 代理 | **三态**：`proxy="url"` / 不写（跟着底座剥）/ `keep_env=[…]`（服务自己的开关 ✓） | 来自 pergaminos 那条教训：「在 wrapper 里硬编码会架空那个开关」 |
| `env_glob` | 声明式取值（`glob`+`sort=version`+`pick=last`） | 把 `ls \| sort -V \| tail -1` 从逻辑变成数据 |
| `identity` | **默认全注入 + 可 opt-out** | "MCP 不知道自己在伺候谁"正是本次要治的根 |

## 三、三条不能动的纪律

1. **stdout 只属于协议** ★ —— 规范原文：server「MUST NOT write anything to its `stdout`
   that is not a valid MCP message」。⟹ 管家**每一句话都走 stderr** ✓
   （规范同时说 stderr 可用于任何日志、且 client「SHOULD NOT assume stderr output
   indicates error conditions」⟹ 往 stderr 报"我起来了"是**规范行为** ✓）
2. **必须 `os.execvpe`，绝不 `Popen` 中继** ★ —— 规范：client 关 stdin 是
   「the primary graceful-shutdown signal and **the only portable one**」。
   中间多一层就挡掉 EOF ✗⟹ exec 之后本进程即服务，管道直通、零转发 ✓
3. **先净化、再注入身份** —— 反过来等于白注入（与 `start-web.py` 的 preload 注入同一条）

## 四、窗口即环境（用户口径，我错过一次）

> 「我们的窗口是**裸运行 `start-web.py`** 的，所以按规则应该是
> **这个窗口里之前塞了什么 python 就会用什么**。」

⟹ MCP 服务是"**那个窗口里的东西**" ✓ 用窗口的解释器是**设计**，不是疏漏 ✓
⟹ 我第一版建议把 `command` 改成 `/usr/bin/python3` ✗ —— **错的**，那会架空这条规则。

**两条推论**（写进了 `mcp启动器.py` 的头部）：
- ① 管家**不得**用「3.11 以下没有」或「某版本独有」的东西
  （实测 **3.14.7 与 3.12.13 都能跑** ✓；只用到 `tomllib`(3.11+)、`os.execvpe` 与常规件）
- ② **不要**改成绝对路径

## 五、身份注入链路（本次最要紧的一段）

**为什么必需**：harness 给 MCP 服务的是**净化过的环境** —— `buildChildEnv()` 就一句
`return { ...scrubbedParentEnv(), ...extra }` ⟹ **`DSH_*` 一个都传不过去** ✗
（实测：活的 MCP 服务进程里连 `DSH_HOME` 都没有 ✓）

**链路**：

```
start-web.py finalize 时 ──► 运行记录/<时间>-PID<n>/identity.env   （KEY=value）
                            └► 运行记录/当前  →  符号链接指过去
mcp启动器.py ──► 读 identity.env ──► 注入 DSH_HOME / DSH_VERSION /
                                    DSH_HARNESS_DIR / DSH_TRACE_LOG
```

**它救活了什么**：melquiades 的 `resolve_dsh_home()` 第 ①b 档是
「`harness_dir` + 版本 → 派生 home」。身份一到，它自己就算出 `dsh-domus-<版本>`，
**一行代码都不用改** ✓✓
少了它，逐级回落到 `~/.dsh`（不存在）⟹ 收割静默 `files=0/0` ——
它自己的注释写着「看起来像没新数据，实则断流」✓

**修复前后**（实测）：

| | 前 | 后 |
|---|---|---|
| 收割 | `files=0/0 advanced=0` ✗ | **`files=1/112 advanced=1`** ✓ |
| 日志 | `sessions 目录不存在: ~/.dsh/sessions` ✗ | 没了 ✓ |

**为什么落到文件而不是环境变量**：MCP 服务的环境是**净化过**的 ✗，
而且它的 env 在 **spawn 那一刻固化** ✗ ⟹ 只有"文件 + 符号链接"这种
**可被外部更新**的载体才管用 ✓
**为什么格式是 `KEY=value`**：它本质就是一份 env ✓ shell 能 `. file`、
python 三行能解析、别的工具也认 ✓ —— TOML 会逼每个消费者都带解析器 ✗

## 六、切换（`tools/cutover-mcp-launcher.py`）

**默认干跑**，做两件事：① **复制** 7 个单文件工具到 `零散单项工具/`（**复制不搬** ⟹
旧管家继续可用 ⟹ 没有"半路状态"窗口 ✓）② 改 profile 里 **10 处**声明
（`args` + `command` 一起换 ✓）。

**保护栏**：备份放 **profile 目录之外** ✗（放里面可能被加载器当配置读）✓ /
**原子替换** ✓ / **回读校验**（0 残留 + 新引用 + YAML 能解析）✓ /
**数量守卫**（替换数对不上就拒绝）✓ / 幂等（重跑无害）✓

## 七、今天的错账（诚实记）

| # | 错 | 教训 |
|---|---|---|
| 1 | 用 **pyyaml** 校验 DSH 配置 ⟹ 把 **`!!js`**（js-yaml 方言）报成"解析失败" ✗ 而且是**改完之后**才报 | **假报警**比不报更坏 ✓ 已放行 js 标签族 ✓ |
| 2 | 只换 `args` ✗ **没换 `command: bash`** ⟹ `bash <python文件>` ⟹ bash 读到 `import os` 把 **ImageMagick 的 `import`** 拉去抓 X 窗口 | **半迁移** ✓ 守卫只盖了 args ✗ 现在两处都有守卫 ✓ |
| 3 | 建议 `command` 改绝对路径 ✗ | **窗口即环境** ✓ 用户纠正 ✓ |
| 4 | 代码头写着「只能用 /usr/bin/python3 跑」✗ | **文档说谎** ✓ 已改 ✓ |
| 5 | `load_config` 只展开 `services` ✗ ⟹ `[launcher].identity_file` 里 `${records}` 从没被替换 ⟹ 管家永远报"无实例归属" —— 而**那是合法状态** ⟹ 看起来完全正常 | **教科书级静默降级** ✓ 已改「一次性展开整棵树」（INF 的规矩：先全部展开，再谈下面）✓ |
| 6 | 本会话另有 **7 次** quoting/语法自伤（ASCII 引号 ×2、海象运算符、反引号被当命令替换…） | 全部被「**写完立刻编译 + 看完输出再说话**」当场抓住 ✓ 一次都没流出去 ✓ |

**四条里 3、4、5 是同一个毛病**：我反复把「更强的确定性」当默认目标 ✗，
而这里的规则**早就定了**（窗口即环境 ✓）。与同一天我批 `DRY`、
批"注册表该是数据"是同一族 —— **先问规则是什么，再问要不要加固** ✓

## 八、待办

- [ ] `wrap/` 退休：她自己是 git 仓库，**删前先 tar**（`zero` 件留在 `零散单项工具/`）
- [ ] `papersearch` 残节：`~/venv-mcp-papersearch` **整个目录已不存在** ⟹
      要么补回 venv，要么把这节从 `mcp服务.toml` 删掉
- [ ] `linkdigest`：**活的**（在 DSH 工具列表里）但旧脚本里没分支 ⟹ 查清后决定收编还是单列
- [ ] `myragwrapper`：旧脚本帮助串里有、`case` 里没有（漂了）——
      新设计帮助由清单生成 ⟹ 结构上不可能再漂 ✓
- [ ] 收割观察：积压追平后若 `compactions` **仍恒为 0**，那是下一件事
- [ ] ⚠️ `FastMCP 4.0.10 → 4.0.11` 那个更新提示**别顺手跟** ✗
      （在 venv 里升 fastmcp/mcp 正是 `papersearch` 那场版本冲突的成因）

## 九、检索入口

| 想干什么 | 去哪 |
|---|---|
| 加/改一个 MCP 服务 | `mcp服务.toml`（`[services.<名字>]` 一节） |
| 看某服务最终怎么起 | `python3 <挂载d>:/DataServices/MCP/mcp启动器.py --dump <名字>` |
| 依赖是否齐 | `… --check`（"悄悄少了东西"的早期报警，不是崩溃） |
| 变量展开后是什么 | `… --vars` |
| 身份从哪来 | `start-web.py` 的 `write_identity()`；落点 `运行记录/当前/identity.env` |
| 为什么 MCP 拿不到 DSH_* | harness 的 `buildChildEnv()`（`{...scrubbedParentEnv(), ...extra}`） |
| 切到新管家的明细 | `tools/cutover-mcp-launcher.py`（干跑）/ `--apply` |
