# DSH 升级：回归与重建清单

> **来源**：`<对话导出目录>\对话\折腾记录\Deepseek Harness相关\Deepseek Harness 3.md`
> 最后一场对话索引（行 12988–13088），标题《DSH迁移全记录：v0.1.1-rc.2基座、五场景Pro分治与MCP全家桶落地》
> **可信度**：索引摘要级。话题/决策表/产出物清单为原索引逐字搬运；需要动手指令细节时回原文件查。
> **生成时间**：2026-09-11（本轮升级调研中提炼）
>
> **⚠ 2026-10-07 状态说明**：本文写于 **v0.1.1-rc.2** 时期，基座已两度换代（0.1.5 → 0.1.7-rc.2），
> 清单**不可再执行**，只能当历史参考读。文中涉及的 `.bak-*` 快照
> （`agent.cordis.yml.bak-011rc2`、`cordis.patch.yml.orig-mcp` 等）已按
> 「备份统一交 git 管理」于当日清退（全仓 163 个），路径全部失效——其中
> `cordis.patch.yml.orig-mcp` 已收进
> `backups/residue-git-unrecoverable-20261007-230429.tar.zst`。
> 详见 `DSH停机卡.md` 的「残件清退」小节；当前升级路径看 `DSH升级-0.2.x-调查与方案.md`。

---

## A. 升级前必办（零风险，独立于升级）

| # | 事项 | 状态 |
|---|------|------|
| A1 | `bin/dsh` wrap 曾硬编码 `原始代码研究/v0.1.1-rc.2`，升级后仍指向旧检出 → `plugin-manager` 子进程 exec 到旧版 CLI | ✅ **2026-09-11 已修**：抽出 `~/deepseek-harness/DSH_VERSION` 唯一真相源，`start-web.sh` 与 `bin/dsh` 共用 |
| A2 | 升级时只需改 `DSH_VERSION` 一行 | 待办 |
| A3 | 备份 `dsh-domus` + `原始代码研究`（排除 `.git`/`node_modules`/`.pnpm-store`/`lost+found`） | 待办 |

## B. 四个已知失败签名 —— 回归检查项（**这是本文档最有价值的部分**）

2026-08 那次 dsh-web-all 升级（alpha 基座）实测失败，签名如下。**本次升级后逐条核对**：

| # | 失败签名 | 根因类别 | 核对方法 |
|---|----------|----------|----------|
| B1 | **`apiProxy` 移除 → `task-board` / `remote-web-ui` pending** | 子包依赖被删的一方 API | 启动后看这两个面板是否 pending；读 `插件源码/dsh-web` 对应子包源码 |
| B2 | **`dsh-client-runtime` 缺失 → `web-ui-settings` 炸** | 子包要求的一方依赖未被装上 | 检查 `node_modules/@deepseek-ai/dsh-client-runtime` 是否存在 |
| B3 | **`allowBuilds` 必须是 map 格式**（数组非法，会写自动占位符） | `pnpm-workspace.yaml` 格式 | 升级后回读该文件，确认 `allowBuilds:` 下是 `key: true` 形式 |
| B4 | **pnpm11 年龄门禁**拦截新发布的包 | 发布年龄策略 | 已加 `minimumReleaseAgeExclude: ['@linxin666/*']` ✅ |

> 当时的决策表原话：
> | 全家桶 | alpha上硬跑 | **回退rc.2等0.3.7** | **回退** | 0.3.6锁定rc.2生态（apiProxy/client-runtime），alpha不兼容 |
>
> **"等 0.3.7"这个条件已于 2026-09-10 满足**：`@linxin666/dsh-web-all` 0.3.20 发布，声明 `dsh >=0.1.5-rc.1`，与基座 0.1.5-rc.2 同日。

## C. 当时的关键决策（2026-08-29；已标注现值）

| 决策点 | 当时选择 | 理由 | 现值（2026-09-11） |
|--------|----------|------|--------------------|
| 基座版本 | v0.1.1-rc.2（否掉 rc.6 与 alpha） | 社区 preset 兼容面最稳；alpha 实测全家桶不兼容后回退 | ⏳ 待升 **0.1.5-rc.2** |
| 配置目录 | `$DSH_HOME=dsh-domus`（VHDX 内） | 即插即用，跟 VHDX 走 | ✅ 未变 |
| 双 key 存法 | `settings.yaml` 的 `apiKeyEnv` | 配置零明文，官方推荐 | ✅ 未变 |
| 创作 vs 编程 key | `route-friend.mjs` 自动分流（逃生门 `DSH_FRIEND_ROUTE`） | 创作→朋友 key、编程→自己 key | ⚠️ 该 mjs 随 Pro preset 一并删除 |
| MCP 清单 | 13 个（按 Chatbox enabled 裁） | 裁掉 memory / duckduckgo / mcp-bc | ✅ 未变（`cordis.patch.yml`） |
| 预算锚 1024 | 加（opt-in，`bootstrapMaxTokens`） | 考据实锤 1024 窗口，晋升后自动剥离 | ⚠️ 随 Pro preset 删除待确认 |
| router-flash | **不装** | persona 替换与 `complete` 冲突；五锚已是超集 | ✅ 未装 |
| 全家桶 | 回退 rc.2 等 0.3.7 | 0.3.6 锁定 rc.2 生态 | 🎯 **0.3.20 已发布，可升** |
| dsh CLI | wrap 冒充（非 npm 全局装） | 版本天然一致、收敛在 VHDX 内 | ✅ 已迁 `~/deepseek-harness/bin/dsh`，并已参数化 |
| MariaDB-MCP embedding | 保持 `None` | memoria 已覆盖向量需求，省内存 | ✅ 未变 |
| 皮肤字体 | 皮肤 CSS 覆盖（衬线哲学） | 现成饭 + 衬线哲学 | ✅ 未变 |

