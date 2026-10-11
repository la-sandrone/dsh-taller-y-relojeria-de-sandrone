# DSH v0.1.7-rc.2 → v0.2.x 升级调查与方案

摘要：本文件为**纯调查产物，未对任何实例、profile 或仓库文件做改动**。
调查时间：2026-10-07 12:45 CST ｜ 本地基座：v0.1.7-rc.2（tag 2026-09-24T14:10:21Z）
上游最新：v0.2.1-alpha.1（2026-10-03T06:42:19Z）

---

## 〇 · 结论摘要（先读这一段）

1. **官方登记的破坏性变更共 6 条**（不是上次调研时的 2 条）。逐条比对本机 profile，
   6 条**全部不中招**。
2. **但真正的暗雷不在官方登记表里**：上游 app-boot 的 `prepareProfileEntries` preflight
   会按 `peerDependencies` 判定兼容性，**不兼容的行直接 `disabled = true`（只往 stderr 写一行）**。
   用上游同款判定逻辑 + 本机真实 manifest 模拟，**被禁数量取决于目标版本**：
   - runtime = `0.1.7-rc.2` → 被禁 **0 个**（与现状吻合，已用历史日志反证）
   - runtime = **`0.2.0-rc.2`** → 被禁 **3 个**
   - runtime = `0.2.1-alpha.1` → 被禁 **8 个**

   **原因（semver 语义，已实测）**：prerelease 小于其对应正式版，故 `0.2.0-rc.2 < 0.2.0` 成立 ——
   显式范围 `>=0.1.7-0 <0.2.0` **能容纳 rc**，而 caret `^0.1.7-rc.1`（上界展开为 `<0.2.0-0`）
   **不能**。**peer 的写法本身决定了 rc 目标下会不会炸。**
3. 按 **rc = 稳定** 的本机口径（见 §一），推荐目标是 **`0.2.0-rc.2`**：**只需动 2 个包**
   （均为升级，无豁免项）。若选 `0.2.1-alpha.1` 则要动 5 个。
   > **⚠ 2026-10-07 状态更新（撤下后修订）**：本节原写「3 个包 = 2 个升级 +
   > `dsh-fulltext-search` 走豁免」。当日 `dsh-fulltext-search`（侧栏文件内容检索）
   > 与 `dsh-search-plus`（会话全文检索）**已一并正式撤下**（前者恰好是唯一没有 0.2 版、
   > 只能靠 `compatibility.json` 豁免续命的包）。故**豁免项归零，随迁量降为 2 个纯升级**；
   > 对照的 `0.2.1-alpha.1` 路径同步由 8 个降为 5 个（原 8 个减去已撤下的
   > `dsh-fulltext-search` 与不受影响的 `dsh-search-plus`，再减去随迁的其余 5 个）。
   > 撤下随附：`profiles/web/package.json` 的 dependencies 与 `dsh.profile.bundles` 两处同步摘除、
   > `pnpm-lock.yaml` 同步（-28 行）、2.5 GB 索引库 `cache/search-plus.db*` 删除、
   > 两个插件目录从 `node_modules/` 移除。`tools/check_patch_layers.py` 复验 ✅ 无重复 id。
   > 备份：`backups/retire-search-plugins-20261007-230227.tar.gz`。
   > **生效边界**：`patchReload: live` 只监视 patch 文件（设计文档
   > `.agents/notes/implemented/architecture/2026-08-22-single-dsh-application-launcher.zh.md`：
   > 「`patchReload: live` 使用启动器的**仅配置** watcher」），**不监视 `package.json`** ⟹
   > 本次改动**需重启实例才生效**。
   **不做这些准备而直接切版本 → 被禁的 bundle 会静默消失**，与 2026-09-26 那次
   「插件禁用风暴」同源。
4. **会话日志格式未断代**（`SESSION_FORMAT_VERSION` 在两个 tag 上均为 4），
   归档收割器 / `scan_*` / `archive_*` / `session.v4.jsonl` 契约不变。
5. **皮肤锚点未失锚**（`ConversationRoot.module.css` 基线 vs 0.2.1-alpha.1 逐字节相同）。
6. **★ 反向锁（见 §四之二）**：第三方生态已跟随官方 sdk cohort **单向切走**——
   **5 个包的最新版已经不支持 0.1.7**（`>=0.2.0-rc.2` / `^0.2.0-rc.1` / 精确钉版）。
   **现在单独点升级 = 在当前环境被同一个 preflight 静默禁用。**
   包版本与基座版本必须配套，**升级必须原子化**。
