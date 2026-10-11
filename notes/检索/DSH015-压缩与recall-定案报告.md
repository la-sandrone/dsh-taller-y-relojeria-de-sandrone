# DSH015 压缩 / 回忆 —— 定案报告

> 日期：2026-09-12 ｜ 基座：`v0.1.5-rc.2` ｜ 范围：对话自动压缩、被压内容的找回、相关工具与配置
> 本报告**取代**同日早先那份《DSH015-压缩与recall-勘察报告.md》的结论部分（那份的过程记录仍有效，但有三处结论已订正，见 §7）。

---

## 0. 一句话

**「找回被压掉的内容」技术上完全可行，但可用的路只有一条，而且不是官方全文检索那条**——官方 `session_event_search` 的 FTS5 用硬编码的 `unicode61` 分词器，把整句中文当一个 token，对中文语料**结构性不可用**；真正能用的闭环是「**scan 给指针 → 官方按 seq 核实与取原文**」。

---

## 1. 今日定案（三条硬结论）

### 1.1 两次「无声死机」的根因 = 两层配置撞 entry id

```
$DSH_HOME/cordis.patch.yml          ┐ 内容相同（复制/硬链接而来）
$DSH_HOME/profiles/web/cordis.patch.yml ┘
        ↓ 同一批 entry id 被定义两次
TypeError: duplicate loader entry id: mcp-filesystem
        ↓ 若撞在【热加载】路径上（而非启动）
插件树留在半套状态 → sessionController 永不激活
        ↓ sessionController 的 static inject 含 sessionQuery
task-board 轮询 session/list 取不到 receiver
        ↓
sessionController is unavailable 无限刷 + 前台假死（无任何预警）
```

**证据链**：
- 影子实例**受控实验**：同一份配置，**两层崩 / 一层好**
- 崩溃时报错**点名** `duplicate loader entry id: mcp-filesystem`（正是 insert 列表第一个 id）
- 当事人自己"注释掉 insert 就好了"——因为那同时消掉了重复
- 配置改回后，**热加载干净生效**（新增 5 个工具、消失 0）→ 反证热加载路径本身没问题

**为什么"没有预警"**：`sessionController` 是 cordis `Service`，10 个注入不齐就**凭空不存在**，不报错；gateway 的 `receiverContext.get(...)` 取不到是**正常代码分支**（运行时抛 RPC 错误）。从 DSH 视角看**什么都没加载失败**。

**规矩**：同一批 entry id **只允许在一层定义**。改任何 `cordis.patch.yml` 前先跑护栏
`python3 tools/check_patch_layers.py --profile web`（`--dump-config` **抓不到**这个重复）。

### 1.2 官方全文检索对中文**结构性不可用**（分词器决定）

官方 `session_event_search` 底层 FTS5：`tokenize = 'unicode61'`（`session-query-sqlite/src/schema.ts:127,158`）。

**离线实测**（完全复刻该定义）：

```
文档：「从如下文件恢复对话上下文，新文件覆盖旧文件。莱杜拉的回忆是这次的核心设定。」
实际 token： '从如下文件恢复对话上下文'(12字) / '新文件覆盖旧文件'(8字) / '莱杜拉的回忆是这次的核心设定'(14字)
              ↑ 到标点为止的【整句】= 一个 token

MATCH '莱杜拉的回忆'  → 0 条   ← 连原文完整子串都命中不了
MATCH '莱杜拉'        → 0 条
MATCH '回忆'          → 0 条
MATCH '莱杜拉的回忆是这次的核心设定'（整段原样） → ✅ 1 条
[英文] MATCH 'shadowedSeqs' / 'shadowed' / 'seq' → ✅ 均能子串命中
```

**结论**：中文只能整段原样匹配；英文与代码标识符正常。
**改 `openAt` / `first-search` / 阈值全都没用**——这是分词器层面的硬约束。

**对照**：MariaDB 有真 Unicode 排序规则（`utf8mb4_uca1400_ai_ci`），比 FTS5 的 `unicode61` 强；
但 **`WITH PARSER ngram` 是 MySQL 的内建解析器，MariaDB 上不存在**
（本报告初稿写成「你已在用 ngram」是错的，2026-09-12 订正——正是自己铁律里那条"别把 MySQL 的语法平移到 MariaDB"）。
**Windows 侧的实际做法是：入库前用 `jieba` 分词**——分词权握在自己手里。
这是官方 FTS 结构上补不上的能力缺口。

### 1.3 可用的闭环：基于 **seq**，不经过分词