## D. 产出物清单 → 重建清单（**含过期标注**）

| 产出物 | 用途 | 现值核对 |
|--------|------|----------|
| `~/deepseek-harness/start-web.sh` | 启动收敛点：DSH_HOME + 双 key + 版本 + 端口 9007 | ✅ 在，版本已参数化 |
| `dsh-domus/settings.yaml` | 双 key 路由（`llm-deepseek` + `llm-pi-ai.amici-mei`） | ✅ 在，含 `inputModalities: [text, image]` |
| `dsh-domus/.agent-presets/`（当时 **10 个**） | 五场景 Flash 版 + anchored-standard + 4 个场景 Pro 版 | ❗**现 6 个**（academic/coding/fantasy/general/liangshen/scifi）；Pro 系列已下线 |
| `dsh-domus/profiles/web/cordis.patch.yml` | 13 个 MCP insert + 超时配置 | ✅ 在，13 条全是 `@deepseek-ai/dsh-mcp-client` |
| `dsh-domus/profiles/web/pnpm-workspace.yaml` | `allowBuilds`（map 格式）+ `minimumReleaseAgeExclude` | ✅ 在 |
| `dsh-domus/.credentials.yaml` | API key（**回退时同步的关键项**） | ✅ 在，⚠️ 不入 git，备份必含 |
| `dsh-domus/skills/humanizer-zh/SKILL.md` | 技能（19.3KB 原样拷贝） | ✅ 在，已被 git 跟踪 |
| `~/.npm-global/bin/dsh` | dsh wrap（当时建议移入 VHDX） | ✅ **已迁** `~/deepseek-harness/bin/dsh` |
| `~/deepseek-harness/tools/github-mcp/` | GitHub MCP v1.11.0 Linux 版 + `start-wrap.sh` | ✅ 在 |
| `~/deepseek-harness/插件源码/` | dsh-web / dsh-router-flash / dsh-anchored-standard 三个 clone | ✅ 在（多一个 `session-export`）；mtime 2026-08-29 |
| 4 个 Pro preset 内的 `route-friend.mjs` | 创作场景自动路由朋友 key | ❌ 已随 Pro preset 删除（若需恢复，见 `3.md` 索引话题 12/15） |
| `memoria` 的 `mcp_server.py`（行 42） | `search_docs` docstring "勿重试勿中断" 提示 | 待核对 |
| 草稿纸 `scratch_notes`（id=5 等） | 调研状态锚点（MariaDB） | 待核对 |

## E. 升级执行顺序（建议）

```
0. 备份（pv|tar|pigz 大串联，排除 .git/node_modules/.pnpm-store/lost+found）
1. clone 0.1.5-rc.2 到 原始代码研究/
2. 改 DSH_VERSION=v0.1.5-rc.2（一行）
3. DSH_HOME 指向 dsh-domus 副本，profile bundles 只留一方包
4. 【第一件事】开老会话（如 c08b4248：62 轮 / 7 次压缩）→ 验 v0→v3 迁移
5. 升 @linxin666/dsh-web-all → 0.3.20（含 20 子包）→ 逐条核对 B1–B4
6. 逐个放开：dsh-context（最高风险）→ plugin-console → annotation → …
7. 皮肤重调（用《DSH皮肤锚点对照表.md》逐条复核）
8. 重打 dsh-user-markdown 补丁（目标已迁至 ui-chat / ui-primitives）
```

## F. 验证命令

```bash
dsh --version          # 应为 0.1.5-rc.2（证明 wrap 跟着 DSH_VERSION 走了）
```

---

## 附：同批档案位置（供回查细节）

| 文件 | 内容 |
|------|------|
| `Deepseek Harness 3.md` | ⭐ 迁移全记录（11 个索引块，最后一块即本文档来源） |
| `Deepseek Harness 4.md` | 楼层模型 / LAMP 庙算、dsh 前后端分离推演（14 个索引块） |
| `Deepseek Harness 5.md` | ⭐ 皮肤 CSS 破案 8 条（5 个索引块） |
| `Deepseek Harness调研.md` | 最早调研：五锚、fast_filesystem 起源（9 个索引块） |
| `用户消息 Markdown 渲染 dsh-user-markdown.jsonl` | 渲染补丁原始记录（4.6MB） |
| `Deepseek Harness 6 - composer粘底破案 backdrop-filter包含块劫持.jsonl` | composer 粘底 CSS 破案（3.4MB） |
| `dsh-domus/patches/dsh-user-markdown.md` | 渲染补丁**蒸馏档案**（唯一存档，含验证用例） |