7. 建议：**窗口在收窄，但不必仓促**。按本机口径 `0.2.0-rc.2` 已是「稳定版」，
   「等稳定版」这条判据**已经满足**；真正的成本是那次**原子化随迁作业**（§六 阶段 0.5 → 1）。
   生态在单向切走（§四之二），拖久了过河的包会变多，但「过河」≠「必须马上迁」。

---

## 一 · 上游版本现状

| tag | 发布时间（UTC） | 性质 |
|---|---|---|
| `dsh-v0.2.0-rc.1` | 2026-09-28T12:36:21Z | 0.2.0 首个 RC，汇总自 0.1.7-rc.2 的主要变更 |
| `dsh-v0.2.0-rc.2` | 2026-09-29T09:42:36Z | RC |
| `dsh-v0.2.1-alpha.1` | 2026-10-03T06:42:19Z | **比 rc.2 更新**，9/30 调研时尚不存在 |

本地 `DSH_VERSION` = `v0.1.7-rc.2`，检出目录 `原始代码研究/v0.1.7-rc.2/`。

### ⚠️ 版本口径（用户校正，2026-10-07）

**DSH 没有「正式版」这个概念。** 实测 `gh release list --limit 100`：
**25 个 release 全部标记为 Pre-release，一个非 Pre-release 的都没有。**
发布模型是 `… → 0.1.x-alpha.n → 0.1.x-rc.n → 0.2.0-alpha.1 → …`，
**永远不会出现 `0.2.0` 正式版**。

本机沿用的判据：

| 标记 | 含义 |
|---|---|
| **rc** | **当作稳定版**，可用于现役 |
| **alpha** | 当作不稳定，仅预览 |

⟹ 本文档早期写的「等 `0.2.0` 转正」是**错误框架**（那个事件不会发生）。
按本口径，**`0.2.0-rc.2`（2026-09-29）已经处于「稳定」状态**，
「等稳定版」这条判据**已经满足**；剩下的是卡池周期 + §四 / §四之二 的随迁作业。

---

## 二 · 官方登记的破坏性变更（全量 6 条）

上游登记体系：`docs/upgrade-guide/<from-version>/<change>/guide.{md,zh.md}`
（`<from-version>` 语义 = **「从该版本升级上来会碰到」**；另有 `docs/persistence-changes/`
只管会话日志持久化格式，与本节独立）。

### 挂在 `v0.1.7-rc.2` 下（→ 升 0.2.0 系列会碰到）

**2.1 `schedule-optional-bundle`**
Web 组合不再包含 `time-context` / `schedule` / `ui-schedule` 三行，改由可选 bundle
`@deepseek-ai/dsh-experimental-schedule-bundle`（插件管理页「自动化任务」）插入。
按 id 覆盖这三行的 profile 升级后会失去 Schedule，loader 报
`patch: entry schedule not found`，`schedule_*` 工具与自动化任务页消失。

**2.2 `transcript-view-legacy-normal`**
设置 `ui-chat.transcriptView` 的旧值 `normal`，以及非 Desktop Web 上未设置/无效的值，
改为按 **detailed** 展示（原为 standard）。已保存的 `compact` / `standard` / `detailed` /
`verbose` 不受影响。

### 挂在 `v0.2.0-rc.2` 下（→ 升 0.2.1-alpha.1 会碰到）

**2.3 `account-sign-in-errors`**
`SignInErrorCode` 新增 `no-response`（fetch 在返回 Response 前失败，含单次超时）。
此前这类失败报 `network`。客户端校验器与穷尽处理需加该码。

**2.4 `remove-runtime-invariants`**
移除 `@deepseek-ai/dsh-invariants` 包与 `InvariantRegistry` / `InvariantInstaller` /
`InvariantFailure` / `InvariantError`，以及**所有 `<package>/invariant` 子路径导出**。
`sdk-minimal` profile 不再含五行 `*-invariant`。引用它们的 cordis.yml / patch / overlay
无法加载；patch 指向那五个 id 会报 `patch: entry <id> not found`。

