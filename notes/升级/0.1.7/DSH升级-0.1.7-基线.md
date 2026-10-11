# DSH 0.1.7-rc.2 升级 · 阶段 1 基线（冻结点）

> **用途**：切换后逐条对拍。**每一条都要么有确定的可测数值，要么明确标"待浏览器侧采集"。**
> **冻结时间**：2026-09-26 11:0x（+08）
> **生成方式**：全部为本次实测读数，非回忆、非推断。

---

## 一、冻结点

| 对象 | 冻结手段 | 标识 |
|---|---|---|
| `dsh-domus` 配置 | 本地 git 提交 | **`fa4bca5`**（"freeze: 0.1.7-rc.2 升级前的原始状态基线"） |
| 上一条可回滚点 | 本地 git | `9cc2e57`（2026-09-19 首次入库时的干净状态） |
| 全量备份 | <D盘>:\ 压缩包 | `<挂载d>:/dsh-full-20260926-100908.tar.zst`（600,086,309 B） |
| 备份完整性 | `zstd -t` 实测 | ✅ 通过，解压后 1,039,421,440 B |
| 基座检出 | git tag | `原始代码研究/v0.1.5-rc.2` = `fb2c4b9` + 本地补丁 `19217dd` |
| 目标检出 | git tag | `原始代码研究/v0.1.7-rc.2` = `477b4f4`（**未安装、未构建**） |

`dsh-domus/.gitignore` 本次新增 `cache/`（约 1.4 GB 索引库）与 `.env`，二者确认已被忽略。

---

## 二、版本与工具链

```
DSH_VERSION = v0.1.5-rc.2          （唯一收敛点：start-web.sh + bin/dsh 共用）
node        = v26.8.2
pnpm        = 12.4.1
```

---

## 三、会话基线（升级后必须能全量恢复）

| 项 | 数值 |
|---|---|
| 会话日志文件总数 | **70** |
| ├ `session.v3.jsonl.zstd` | **50** |
| └ `session.jsonl.zstd`（格式 v0，0.1.1 时代） | **20** |
| 工作区目录 | 13 个 + 4 个子会话目录 |
| **会话头 `agentPreset`** | **70 / 70 全部为 `"coding"`** ⚠️ |

> ⚠️ **本次升级最大单点**：0.1.7 移除了目录预设读取，`agent-preset-registry.resolve()`
> 对未知 id 抛 `agent-preset/not-found`。
> **不在 profile 里声明 `coding`，这 70 份一份都打不开。**
>
> 分布（按工作区，v3 文件数）：
> `~/deepseek-harness` 18 · `<D盘>:\...\冰质星球与是啊，吃什么` 13 · `mcp-draftpaper` 3 ·
> `venv-mineru` 3 · `<D盘>:\...\Documents` 2 · `memoria-del-hielo` 2 · 视频文件语音识别转录 2 ·
> 简历 1 · `MCP/wrap` 1 · `ai-services` 1

---

## 四、工具清单基线（事实层：读会话日志的 `request/header`）

来源：`python3 tools/list_tools.py`（读 `session-97fd36b3` 最后一次 request/header，2026-09-26 11:01:40）

**工具总数 182，来源 14 个。**

| 来源 | 工具数 |
|---|---|
| `mcp:papersearch` | 57 |
| 内置 | 38 |
| `mcp:github` | 26 |
| `mcp:filesystem` | 13 |
| `mcp:mcp-entropia` | 13 |
| `mcp:melquiades` | 10 |
| `mcp:mcp-memoria` | 7 |
| `mcp:mcp-localgit` | 6 |
| `mcp:mcp_eqsolve` | 6 |
| `mcp:bingcn` | 2 |
| `mcp:cloakbrowser` | 1 |
| `mcp:mcp-calculator` | 1 |
| `mcp:mcp-time` | 1 |
| `mcp:mcp_pysyntaxcheck` | 1 |

**MCP 挂载条目 13 条**（`profiles/web/cordis.patch.yml`）：
`mcp-filesystem` `mcp-papersearch` `mcp-bingcn` `mcp-cloakbrowser` `mcp-time`
`mcp-localgit` `mcp-eqsolve` `mcp-pysyntaxcheck` `mcp-entropia` `mcp-calculator`
`mcp-memoria` `mcp-github` `melquiades`

> 切换后对拍命令：`python3 tools/list_tools.py`（比对总数与逐来源计数）
> 与 `python3 tools/list_tools.py --diff`（新旧会话增减）。