---

## G) dry run 实战踩坑（2026-09-11，Step 1 / Step 2）

### G1 ⚠️ `dsh plugin` 的静默失败：Ctrl+C 打断 = 包装了但配置里没有

`dsh plugin --profile <p> add <pkg>` 的执行顺序是：

```
spawnSync('pnpm', args)        ← 在这里 Ctrl+C
        ↓（只有正常返回才继续）
reconcilePlugins()             ← 改写 dsh.profile.bundles
```

中途打断 → pnpm 可能已把包装完，但 `dsh.profile.bundles` **一个字都没写**，
而且**再跑 `pnpm install` 会说 "Already up to date"（假成功）**。

后果：启动后插件**不会被加载，且不报错**。

- **判据**：`dsh plugin` 必须以**退出码 0 回到提示符**才算成功
- **验证**：装完立刻 `cat profiles/web/package.json`，确认同时出现在
  `dependencies` 和 `dsh.profile.bundles` **两处**

### G2 ⚠️ 往 node_modules 手工放文件，必须在所有 pnpm 操作之后

`cloudflared` 的二进制是 postinstall 产物（`node lib/cloudflared.js bin install`），
**不在 npm tarball 里**。pnpm 从 store 重新解压该包目录时，`bin/` 会凭空消失 ——
手工放进去的文件一起没了。

- **做法**：pnpm 全部跑完后再放；或让启动脚本兜底（`start-web-dryrun.sh` 已加）

### G3 cloudflared 二进制：直连 GitHub 极慢，走镜像

实测各源下载 2MB 均速：

| 源 | 均速 | 38MB 换算 |
|---|---|---|
| 直连 GitHub | ~16 KB/s | ~28 分钟 |
| **`ghfast.top`** | **352 KB/s** | **~2 分钟** ✅ |
| gh-proxy.com | 130 KB/s | ~5 分钟 |
| ghproxy.net / gh.llkk.cc / ghproxy.cc | ✗ 超时 / SSL 过期 | — |

- 完整件：`https://github.com/cloudflare/cloudflared/releases/download/2026.9.0/cloudflared-linux-amd64`
  （版本 **2026.9.0**，大小 **39,838,050**，md5 **1d0ea8cd29387b0050075c5aca1485ae**）
- 暂存于 `tools/cloudflared-linux-amd64.staged`

### G4 该下载器**不支持断点续传**，且**不认代理环境变量**

`lib/install.js` 用 `fs.createWriteStream(to)` + `res.pipe(file)`，**无 Range 请求**
→ 重跑从 0 字节开始。
且用 node 原生 `https.get()` → **`https_proxy` / `HTTPS_PROXY` 对它无效**；
要生效必须加 **`NODE_USE_ENV_PROXY=1`**（Node 24+ 内置代理支持，
已在 v26.8.1 二进制里确认该标识存在）。

### G5 session 迁移是**非破坏性 + 惰性**的（Step 1 结论，实测）

- 原件 `session.jsonl.zstd` **原样保留**，迁移写成 `session.v3.jsonl.zstd`（后继）
- 只有**被打开过**的会话才迁移（24 个里只有 5 个迁移）
- v3 后继约为原件的 **36%**（`c08b4248`：4.21MB → 1.60MB）
- **回退路径因此是通的**：老引擎读原件照常能跑

### G6 排查「卡机」的四步法（本次实战）

1. `wc -c < 目标文件` 隔 20s 测两次 —— **数字在变 = 没死，只是慢**（本次实测 16,384 B/s 恒定 = 限速，非拥塞）
2. `ss -tnp | grep -v 127.0.0.1` —— `ESTAB` 指向目标 CDN = 在传；`SYN-SENT` 挂着 = 被墙
3. **分项测网络**，别只测「能不能上网」—— 本次 `npmjs` 200 而 `github.com` 超时，两者是不同的路
4. **读那个卡的脚本** —— 本次读到 `createWriteStream(to)` 无 Range → 直接断定不能续，省下徒劳重试

**反直觉经验**：包管理器「卡住」十有八九卡在 **postinstall**，不是包下载。
`pnpm-workspace.yaml` 里的 **`allowBuilds` 清单就是「哪些包有 postinstall」的名单**。

---

## H) 基座 0.1.1 → 0.1.5 的客户端架构改动（Step 2 实测）

### H1 ❌ `packages/client/runtime` 被整个删除

`packages/client/` 包清单对比：**只删了 `runtime` 一个**，新增 12 个 ——
`store`、`resources`、`file-upload`、`ui-chat`、`ui-session`、`ui-approval`、
`ui-dockkit`、`ui-schedule`、`ui-open-in-app`、`ui-sidebar-files`、
`ui-sidebar-right`、`ui-sidebar-documentpreview`。