**2.5 `schedule-bundle-retired`**
**撤回** 2.1 引入的「自动化任务」bundle。`@deepseek-ai/dsh-web-app` 改为在每个 Web profile
中自行挂载 `schedule` 与 `ui-schedule`；`time-context` 改由 preset 声明
（`standard` / `cordis` / `ptc` 声明，`minimal` 不声明）。加载 profile 时自动从
`dsh.profile.bundles` 删除该 bundle 并重写 `package.json`。

> ★ **2.1 与 2.5 是一对反向变更**：直接从 0.1.7 跳到 0.2.1-alpha.1，schedule 的**净效果
> 约等于回到原样**；但 `time-context` 的归属从「Web 组合的 disabled 行」变成「preset 声明」，
> 指向它的**顶层覆盖项会失效**（guide 明确要求删除）。

**2.6 `subpath-plugin-display-manifest`**
子路径插件不再读取导出的 `<子路径>/package.json`；标题/描述改来自
`<子路径>/locale/*.json` 的 `meta.title` / `meta.description`，图标改来自
导出的 `<子路径>/icon`。影响**导出子路径 package.json 的包作者**。

### 与 release notes 的「其他变更」交叉核对

- `0.2.0-rc.1`：自动化任务改由可选插件包提供（= 2.1）；调整工作过程展示默认值（= 2.2）
- `0.2.0-rc.2`：pi-ai 0.87.1，**部分旧模型 ID 被移除，已保存的选择可能需重选**；
  实验性异步问答模式（需手动配置）；Bash/PowerShell 工具提示加强（删除/移动前核对路径）
- `0.2.1-alpha.1`：移除 runtime invariants（= 2.4）；`stats` 行拆成 `activity` + `usage`
  （覆盖旧 `stats` 整行的插件需改注册 ID）；**子路径插件不再读独立 package.json**（= 2.6）；
  Claude Code Mods 兼容层（实验）；新增开发者工具组合包

---

## 三 · 本机逐条中招判定

判定方式：直接 grep `dsh-domus-0.1.7-rc.2/profiles/web/cordis.patch.yml`（246,083 B）与
`package.json`，并对上游文件做逐字节对比。

| # | 变更 | 本机状态 | 判定 |
|---|---|---|---|
| 2.1 | schedule 移入可选 bundle | profile patch 中 `time-context` / `ui-schedule` / `schedule` 均 **0 处命中** | ✅ 不中招 |
| 2.2 | transcriptView 旧值 normal | patch:189 已显式 `transcriptView: standard`（guide 明示已保存的 standard 保持） | ✅ 不中招 |
| 2.3 | 登录错误码新增 no-response | 仅影响客户端校验器代码；本机未使用 `@deepseek-ai/dsh-deepseek-account` | ✅ 不中招 |
| 2.4 | 移除 invariants | profile patch 中 `invariant` **0 处命中**；`sdk-minimal` 五行未被引用 | ✅ 不中招（详见下） |
| 2.5 | schedule bundle 撤回 | `experimental-schedule-bundle` 不在 `dsh.profile.bundles`；patch 无 `time-context` 顶层覆盖 | ✅ 不中招 |
| 2.6 | 子路径插件清单 | 本机为插件**使用者**而非作者；`dsh-suigintou-ui-patches` 是 root 插件 | ✅ 不中招 |

**2.4 的额外核查（曾疑为硬命中）**：`dsh-better-sidebar@0.21.1` 的 `peerDependencies`
里确有 `@deepseek-ai/dsh-invariants@^0.1.7-rc.1`，且包内自带
`src/invariant.ts`（`inject = ['invariants']`）+ 导出 `./invariant` 子路径。
但该包的 `cordis.patch.yml` **只 insert 一行**（`id: better-sidebar`），
**没有挂载** `dsh-better-sidebar/invariant` → companion 不会被加载 → 不构成加载失败。
（该 peer 声明仍会参与 §四 的兼容性判定。）

---

## 四 · ★ 真正的暗雷：preflight 会静默禁用若干 bundle

