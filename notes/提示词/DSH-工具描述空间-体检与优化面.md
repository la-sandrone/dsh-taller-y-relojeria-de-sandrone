/* 文件名: DSH-工具描述空间-体检与优化面.md
 * 摘要: 以 DSH 官方 token 口径实测本部署 tools 常驻成本，交叉真实用量，
 *       给出官方杠杆清单与可裁剪空间。所有数字可复现。
 * 依赖: tools/tool_payload_audit.py, tools/tool_usage_audit.py,
 *       tools/tool_budget_optimize.py, tools/ptc_sdk_render_probe.ts
 *
 * 口径权威来源（v0.1.7-rc.2 检出）:
 *   packages/llm/token-meter/src/estimate.ts       → CHARS_PER_TOKEN=4 / estimateToolsTokens
 *   packages/llm/token-meter/src/breakdown-projection.ts → UI 三档 system/tools/message
 *   packages/core/tools/src/index.ts               → schemas() 白名单 / mode / presentAs / restrict
 *   packages/core/tools/src/ts-types.ts            → PTC SDK 渲染器
 *   packages/llm/llm-deepseek/src/serialize.ts     → defer_loading 透传
 */

# DSH 工具描述空间：体检与优化面

**日期**：2026-10-03
**基座**：v0.1.7-rc.2（`原始代码研究/v0.1.7-rc.2`）
**会话**：`session-b868cd47-6657-4789-8ee7-21d3f245c6cb`（deepseek-flash，contextWindow = 1,000,000）
**结论一句话**：41,226 token / 4.1% 上下文，其中 **一半（21,011 token）花在 80 份会话日志里从未被调用过的 112 个工具上**；官方有三条杠杆，但真正落地的是"关掉没人用的自制 MCP"。

---

## 一、官方口径（不是估算，是复刻）

DSH 的 UI「上下文构成」把请求分成三档：`systemTokens / toolsTokens / messageTokens`
（`breakdown-projection.ts` L24-28）。工具档的定价函数在 `estimate.ts` L99-102：

```ts
const CHARS_PER_TOKEN = 4
export function estimateToolsTokens(header) {
  return Math.ceil(JSON.stringify(header.tools).length / CHARS_PER_TOKEN) + 4
}
```

**⚠️ 复现时的坑（我踩过一次）**：这是 **JavaScript** 的 `JSON.stringify`，**不插空格**；
Python `json.dumps` 默认 `separators=(', ', ': ')` 会多插空格，同一对象实测
171,994 vs 164,888 字符 —— 直接虚高 4%。必须用 `separators=(',', ':')`。

数据源是事实层：每个请求的完整 tool schema 都落在会话日志的
`request/header` 事件（`data.header.tools[]`），那是模型当时真正看到的清单。

---

## 二、实测：41,226 token 的构成

```
★ toolsTokens（官方口径） = 41,226      工具数 202
  description 字段        15,139  (36%)
  parameters/JSON Schema  22,833  (55%)
  name + 结构开销          3,254  ( 9%)
```

### 按来源

| 来源 | 工具数 | 常驻 token | 占比 | 历史调用 | 零调用工具 | 零调用 token | 浪费率 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 内置 | 57 | 14,476 | 35% | 10,859 | 32 | 9,275 | 64% |
| mcp:papersearch | 57 | 9,232 | 22% | 256 | 47 | 7,208 | **78%** |
| mcp:github | 26 | 6,861 | 16% | 195 | 12 | 2,417 | 35% |
| mcp:filesystem | 13 | 4,047 | 9% | 1,133 | 1 | 102 | 2% |
| mcp:melquiades | 10 | 1,797 | 4% | 526 | 3 | 234 | 13% |
| mcp:mcp-memoria | 7 | 1,280 | 3% | 412 | 1 | 135 | 10% |
| mcp:mcp-entropia | 13 | 1,125 | 2% | 29 | 11 | 942 | **83%** |
| mcp:mcp_eqsolve | 6 | 539 | 1% | 5 | 3 | 109 | 20% |
| mcp:mcp-localgit | 6 | 492 | 1% | 117 | 1 | 99 | 20% |
| **mcp:linkdigest** | 1 | 490 | 1% | **0** | 1 | 490 | **100%** |
| mcp:mcp_pysyntaxcheck | 1 | 269 | 0% | 242 | 0 | 0 | 0% |
| mcp:mcp-calculator | 1 | 217 | 0% | 1,391 | 0 | 0 | 0% |
| mcp:bingcn | 2 | 150 | 0% | 126 | 0 | 0 | 0% |
| mcp:cloakbrowser | 1 | 143 | 0% | 412 | 0 | 0 | 0% |
| mcp:mcp-time | 1 | 123 | 0% | 91 | 0 | 0 | 0% |
| **合计** | **202** | **41,241** | 100% | 15,794 | **112** | **21,011** | **50%** |

