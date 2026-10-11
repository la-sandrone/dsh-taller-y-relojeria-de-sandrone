# 启动器 python 重写 · 庙算与定案

文件名: 用户笔记/部署/启动器-python重写-庙算与定案.md
摘要: 把 `start-web.sh`（582 行 bash）整体重写为 `start-web.py` 的决策记录 —— 26 条定案、
      新的「启动器配置和日志」结构、必须逐项等价的行为契约、以及两条被实验推翻的原判断。
依赖: ../../start-web.sh（现役，被移植方，当前作 oracle）
      ../../tools/dsh-instance-env.sh（净化器，被移植方，当前作 oracle）
      ../../bin/dsh（python 重写对象）
      ./DSH启动器-架构与bash-python分工.md（上游设计文档）
      ./版本标记依赖审计.md（本轮的输入之一）

---

## 零、这份文档是什么

`start-web.sh` 已经压到 bash 的能力上限（582 行：实例所有权记录、严格目标解析、两套退出
语义、信号处理）。本轮的定案是 **把它搬走**，不是把它修得更好。

本文记录三件事：**决定了什么**（§二）、**新结构长什么样**（§三）、
**什么东西必须逐字节等价**（§四）。以及 —— **庙算期间被实验推翻的两条判断**（§五），
因为那两条的教训比结论本身值钱。

---

## 一、工作包

| 段 | 内容 | 状态 |
|----|------|------|
| W0 | 本文（记档） | ✅ |
| W1 | 净化器移植 `tools/dsh_instance_env.py` + 双实现对拍 | |
| W2 | `启动器配置和日志/` 结构 + 共享派生模块 | |
| W3 | `start-web.py` 骨架：参数/派生/运行记录/对账归档/`--status`/`--stop` | |
| W4 | `start-web.py` 启动路径：净化/注入/代理/cloudflared/护栏/版本门/守护/前后台 | |
| W5 | `bin/dsh` python 重写；退役 `bin/dsh-dryrun`；`backup-dsh.sh:122` 一行 | |
| W6 | shim 原子替换 + bash/python 对拍 + 停机窗口真机验收 | |
| W7 | 文档收敛（审计文档、架构文档、README、INDEX） | |

---

## 二、定案表

### 入口与运行形态

| # | 决策点 | 定案 | 依据 |
|---|--------|------|------|
| D1 | 入口 | `start-web.py` 放仓库根；`start-web.sh` 缩成 shim `exec /usr/bin/python3 "$DIR/start-web.py" "$@"` | 十几处文档/工具引用 `./start-web.sh`，名字不动则引用面零改动 |
| D2 | 解释器 | shebang **`#!/usr/bin/python3`**（绝对，不用 `env`）；脚本内断言 `sys.prefix == '/usr'`，否则拒绝启动 | `env` 会撞上 PATH 里第一顺位的 `~/ai-services/bin/python3`（3.12）；有人手动 `python3 start-web.py` 也必须当场被拦，不许静默换解释器 |
| D3 | 依赖 | **纯标准库**：argparse / json / tomllib / os / signal / subprocess / pathlib / shutil / socket / time | 用户约束；实测启动器不需要任何第三方包 |
| D14 | 写 shim | **原子 `mv` 替换，绝不就地截断** | 见 §五·证据 C：bash 按字节偏移续读被执行的脚本 |
| D22 | 配置 vs 代码 | 配置只放**随环境变的选择**（version / main_port / home_prefix / try_port_from）；**设计规则留代码**（等待秒数、退避阶梯、退出码、SIGTERM→20s→SIGKILL） | 规则一旦能被配置文件改，就没人知道「标准行为」长什么样；那是把魔法数字从「藏在代码里」升级成「藏在某文件里且每人不同」 |

### 环境与子进程