> **⚠️ 2026-10-07 修订（按用户校正的版本口径重算）**：被禁清单**取决于目标版本**，差别很大 ——
>
> | 目标 | 被禁 | 说明 |
> |---|---|---|
> | **`0.2.0-rc.2`（rc = 稳定）** | **3 个** | 只有 caret 型与精确钉版会被拦 |
> | `0.2.1-alpha.1`（alpha） | **8 个** | 多出 5 个「显式 `<0.2.0`」型 |
>
> **原因（semver 语义，已实测）**：prerelease **小于**其对应的正式版，于是 `0.2.0-rc.2 < 0.2.0` 成立 →
> - 显式范围 `>=0.1.7-0 <0.2.0` → **满足**（`0.2.0-rc.2` 落在区间内）
> - caret 范围 `^0.1.7-rc.1` → **不满足**（semver 把 caret 的上界展开成 `<0.2.0-0`，
>   从而排除 `0.2.0` 的**所有** prerelease）
>
> ⟹ **peer 的写法本身决定了 rc 目标下会不会炸。** 按 rc = 稳定的口径，
> 推荐目标就是 **`0.2.0-rc.2`**，随迁量从 8 降到 3（见 §六 阶段 1）。

### 4.1 机制（源码实证，非推断）

判定逻辑：`packages/boot/app-boot/src/plugin-compatibility.ts`
执行点：`packages/boot/app-boot/src/compatibility-preflight.ts` → `prepareProfileEntries()`

```
每个 row → 取其 manifest → evaluatePluginCompatibility(manifest, exemptions)
  不兼容且未豁免 → deny(row, reason) → row.disabled = true
                                      + process.stderr.write("dsh: disabling profile plugin ...")
```

裁判口径（`plugin-compatibility.ts:75`）：
- 只看 `peerDependencies` 中**名为 `@deepseek-ai/dsh` 或以 `@deepseek-ai/dsh-` 开头**的项
- **`engines.dsh` 不参与判定**；`@deepseek-ai/cordis` 也不参与（不匹配前缀）
- `workspace:^` / `~` / `*` 视为当前 runtime
- `semver.satisfies(runtime, range, { includePrerelease: true })` 为假 → 不兼容
- 无 `peerDependencies` 字段 → 直接放过

豁免机制：`profiles/<name>/compatibility.json`（`profile-compatibility.ts`）
```json
{ "<包名>@<精确版本>": ["<精确 dsh 版本>"] }
```
授予：`dsh plugin allow-version`（写盘需显式 `--accept-risk`；插件管理器的安装/启用路径
是**硬拒绝**并抛出 `incompatible-version`）。
**本机当前不存在 `compatibility.json`。**

> ⚠️ 该逻辑在 `0.1.7-rc.2` 与 `0.2.1-alpha.1` 上**逐字节相同**（已 diff 验证），
> 所以它现在就在运行——只是当前所有 peer 都满足，所以从未触发。

### 4.2 模拟结果（上游同款 semver 口径 + 本机真实 manifest）

复现脚本：`_scratch/up020/simulate-compat.mjs`（只读）
```
node simulate-compat.mjs 0.1.7-rc.2      # → 被禁用 0 个
node simulate-compat.mjs 0.2.1-alpha.1   # → 被禁用 8 个
```
**反证**：`_scratch/web-9007.log` 与 `_scratch/ops-daemon.log` 中
`disabling profile plugin` 命中数均为 **0**，与 runtime=0.1.7-rc.2 的模拟结果一致。

### 4.3 会被禁用的 8 个（runtime = 0.2.1-alpha.1）

| # | 包 | 当前版本 | 触发的 peer（摘） | 是否有支持 0.2 的新版 |
|---|---|---|---|---|
| 1 | `@deepseek-ai/dsh-tool-session-query` | 0.1.7-rc.2 | 全部 peer 精确钉 `0.1.7-rc.2` | ✅ `0.2.1-alpha.1` |
| 2 | `@perrylink/dsh-plugin-kit` | 0.1.9 | `<0.2.0` | ✅ `0.1.16` |
| 3 | `@perrylink/dsh-skill-pack-security-provider` | 2.2.16 | `<0.2.0` | ✅ `2.2.22` |
| 4 | `dsh-better-sidebar` | 0.21.1 | `^0.1.7-rc.1`（含 `dsh-invariants`） | ✅ `0.24.1` |
| 5 | ~~`dsh-fulltext-search`~~ | ~~0.1.1 (github)~~ | ~~`^0.1.0-rc.8`~~ | **已撤下**（2026-10-07）——不再需要豁免 |
| 6 | `dsh-industry-research` | 0.3.15 | `<0.2.0` | ✅ `0.3.18` |
| 7 | `dsh-plugin-guide` | 0.3.19 | `<0.2.0` | ✅ `0.3.26` |
| 8 | `dsh-research-report` | 0.3.16 | `<0.2.0` | ✅ `0.3.21` |