用量口径：80 份本机留存会话日志、17,917 次 `tool/call`、出现过 125 个不同工具。
（历史会话里还有 mariadb / tavily / draftpaper / recall / win_* 等**已下架**的服务器，
不在当前 202 之内。）

### 单工具 Top 10（常驻成本）

| 工具 | token | desc | params |
|---|---:|---:|---:|
| `mcp__filesystem__write_myfilesystem_text_file` | 904 | 501 | 382 |
| `workflow` | 848 | 420 | 416 |
| `task_board_create` | 776 | 147 | 615 |
| `company_scan` | 695 | 45 | 637 |
| `research_report` | 691 | 212 | 465 |
| `deepread` | 618 | 185 | 422 |
| `mcp__github__pull_request_read` | 611 | 17 | 577 |
| `mcp__github__list_issues` | 588 | 35 | 538 |
| `industry_map` | 586 | 34 | 540 |
| `mcp__filesystem__grep_myfilesystem_file` | 580 | 247 | 314 |

**结构性观察**：55% 的成本在 JSON Schema，36% 在 description。
GitHub MCP 是典型「description 极短、params 极胖」（`pull_request_read`：17 vs 577）——
上游 schema 自动生成的，改不动。自制 MCP 相反（`filesystem` 的 desc 1,916 token）——
**改得动**。

---

## 三、官方给了哪些杠杆（精确出处）

### 杠杆 1：PTC 呈现模式 —— 已实渲染测量

出处：`config-catalog.zh.md` L3964-3989 `@deepseek-ai/dsh-tools`

```ts
interface Config {
  mode?: 'native' | 'ptc' | 'both'   // native 默认：发每一条可见 schema
  maxParallelSubCalls?: number
}
```

`ptc` 下注册表对协议格式的**唯一贡献是 `run_code`**，其余能力改写进
生成的 SDK 提示词章节（`index.ts` L896-914 `sdkSection()`）。

**我实跑了官方渲染器**（`tools/ptc_sdk_render_probe.ts`，用 `renderToolsSdk` /
`renderToolsSdkPy`，输入是这 202 个工具的真实 schema）：

| 形态 | 字符 | ≈ token |
|---|---:|---:|
| native（JSON Schema 数组） | 164,888 | 41,222 |
| ptc：SDK 章节 TypeScript | 126,100 | 31,525 |
| ptc：SDK 章节 Python | 153,639 | 38,410 |

- TypeScript 运行时：**约 -9,700 token（-23%）**
- Python 运行时：仅 **约 -2,800 token（-7%）**

**⚠️ 这个数是下界**：SDK 渲染器同时输出 `ToolArgsMap`（参数）和 `ToolOutputMap`（**输出**），
而 native 模式**根本不发 output schema**（`schemas()` 只白名单 name/description/parameters，
见 `index.ts` L43-46 注释）。会话日志里拿不到内置工具的 output schema，
我只能用 `{}` 占位 —— 真实 ptc 只会更大。内置工具的输出类型越丰富，这个杠杆越不划算。

### 杠杆 2：按作用域过滤 / 按作用域换呈现

出处：`index.ts` L1083 `restrict()`、L974 `presentAs()`、L922 `modeFor()`

- `ctx.tools.restrict({ allow, deny })` —— 每作用域实时过滤器，多限制取交集，
  且**不影响该作用域自身的注册**（被委派的子 agent 保留其回报所依赖的工具）。
