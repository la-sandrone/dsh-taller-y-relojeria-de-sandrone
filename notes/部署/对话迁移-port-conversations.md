# 对话迁移：0.1.7 → 0.2.0（`tools/port-conversations.py`）

文件名: 用户笔记/部署/对话迁移-port-conversations.md
摘要: 版本切换时把「对话」完整搬到新 home 的工具与作业流程。**含三条已实测踩过的坑。**
依赖: ../tools/port-conversations.py（正本）
      ../tools/check-inode-sharing.py（搬完复核隔离）
      ../tools/stage-upgrade-home.py（建 home 的那一步，取向须一致）

建档：2026-10-08

---

## 一、为什么需要它

0.2.0 的 home 是**从 0.1.7 复制**出来的（`stage-upgrade-home.py`）。但复制是**一次性**的：

- 之后 **0.1.7 还在跑**，一直往 `sessions/` **追加**写 ⟹ 新对话、新消息**只存在于 0.1.7**
- 0.2.0 建库时**刻意排除**了 `attachments/`（当成"隐私附件，试探实例不需要"）
- `session_projcache` 是**投影缓存**，只在"活会话"的几个时点写盘

⟹ 切到 0.2.0 之前必须做一次**完整的增量搬运**，否则：**新对话没有、老对话破图、全部「未命名」**。

## 二、搬四样东西（各有一个必须搬的理由）

| 项 | 体量（实测） | 不搬会怎样 |
|---|---|---|
| `sessions/` | 304 MB / 234 文件 | **对话本体没了**。每会话一个目录，内含 `session.v4.jsonl.zstd` |
| `attachments/` | **74 MB / 143 文件** | **历史对话里的图全成破图**。内容寻址 `v1/objects/<sha256[:2]>/<sha256>`，幂等，可重复搬 |
| `storages/session_projcache/` | 35 MB / 108 文件 | **界面全「未命名」**（2026-10-08 已实测踩过：109 个会话只有 3 个有条目） |
| `dsh-session-archive/` | 12 KB / 2 文件 | 归档会话消失 |

**不搬**（运行态，目标端自己长）：`cache/` `llm-deepseek/` `dsh-usage/` `task-board/`
`skin-center/` `pets/` `node_modules/` —— 与 `stage-upgrade-home.py` 的口径一致。

> **三号坑（本次新踩）**：`attachments/` 当初被当"隐私附件"排除，看起来无关紧要；
> 但它**是对话的一部分**——你在对话里贴的每张截图都住在那里。
> 0.2.0 侧实测 `attachments/` **0 文件** ⟹ 不搬，**整段对话的图全瞎**。

## 三、★ 铁律：双方必须**都离线**

**这是硬门。`--apply` 不过门即拒绝（exit 2）；干跑只读，允许带警告继续。**

为什么不是洁癖：

| 谁在线 | 后果 |
|---|---|
| **源端在线** | 它正在**追加**写 `session.v4.jsonl.zstd`。拷到一半是**撕裂的多帧 zstd**（最后一帧坏）——你以为搬全了，**症状是"最后一个会话打不开"，不是报错** |
| **目标端在线** | 它会同时往同一批文件写，两边互相覆盖 |

判据（只在 `/proc` 里找**会写 sessions 的那个 host**）：

```
/proc/<pid>/environ 的 DSH_HOME == 该 home
且 /proc/<pid>/cmdline 含 "bin.ts" 或 "dsh web"
```

> **为什么加 cmdline 过滤**：任何继承 `DSH_HOME` 的子进程（MCP 服务器、你从 DSH 终端起的 shell、
> 甚至**这个工具自己**）都带着那个变量。只按环境变量判会把它们全算作"在线"，
> 门就永远过不去。实测：加过滤后，它精准认出 9007 那条 `pnpm → pnpm-native → node` 三进程链，
> 而**我自己的 shell 被正确排除**。

**离线门自证**（2026-10-08，源端在线时）：

```
⛔ 离线门未通过——以下实例还在线：
    dsh-domus-0.1.7-rc.2  pid=1746142  node --import tsx/esm apps/cli/src/bin.ts web --port 9007 --no-open
    …（三进程链）
退出码=2
```