```
① 拿候选 —— scan（字面子串匹配，中文安全）
     · compaction 报告：次数 / 时间 / turn / 遮蔽条数 / token 数 / 摘要全文
                        + 「被遮蔽 seq（日志自报、未核实）」作为回查指针
     · debug="keywords"：挖出「只在被压区出现、当前表层已看不到」的候选词
② 核实   —— session_event_trace(session_id, seq)   → shadowed / current + 替换链
③ 取原文 —— session_event_read(session_id, seq)     → 完整未删节原文
```

**三条都不经过分词，中文无碍。**

⚠️ **read 的硬限制**：返回的是**整条原始事件**（含 `stream` 逐 token 数组），且**没有裁剪参数**。
实测：`seq=11`(小事件) = **1,453 字节**；`seq=902`(assistant/message) = **15,326 字节**，**10.5 倍**。
→ 定向读前必须先估规模。**scan 有 48KB 预算闸门 + 折叠提示，比 read 更能控住输出量。**

---

## 2. 决策落地状态（2026-09-12 批复）

| # | 决策 | 状态 |
|---|---|---|
| D1 | recall 返回「摘要 + 遮蔽 seq 指针 + 按需展开」 | ✅ 已实现（scan 输出「被遮蔽 seq」） |
| D2 | recall 形态 | ✅ **已定并落地：新 MCP `session-recall`**。原本打算写 TS 进程内插件（E1），但**暴力法不需要 `ctx`**——于是降级为"新开一个 MCP"，成本与风险各降一个数量级。3 个工具：`recall_search`（中文全文检索）/ `recall_fetch`（带裁剪取证）/ `recall_compactions`（压缩点清单） |
| D3 | 挂 `tool-session-query` + 开 `session-query-sqlite` | ⚠️ 工具**已上现役**（包名挂载）；**索引未上现役**（收益被分词器吃掉） |
| D4 | 摘要标注「有损摘要，可能失真」 | ✅ 已实现（完整版 + 降级版都有） |
| D5 | 索引+摘要优先，原文按需展开 | ✅ 已实现，且有硬数据支撑（read 15KB/条） |
| D6 | 不动 `compaction-basic` 阈值 | ✅ 未动（理由：自动压缩粗暴但有效地治 context rot） |
| D7 | 保留 tool-result-pruner | ✅ 未动 |
| D8 | 不装第三方记忆插件 | ✅ 未装 |
| D9 | 暂不做「结构化笔记」层 | ✅ 暂缓 |
| D10 | `fast_filesystem` 排除 `stream` | ✅ 已提交 `8e6d8a1`（v3 省 10.5%，索引块省 34%；v0 无效） |
| D11 | `fast_filesystem` 支持 `.jsonl.zstd` 直读 | ✅ 已提交 |
| D12 | preset 里 `recall_compactions` 悬挂引用 | ✅ **已完成**（5 个 preset 0 残留，见 §5） |
| D13 | 清理 + 订正 | ✅ 见 §7 |

---

## 3. 产出物

### 3.1 工具（`deepseek-harness/tools/`）

| 文件 | 用途 |
|---|---|
| `check_patch_layers.py` | **护栏**：改配置前预检「重复 entry id」。支持 `--extra` 试算候选文件。能吃到 `!!js` 标签 |
| `list_tools.py` | **查某工具在不在**：读会话日志里 `request/header` 的**事实**。`--grep` / `--diff` / `--session` |
| `session_tool_audit.py` | 审计某会话的工具调用原始证据（参数/返回大小/错误） |
| `session_index_survey.py` | 索引成本测绘（30 会话/49MB ≈ 4s），给进度分母 |
| `watch_index.py` | 索引建库实时看板 + 卡死检测（靠 WAL 增长与 CPU；**注意沙箱里 `ps` 看不到宿主进程**） |
| `verify_shadowed.py` | 用 foldSurface 语义独立判定某 seq 是否已离开表层 |
| `dsh-stop.sh` | 停机助手（ss→fuser→lsof→pgrep 四级回退） |
| `switch_live_pkgname.py` | 把挂载从绝对路径改为包名（带锚点断言 + 备份 + 原子替换） |
| `fix_preset_recall_prompts.py` | D12：改 5 个 preset 的回忆指引段（结构定位 + sha 校验） |
| `apply_patches_ffs{1,2,3}.py` | `fast_filesystem.py` 的三批补丁记录 |
| `brute_recall.py` | 暴力检索原型 + 计时（证明 3.0s 扫完 50MB 可行） |
| `mcp_smoke.py` | **MCP 协议层冒烟**：真起 stdio server 走 initialize/list_tools/call。改完 MCP 先在这里验通，再去动配置 |

### 3.1b 新 MCP：`session-recall`（`<挂载d>:/DataServices/MCP/wrap/mcp_session_recall.py`）

独立 MCP server（**不塞进 `fast_filesystem.py`**——它已 2687 行）。`mcp-stdio.sh` 的 `recall` 分支现指向它。