- `modeFor(scope)` 沿作用域链**最近者胜**，"a preset's standing declaration covers every
  agent parented under it" —— 即 **agent preset 可以单独声明呈现模式**。
- `run_code` 在可过滤能力层之外，`restrict()` 不能移除它（会抛错）。

**但它们都是程序化的**：`restrict()` 要求 scoped context（`agent.ctx`），
`presentAs()` 同样。第一方没有提供"profile 里写个 allow/deny 列表"的配置项——
要落地得自己写一个小插件或预设。

### 杠杆 3：`deferLoading` —— 官方有，但本部署用不上

出处：`llm-streaming.zh.md` L682-684、`llm-deepseek/src/serialize.ts` L164

```ts
/** Requests deferred loading of the tool definition into model context ...
 *  Uses Anthropic's defer_loading terminology. */
deferLoading?: true
```
→ 序列化为 Anthropic 风格的 `defer_loading: true`。

**三个理由说明它现在不是可用杠杆**：
1. 它是**插件作者**的标志（`defineTool({ deferLoading: true })`），不是部署开关；
   MCP 客户端注册工具时不设它。
2. LLM 包明确写着：「**不支持更新的路由接收有效工具，不携带 developer 消息或 `deferLoading`**」
   （`llm/README.zh.md` L162）。
3. 全部第一方代码里，只有 `llm/src/content.ts` L391 会**程序性**给"历史位置新增的定义"打上它，
   没有任何工具作者用它。（`grep -rn "deferLoading: true" packages/*/*/src/` 只命中这一行。）

→ 属于「记着，将来可用」，不属于「今天能省」。

### 杠杆 4：MCP 客户端**没有** per-tool 过滤配置

出处：`config-catalog.zh.md` L1990-2066 `@deepseek-ai/dsh-mcp-client`

`StdioConfig` / `StreamableHttpConfig` 的字段里**没有** include/exclude 工具列表。
唯一的预算字段是 `maxInstructionBytes`（默认 32768）——那是**服务器 instructions 文本**的
上限，走的是 system 面，**不是** toolsTokens 那一档。

→ 要裁 MCP 工具，只有两条路：**不挂这个服务器**，或在作用域层 `restrict()`。
（第三条：自制服务器的 `list_tools()` 少注册几个 —— 见下。）

---

## 四、可裁剪面（数据驱动，按性价比排序）

### ① 零调用且成本高 —— 直接摘

| 目标 | 工具 | 省 | 依据 |
|---|---:|---:|---|
| **停 `mcp:linkdigest`** | 1 | **-490** | 80 份日志零调用，单工具 490 token |
| 停 `mcp:mcp-entropia` 的 11 个死工具 | 11 | -942 | 只在 `uniform_range`(21) / `randint`(8) 用过；服务器是自家的，`list_tools()` 里删条目即可 |
| 停 `mcp:eqsolve` 3 个死工具 | 3 | -109 | 6 个工具只用了 3 个（`add_equation`/`declare_vars`/`solve` 各 1-3 次） |

### ② papersearch —— 单项最大的一块，但也最需要掂量

57 个工具 / 9,232 token / 78% 零调用。历史用量只有 256 次，集中在 9 个：

`search_arxiv`(99) · `search_crossref`(43) · `search_papers`(39) · `search_unpaywall`(36) ·
`get_crossref_paper_by_doi`(11) · `download_with_fallback`(11) · `search_semantic`(9) ·
`read_arxiv_paper`(6) · `search_dblp`(1)

→ 若只保留这 9 个，**约 -7,000 token（-17% 总常驻）**。
但它是上游包（`~/ai-services/paper-search-mcp`），要改得 fork 或加一层包装。
**判断点**：这 48 个零调用工具是"没用上"还是"不该有"？——`download_scihub` / `download_*`
这类是**按需才会用**的（真用到时才想起它），零调用不等于冗余。

### ③ github —— 26→14

12 个零调用（-2,417 token），但 `github` 是上游 MCP server 注册的，
裁剪要动服务器。且 GitHub 的调用是**突破性任务**时才密集出现。