| # | 决策点 | 定案 | 依据 |
|---|--------|------|------|
| D4 | 实例级 venv 注入 | **作废 —— 不注入** | 见 §五·推翻一：全局注入既不足（服务不了 papersearch）也不必要 |
| D5 | 净化器 | **移植成 `tools/dsh_instance_env.py`**；bash 原版留作 oracle 做双实现对拍，验收通过后删除 | 原版测试文件已丢失（全仓 grep 只剩注释里提到的用例名 `strip:foreign`）⇒ 用**原件本身**当 oracle 比「重建测试」可信 |
| D6 | 护栏脚本 | 用 `sys.executable` 绝对路径调用；退出码**既非 0 也非 1 → 放行 + 告警** | 杀掉「换个地方启动换解释器」的隐性不一致；沿用 `start-web.sh:474` 现有哲学「一个护栏 bug 不该把 DSH 锁死在门外」 |
| D7 | pnpm | 净化后 `shutil.which('pnpm')` 取绝对路径（实测 `/usr/bin/pnpm` → corepack shim，净化不伤它）；**找不到即拒绝启动** | 消掉又一个静默失败模式 |
| D8 | 子进程 | 一律参数数组、`shell=False`；host 输出用 `Popen` + `stderr=STDOUT` + 单线程读写，**抛弃 `tee` 与 `PIPESTATUS`** | 消掉嵌套引号与 `PIPESTATUS` 两类坑 |
| D9 | 会话脱离 | `Popen(start_new_session=True)` 取代 `setsid nohup` | 同语义，不 shell 出去 |
| D10 | SIGINT | **不碰信号**。python 默认收 `KeyboardInterrupt`，node 在同一前台进程组自然收 SIGINT；`except KeyboardInterrupt` 里等 child 收尾、打收尾信息、透传退出码 | ⚠️ **绝不能照抄 `trap '' INT`**：SIG_IGN 跨 `execve` 继承 ⇒ node 会对 Ctrl+C 完全免疫 ⇒ 把前台唯一的停止路径弄死 |

### 接口契约

| # | 决策点 | 定案 | 依据 |
|---|--------|------|------|
| D11 | 退出码 | 0 正常 / 1 前置拒绝 / 2 环境不干净 / 3 参数错误 / 4 找不到实例记录 —— **原样保留**；**argparse 默认的 2 必须改写成 3** | 与「环境不干净 = 2」撞车；停机卡与工具按这套码行事 |
| D13 | 帮助文本 | 模块 docstring + argparse，**不学 bash 自读文件头** | 规范禁止非 docstring 多行字符串；docstring 是唯一合法位置 |

### 配置与运行记录（新结构）

| # | 决策点 | 定案 | 依据 |
|---|--------|------|------|
| D15 | 配置载体 | **TOML**，三处统一（`当前配置.toml` / `版本信息说明/<V>.toml`）；用标准库 `tomllib` **只读** | ① 有**注释**（这文件的用途一半是记教训）；② 语义严格度与 JSON 同级（错的会报错，不会静默变形）；③ 只需一个标准库模块，零第三方依赖 |
| — | 谁写配置 | **人写、机读**。启动器永远不替人改配置文件；要「转正」只**打印**该改哪一行 | `tomllib` 只读、写需 `tomli-w`（未装）而系统里只有上游已弃用的 `toml 0.10.2`；且「谁写它 = 谁是唯一真相源」，`--try` 不碰配置这条今天是好设计，保留 |
| D16 | 记录目录名 | `YYYYMMDD.HHMMSS-PID<pid>`（本地时间，UTC+8 无 DST ⇒ 排序单调）；**指纹 `starttime`（jiffies）进 `instance.json`** | 挂钟名字**不可从 `/proc` 反验**（`uptime` 精度 + NTP 步进会让重算对不上）⇒ 它是**标签不是指纹**。人的可读性不该为机器反验让步，但指纹不能丢 |
| D17 | 归档 | **惰性对账**（启动第一步 + `--status` 时）：扫 `运行记录/`，`pid + starttime` 已死的移进 `历史/`。**对账在前，建目录在后** | 后台模式下 launcher 起完即退，**没人看着 host**；被 SIGKILL 的也来不及挂钩子 ⇒ 一个机制同时处理正常退出/崩溃/强杀/断电。「对账在前」同时也防跨 boot 同名覆盖 |
| D18 | 版本门 | **数据驱动**：声明在 `版本信息说明/<V>.toml`；**缺失即拒绝启动** | 修掉 `start-web.sh:365-369` 那个 🔴：`case "$DSH_VERSION" in v0.1.7-rc.2)` 对 0.2.0 **一个分支都不匹配 ⇒ 一条检查都不做**。数据驱动让「加版本 = 加数据」，并把「新版本必须先写下你知道的事」变成门 |
| D19 | 版本拼写 | 规范拼写 **`v0.2.0-rc.2`**（= 检出目录名 = `DSH_VERSION` 的值 = 上游 tag 剥掉 `dsh-`）；文件内记 `upstream.version` 与 `upstream.git_tag`，**启动时读检出 `package.json` 断言校验** | 见 §三·版本拼写的四种形态：**`v0.2.0-rc.2` 不是任何上游字节串**，所以「文件名 = 上游字节串」字面上做不到；改成「对应关系存进文件 + 启动时校验」，比要求逐字节相同**更强**（它能发现我们对不上） |
| D21 | 离线可读 | 启动器的配置与日志**必须在 DSH 停止、网络不可用时仍可读** ⇒ **不进 MariaDB** | 实证：守护日志里 [`09:55:23] ERR 连不上 MariaDB … (timed out)`]，而 MariaDB 在 Windows 侧、跨 WSL 边界、还要过那条每两分钟抖一次的网络。**把停机诊断的账本放进需要网络才能读的存储 = 在最需要它的那一刻它不可读。** 这是 `start-web.sh:476`「护栏自己是离线的……这一点是『敢拦』的前提」的自然延伸 |