## 四、作业流程（版本切换）

```bash
# ① 停双方  —— 必须由【人】做：正在跑的那个 DSH 就是你自己的会话
```

**停法取决于它是前台还是后台**（`ps -o tty= -p <pid>`，有 tty 就是前台）：

| 跑法 | 停法 | 为什么 |
|---|---|---|
| **前台**（`TTY=pts/N`） | **在那个终端按 `Ctrl+C`** | launcher 自己写着：**「前台实例不要用 `--stop`（两条路径会打架）」** |
| **后台**（`--background`） | `./start-web.sh --version V --stop` 或 `--port N --stop` | 后台脱离了终端，只能靠记录停 |

```bash
# ② 离线门 + 差异清单（干跑，只读）
python3 tools/port-conversations.py

# ③ 执行（备份 + 原子复制 + 逐文件校验）
python3 tools/port-conversations.py --apply

# ④ 复核隔离 —— 确认真复制、没用硬链接把两棵树焊死
python3 tools/check-inode-sharing.py --isolate dsh-domus-0.2.0-rc.2 dsh-domus-0.1.7-rc.2

# ⑤ 起 0.2.0
./start-web.sh --try v0.2.0-rc.2
```

> **实测坑（2026-10-08）**：`--stop` 是**查 `_scratch/instances/<版本>.json` 所有权记录**的。
> 当时那个目录**是空的**（早先 `forget_instance` 用错变量删掉了 v0.1.7 的记录），
> 于是 `./start-web.sh --stop` 只会报「找不到运行记录」——**停不掉任何东西**。
> 停之前先 `ls _scratch/instances/` 确认；空的话就按上表走 Ctrl+C。

### ★ 推荐入口：`tools/cutover-0.2.0.sh`（独立脚本，一条命令全做完）

上面那五步是**手工**序列。日常更该用独立脚本：

```bash
cd ~/deepseek-harness
./tools/cutover-0.2.0.sh --dry-run     # 先看：谁在线、要搬什么（只读）
./tools/cutover-0.2.0.sh               # 走全套：停 → 搬 → 复核 → 报出启动命令
```

它做的事：① 侦察在线 host → ② 打印差异清单 → ③ **分级停实例**
（`SIGTERM` → 10s → `SIGINT` 到进程组 → 10s → `SIGKILL`，每级如实报告用的哪个）
→ ④ 调用 `port-conversations.py --apply` 搬 → ⑤ 跑隔离复核 → ⑥ 报出
`./start-web.sh --try v0.2.0-rc.2`（**不擅自拉起**，那一步留给人）。

`--dry-run` / `--no-stop` / `--yes` / `--from` / `--to` / `--force` 可用。

### ⛔ 已被证伪的做法：从 DSH 会话内起"守候进程"自动搬

初版我做过这个（`--wait-for-offline`）：

```bash
# ❌ 不要这样用：它在最需要它的那一刻已经死了
setsid nohup python3 tools/port-conversations.py --wait-for-offline --apply &
```

看起来防住了一切：`setsid`（自己一个会话：实测 `PGID=SID=自己的 pid`）、`nohup`、
stdin 接 `/dev/null`。**结果：用户关停 DSH 的那一刻，它也死了，一次都没搬成。**

证据（2026-10-08）：

| 标记 | 出现次数 |
|---|---|
| `⛔ 离线门未通过` | **305**（我的 `quiet` bug，每 2s 重打一遍 ⟹ 3051 行日志） |
| `⏳ 等双方离线` | 1 |
| **`✅ 双方已离线`** | **0** ⟹ 门一次都没通过，**搬运 0 次** |
| `Traceback` | 0 ⟹ 不是异常死的，**是被 kill 的** |

305 × 2s ≈ 610s，正好死在用户停 9007 的那一刻。

**机制**：`setsid` 挡得住"终端/会话"层面的信号，**挡不住 host 关停时按自己记录的
tool/后台 job 进程树逐个 kill**。它 `SID=PGID=自己` 也没用——那是**直接 kill pid**，
不是发给进程组。