新版本的 peer 范围已核查：均含 `>=0.2.1-0 <0.3.0`（或 `^0.2.0-rc.1`）分支，可解锁。
注意 `dsh-better-sidebar@0.24.1` 的 peer 已改为 `^0.2.0-rc.1`——**它是「只支持 0.2」**，
与基座**必须成对升级**，不能单独先升。

### 4.4 判定通过的 10 个（不受影响）

`@changfenhuang/dsh-annotation@1.4.10`、`@linxin666/dsh-web-all@0.4.3`、
`@linxin666/dsh-client-ui-session-id@0.4.3`、`dsh-context@0.56.2`、`dsh-deepread@1.0.1`、
`dsh-linkdigest@1.0.0`、`dsh-ppt-studio@1.1.5`、`dsh-search-plus@1.0.0`、
`dsh-session-insights@0.3.0`、`dsh-suigintou-ui-patches@0.1.0`

> `dsh-context` 的 `dsh.compatibility.dshReleases` 只列到 `0.1.7-rc.2`（**需包作者确认是否
> 声明滞后**），但该字段**不参与判定**；其 peer 全为无上界的 `>=` 或 `*`，故放过。

> `@linxin666/dsh-web-all@0.4.3` 是重度 UI 补丁包，peer 为 `@deepseek-ai/dsh@>=0.1.7-rc.2`
> （无上界）→ 判定放过。但**判定放过 ≠ 运行时兼容**：它锚定的客户端 DOM/接口是否在 0.2
> 有变动，本次未核（见 §五 缺口）。

---

## 四之二 · ★ 反向锁：第三方生态已开始「过河」

§四 讲的是「第三方包声明**上界** `<0.2.0` → 升到 0.2 时被禁」。
**同一把刀还有相反的一面**：包声明**下限**（`>=0.2.0-rc.2`）时，
**留在 0.1.7 的机器一旦点了升级，包会立刻被同一个 preflight 禁用**。

这正是生态「跟随官方 sdk cohort」的结果 —— `@linxin666/dsh-web-all` v0.4.5 更新说明原文：

> **[sdk] 官方 cohort 推进到 `0.2.0-rc.2`**：下限、host peer、README 徽章与 CI/发布的挂载 pin 一起移动

### 实测：分水岭就在 0.4.3 → 0.4.4 之间

| `@linxin666/dsh-web-all` | peer 要求 | 在 0.1.7 下 | 在 0.2 下 |
|---|---|---|---|
| **0.4.3（本机在装）** | `>=0.1.7-rc.2` | ✅ | ✅ |
| 0.4.4 | `>=0.2.0-rc.1` | ❌ 禁用 | ✅ |
| **0.4.5（最新）** | `>=0.2.0-rc.2` | ❌ 禁用 | ✅ |

（同作者的 `@linxin666/dsh-client-ui-session-id` 同样：0.4.3 支持两代，0.4.5 只支持 0.2）

### 全量扫描：5 个包的最新版已经「过河」

判定脚本 `_scratch/up020/judge-cohort.mjs`（读 `peers.tsv`，口径与 DSH 的
`evaluatePluginCompatibility` 完全一致）：

| 包 | 最新版 | 要求 | 0.1.7 | 0.2.0-rc.2 | 0.2.1-alpha.1 |
|---|---|---|---|---|---|
| `@deepseek-ai/dsh-tool-session-query` | 0.2.1-alpha.1 | **精确** `0.2.1-alpha.1` | ❌ | ❌ | ✅ |
| `@linxin666/dsh-client-ui-session-id` | 0.4.5 | `>=0.2.0-rc.2` | ❌ | ✅ | ✅ |
| `@linxin666/dsh-web-all` | 0.4.5 | `>=0.2.0-rc.2` | ❌ | ✅ | ✅ |
| `dsh-better-sidebar` | 0.24.1 | `^0.2.0-rc.1` | ❌ | ✅ | ✅ |
| `dsh-session-insights` | 0.5.2 | `>=0.2.0-rc.2` | ❌ | ✅ | ✅ |

其余 9 个 npm 包（annotation / plugin-kit / skill-pack-security-provider / context /
deepread / industry-research / plugin-guide / research-report / ppt-studio）的最新版
**两代都兼容**。**反向（最新版仍只支持 0.1.7）一个都没有** —— 生态是**单向切走**的。