### ④ 自制 MCP 的 description —— 可控、但收益分散

description 总 15,139 token。最大几条都是**自家写的**（filesystem / melquiades / memoria）：
`write_myfilesystem_text_file` 501 · `scan_myfilesystem_indices` 301 ·
`grep_myfilesystem_file` 247 · `plugin_vet` 257 · `draftpad_find` 238 · `search_docs` 293。

但这些工具调用量都高（filesystem 1,133 次 / memoria 412 次）——**说明长描述可能正是它们
好用的原因**（`write` 工具那 1,924 字的"先读后写铁律"就是这个仓库的规矩）。
**不建议为了省 token 砍掉行为约束**，那是拿正确性换钱。

### 情景投影

```
基线                                    41,241
① 停 linkdigest + entropia 死工具 + eqsolve 死工具   → 约 39,700  (-1,500)
① + ② papersearch 裁到 9 个              → 约 32,700  (-8,500, -21%)
① + ② + ③ github 裁到 14 个              → 约 30,300  (-10,900, -26%)
```

---

## 五、我的判断（含反方意见）

**1. 这件事的收益被高估了，先算清楚再动手。**
41,226 token 在 1,000,000 的窗口里是 **4.1%**——上下文容量根本不是瓶颈。
真正的成本是**每请求重复支付**。但 tool schema 是**稳定前缀**，
DeepSeek 的 KV 缓存正是靠前缀命中打折的（`TokenUsage` 里有"不相交的缓存字段"）。
所以边际成本远低于 41K 的字面值。
→ **动手前先看账单**：`usage-analysis/` 里已有现成的按会话归属脚本。

**2. PTC 是最大的官方杠杆，但不是免费的。**
- 名义 -9,700 token（TS 运行时），且这是**下界**。
- 代价是**模型行为契约改变**：不能直接调工具，必须写程序；`run_code` 排错成本、
  子调用结果不进对话（这其实是**另一个**好处，但也是行为差异）。
- 你用的是 flash + low reasoningEffort。让 flash 写 TypeScript 编排来调工具，
  值不值得省 23%？**我倾向于不值**，但这是你的调用。
- **好消息**：`mode` 可以按 preset 声明（`modeFor(scope)` 最近者胜）。
  所以可以**只在一个 preset 上试**，A/B 出数再推广——这是低成本验证路径。

**3. 最诚实的建议**：先摘 ①（约 -1,500 token，零风险、零行为变更），
再看账单决定要不要碰 ②。PTC 留作"如果真要压"的选项，且只在单个 preset 上试。

**4. 反方**：如果目标是**上下文容量**（比如想把长会话榨得更久），那 41K 省到 30K 也
只是把 1M 窗口的 4.1% 降到 3.0%，不如直接看 compaction 策略。
**这个优化只在"按 token 计费"的场景下有意义。**

---

## 六、复现方式

```bash
cd $HARNESS

# 1) 当前工具空间构成（官方口径）
python3 tools/tool_payload_audit.py --top 30

# 2) 单来源深挖
python3 tools/tool_payload_audit.py --source mcp:papersearch --top 100

# 3) 跨会话用量统计（要几分钟，吃全部 80 份日志）
python3 tools/tool_usage_audit.py --json /tmp/tool_usage.json

# 4) 成本 × 用量 交叉 + 情景投影
python3 tools/tool_budget_optimize.py --usage /tmp/tool_usage.json

# 5) PTC 实渲染（在检出目录里跑）
cd 原始代码研究/v0.1.7-rc.2
cp $HARNESS/tools/ptc_sdk_render_probe.ts ./probe.ts
./node_modules/.bin/tsx ./probe.ts && rm probe.ts
```

**口径边界（随结论一起读）**：
- 用量是**下界**——只统计本机留存的 80 份日志，已删会话不计。
- 某些工具是近期新挂的，零调用可能只是"还没用上"。
- 工具清单在**会话启动时快照固化**，所以"当前清单"= 本会话开始时的配置。
- PTC 数字是**下界**（内置工具 output schema 用 `{}` 占位）。

---

# 七、按「可替代性」重算（2026-10-03 修订）