**插件 bundle 12 条**：
`@deepseek-ai/dsh-base` `@deepseek-ai/dsh-web-app` `@linxin666/dsh-web-all`
`dsh-suigintou-ui-patches` `@changfenhuang/dsh-annotation` `dsh-session-insights`
`dsh-context` `dsh-deepread` `@linxin666/dsh-client-ui-session-id`
`dsh-fulltext-search` `dsh-better-sidebar` `dsh-search-plus`

---

## 五、防护链状态（三条铁律的现状）

| 项 | 现值 | 说明 |
|---|---|---|
| `tools/h1-mode` | `on` | 臂开关文件在位 |
| `force-h1 applied` | ✅ **true**（2026-09-26 03:02，`resolvedFrom` 指向 v0.1.5 检出的 http-proxy） | **切换后必须重新核对**（铁律 2 第②条） |
| 飞行记录仪 | 运行中（`_scratch/fetch-trace.log`） | 有 `force-h1` / heartbeat 事件 |
| `.env` 代理守卫 | ✅ 生效（`dsh-domus/.env` 仅 1 字节空行） | `start-web.sh` 启动期拦截 |
| ✅ 运维守护 | **已修（2026-09-26 11:06）**：见第九节 | 修前摄取静默死了约 5.5 小时、日志被刷 11487 行 |

---

## 六、皮肤锚点（⚠️ 待浏览器侧采集）

本次无法在无浏览器环境下取数。**切换后按 `DSH皮肤锚点对照表.md` 的 8 话题锚点逐项复核**，
并把实测计数写回本节。

关键前提（该文档已定案，重申）：
- `data-dsh-surface` / `data-dsh-part` / `data-dsh-frame` / `data-dsh-skin-layer` /
  `data-dsh-skin` / `data-dsh-plugin` 的**生产者是 `@linxin666/dsh-client-ui-skin-center`**，不是 dsh 核心
- `data-ds-dark-theme` 才是 dsh 核心（`ui-layout/theme-presenter` 打在 `<body>`）
- **→ 皮肤锚点的命运押在 `dsh-web-all` + `skin-center` 上**

---

## 七、已知未决（升级前后都在册）

| # | 事项 | 状态 |
|---|---|---|
| 1 | 用户气泡 Markdown 补丁在 0.1.7 需重打（`projectUserText` 3 参 → 5 参，须转发 `references`） | 阶段 3 做 |
| 2 | `agent-presets` 目录预设 → `dsh-agent-preset` 声明（6 个 id 逐字保持） | 阶段 3 做 |
| 3 | `settings.yaml` 11 节 → profile patch 手工转换（**不赌官方一次性导入**） | 阶段 3 做 |
| 4 | `@deepseek-ai/dsh-tool-session-query` 0.1.5-rc.2 → 0.1.7-rc.2 | 阶段 3 做 |
| 5 | 建议新增「ui-chat 补丁漂移护栏」（源码标记 + 构建产物双向校验） | 阶段 3 做 |
| 6 | ~~`wrap/mcp_recall.py` / `wrap/mcp_session_recall.py` 无引用~~ | ✅ **2026-09-26 已移入 `wrap/废弃/`**（`git mv`，历史保留、可一键取回） |
| 7 | ~~`cordis.patch.yml` 尾部注释掉的 `mcp-tavily`（含明文 key）+ 缺尾换行~~ | ✅ **2026-09-26 已裁**（`b9badc8`） |
| 8 | ~~ops-daemon 的 `mcp-draftpaper/config.yaml` 缺失~~ | ✅ **2026-09-26 已修**（见第九节） |
| 9 | ~~`~/deepseek-harness` 没有 git 仓库~~ | ✅ **2026-09-26 已建**（见第十节）：`7d6c4e0` |
| 10 | ~~`_scratch/` 产出物没进版本控制~~ | ✅ **2026-09-26 已放行**（`3119a36`，见第十一节） |
| 11 | ~~`_scratch/watch_status.py` 是 ops-daemon 的活依赖却无版本控制~~ | ✅ **2026-09-26 已放行**（`85fe556`，见第十三节） |
| 12 | ~~`_scratch/*.mjs` 未放行；`_scratch/dsh-fetch-trace.mjs` 是 `tools/` 版的陈旧副本~~ | ✅ **2026-09-26 已清理**（`49e76f9`，见第十七节） |
| 13 | ~~`wrap` 仓库同病：只跟踪 6 个文件，`mcp-stdio.sh`（**所有 MCP 的启动器**）改动未提交，20+ live 脚本未跟踪~~ | ✅ **2026-09-26 已补**（`759c07a`，见第十四节） |
| 14 | **阶段 2 离线预演**（构建 + dump entry id）——用户自跑 | 📋 指引见 `DSH升级-0.1.7-阶段2-自跑指引.md` |