### 相邻工具

| # | 决策点 | 定案 | 依据 |
|---|--------|------|------|
| D20 | `bin/dsh` | **python 重写**，shebang `/usr/bin/python3`，用 `tomllib` 读配置。必须原样保住三条语义：① **环境优先，文件仅作回落**（`:=` 语义，绝不覆盖调用方身份）② **刻意不做环境净化**（会话变量同实例内必须透传）③ **`os.execv` 而非 `subprocess.run`**（今天结尾是 `exec node`，替换进程；多一层进程会改掉 Ctrl+C / 退出码 / 信号语义）。缺省 home 改为**与启动器同一个派生式**，删掉 `dsh-domus-0.1.7-rc.2` | 用户定案「按 DSH_VERSION 走」；三条语义写在它自己的头注释里 |
| — | `bin/dsh-dryrun` | **退役**。`DRYRUN_VERSION` 默认停在 `v0.1.5-rc.2`，`DSH_HOME` 指向的 `dsh-domus-dryrun` **不存在**，全仓只有文档提到它，而 `--try` 早已取代其职能 | 实测确认死代码 |
| — | `tools/backup-dsh.sh:122` | 备份清单里的 `'./DSH_VERSION'` 改成新配置路径 | 删掉 `DSH_VERSION` 文件后那一项会悬空 |

---

## 三、新结构

```
~/deepseek-harness/启动器配置和日志/
├── 当前配置.toml                    ← 人写机读，唯一真相源（version/main_port/home_prefix/try_port_from）
├── 版本信息说明/
│   ├── v0.1.7-rc.2.toml
│   └── v0.2.0-rc.2.toml             ← 文件名 == 检出目录名 == DSH_VERSION 值
└── 运行记录/
    ├── 20261008.100747-PID1787794/  ← 活着的实例；"存在"即"活着"
    │   ├── instance.json            ← 身份 + starttime 指纹 + host_pid + launcher_pid
    │   ├── web.log                  ← host 输出（取代 _scratch/web-<端口>.log）
    │   ├── guards/                  ← 各道启动门的判定输出
    │   └── env-diff.txt             ← 净化掉了哪些【变量名】（不记值：净化前那份含 API key）
    └── 历史/                        ← 已死实例归档（不删：崩溃现场最需要留档）
```

**`.gitignore` 要精准**：只忽略 `启动器配置和日志/运行记录/` 这个**子目录**，
不要写「忽略 `.log`」——后者会漏掉里面的 `instance.json`。
（harness 的 git 是用户的备份系统；运行时产物不该占备份，而配置与版本知识该进备份。）