**修订理由**：第四节那份排序是**拿"零调用"当唯一判据**，问错了问题。
真正该问的是：**这个工具的能力是否已被 `bash` 覆盖？**
bash 占全部调用的 **42%**（7,620/17,917），它就是万能逃生舱。

## 7.1 修订后的三块

| 目标 | 工具数 | 省 | 依据 |
|---|---:|---:|---|
| **github server 整体裁掉** | 26 | **-6,861** | 公开信息走 bash+curl；PAT 场景写 wrap 脚本 |
| **papersearch 精简到 8 个** | 49 | **-7,405** | 只需 OA + crossref；63 个 `@mcp.tool` 平铺，删函数即可 |
| **内置三块第三方插件** | 22 | **-7,393** | 见下，全部是**已装插件**，可逆 |
| 合计 | 97 | **-21,659** | 41,226 → **约 19,567（-53%）** |

内置三块明细（全部来自 profile 依赖里的第三方包）：

| 插件包 | 工具 | token | 历史调用 |
|---|---|---:|---:|
| `@linxin666/dsh-web-all`（task_board_*） | 8 | 2,893 | **0** |
| `dsh-industry-research` + `dsh-research-report`（company_scan / industry_* / research_report / evidence_add / ledger_query） | 8 | 3,864 | deepread 4，其余 **0** |
| `dsh-session-insights` | 6 | 636 | **0** |

## 7.2 github：不用 fork，但 PAT 甩不掉

**server 自带工具过滤**（`./github-mcp-server stdio --help` 实测）：

```
--toolsets strings       Available: actions, code_quality, ..., repos, issues,
                         pull_requests, users, git, labels, notifications, ...
                         default = context, copilot, issues, pull_requests, repos, users
--tools strings          逐个指定
--exclude-tools strings  逐个排除
```
→ 若只想"瘦身"，改 `start-wrap.sh` 加一行 flag 即可。

**但整体裁掉需要处理凭证**（实测未认证访问 api.github.com）：

```
core         limit=60/hr    remaining=46     ← 这个小时配额已被消耗过
search       limit=10/hr
code_search  limit=60/hr
GET /search/code?...  → HTTP 401   ← 代码搜索强制认证
```

两个结论：
1. **`search_code` 未认证直接 401**，PAT 不是可选项。
2. `core 60/hr` 是**按出口 IP**计数的，而你走共享代理（`HTTP_PROXY=localhost:8994`）
   → 60/hr 不可靠。**建议保留 PAT，但只放在 wrap 脚本里。**

## 7.3 ⚠️ 顺带发现：明文 PAT 进了 git 仓库

`tools/github-mcp/start-wrap.sh` 含明文 `GITHUB_PERSONAL_ACCESS_TOKEN`，且：
- `git ls-files` 确认**已被跟踪**（commit `7d6c4e0` 首次入库）
- `.gitignore` L64 注释明确写「同目录的 start-wrap.sh 是**要收的**」→ 当时是有意收的
- `git remote -v` **为空** → 本地仓库，未推送，**不是已泄露**
- 但 `tools/backup-dsh.sh` 会带着它走；且本次会话日志里也出现了（我 `cat` 的），
  而你的管线（archive → MariaDB `dsh_message`、export → D: zip）会继续传播

**建议**：① 轮换这个 PAT；② 改从仓库外的 env 文件读（`~/.config/dsh/github.env`，600）；
③ `.gitignore` 里把 `start-wrap.sh` 从"要收的"改成例外。这条正好和 7.2 的 wrap 脚本改造一起做。

## 7.4 papersearch 精简版设计

`paper_search_mcp/server.py` 注册了 **63 个** `@mcp.tool`（DSH 侧看到 57），**平铺函数、无循环注册**
→ 精简版 = 复制 server.py，删掉不用的工具函数 + 对应 import。

建议保留 8 个（OA 主线 + crossref 主线）：