> ⚠️ `@deepseek-ai/dsh-tool-session-query@0.2.1-alpha.1` 的 peer 是**精确版本**，
> 所以它**只认 0.2.1-alpha.1**，连 `0.2.0-rc.2` 都不满足。目标版本必须按它来配。

### 结论：包版本与基座版本必须「配套」，升级必须原子化

- **现在绝对不要单独点升级这几个包** —— 在当前 0.1.7 环境里会被静默禁用
- **迁移到 0.2.x 时，5 个「下限型」包 + §四 的 8 个「上界型」包必须和基座一起换**
- **留在 0.1.7 的代价在上升**，但「过河」≠「必须马上迁」：当前装着的旧版本仍可用，
  只是拿不到新功能与修复

---

## 五 · 隐性变更核查（官方指南未登记的）

| 核查项 | 方法 | 结果 |
|---|---|---|
| 会话日志格式断代 | 对比两 tag 的 `packages/core/session/src/types.ts` | `SESSION_FORMAT_VERSION = 4` **三版一致** → 未断代 ✅ |
| 持久化变更登记 | `docs/persistence-changes/` 目录 diff | 相对基线仅新增 `2026-09-21-user-question-reply`；`releases/` 最新仍到 `dsh-v0.1.5-rc.2` |
| 皮肤/UI 锚点 | `ConversationRoot.module.css` 逐字节 diff | md5 `5cd1e5f8d84733e7b2d710c746c6cdcc` **全等** ✅ |
| 兼容性判定逻辑 | `plugin-compatibility.ts` diff | **逐字未变** ✅（§四 模拟口径有效） |
| 工具链要求 | 根 `package.json` 对比 | `engines.node` 不变（`^22.19.0 \|\| >=24.0.0`）；<br>⚠️ `packageManager` 由 `pnpm@12.6.0` → **`pnpm@11.7.0`（回退）** |
| 顶层结构 | 两 tag tree diff | 删 `packages/runtime-diagnostics/*`（含 `invariants`）、`tsconfig.desktop-keyboard-tests.json`；<br>增 `packages/client/product-analytics`、`client/ui-settings-session-log`、<br>`experimental/{claude-code-mods,client-ui-claude-code-mods,inspector-profile,session-inspector}`、<br>`schedule/tool-schedule`、`telemetry/otel` |

### 本次未覆盖的缺口（诚实声明）

1. **`@linxin666/dsh-web-all@0.4.3` 在 0.2 上的运行时兼容性**未验证——它不在 preflight
   拦截范围内，但重度 DOM 补丁包是历史上最易失锚的一类。需专测。
2. **pi-ai 0.87.1 的模型 ID 移除**：未核对本机已保存的模型选择是否失效。
3. **`dsh-context` 的 `dshReleases` 声明滞后**：需向作者确认（或实测）。
4. **官方 `docs/postmortem/`** 未逐篇读（可能有 0.2 期间的已知事故）。
5. **19 个 bundle 的运行时行为**未在 0.2 上实跑——本次只做了**静态兼容性判定**。

---

## 六 · 升级方案（未执行，仅供决策）

### 阶段 0 · 前置准备（现役照跑，零风险）

```bash
cd $HARNESS
tools/backup-dsh.sh                 # 全量备份
tools/check-profile-links.py        # 链接护栏
```
另存一份 `profiles/web/package.json` + `pnpm-lock.yaml` + `cordis.patch.yml` 快照。

### 阶段 0.5 · cohort 体检（新增，动手前必跑）

```bash
cd $HARNESS/_scratch/up020
node judge-cohort.mjs peers.tsv      # 看【A】清单
```

【A】非空 = 说明「不能单独点升级」的包又多了一个。把 **【A】清单 + §四 的 8 个包**
合并成一份「随迁清单」，**一次性换**——中间态两边都炸。

### 阶段 1 · 准备「升级包」（关键，不可跳过）

**按推荐目标 `0.2.0-rc.2`（rc = 稳定）**，随迁量只有 **3 个包**：

**(a) 升级 2 个 bundle**（在 `profiles/web/package.json`）：
```
@deepseek-ai/dsh-tool-session-query   0.1.7-rc.2 → 0.2.0-rc.2   ← 精确钉版，必须同版本
dsh-better-sidebar                    0.21.1     → 0.24.1       ← caret 型，与基座成对
```
其余 bundle 的**当前版本在 `0.2.0-rc.2` 下判定通过**，无需改动。
> **2026-10-07 计数修正**：随两个搜索插件撤下，bundle 总数 **19 → 17**；扣除上面要升的 2 个，
> 判定通过者为 **15 个**（原文写「其余 14 个」，与当时 19 个的总数对不上，以本行为准）。
> 建议动手前用 `_scratch/up020/judge-cohort.mjs` 重跑一次，以实测为准、不以本文档为准。