**结论**：**职责是"关掉那个 DSH"的进程，绝不能寄生在那个 DSH 里。**
寄生 ⟹ 随执行者一起死 ⟹ 恰恰在最需要它的时刻失效。
这正是项目铁律点名的「假电源开关」。故本脚本第一件事就是**拒绝在 DSH 会话内运行**
（`DSH_HOME` 非空即退出 4）。

> `--wait-for-offline` 仍保留在 `port-conversations.py` 里，但**只在你自己的、
> 与 DSH 无关的终端里**才安全。默认路径请用 `cutover-0.2.0.sh`。

### 另一条教训：「查不出来」不许当成「都没在线」

脚本初版用 `hosts="$(python3 ... 2>/dev/null || true)"` 取在线清单。参数名写错
（用了 `--from/--to`，工具实际收 `--src/--dst`）⟹ python 报错退出 ⟹ `|| true`
把失败**吞成空字符串** ⟹ 脚本宣布「双方都不在线，可以直接搬」——**而 9007 当时正在跑**。

若没有 `--dry-run` 拦住，它就会从**正在写的源端**拷贝，产出撕裂的多帧 zstd，
而症状只是"最后一个会话打不开"（见第三节）。

**修法**：检测类调用的失败一律**中止**；实现上不用命令替换
（子 shell 里的 `exit` 传不出来，失败照样被吞），改用临时文件 + 在**当前 shell** 里判退出码。


## 五、安全设计

| 机制 | 做法 |
|---|---|
| **默认干跑** | 只有 `--apply` 才写文件 |
| **覆盖前备份** | 被覆盖的原文件进 `backups/port-conversations-<stamp>/<相对路径>` |
| **可回滚** | `python3 tools/port-conversations.py --restore <备份目录>` |
| **不删目标端独有** | 只列出来交人判断（如 trial 自己建的会话） |
| **原子替换** | 每文件先写 `.port-tmp` 再 `os.replace`，中途断了不留半截 |
| **逐文件校验** | 搬完比对 sha256，不一致即失败并给回滚命令 |
| **真复制** | 用 `shutil.copy2`，**不用硬链接**——见下 |

### 为什么绝不能用硬链接

本项目「跨版本隔离」纪律：**包字节**（`node_modules/` 内、内容寻址）共享 inode 是**预期**的；
但**非包字节**一旦跨树共享 inode，就等于**把两棵树焊死**——你改 A，运行时读 B。

**会话是会被编辑的数据** ⟹ 必须真复制。搬完跑 `check-inode-sharing.py` 复核，**必须 0 越界**。

## 六、本次作业记录（2026-10-08，0.1.7 → 0.2.0）

干跑结果：

```
sessions                     新增 0   更新 5     ← staging 之后又被写过的
attachments                  新增 143 更新 0     ← 全部图片（0.2.0 侧原本 0 个）
storages/session_projcache   新增 0   更新 5     ← 对应标题
dsh-session-archive          新增 0   更新 1
合计：待搬 154 个（新增 143 / 更新 11）｜ 已一致 333 个
目标端独有 9 个（trial 实例自己建的，含 session.lock，不删）
```

5 个待更新会话：

| 大小 | mtime | 会话 |
|---|---|---|
| 0.96 MB | 00:43:45 | `session-134d5c47…` |
| **4.00 MB** | **08:06:33** | **`session-954fba6f…`（本次作业的那段对话，仍在写）** |
| 0.91 MB | 00:50:17 | `session-aeec91b3…` |
| 2.67 MB | 19:37:12 | `session-da675069…` |
| 3.13 MB | 02:18:39 | `session-521aa319…` |

## 七、已知边界

1. **不处理"目标端独有"的文件**——只报不删。若有该删的，人工确认后再动。
2. **不做冲突合并**：同名文件以**源端为准**（覆盖前备份）。因为目标端是"旧副本 + trial 自建"，
   源端才是权威。
3. **`attachments/` 是全量搬**（74 MB），不做"只搬被引用的对象"的精细裁剪——
   内容寻址 + 幂等，重复搬零成本，精细裁剪反而引入"漏引用"的风险。
4. **`session.lock` 会跟着搬**：它是 `flock` 租约，**锁状态在内核里不在文件里**，
   复制文件是安全的；0.2.0 的实例起来会自己重新持锁。