| 工具 | token | 历史调用 |
|---|---:|---:|
| `search_papers`（多源聚合入口） | 252 | 39 |
| `search_crossref` | 311 | 43 |
| `get_crossref_paper_by_doi` | 132 | 11 |
| `search_arxiv` | 217 | 99 |
| `read_arxiv_paper` | 144 | 6 |
| `search_openalex` | 241 | 0 |
| `search_unpaywall` | 184 | 36 |
| `download_with_fallback`（OA 降级管线） | 346 | 11 |
| **合计** | **1,827** | — |

**但更值得考虑的选项**：按你 melquiades / recall 的既有模式**自己写一个自包含的**。
理由——这 63 个工具里你只要 8 个，而其中真正的核心逻辑是
`download_with_fallback` 的降级链（OA 仓库 → Unpaywall → 可选 Sci-Hub）。
自制版可以：只依赖 `httpx`、把降级链写死成你实际可用的源、凭证走仓库外 env。

## 7.5 关键账：skill 比 tool schema 便宜 5 倍

实测两者的**常驻成本**：

| 机制 | 条目数 | 常驻 token | 每条 |
|---|---:|---:|---:|
| **skill 目录**（系统提示词里的 `<available_skills>`） | 13 | **694** | **≈ 50** |
| **tool schema**（github MCP） | 26 | 6,861 | **≈ 264** |
| **tool schema**（全部 202） | 202 | 41,226 | ≈ 204 |

→ **把接口说明从 tool schema 挪进 skill，常驻成本降约 5 倍**，且一个 skill 能装多个能力。
这正是 DSH 原生的"渐进披露"：skill 只常驻一行 `name + description`，正文按需 `skill()` 加载。

**所以 github 裁掉的正确姿势不是"让它凭空猜 curl 参数"**，而是：
`wrap 脚本（提供确定性接口）` + `一个 skill（写清接口清单与用法）`。
模型先用 `bash` 摸清脚本，再照 skill 调用——常驻成本从 6,861 降到 ~50–200。

## 7.6 修订后的结论

- 你的判断对：**内置、github、papersearch 才是主战场**，我上一轮盯 linkdigest/entropia
  那种边角料是抓错了重点（它们合计才 1,400 token）。
- **降幅从 -4% 变成 -53%**（41,226 → 约 19,600）。
- **反方仍然成立**：github 和 research 属于"平时不用、需要时不可替代"的突破性工具。
  裁掉省的是常驻，代价是"需要那天配回来"。**只要启用路径足够便宜**
  （插件可逆禁用 / cordis.patch 一行 / skill 按需加载），这个交易就是划算的 ——
  **但别把"平时不用"当成"不该有"**，那是两回事。
- **优先级建议**：先做**可逆、零能力损失**的两块 ——
  ① 第三方插件三块禁用（-7,393，纯赚，随时装回）
  ② papersearch 精简（-7,405，能力按你实际用的源保留）
  github（-6,861）放最后，因为它要新写 wrap + skill，有开发成本；
  但**做它的时候顺手把 PAT 从 git 里挪出去**。

---

# 八、「浪费率」是个坏指标 —— 按「失效模式」重算（2026-10-03 二次修订）

## 8.1 撤回：我用的判据错了

第四节那张表把 token 当唯一成本、把工具当同质项，算出「entropia 浪费率 83%」。
**这个标签是错的。** entropia / calculator 这类工具的价值不在调用频次，在于：

> **如果它不在，模型会不会静默降级到"瞎编"？**

算术、随机数、语法检查、时间戳——LLM 在这些地方**会自信地编出错误答案且不报错**。
用确定性路径接住，是**给正确性买单**，和"以静默降级为耻"是同一条原则的正反面。
**按频次给它们定价，本身就是一种误判。**

正确的判据应该是「**失效模式**」，不是「调用次数」。

## 8.2 但正确性护栏也分两种成本

护栏**必须留**，不代表它的**表面**必须这么大。把 entropia 的 13 条描述拉出来看：

```
⚠️ 非密码学安全。使用 Mersenne Twister / PCG-64 伪随机数生成器，严禁用于密钥、密码盐值或安全令牌。
```

**这同一句 55 字被复制了 13 遍**（17 tok × 13 = **221 tok 纯重复**），
13 个工具的 `n` 参数 schema 也几乎逐字相同。