架构从「1 个 monolithic `runtime`」拆成「`store` + 一堆聚焦包」。

**但不会硬崩**：web-all 0.3.20 用**运行时拼串**做兼容探针，避开静态 import ——

```js
const legacy = ["@deepseek-ai/dsh-client-runtime", "/client"].join("");
```

实测 10 个插件文件都有这段，内容完全一致。Console 无报错。

→ **修正原 B2 判断**：结构上确认包被删，但 0.3.20 已适配，**不会炸**（原写"→ web-ui-settings 炸"过于悲观）。

### H2 ⚠️ `workspaces` 服务被拆成两层

| | 旧 v0.1.1-rc.2 | 新 v0.1.5-rc.2 |
|---|---|---|
| 位置 | `packages/client/runtime/src/client/workspaces/service.ts` | `packages/api/workspace-controller/src/client/service.ts` |
| 数据层 | `list` `create` `rename` `delete` `insert*` `archiveSession` | 同左（保留在 `workspaces`）|
| **导航层** | `connectWorkspace` `startSession` `pickDirectory` … **也在 `workspaces` 上** | **搬到 `packages/client/ui-workspace/src/client/navigation.ts` 的 `UiWorkspaceService`** |

**后果（实测）**：`@linxin666/dsh-client-ui-git-graph` 的 **auto-isolation 自动关闭** ——

```
[git-graph] auto-isolation disabled: the workspaces service shape changed;
            using the official new-session behavior
```

它的探针要求 `workspaces` 上四成员齐全（`startSession` / `create` /
`connectWorkspace` / `list.getSnapshot`），新版缺 `startSession` 与
`connectWorkspace` → **正确判定形状变了，优雅降级，不崩**。

- **丢失**：新会话自动在隔离 worktree（`wt/<name>` 分支）里开
- **未丢**：手动 worktree 功能（菜单「在 worktree 中开始新会话…」走 `/git/*` client，不经过 `workspaces`）
- **真修复**：需作者把探针改指 `uiWorkspace.startSession`（第三方插件，非我们能改）

### H3 ⚠️ Step 3 前置缺口：`profiles/web/packages/` 必须一起复制

`dsh-font-serif` 的依赖声明是 **`file:packages/dsh-font-serif`**。
建副本时若只拷 `profiles/web/` 下的配置文件、**没拷 `packages/` 子目录**，
Step 3 一装它就解析失败。

```bash
cp -r ~/deepseek-harness/dsh-domus/profiles/web/packages \
      ~/deepseek-harness/dsh-domus-dryrun/profiles/web/
```

现役 `packages/` 里有 `dsh-font-serif` 和 `dsh-user-markdown` 两个本地包；
后者未在 bundles 里声明（孤儿），一并拷过去无副作用。

### H4 升级方法论：一次只动一个变量

Step 3 加包时**版本号沿用现役的 `^` 范围**，不要顺手升到 latest。
例：现役 `dsh-context ^0.38.5`，而 latest 已是 **0.49.2** ——
先让它在 `^0.38.5` 下跑通，把「基座升级」和「插件升级」两个变量分开。
0.38.5 → 0.49.2 是**独立的一步**。

### H5 🩹 `cloudflared` 二进制会被 pnpm 重新解压抹掉

它是 postinstall 产物、不在 npm tarball 里，pnpm 每次重建 `cloudflared/`
包目录都会让 `bin/` 消失（实测：15:23 放入，15:26 一次 `add` 后被抹）。

**规则**：pnpm 全部跑完后再放；`start-web-dryrun.sh` 已加幂等兜底，
缺失时自动从 `tools/cloudflared-linux-amd64.staged` 补回。

---

## I) `@linxin666/dsh-web-all` 0.3.6 → 0.3.20 插件清单 diff

| | 插件 |
|---|---|
| **删除 3 个** | `dsh-client-ui-aionui-panel`（早已标「停更」）、`dsh-desktop-launcher`、**`dsh-perf`** |
| **新增 5 个** | `dsh-client-ui-model-capabilities`、`dsh-client-ui-preset-center`、`dsh-i18n`、`dsh-session-archive`、`dsh-usage` |

0.3.20 产物里有显式退役清单（只作跳过判断，无副作用）：

```js
const RETIRED_PLUGINS = new Set(["@linxin666/dsh-perf", "@linxin666/dsh-desktop-launcher"]);
// ...
if (RETIRED_PLUGINS.has(spec)) return;
```

**推论**：`dsh-perf` 那族 Console 消息（`[dsh-perf] list gate: installed on sessions.list`、
`[dsh-perf] assistant shadow: registered at priority -9`、`[dsh-perf-integrity] draft-residue`）
**在新版不会再出现** —— 是退役，不是回归。它原本 wrap 的 `sessions.list`
不再被碰，**升级风险随之消失**。

现役 `dsh.profile.bundles` 里**没有**退役插件残留（它们只是传递依赖，从未进 bundles），
**无需清理**；`node_modules` 里那个 `dsh-perf` 目录下次 `install` 自动裁掉。