**(b) ~~为 `dsh-fulltext-search` 准备豁免~~ → 豁免项已取消（2026-10-07）**：

`dsh-fulltext-search` 已于 2026-10-07 **正式撤下**，与 `dsh-search-plus` 一同退出 profile。
**不再需要 `compatibility.json`，也不再需要 `dsh plugin allow-version --accept-risk`。**
（`compatibility.json` 至今从未创建过——实测该文件不存在，所以也没有历史遗留要清。）

> 撤下的动机之一正是本节：它是 0.2.0-rc.2 目标下**唯一**「无新版可升、只能靠豁免硬闯」的包。
> 豁免的语义是「明确接受可能崩溃或数据丢失」，能免则免——撤下后 0.2 升级路径**全程无豁免**。

> **若选择 `0.2.1-alpha.1`**（alpha，按本机口径属不稳定）：随迁量升到 **8 个** ——
> 在上述基础上再加 `@perrylink/dsh-plugin-kit`(→0.1.16)、
> `@perrylink/dsh-skill-pack-security-provider`(→2.2.22)、
> `dsh-industry-research`(→0.3.18)、`dsh-plugin-guide`(→0.3.26)、
> `dsh-research-report`(→0.3.21)，且 `dsh-tool-session-query` 要装 `0.2.1-alpha.1`。

### 阶段 2 · 在试探实例上验证（**不要直切现役**）

2026-09-26 的翻车教训（`id=1172`）：**必须做 dsh-domus-new 式的试探文件夹**。
流程沿用 0.1.7 那次：改名试探 → 冷启 → 护栏 `--strict` → 观察启动日志。
**重点看两项**：
1. stderr 里**不再出现** `disabling profile plugin`
2. 插件管理页里 19 个 bundle 都在

### 阶段 3 · 切换与验证

1. 两处一起改：`DSH_VERSION` 与 `start-web.sh` 的 `export DSH_HOME`（`start-web.sh` 已有
   「基座↔home 配套断言」兜底）
2. 按 `tools/DSH-升级铁律.md` 跑完铁律 2 的核对表——**尤其第 ② 项**
   （`fetch-trace.log` 里 `force-h1` 的 `applied:true`）。
   ⚠️ 0.2.1 的 `packageManager` 回退到 `pnpm@11.7.0`，依赖重装后务必复核 undici 解析
   （`dsh-force-h1.mjs` 依赖 undici 路径解析，铁律 2 的「已知的升级坑」正是这一类静默失效）
3. 检查 `profiles/web/compatibility.json` 是否被自动重写、
   `dsh.profile.bundles` 是否被 `schedule-bundle-retired` 逻辑改动

### 阶段 4 · 回滚

保留阶段 0 的备份与快照；回滚 = 恢复 `DSH_VERSION` + `DSH_HOME` + `package.json` /
`pnpm-lock.yaml` / `cordis.patch.yml`，重启即可。

---

## 附录 · 证据与复现

| 证据 | 位置 |
|---|---|
| 三个 tag 的 release notes 原文 | `_scratch/up020/dsh-v0.2.0-rc.1.md` / `-rc.2.md` / `dsh-v0.2.1-alpha.1.md` |
| 6 份 upgrade-guide 中文正文 | `_scratch/up020/ug-017-*.md`、`ug-020-*.md` |
| 上游目录树（两 tag） | `_scratch/up020/tree-017rc2.txt`、`tree-021a1.txt` |
| 兼容性模拟脚本（只读） | `_scratch/up020/simulate-compat.mjs` |
| bundle 清单扫描脚本（只读） | `_scratch/up020/scan-bundle-compat.py` |
| 判定逻辑源码 diff | `_scratch/up020/pc-021a1.ts` vs 基线 |
| 官方笔记（profile 刷新 / schedule 组合） | `_scratch/up020/note-*.md` |

**核心判据一句话**：升级本身不难，**难的是让 19 个 bundle 在新基座上「不被静默禁用」**——
先备好「升级包 + 豁免」，再动版本。