| | 工具数 | token |
|---|---:|---:|
| 现状 | 13 | 1,125 |
| 收拢成一个 `sample(distribution, ...)` dispatcher | 1 | 237 |
| **差** | | **-888（-78%）** |

**13 种分布的确定性路径一种没少**——只是从"13 个工具"改成"1 个工具 + 枚举"。
安全警告还从 13 份收敛成 1 份（**可维护性反而更好**，改一次就够）。

→ **收拢表面 ≠ 削减能力。** 这才是护栏类工具该用的刀。

## 8.3 同一个刀切 papersearch，账比第七节更好

把 57 个工具按动词拆：

```
search_*   22 个      download_*  18 个      read_*  16 个
```

去重后的**源**只有 **22 个**：arxiv / base / biorxiv / citeseerx / core / crossref /
dblp / doaj / europepmc / google_scholar / hal / iacr / medrxiv / openaire /
openalex / pmc / pubmed / scihub / semantic / ssrn / unpaywall / zenodo

**所以 57 个工具表达的是「22 个源 × 3 个动词 = 66 个格子」。
真正的能力维度是 66，不是 57 个独立能力。**

收拢设计（3 个 dispatcher）：

| 工具 | 覆盖 |
|---|---|
| `search(query, source, max_results, year)` | 22 个源的检索（`source=all` 即多源聚合） |
| `fetch(doi, title, source, use_scihub)` | 全部 download_*，含 OA 降级链 |
| `read(paper_id, source, save_path)` | 全部 read_*（按源选解析器） |

| | 工具数 | token |
|---|---:|---:|
| 现状 | 57 | 9,232 |
| 收拢 | 3 | **218** |
| **差** | | **-9,014（-97%）** |

**源覆盖一个不少。** 这比第七节"保留 8 个、砍掉 49 个"（-7,405）**省得更多、且能力更全**。

## 8.4 修订后的总账

| 目标 | 手法 | 省 |
|---|---|---:|
| papersearch | **收拢** 57 → 3（源不丢） | **-9,014** |
| 内置三块第三方插件 | **禁用**（可逆，纯赚） | **-7,393** |
| github | **裁掉** → wrap 脚本 + skill | **-6,861** |
| entropia | **收拢** 13 → 1（分布不丢） | **-888** |
| eqsolve（6 工具，539 tok） | 收拢 6 → 1~2（估算） | ~-390 |
| localgit（6 工具，492 tok） | `bash` + `/usr/sbin/git` 已覆盖（估算） | ~-492 |
| **合计** | | **约 -25,000** |

→ **41,226 → 约 16,200（-61%）**，且**没有一条确定性路径被牺牲**。

## 8.5 分类框架（替换掉"浪费率"）

| 类 | 判据 | 处置 | 例子 |
|---|---|---|---|
| **A 正确性护栏** | 不在 → 模型静默瞎编 | **保留确定性路径**；描述里的能力边界/触发词**不能砍** | `calculate`(1,391 次) · `check_syntax`(242) · `get_current_time`(91) · `entropia` |
| **B 可收拢的族** | 一个能力族被拆成 N 个同构工具 | **收拢表面**（枚举 + dispatcher），能力不减 | `entropia` 13→1 · `papersearch` 57→3 · `eqsolve` 6→1 |
| **C bash 可替代** | bash + 现成 CLI/HTTP 等价可达 | **裁掉**，接口写进 skill | `github`（公开信息）· `localgit`（`git` 就在） |
| **D 突破型专用** | 平时不用、需要时不可替代 | **可逆禁用**，衡量"配回来的成本" | task_board · industry_research · session_insights |

**A 类的描述是"行为护栏"，它的作用就是每次提醒模型别瞎编——砍它等于拆护栏。**
这解释了为什么 `calculate`（描述 112 tok，讲清"只做数值求值、不解方程"）
能拿到 17,917 次调用里的 1,391 次：描述在干活的。

同理，第六节里我说 filesystem 的 `write`（501 tok 描述 = 那 1,924 字的先读后写铁律）
"改得动"——**那个说法要撤回**。那是 A 类，砍了就是拆仓库自己的规矩。