### 运行时锚点复核：方法论修正（重要，原方法有缺陷）

**❌ 错误做法**：在两个实例上比 `document.querySelectorAll('[data-dsh-part]').length` 的**总数**。

实测 9007（旧）= **812**，9009（新）= **133** —— 看着像 -84% 回归，实则**不可比**：

1. **会话内容不同** —— 9007 开着有内容的会话，9009 是新会话。
   计数按 DOM 元素打，消息越多数越大
2. **皮肤不同** —— 9007 挂 `navia`，9009 只有默认皮肤；
   皮肤自己注入 DOM，同样影响计数
3. **对照组失效的铁证**：`data-decoration` 在 9007（旧）实测**也是 0**，
   而本文档前面写的「26 → 0」是**源码静态计数**，不是 DOM 元素数 ——
   拿静态数字当 DOM 预期值是错的（与初版 `attr="value"` 假警报同类的错误）

**✅ 正确做法**：查**具体锚点取值是否被补打**，而不是总数 ——

```js
['message-row','message-body','scrollport','composer-input','sidebar-entry','new-session',
 'conversation-header','session-title-cluster','skin-layer']
  .forEach(v => console.log('part:'+v, document.querySelectorAll('[data-dsh-part="'+v+'"]').length));
console.log('pane:sidebar', document.querySelectorAll('[data-pane="sidebar"]').length);
console.log('resp:session-title-cluster', document.querySelectorAll('[data-dsh-responsive-part="session-title-cluster"]').length);
```

**取值为 0 才是真失效**；总数变化只是 DOM 规模变化，对皮肤无影响 ——
皮肤按**取值**选元素，不按数量。

**最权威的验证在皮肤本体**：把 `skins/` 拷进副本 → 9009 切到与 9007 相同的皮肤
→ 同一会话视觉比对。不受内容干扰。**这属于皮肤那一步，Step 2/3 不做。**

---

## J) 🔴 重大：preset 的 persona 配置键被上游改名（硬阻断，已修）

### 症状

开老会话即失败，与 API key、与插件都无关：

```
resume failed for session "session-...":
RemoteError: agent-presets: preset "coding" failed to mount:
failed to apply loader entry persona (@deepseek-ai/dsh-persona):
invalid config: - $.prefix missing required value (at prefix)
```

**排除法**：换 API key 一样报（朋友 key 没报是因为只选了没开会话，未触发 preset 挂载）；
Step 1/2 没装任何插件时就存在。→ **纯 preset 层问题**。

### 根因：`packages/preset/persona` 的 schema 改名

```ts
// 0.1.1-rc.2                          // 0.1.5-rc.2
text: z.string().required()         →  prefix: z.string().required()
                                       suffix: z.string().default('')   # 新增
complete: z.boolean().default(false)               # 未变
includeRuntimeContext: z.boolean().default(true)   # 未变
```

**权威对照**：新基座自带的
`packages/preset/agent-presets/presets/minimal/agent.cordis.yml` 用的就是 `prefix:`。

### 修法：只改键名，不动文本内容

```bash
cd ~/deepseek-harness/dsh-domus-dryrun/.agent-presets
for f in academic coding fantasy general scifi liangshen; do
  cp -p $f/agent.cordis.yml $f/agent.cordis.yml.bak-011rc2
  sed -i '0,/^    text:/s/^    text:/    prefix:/' $f/agent.cordis.yml
done
```

替换前已核实：每个文件里 `^\s+text:` **恰好只出现 1 次**（liangshen 的
`persona=2` 是注释里提了一次），所以首匹配替换是安全的。

### 验证（三重，全部通过）

1. **字节差 +2、行数差 0**（`text`(4) → `prefix`(6)）→ 只动了那一个 token
2. **YAML 结构化解析通过** → 块标量没被改坏
3. **`tools/preset-key-check.py` 带对照组三跑**：
   - 副本 → 目标 0.1.5：全 ✅（退出码 0）
   - 现役 → 目标 0.1.1：全 ✅（退出码 0，现役未被碰）
   - 现役 → 目标 0.1.5：全 ❌（退出码 1，**证明探测器有效**）

### 副产品：preset 用了 `!!js` 标签

```yaml
372:  disabled: !!js process.platform === 'win32'
376:  disabled: !!js process.platform !== 'win32'
```

`!!js` = cordis 的 JS 表达式标签（`tag:yaml.org,2002:js`），用于平台条件禁用。
**PyYAML 默认拒绝该标签**，任何解析这些 preset 的 YAML 工具都必须先注册
构造函数（`tools/preset-key-check.py` 里已加）。

### ⚠️ 这可能不是最后一个错误

`invalid config` 只报**第一个**失败项。persona 修好后，下一个 loader entry
可能再报同类漂移。你的 preset 源自 standard 出厂基线（文件头注释如此写明），
39KB / 663 行、条目众多，**每个 entry 的 config schema 都值得查一遍**。

**现役迁移到 0.1.5 时，现役的 6 个 preset 也要做同样改名**，用这个查：