---

## 八、阶段 1 结论

- ✅ 配置冻结点建立（`fa4bca5`），且**未污染**——迁移改动将落在独立提交里
- ✅ 备份完整性实测通过
- ✅ 会话 / 工具 / 插件 / 防护链四项基线已落数
- ✅ 运维守护已修复（见下）
- ⏳ 皮肤锚点待浏览器侧采集

---

## 九、附带修复：运维守护（2026-09-26 11:06）

**根因**：`tools/rename-to-melquiades.py` 的扫描根只覆盖 `<挂载d>:/DataServices/MCP`，
**漏了 `~/deepseek-harness`**。于是 `tools/dsh-trace-ingest.py` 的
`DEFAULT_CONFIG` 仍指向已不存在的 `<挂载d>:/DataServices/MCP/mcp-draftpaper/config.yaml`。

**后果（实测）**：
- 摄取静默失效约 **5.5 小时**（自 09-26 05:40 改名起），`ops-daemon.log` 被刷成 **11,487 行**、其中 **1,005 次** `FileNotFoundError`
- 每 20 秒一轮的 4 行 traceback **把真信号埋了**——这正是升级后判断 H1 是否生效时要看的那块日志
- 哨兵与状态快照未受影响（它们不读配置），故障期间仍在工作

**修复三处**：
1. `tools/dsh-trace-ingest.py`：`DEFAULT_CONFIG` → `<挂载d>:/DataServices/MCP/melquiades/config.yaml`，并加注释警示"改名必须同时扫两个根"
2. 同文件：缺配置时改为**一行** `ERR 读不到 config（…）`（原为 4 行 raw traceback）
3. `tools/dsh-ops-daemon.sh`：输出**去重**——内容变了立刻打印、没变只计数、每 15 轮（约 5 分钟）报一条"仍在重复"。这是降噪不是静默：错误始终可见

**验证**：
- 手动补齐积压 738 行（游标 3025 → 3763）
- 守护重启后 70 秒内仅 4 行输出，游标持续推进（3769 → 3780）
- MariaDB 实测：`test_db.dsh_transport_log` **3,755 行**，最新事件 `03:07:16Z`（= 本机 11:07）——**数据确在实时落库**

**回滚点**：改动前的两个脚本都在备份 `<挂载d>:/dsh-full-20260926-100908.tar.zst` 里（已实测可列出）。
旧日志归档为 `_scratch/ops-daemon.log.preconfigfix-20260926-110556`。

---

## 十、附带：为 harness 根目录建本地 git 安全网（2026-09-26 11:09）

**动机**：第九节那起事故暴露——`tools/` 下的全部运维脚本（升级铁律 / `dsh-force-h1.mjs` /
ops-daemon / 转录器 / 探针）**当时没有任何版本控制**，改动前后只能靠 tar 兜底。

**成果**：`git init` 完成，首次入库 **87 文件 / 1.1 MB**（`7d6c4e0`），
随后漏网清扫（`ccdbc29`）。工作区干净。

**`.gitignore` 设计**（与 `dsh-domus` 同调：收手写脚本与文档，排检出/依赖/大数据/凭据/可重建）：

| 排除 | 理由 |
|---|---|
| `原始代码研究/`(2.2G) `插件源码/`(375M) `dsh-domus-probe/`(479M) | 完整检出，各自内含 `.git` |
| `dsh-domus/`(2.1G) | **自带 `.git`**，有自己的安全网，绝不嵌套 |
| `_scratch/` | 含 `trace-db.cnf`(600) 与持续增长的 `fetch-trace.log` |
| `backups/` `session-backups/` `lost+found/` `.pnpm-store/` | 备份件与依赖缓存 |
| `tools/cloudflared-linux-amd64.staged`(38M) `tools/github-mcp/github-mcp-server`(25M) | 二进制工件，丢失后从 `<D盘>:\dsh-full-*.tar.zst` 取回 |
| `tools/plugin-peek/` | 下载的 npm 包与解包快照，可重下 |

入库示例：根文档 14 份 · `tools/` 52 个文件（含 `github-mcp/start-wrap.sh`——
`cordis.patch.yml` 引用它，**必须收**）· `bin/dsh` · `start-web.sh` · `DSH_VERSION` ·
`usage-analysis/` · `survey/` · `_work_mineru_v5/`。