### 版本拼写的四种形态（实测）

| 拼写 | 出现在哪 | 是谁的字节串 |
|------|----------|--------------|
| `0.2.0-rc.2` | 检出 `package.json` 的 `version` | **上游权威版本号本体** |
| `dsh-v0.2.0-rc.2` | 检出 HEAD 上的 git tag | **上游权威 git 引用** |
| `v0.2.0-rc.2` | `原始代码研究/` 目录名 · `DSH_VERSION` 的值 | **我们的约定**（= tag 剥掉 `dsh-`） |
| `dsh-domus-0.2.0-rc.2` | home 目录名 | 我们的（前缀 + 剥掉 `v`） |

**不重命名检出目录**：home 的 `node_modules` 里有大量指回检出的**绝对 symlink**，
重命名会让它们全断 ⇒ `check-profile-links.py` FAIL ⇒ DSH 拒启动。
（既有教训：「清掉 `node_modules` 后该层 276 条链接成断链，DSH 直接砖」。）

---

## 四、行为契约（必须逐项等价）

1. **六个参数与语义**：`--try V` / `--version V` / `--port N` / `--stop` / `--status` / `--background`。
   `--try` 不读也不写配置；home 名与端口都按版本自动派生。
2. **派生链**：`HOME_NAME = "${HOME_PREFIX}-${DSH_VERSION#v}"` → `DSH_HOME_DIR = $SCRIPT_DIR/$HOME_NAME`
   → `CHECKOUT = $SCRIPT_DIR/原始代码研究/$DSH_VERSION` → `--try` 时端口从 `TRY_PORT_FROM` 起找空闲。
3. **`resolve_target` 的严格优先级**：`--port` → `--try/--version`（查记录，**查不到即报错退出 4，
   绝不回落到 `free_port()`**）→ 都不给则主实例。理由：回落正是旧的误杀源。
4. **`--stop` 阶梯**：`SIGTERM` → 最多等 20s → 升级 `SIGKILL` → 复验端口；仍占用则报错返回 1。
5. **「谁的儿子谁抱回家」**：后台模式连带收掉 launcher 包装进程（避免孤儿）；前台模式不这么做
   —— 那个进程正是持终端、把 SIGINT 转给同组 node 的角色。
6. **前台停止路径 = Ctrl+C**；后台（脱离终端）= `--stop`。前台 `--stop` 的行为按 D10/§三 的新语义定。
7. **启动门序列**（顺序不可换）：`0` 基座↔home 配套 → `1` 路径自检（不能读别的 home 的配置）
   → `2` 前置自检（检出存在 / 已构建 / 端口空闲）→ `3` 身份声明 → `3b` 环境净化 → `3c` 注入自家 preload
   → `3d` 放自家 `bin/` 进 PATH → `4` 代理守卫 → `5` cloudflared 兜底 → `6` 补丁层护栏
   → `6b` profile 链接护栏 → `7` 运维守护（幂等 flock）→ `8` 开跑。
8. **净化顺序的理由必须保留**：preload 与 `bin/` 的 PATH 注入**都在净化之后**——
   先注入等于白注入（会被 `dsh_env_sanitize` 剥掉）。

---

## 五、被实验推翻的两条（教训比结论值钱）

### 推翻一：实例级 venv 是真需求 —— 错

**原判断**：`start-web.sh:68` 的 `source ~/ai-services/bin/activate` 是「实例 venv 的唯一来源」，
去掉它整个实例的 python 环境就没了 ⇒ 新启动器必须**显式注入**（原 D4）。

**实测（2026-10-08，用户撤掉那句并重启后）**：