```bash
python3 ~/deepseek-harness/tools/preset-key-check.py \
        ~/deepseek-harness/dsh-domus/.agent-presets --target 0.1.5
```

### 皮肤实测结果（4 项需重做）

| 话题 | 实测 | 原预测 |
|---|---|---|
| 4 宽表格 | 🔴 文字直接溢出 `data-chat-flow` | 🔴 最高 ✓ |
| 5 表格分割线 | 🟠 需重新明显化 | 🟠 高 ✓ |
| **1 pi-ai 档位** | 🟡 **看不见档位，需重做** | 🟡 中（**低估**）|
| 7/8 标题居中 | 🟡 需重做 | 🟡 中 ✓ |

**这 4 项全部属于「靠 dsh 核心官方 CSS / 组件结构锚定」那一类** ——
即文档里判定的高风险类，**不在 skin-center 契约保护内**。
契约锚定的那几族（`data-dsh-part` 等）实测全部存活，与静态结论一致。

---

## K) 皮肤 3 项回归的官方根因（静态已确认）

### 话题 5 表格分割线 —— `1px` → `0.5px`

`ui-primitives/src/markdown/MarkdownText.module.css`：

```diff
-  border-bottom: 1px solid var(--dsw-alias-border-l3);     /* th */
+  border-bottom: 0.5px solid var(--dsw-alias-border-l3);

-  border-bottom: 1px solid var(--dsw-alias-border-l2);     /* td */
+  border-bottom: 0.5px solid var(--dsw-alias-border-l2);
```

**变量名没变**（仍是 `--dsw-alias-border-l3/-l2`），所以旧补丁的颜色覆盖依然生效 ——
但它只改了颜色，**线的物理宽度被官方砍半**，暗底下照样看不见。

**修法方向**：补丁里补 `border-bottom-width: 1px !important`。

同批 `1px → 0.5px` 还有：`height: 1px → 0.5px`、新增
`border: 0.5px solid var(--dsw-alias-border-l1)`；
另有 `line-height: 28px → 24px`、`font-size: 13px → 11px`、
链接色 `--dsw-alias-state-business-primary → --dsw-alias-link`（**变量改名**）。

### 话题 4 宽表格 —— 列宽从固定值改成自适应

`ui-conversation/src/client/skeleton/ConversationRoot.module.css`：

```diff
-  --dsh-chat-content-width: 748px;
+  --dsh-chat-content-width: var(
+    --dsh-chat-user-width,
+    clamp(680px, calc(var(--dsh-conversation-column-width, 0px) * 0.64), 920px)
+  );
```

新版列宽**自适应**（680px 下限、列宽 ×0.64、920px 上限），由组件用 ResizeObserver
把列宽发布成 `--dsh-conversation-column-width`（注释明确说明刻意不用 `container-type`，
以免重锚 portal-free 的 `position: fixed` 后代）。
**任何基于固定 748px 的宽度算术都会失准。**

**`.md-table-wide` 那块 CSS 两版逐字节相同**（`overflow-x: hidden` 默认态，
仅 `:hover`/`:focus-visible` 才 `auto`）—— **不是它变的**，别再往这里找。

### 话题 7 / 8 标题集群 —— header 结构重构

```diff
-  padding: 12px 28px 0 20px;
-  border-bottom: 1px solid transparent;
-  .header::after { height: 1px; background: var(--dsw-alias-border-l2); }   ← 删除
+  box-sizing: border-box;
+  min-height: 76px;
+  padding: 10px 28px 0 20px;

+  position: relative;   /* positioning context for slot-owned absolute chrome */
```

`::after` 分隔线删除、header 高度改 `min-height: 76px`、`.root` 新增 `position: relative`
（为 slot-owned absolute chrome）→ **话题 7 里 `headerActions` 绝对定位 `left: 0`
的参照物变了**。另有 `.heroGlow` 整块规则被删除。

**好消息（两条）**：

1. `data-dsh-responsive-part="session-title-cluster"` 在 web-all `0.3.6 → 0.3.20`
   命中数 **3 → 3 存活**
2. 官方 `.crumb { max-width: 220px }` **未变**

→ 所以话题 8 坏在 **`nav button` 的 DOM 层级**，**不是锚点失效**。

### ⚠️ 待运行时确认（静态查不到的三项）

1. `--dsh-chat-content-width` / `--dsh-conversation-column-width` 的**实际计算值**
2. `session-title-cluster` 在 9009 上**是否真被打标** —— web-all 是先用
   `titleCluster` 变量找到元素再 `mark()`，官方 header 结构变了，**可能查找失败**
3. 宽表格 wrapper 的 `overflowX` **计算值**

诊断片段（9009 与 9007 各跑一次，对照）：