> ⚠️ **已知并接受**：`start-web.sh` / `start-web-dryrun.sh` 含明文 API key。
> 用户明示这是本地 git 备份，不处理。**若将来要推到任何远端，必须先清理这两个文件。**

> 🕳️ **踩坑自曝**：`.gitignore` **不支持行尾注释**——初版把说明写在 pattern 后面，
> 导致 `原始代码研究/`、`dsh-domus/`、`_scratch/` 等**全部失效**（git 只认行首 `#`），
> `git add -A` 差点把 5.3G 吞进索引。已改为注释独立成行，并在文件头写明禁令；
> 建立时用 `git check-ignore` 做了双向核对（该排的排掉 / 该收的没被排）。

**覆盖缺口（未决 10）**：7 个被修好的探针在 `_scratch/` 下，按上表被整体排除，
故本次修复**没有进版本控制**。

---

## 十一、附带：`_scratch/` 产出物放行 + 凭据按类型排除（2026-09-26 11:19）

第十节留下一个缺口：第十轮修好的 7 个探针在 `_scratch/` 下、被整体排除，
**修复没进版本控制**——正是本仓库要治的病。

**做法**：`_scratch/` → `_scratch/*` + 三个白名单。

> ⚠️ 必须写 `_scratch/*` 而不是 `_scratch/`：git 规定**父目录被排除时，其下文件
> 无法用 `!` 重新纳入**（"It is not possible to re-include a file if a parent
> directory of that file is excluded"）。排除"内容"才能对子项做例外。

| 放行 | 内容 |
|---|---|
| `_scratch/search-probe/` | 10 个探针（折叠地基 / UCA / PyICU / 命名空间 / FTS5 / 全量普查…）+ `out/` 实测输出 |
| `_scratch/dsh-transcribe/` | 转录取证（`commit-report.json` / `evtime-backfill.*` / `probe-*`） |
| `_scratch/dsh-rel/` | 22 份官方 release notes + `releases.json` |

**凭据按类型排**：新增 `*.cnf`。本机惯例 `*.cnf` 就是 MariaDB 凭据，已确认两处明文口令
（`_scratch/trace-db.cnf`、`_scratch/search-probe/out/bench.cnf`——后者文件里自己就写着
"勿提交"）。**按类型排而非按路径排**，防止将来再落一个。

**双向核对**（`git check-ignore`）：7 项必排全部 IGNORED；5 项必收仅 1 项例外——
`_scratch/watch_status.py` 仍在白名单外（见未决 11）。

新增入库 **51 文件 / 692K**（最大 `releases.json` 216K）。

---

## 十二、附带：裁掉 `cordis.patch.yml` 尾部明文 key（2026-09-26 11:20）

尾部有整段注释掉的 `mcp-tavily` 配置，含明文 `tvly-dev-…` key；且文件缺尾换行。一并清理。

**不是"我觉得没事"**：`tools/trim-cordis-tail.py` 在写回前后各 `yaml.safe_load` 一次，
**断言两棵树完全相等**。被删的 9 行全是注释与空行，YAML 语义零变化。
实测：165 → 157 行、尾换行已补、`tvly-` 残留 0 处、YAML 相等 `True`。

该文件是 **cordis 热加载**的（停机卡第二节：编辑它就是一次线上变更），
但本次只删注释，不构成变更。写回后实测：
- DSH 仍在 9007 存活（pid 56401）
- 传输取证持续入流（游标 3874 → 3883）
- `check_patch_layers.py` 仍报「196 个 id、无重复、可以启动」

提交落在**冻结基线 `fa4bca5` 之后的独立提交** `b9badc8`——正是阶段 1 设计的目的：
迁移改动与原始状态可以分别 diff。

---

## 十三、附带：放行 `_scratch/` 顶层 `.py`（2026-09-26 11:2x）

第十一节留下的残留：`_scratch/watch_status.py` 是 **ops-daemon 的活依赖**
（守护脚本里写死 `$REPO/_scratch/watch_status.py`，每 5 分钟调一次做状态快照），
却在白名单之外 → live 代码继续裸奔。

新增一行 `!_scratch/*.py`，入库 **14 个手写脚本**：
`watch_status.py` `correlate_failures.py` `extract_failures.py` `extract_kw.py`
`pi_junk.py` `pi_slow.py` `regen_note.py` `scan_plugin_deps.py`
`session_timeline.py` `slice_ctx.py` `test_annotate.py`
`verify_attach_dedup.py` `verify_incremental.py` `window_dump.py`