| 消费者 | 结果 | 机制 |
|--------|------|------|
| 7 个 MCP 服务 | **好的** | `/proc/<pid>/exe` = uv 的 3.12.13，各自 env 里 `VIRTUAL_ENV=~/ai-services` —— 因为 **`mcp-stdio.sh` 每个 python 分支自己 `source` 一次** |
| 启动器自己的护栏 | **好的** | `/usr/bin/python3`(3.14) 下实测跑得通 |
| `dsh-ops-daemon.sh` | **好的** | 它**确实**用裸 `python3`（两处）——唯一真正依赖那句的消费者；但活着的守护是 **pid 602**（`setsid` 活的 boot 时代进程，flock 让新守护退出），带着**撤除之前**的环境 |

**决定性反例**：`mcp-stdio.sh` 的 `papersearch` 分支用的是**另一个** venv
（`~/venv-mcp-papersearch`），理由是上游钉 `mcp[cli]>=1.8.0,<2` 而 ai-services 的 vllm 要 `mcp>=2.0.0`。
⇒ **一个实例级 venv 根本服务不了它。**

**结论**：那句 activate 从来不是「实例 venv 的注入机制」，它只是「**让裸 `python3` 指向 venv 3.12**」。
真正需要 venv 的消费者**各自带**。全局注入**既不足也不必要** ⇒ **D4 作废**。

**方法论**：我观测到的（`VIRTUAL_ENV` 在实例 env 里）是**对的**，
但我把「存在」读成了「必要」。**观测到的东西 ≠ 起作用的东西。**

### 推翻二：「两个 py 并存」是抑制器 —— 错

**原判断**：PATH 第一顺位是 uv venv 的 python3 是个隐患，要想法子压回去。

**实测**：三个 rc 文件里**都没有** activate，那句只在 `start-web.sh` 里。
⇒ 它其实是用户**刻意**塞的（「防止 dsh 你现在用啥找不到」），
作用面比我以为的窄得多（见推翻一）。

### 证据 C：为什么不能就地改 `start-web.sh`

实测进程链：`zsh(1739466) → bash ./start-web.sh(1735955) → node /usr/sbin/pnpm dsh web → node bin.ts web --port 9007`。
**bash 按字节偏移续读被执行的脚本** ⇒ 就地改写（同 inode、字节前移）
会让它从**新内容的中段**继续解析，而剩下那十几行里有 `forget_instance`、`tail -20 "$LOG"`、`exit "$rc"`。
2026-10-08 用户曾就地注释掉第 68 行（`-source` → `+#source`，**+1 字节**）并重启——这次侥幸没事，
但**机制上它是错的**，故 D14 定为原子 `mv` 替换。

---

## 六、待验收清单

- [ ] `--help` / `--status` / 参数错误的输出与 bash 版**逐项对拍**
- [ ] 净化器：合成脏环境喂 bash 版与 python 版，`env -0` **逐字节一致**
- [ ] 真机：停机窗口内用新启动器起 9007，验启动门序列、记录落位、对账归档
- [ ] 真机：前台 Ctrl+C 后收尾信息与退出码正确，记录被归档
- [ ] 真机：`--stop` 对后台实例的 TERM → 20s → KILL 阶梯
- [ ] `bin/dsh` 在「有环境身份」与「裸终端无身份」两种情形下解析正确
- [ ] 越界检查：`python3 tools/check-inode-sharing.py --isolate <A> <B>` 必须 0 越界

---

## 关键词

启动器 python 重写 · start-web.py · dsh_instance_env · 净化器移植 · 双实现对拍 oracle ·
启动器配置和日志 · 当前配置.toml · 版本信息说明 · 运行记录 · starttime 指纹 ·
惰性对账归档 · 数据驱动版本门 · 离线可读 · TOML 取代 YAML · Norway problem ·
bin/dsh python 化 · os.execv · SIG_IGN 跨 execve 继承 · shim 原子替换

## 近似入口点

- 「净化器怎么移植的」→ §二 D5 + §六对拍清单
- 「为什么不用 yaml」→ 本文未展开，见 `./启动器-配置载体-为什么不用yaml.md`（待写）；要点在 D15
- 「版本号为什么有这么多种写法」→ §三·版本拼写的四种形态
- 「为什么不进 MariaDB」→ §二 D21
- 「哪两条判断被推翻了」→ §五
- 「我该从哪里开始改」→ §一 工作包