```js
const cs = getComputedStyle(document.documentElement);
console.log('content-width   =', cs.getPropertyValue('--dsh-chat-content-width'));
console.log('column-width    =', cs.getPropertyValue('--dsh-conversation-column-width'));
console.log('user-width      =', cs.getPropertyValue('--dsh-chat-user-width'));
console.log('title-cluster   =', document.querySelectorAll('[data-dsh-responsive-part="session-title-cluster"]').length);
console.log('titleCluster DOM=', document.querySelectorAll('[data-dsh-responsive-part="session-title-cluster"] > div').length, '（话题7的 > div 选择器）');
const flow = document.querySelector('[data-chat-flow]');
console.log('chat-flow W     =', flow && flow.clientWidth, '/ scrollW', flow && flow.scrollWidth);
document.querySelectorAll('.md-table-wide').forEach(function (el, i) {
  const s = getComputedStyle(el);
  console.log('md-table-wide[' + i + '] overflowX=' + s.overflowX + ' clientW=' + el.clientWidth + ' scrollW=' + el.scrollWidth);
});
```

---

## L) 皮肤返工：补丁重写入皮肤文件（2026-09-11）

### 起因

话题 4/5 的旧补丁**在文件系统里找不到** —— 搜遍 8 个皮肤的 `patches.css`（共 2,269 行）、
`skin.css`、`hooks.mjs`，无 `md-table-wide` / `table-layout` / `overflow-wrap: anywhere`。
用户确认记不清落点 → 决定**按锚点纪律重写进皮肤文件**，让皮肤文件成为唯一权威来源。

### 本轮两次自我纠错（撤回记录）

1. **怀疑 dry run 清空 `cordis.patch.yml` 丢了皮肤补丁** → ❌ 归档件
   `cordis.patch.yml.orig-mcp` 是**纯 MCP 挂载**（13 个 `dsh-mcp-client` + 1 个
   disabled 的 `dsh-session-export`），零样式注入。**撤回。**
2. **以为 `furina/patches.css:220/229` 的 `--dsw-alias-border-l2` 重映射属于话题 5** → ❌
   其作用域是 `div:has(> div > [data-gitgraph-chip])`，**是 git-graph 的 chip**。**撤回。**

**话题 5 的 furina 侧真身在 `furina/skin.css`**：皮肤重映射了
`--dsw-alias-border-l2: #2c3a7338 / #a0b4e62e`、`--dsw-alias-border-l3: #2c3a7352 / #a0b4e642`
（alpha 仅 22% / 32%），叠加官方的 `0.5px` 物理宽度后暗底上彻底消失 —— 根因闭环。

### 写入内容

`navia/patches.css`（272 行 / 9,984 B）、`furina/patches.css`（312 行 / 9,600 B）各追加两段：

**话题 5** —— 宽度与颜色分开处理：

- `border-bottom-width: 1px !important`（补回被官方砍半的宽度，两皮肤都加）
- 颜色提亮为半透明白 `rgba(255,255,255,.35) / .22`
  - navia 无视深浅主题、一律暗底 → 直接加
  - furina 有浅色主题（`#2c3a73xx` 深蓝线在浅底本来可见）→ **加在
    `body[data-ds-dark-theme]` 下**，不污染浅色主题

**话题 4** —— 强制压缩，锚点用官方保证的全局钩子 `.md-table-wide`
（`render.tsx` 给 ≥4 列表格加），**不用 CSS Module 哈希**：

- `.md-table-wide { width/max-width: 100%; margin-left/padding-left: 0 }`
- `.md-table-wide > table { width/max-width: 100%; table-layout: auto }`
- `.md-table-wide th/td { overflow-wrap: anywhere; white-space: normal }`

### 验证

- **大括号平衡**：navia `{`42 = `}`42 ✅ / furina `{`63 = `}`63 ✅
- 回读内容正确 ✅

### ⚠️ 三项待运行时确认

1. `[data-dsh-part="message-row"]` **是否真包含 markdown 表格** —— 话题 5 锚点的前提
   （查：`document.querySelector('.md-table-wide th')?.closest('[data-dsh-part="message-row"]')`）
2. **浏览器侧是否还有旧规则在生效** —— 若有，写进皮肤文件后会叠加
3. **话题 7/8 仍未修** —— 需要 titleCluster 的 DOM 与计算样式

---

## M) 🎯 元凶查明：补丁全在 `dsh-font-serif` 里 —— 话题 4/5/7/8 全属误判

### 发现过程

搜 `插件源码/` + `dsh-domus/profiles/`，`md-table-wide` 与特征值 `calc(100% - 16px)`
双双命中 **`dsh-domus/profiles/web/packages/dsh-font-serif/lib/client.js`** ——
一个**字体**插件，却注入了表格与标题布局的「外挂 CSS」。

### 该插件注入的全部内容（130 行，`FONT_CSS` 数组 → `<style data-plugin-css="dsh-font-serif/font.css">`）

| # | 内容 | 清单话题 |
|---|---|---|
| 1 | `--dsw-font-family` / `--ds-font-family-code` + matrix/xp 双锚点特判 | 字体方案 |
| 2 | `.md-table-wide { box-sizing / width / max-width / margin-left / padding-left / overflow-x }` + `table` + `th,td` | **话题 4** |
| 3 | `html[data-dsh-skin="furina"\|"navia"] [data-dsh-part="message-row"] table th/td { border-bottom-color }` | **话题 5** |
| 4 | `[data-dsh-responsive-part="session-title-cluster"]` + `> div` + `nav button` | **话题 7/8** |