凭据与运行态不在 `.py` 之列，故仍全排除（双向核对）：
排除 ✓ `trace-db.cnf` `fetch-trace.log` `WATCH-ALERT.txt` `WATCH-STATUS.txt`
`ops-daemon.lock` `prompt-diff`

---

## 十四、附带：`wrap` 仓库同病同修（2026-09-26 11:2x）

提交 `cordis.patch.yml` 时发现的**同类问题**：`<挂载d>:/DataServices/MCP/wrap`
（唯一的 git 仓库根）**只跟踪 6 个文件**，而：

| 项 | 状态 |
|---|---|
| `mcp-stdio.sh` | **已修改未提交**——它是**所有 MCP 服务器的启动器**（filesystem / papersearch / bingcn / cloakbrowser / mcp-time / mcp-localgit / mcp_eqsolve / mcp_pysyntaxcheck / mcp-entropia / mcp-calculator / mcp-memoria / **melquiades** 全走它的 case 分支）。「梅尔基亚德斯」那场删 `recall` / `mariadb` case 的改动至今没进版本控制 |
| 20 个 live 脚本 | **完全未跟踪**：mcp_eqsolve.py / mcp_localgit.py / mcp_time.py / mcp_pysyntaxcheck.py / mcp_bc.py / mcp_debug_proxy.py / mcp_gateway.py / mcp_smoke_test.py / cloakbrowser_fetch.py + 8 个 `.sh` 启动器 + `一键拉起本地MCP知识库运行三大环境.cmd` |
| 仓库无 `.gitignore` | `fast_filesystem.py.bak*` 五个副本、`__pycache__/` 全裸露 |

**处置**：补 `.gitignore`（与 harness / dsh-domus 同调）+ 入库 **25 项 / 116K**（`759c07a`）。

入库前**做过凭据扫描**（`api_key` / `token` / `secret` / `password` / `sk-` / `tvly-`）：
wrap 下**无明文密钥**——唯一命中 `fast_filesystem.py` 的是第十二节新写的 token 预算注释。

双向核对：7 项必排全 IGNORED（6 个 `.bak`/`.pre-*` 实例 + `__pycache__`）；
9 项必收全 OK。

---

## 十五、三个仓库的当前状态

| 仓库 | HEAD | 工作区 |
|---|---|---|
| `~/deepseek-harness` | `85fe556` | 干净 |
| `~/deepseek-harness/dsh-domus` | `b9badc8`（冻结点 `fa4bca5` 之后） | 干净 |
| `<挂载d>:/DataServices/MCP/wrap` | `759c07a` | 干净 |

---

## 十六、附带：守护改用 `setsid`（2026-09-26 11:27）

**发现过程**：本轮手工重启运维守护时用的是 `nohup ... & disown`，
但实测它**仍与启动它的 shell 同会话**：

```
   PID   PPID  PGID   SID   CMD
 57682  57676 57653 57653   bash tools/dsh-ops-daemon.sh
```

一旦那个会话被整个回收（**SIGKILL 不理会 nohup**），守护会跟着死——
而且是**静默**死：日志停在某一行，没人知道哨兵已经不在了。
对一个"专门用来记录 DSH 自己崩溃"的守护来说，这是最不能接受的一种死法。

**处置**：`start-web.sh` 改为 `setsid nohup ... &`（`c832f59`），让它自成一系。

**实测**：新守护 PGID=60664 / SID=60664（自成一系），日志按 20s 节拍推进；
flock 单实例闸门正常（重复拉起即 `已有实例在跑(flock)，本进程退出`）。

> 此前 nohup+disown 在"终端正常关闭"场景下是够用的（nohup 挡住 SIGHUP）；
> 本次补的是"进程组被强杀"这一档。

**方法教训**：本轮判进程数量时用过两次错误写法——
`grep -c 'dsh-ops-daem[o]n.sh'` 会把**自己的命令行**算进去（`bash -c` 里就含这段文本），
`ps -eo pid,pgid,sid,cmd | awk '$5=="bash"…'` 则因列数变化而失配。
**查进程数一律用 `pgrep -af <精确模式>`，别拿 grep 数 ps 输出。**

---

## 十七、附带：清理 `_scratch/*.mjs`（2026-09-26 11:29）

上一轮没放行 `.mjs`。逐一核对后发现里面混了三类东西，分别处置：