| 工具 | 能力 | 关键点 |
|---|---|---|
| `recall_search` | 会话语料**字面子串**全文检索 | **中文可用**（FTS 恒 0 条）；jieba **只切查询**、语料侧永远子串匹配（`乌兹别克` 命中 `乌兹别克斯坦`）；支持 `mode=all/any`、`session_id`、`types`、`shadowed_only`；每条命中给 行号/`seq`/类型/**★是否被压区** |
| `recall_fetch` | 按 `(session_id, seq)` 取原文 | **默认排除 `stream` 并限长**——官方 `read` 两件都做不到（实测同一条 15,326B vs 本工具 300 字符） |
| `recall_compactions` | 压缩点清单 | turn/遮蔽条数/token/模型 + **被遮蔽 seq 指针** + 摘要（默认开头，`full=true` 给全文） |

**实测**：扫 31 个会话 / 50.5MB / **0.9 秒**（`zstandard` 进程内解压；`zstdcat` 版是 3.0s）。
**协议层**：`initialize` / `tools/list`(3) / `tools/call`×3 全通（`tools/mcp_smoke.py`）。

**两个坑**（已解决）：① 会话日志是**多帧** zstd，`decompress()` 报 "could not determine content size in frame header"，必须用 `stream_reader()`；② 非命中行**不做 JSON 解析**——这是 3 秒扫完 50MB 的关键。

### 3.2 文档

| 文件 | 内容 |
|---|---|
| `DSH停机卡.md` | **离线**停机/回滚卡：三级处置 + 回滚点清单 + 血泪坑 |
| `DSH015-压缩与recall-勘察报告.md` | 早先的勘察过程记录（结论部分见本报告 §7 订正） |
| `TXX-压缩找回测试prompt集.md` | 测试 prompt 集（含 T7 / 判读表 / 回滚） |
| `context-compaction-survey.md` | 文献与实践调研（10 产品 + 反方意见 + 未能核实项） |

### 3.3 现役配置变更

| 变更 | 内容 |
|---|---|
| `profiles/web/cordis.patch.yml` | `tool-session-query` 挂载由**绝对路径**改为**包名** `@deepseek-ai/dsh-tool-session-query` |
| `profiles/web/package.json` | 新增依赖 `@deepseek-ai/dsh-tool-session-query: 0.1.5-rc.2`（正统安装，升级不失效） |

---

## 4. 下一步方向：MariaDB 挂件（2026-09-12 用户拍板，以后做）

**决定**：做一个挂件，**把对话记录直接同步进 MariaDB**，检索走 MariaDB 而不是 DSH 自带的 FTS。

**为什么这条路对**：中文分词权**回到自己手里**——入库前 `jieba` 分词，存一份分词副本供检索，
不受 `unicode61`（官方）也没得可用的 ngram（MariaDB 无此解析器）制约。
且有先例：`scratchpad_db.draftpad` 已经是这套模式（MariaDB 当权威账本）。

**已识别的设计要点（动手前先过一遍）**：

| 要点 | 取向 | 理由 |
|---|---|---|
| 数据源 | **优先 `ctx.sessionQuery.readSession()`（插件内）**，其次 `session.v*.jsonl.zstd` 直读 | 前者省掉 zstd 解压 + v0→v3 迁移的坑；后者要自己处理多帧与格式代 |
| 主键 | **`(session_id, seq)`** | seq 是天然的单调事件号，天然幂等 |
| 增量水位 | 每会话 `max(seq)` 作 watermark | 只追加不修改，增量同步最省 |
| 分词 | 入库时 jieba → 存一列分词副本 | 检索列与原文列分离，检索不影响原文保真 |
| 表结构 | 参考 `draftpad` 的既有约定（`session_id` / `deleted_at IS NULL` / `created_at`） | 沿用已有习惯，别再起平行宇宙 |
| 迁移 | 历史 jsonl 一次性灌入 | 与增量同步共用同一入口，避免两套写路径 |
| 与 scan 的关系 | **互补**：scan 管"文件形态的历史导出"，MariaDB 管"在跑会话的持续同步" | 两者都按 `(session_id, seq)` 对齐，不冲突 |

**在它落地之前**，现役可用的仍是 §1.3 的 seq 闭环（scan 指针 → trace 核实 → read 取证）。

---

## 5. D12 已执行（2026-09-12 完成，含验证）

```bash
python3 tools/fix_preset_recall_prompts.py --apply
python3 tools/check_patch_layers.py --profile web
```

改法要点：把「调 recall_compactions…」段（5 个 preset 完全相同，sha 已校验）换成
**① 官方检索对中文不可用的警告 + ② 基于 seq 的两条可用路径**（trace 核实 / read 取证 / scan 给指针）。

**执行后核实**：

| 项 | 结果 |
|---|---|
| 5 个 preset 的 `recall_compaction` 残留 | **全部 0** |
| 备份 | 5 份 `agent.cordis.yml.bak-d12-*`（⚠️ 已于 2026-10-07 清退，见下） |
| 护栏（profile 层） | ✅ 无重复 id |
| 9007 监听 | ✅ 1 条 |
| 新工具在活会话中可用 | ✅（`session_event_trace` 实测调用成功） |

**无待执行项。**

> **⚠ 2026-10-07 更新：`.bak-d12-*` 这族快照已清退。** 当日共清退 163 个残件；
> 这一族 10 个里 **5 个内容仍在 git 对象库**（可用
> `git -C <home> log --all -- <对应活文件路径>` 找回），**5 个 git 里没有**，
> 已收进 `backups/residue-git-unrecoverable-20261007-230429.tar.zst`。
> 详见 `DSH停机卡.md` 的「残件清退」小节。

---

## 6. 遗留与未决

| # | 事项 | 说明 |
|---|---|---|
| L1 | **影子索引为空**（`persisted_docs=0`） | 独立问题，**未查清**。是"影子配方（掏空 `storages/`）的副作用"还是"冷读路径缺陷"，需一个探针分辨。当前不影响主结论（有索引中文也匹配不上） |
| L2 | **E1（进程内插件）未开工** | 关键发现：宿主 seam `ctx.sessionQuery.filterEvents` 走的是**字面量正则扫描、与 FTS 提供方无关** → **中文可用、且不需要索引**。这是官方工具结构上做不到、而插件能做到的能力 |
| L3 | 更早遗留：「recall 修复 A–F」细目 | 仍在 `DSH 0.1.1 到 0.1.5 升级.jsonl` 被压缩的前半段，未回查 |
| L4 | `dsh-domus/cordis.patch.yml`（home 级）来历 | 当事人也记不清，疑为旧版差异。**已删**（现役只余 profile 一层 → 安全）。规矩已立：单层定义 |
| L5 | 那次 `session-32d3f9ef` 测试会话 | 已用 `session_tool_audit.py` 复核，T1/T3/T4/T5 为同一错误四个副本，T2/T6/T7 通过 |

---

## 7. 订正（含对本报告初稿的自我订正）

| 早先说法 | 订正为 | 依据 |
|---|---|---|
| 「curl export 本机免认证 200」 | **0.1.5 上返回 401** | 0.1.5 新增 `browser-auth.ts`（0.1.1 无此文件），`/api/*` 全部走认证 |
| 「官方工具能按关键词找回被压原文」 | **仅限拉丁文/标识符；中文结构性不可用** | `unicode61` 分词器离线实测 |
| **（本报告初稿）「MariaDB 用 `WITH PARSER ngram`」** | **`ngram` 是 MySQL 内建解析器，MariaDB 没有**；Windows 侧实际做法是**入库前 `jieba` 分词** | 用户指出；且违反了自己铁律里"别把 MySQL 语法平移到 MariaDB"那条 |
| 「packChunks 打包单行仍可逐行 json.loads」 | 那是 v1/v2 物理解码器概念，**v3 一行一事件**，不构成本次问题 | 活会话实测 + 迁移文档 |
| auto-memory 的 `lib/index.js` 是「编译产物」 | **手写 ESM，8163 行**（无 TS、无构建） | 源码直读 |
| auto-memory「0.75 压在宿主 0.80 之下，属实」 | **分母被减了 reserve，实测在声明窗口的 47.5% 触发，早触发约 45%**；且 v2.4.2 出厂 `handoffEnabled:false` | 源码 `lib/index.js:1904,1947,254` |
| `shadowedRange` 可当 seq 区间用 | 它是 **surface 位置跨度**（`start` 可 > `end`，实测 `400..238`）；权威集合是 `shadowedSeqs`，而后者**是日志自报、未核实**（与 fold 重放互不包含） | 官方 types.ts + 6 会话实测 |

---

## 8. 三条可直接抄的运维规矩

1. **同一批 entry id 只允许一层定义**；改 `cordis.patch.yml` 前先跑 `check_patch_layers.py`。
   *`--dump-config` 抓不到重复，别拿它当护栏。*
2. **`cordis.patch.yml` 是热加载的**——保存即生效，**没有"先存盘再挑时间重启"这个缓冲**。
   编辑它就是一次线上变更。**改完立刻看 UI**；出事第一反应是**还原配置**（L1，通常够），不是停机。
3. **`bin/dsh` 硬编码 `DSH_HOME`** —— 起影子实例**不能**用它，否则两实例共用一个 home 互相踩。
   要直调 CLI 入口并预先 `export DSH_HOME`。