注入方式：`injectFontCss()` 幂等创建 `<style>` 挂 `document.head`，`exports.apply`
与物化时各调一次。**是插件，不是油猴脚本。** 安装 spec：`"file:packages/dsh-font-serif"`。

### 🚨 由此推翻整张回归清单的一半

dry run 未装此插件 → 9007 vs 9009 比的是
**「有补丁的 0.1.1」vs「没补丁的 0.1.5」**，不是版本差异。

**话题 4 / 5 / 7 / 8 全部源于此，与 0.1.5 无关。**

**且 0.1.5 上四项锚点全部存活**：

| 锚点 | 9007 | 9009 |
|---|---|---|
| `.md-table-wide` | 有 | 有 |
| `[data-dsh-part="message-row"]` 含表格 | true | true |
| `[data-dsh-responsive-part="session-title-cluster"]` | 1 | 1 |
| 同上 `> div` | 1 | 1 |

### 两处顺带坐实的细节

1. **话题 5 原件只设 `border-bottom-color`，从未设宽度** → 9007 实测 `0.6px` 即官方
   `0.5px` × **120% 页面缩放**。**新加的 `border-bottom-width: 1px` 是针对 0.1.5 的真修复。**
2. 插件注释自述「官方 breakout 把容器撑到整个 transcript 宽度（100cqw, max-width:none）」
   与「Firefox 滚动条视觉隐形」—— 与本文档 话题 4 结论一致。且 **994px 的算式已复现**：
   `spare=(994−680)/2=157`、`lead=157+680−701=136`、`width=701+136+157=994`。

### 写入皮肤文件的内容（navia / furina 各一份）

| 文件 | 行 | 字节 | 大括号 |
|---|---|---|---|
| `navia/patches.css` | 303 | 11,474 | 45/45 ✅ |
| `furina/patches.css` | 340 | 10,815 | 66/66 ✅ |

含 话题 4 + 话题 5 + 话题 7/8（与原件逐条对齐）。旧版本已墓碑化并 GC。

### ⚠️ 归属地问题（迁移前须决定）

原件中 **话题 4 / 7/8 是全局作用域**，复制进皮肤文件后**变成 navia/furina 专属**
—— 换到 matrix / xp 等皮肤会静默消失。

**正解：新建专职本地补丁插件（如 `dsh-ui-patches`）承载话题 4/7/8，
`dsh-font-serif` 只留字体**；插件里那份补丁在迁移完成后删除。

### 方法论教训

**对照组设计缺陷**：皮肤层的版本对比，必须在「补丁齐备」的前提下做。
插件关着时观察到的「回归」，很可能只是补丁缺失。

---

## N) 补丁载体：改名而非拆分（2026-09-11 用户决策）

### 决策

**不拆成两个插件。** 把现役的 `dsh-font-serif` 改名为一个「自用 UI 补丁」包，
让**所有全局 CSS 补丁共用一个载体**。字体只是其中一条。

### 为什么用户的方案优于「拆成 font + ui-patches」

| 维度 | 拆分 | 改名（采纳） |
|---|---|---|
| 查找点 | 两个，仍需"猜在哪" | **一个** |
| 话题 4/7/8 的全局作用域 | 保住 | **保住** |
| 改造量 | 新建包 + 改 profile 依赖 + 双插件验证 | 改 8 处引用 |
| 失败模式 | **重演今天"补丁隐形"的事故** | 消除 |

**关键**：拆分是「命名纯度」驱动的（审美）；改名是「这东西实际是什么」驱动的（功能）。

**⚠️ 已知代价**：我先前把 话题 4 / 话题 7-8 复制进了
`skins/{navia,furina}/patches.css`（约 60 行）。若插件成为唯一载体，
**这 60 行必须撤掉** —— 否则同一补丁两个载体、两边都 `!important`、
特异度相同，胜负由 DOM 注入顺序决定，而那是实现细节，脆。

### 待定项

- **那 60 行的去留**（未决）→ **同时决定验证方式**：
  - 撤 → 验证靠**在 dry run 装插件**（更忠实于最终形态）
  - 留 → 验证靠**拷 `patches.css`**（但保不住全局作用域）
- **ASCII 包名**（用户已定中文名「水银灯的UI补丁」，待落实为 npm 合法 name）

### 顺带记录：navia 的深浅主题

navia 自称「无视深浅主题」，但**这是大部分情况** ——
**新会话按钮、若干 SVG fill 型按钮仍会响应主题**（用户因此常驻深色模式）。

**推论**：`body[data-ds-dark-theme]` 属性在 navia 上是**活的** →
话题 5 的 selector 从硬编码 `furina`/`navia` 改为按该属性判定**技术上可行**，
可一劳永逸覆盖未来的暗色皮肤。**用户指示：稍后再搞，先记着。**