| 类别 | 文件 | 处置 |
|---|---|---|
| **陈旧副本**（有误用风险） | `dsh-fetch-trace.mjs`（3151B / 09-25 17:42） vs `tools/` 同名（7572B / 09-25 20:10） | **删** —— 两个不同版本同名共存，改错那份就是静默故障 |
| **零引用的一次性复现脚本** | `probe_dispatcher.mjs` `repro_abort.mjs` `repro_long.mjs` `repro_post.mjs` `repro_stream.mjs` `trace_test.mjs` | **删** —— 全库 grep 零引用 |
| **可复用技法** | `verify_suigintou_css.mjs`（被 `皮肤主题笔记.md` 引用） | **移入 `tools/`** —— 是方法论级工具，不是草稿；随仓库入库 |

移动后实测可用：拿现役 client bundle 跑出 **97 行 / 6684 字节** CSS。

> ⚠️ **删除前差点漏掉的回滚点核查**：`_scratch/` **不在**
> `<D盘>:\dsh-full-20260926-100908.tar.zst` 里（实测 0 条命中，它是**唯一**被排除的顶层目录）。
> 所以直接 `rm` 是**不可恢复**的。
> 已先归档到 `backups/_scratch-mjs-20260926-112944.tar.gz`（6.3K / 8 文件）——
> `backups/` 在备份范围内。

结果：`_scratch/` 下已无 `.mjs`；`tools/` 现为 `dsh-fetch-trace.mjs` + `dsh-force-h1.mjs` +
`verify_suigintou_css.mjs`，三个都在版本控制下。

---

## 十八、阶段 2 指引已交付

`DSH升级-0.1.7-阶段2-自跑指引.md` —— 用户自跑。要点：

- 定义**算什么/不算什么**（算：装得上、构建得出来、拿到 0.1.7 真实 entry id 全集；不算：不切版本、不停 9007、不碰 domus）
- 前置检查含一条**新发现的版本落差**：检出钉 `pnpm@11.7.0`，本机 **12.4.1**（大版本差一档），
  `allowBuilds` / `minimumReleaseAge` 语义可能收紧 → 列为 install 报未知 policy 错误的第一嫌疑
- 明确 **cloudflared 本次碰不到**（它是 `dsh-domus/profiles/web` 的依赖，不在基座检出里），
  那个坑留给阶段 4
- 三条 dump 命令：`(A)` 出厂模板视角 `(B)` 我们 profile 视角 ★ `(C)` 组装后 profile 树
- 预期 `(B)(C)` 会**报错或大量缺失**——这正是要的信息，**别急着修，原样回传**
- 禁用清单：不跑 `bin/dsh`（硬编码 DSH_HOME）/ 不动 profile 的 node_modules / 不停 9007

---

## 十九、阶段 2 进展（2026-09-26 14:2x）

### 已完成

| 项 | 结果 |
|---|---|
| `pnpm install` | ✅ `node_modules` **1.9 G** |
| `pnpm run build` | ✅ **全绿** —— `apps/web/dist/index.html` 824 B、`dist` **21 M**（0.1.5 是 13 M） |
| 客户端产物 | **343** 个（`build: recorded 343 client artifact(s)`） |
| `packages/**/lib` | **312** 个（中断时 265；0.1.5 是 267） |
| 日志 error/failed | **0** |

### 三处需要记在册的状态变更

1. **`package.json` 的 pin**：`pnpm@11.7.0`（上游）→ **`pnpm@12.6.0+sha512…`**
2. **`pnpm-lock.yaml`**：**+158 行**，头部多 `importers.….packageManagerDependencies: pnpm 12.6.0`
3. **`node_modules/.bin/pnpm` 已删除**（连同 vendored 的 `pnpm@11.7.0`）
   —— 这是修 pnpm 版本故障的必要动作，详见阶段 2 指引 §1.5

> 上面前两条是**与上游的偏离**，是本机环境（corepack + pnpm 12 的
> `packageManagerDependencies`）造成的，不是检出本身的问题。
> 阶段 3 要决定是留还是 `git checkout` 还原——**倾向留**（1.9 G 依赖与 312 个 lib
> 都是在这个版本组合下产出的，还原要重装）。

### 阶段 2 还没做的一步

三条 dump 命令（见指引 §5）：`(A)` 出厂模板视角 / `(B)` 我们 domus 视角 ★ /
`(C)` 组装后 profile 树。**`(B)(C)` 是阶段 3 settings 迁移的唯一输入。**
