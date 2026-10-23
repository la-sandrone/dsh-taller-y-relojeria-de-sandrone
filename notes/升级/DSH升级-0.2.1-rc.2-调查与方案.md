# DSH v0.2.0-rc.2 → v0.2.1-rc.2 升级调查与方案（破坏性变化为主）

文件名: 用户笔记/升级/DSH升级-0.2.1-rc.2-调查与方案.md
摘要: 本次**非常规升级**（不在 42 天卡池周期内，因上游发新模型 V4.1-Flash-1017 + 新 Search/Fetch API 并强烈建议升级）的完整调查与方案。重点是破坏性变化：上游登记 40 条、本机机械核查 243 个已装包、3 份源码补丁、5 个预设。
依赖: `原始代码研究/v0.2.1-rc.2`（tag `dsh-v0.2.1-rc.2`，2026-10-17T08:16:33Z 发布）
      `原始代码研究/v0.2.0-rc.2`（现役基座）
      `dsh-domus-0.2.0-rc.2`（旧 home，回滚点）
      `tools/check-plugin-compatibility.mjs`、`tools/dsh-ui-patches.py`、`tools/stage-upgrade-home.py`

调查时间：2026-10-17 17:00 CST ｜ **状态：已执行并转正（2026-10-17 18:44）**
  · 现役 = v0.2.1-rc.2 @ 9007，home = `dsh-domus-0.2.1-rc.2`
  · 本文 §一～§十 是**动手前的调查**（保留原样，便于对照判断错了哪里）；
    §十一 是**执行记录与实测结论**，两者冲突时以 §十一 为准。
本轮沿用 2026-10-07 的版本口径：**rc = 稳定，可用于现役；alpha = 仅预览。**

---

## 〇 · 结论摘要（先读这一节）

1. **这是一次「小版本、大改动」**：`0.2.0-rc.2 → 0.2.1-rc.2` 之间上游登记了 **40 条破坏性变更**
   （`docs/upgrade-guide/` 下 `v0.2.0-rc.2` 6 条 + `v0.2.1-alpha.1` 22 条 + `alpha.2` 10 条 +
   `alpha.3` 1 条 + `alpha.4` 1 条），是 0.1.7→0.2.0 那次（6 条）的六倍以上。
   **但本机真正「不改就起不来」的硬命中只有 3 类**（见下），其余要么不中招，要么是软后果。
2. **硬命中（必须改）**：
   - **6 个 bundle 会被 preflight 静默禁用**（机械核查 243 个已装包得出，不是估算）：
     `@deepseek-ai/dsh-tool-session-query@0.2.0-rc.2`（8 条**精确钉版** peer）、
     `@perrylink/dsh-plugin-kit@0.1.9`、`@perrylink/dsh-skill-pack-security-provider@2.2.16`、
     `dsh-industry-research@0.3.15`、`dsh-plugin-guide@0.3.19`、`dsh-research-report@0.3.16`。
     六个都有可用的目标版本（全部实测评判通过）。
   - **`补丁/Markdown渲染/` 已经漂移**：上游把用户消息渲染整条管线重构了
     （`projectUserText` 被删、改走 `conversation.user.text` 工厂槽 + 规则求值 + keyed 节点槽），
     `dsh-ui-patches.py --checkout 原始代码研究/v0.2.1-rc.2` 报 **3 项 verify 失败**。
     另两份补丁（空回复兜底、sandbox-scratch）`git apply --check` **全部干净通过**。
   - **`{{cwd}}` 变量上游被删**（`agent-loop` 不再注册 `cwd`，0.2.0 有、0.2.1 无）。
     本机 5 个 preset 里各有 1 处 `{{cwd}}`，全靠本地插件 `cwd-fallback.mjs` 重新注册才不掉。
     **这个插件必须被实测确认还活着**，否则 5 个预设的每一次请求都会在装配期抛
     `unknown prompt variable "{{cwd}}"`。
3. **最重要的「暗雷」不在登记表里**：`0.2.1-alpha.3` 起，插件兼容性判定改为
   **`engines.dsh` 优先、peer 忽略**。本机现有 `tools/check-plugin-compatibility.mjs`
   只实现了 peer 规则 ⟹ **它会漏判其中 2 个**（`dsh-industry-research`、`dsh-research-report`
   是 `engines.dsh` 违规，peer 反而在范围内）。**升级前必须先把这个工具按新规则改掉**，
   否则「体检通过」是假绿。
4. **会话日志格式未断代**：`SESSION_FORMAT_VERSION = 4` 两版一致，
   `docs/persistence-changes/finalized/v4.json` **逐字节相同** ⟹ 归档/收割/检索/导出工具
   （`archive_*`、`scan_*`、melquiades 收割器、`dump-session-stream.py`）**契约不变**。
   连 2.6 GB 的 `cache/session-query.sqlite` 都不用重建（两版的
   `SESSION_QUERY_SQLITE_SCHEMA_VERSION` 都是 8）。
5. **`patchReload: live` 只盯 patch 文件，不盯 `package.json`** ⟹ 随迁的依赖变更**必须重启**才生效。
6. **新 Search/Fetch API 的计费闸门是 2026-11-01 00:00（北京时间）**：届时 DSH 里经
   Server 端工具调用打到的 Search/Fetch 开始按次收费（5 元/千次）。
   **本机现在的默认配置已经走这条路**（`searchProvider: deepseek-official` = Messages 服务端搜索，
   每次搜索耗一整轮模型）。所以「MCP 优先、API 只兜底」不只是新版本的配置题，
   **它今天就已经在产生成本路径，只是账单还没开**。详见 §六。
7. **建议节奏**：不必抢在 10 月内切（除非要用 1017 模型）；但 **11-01 前必须把搜索策略定下来**，
   这两件事可以分开做、互不阻塞。

---

## 一 · 上游事实：这次发了什么，为什么催升级

| 事实 | 值 |
|---|---|
| tag | `dsh-v0.2.1-rc.2`（仓内 `git describe` 实测） |
| 发布时间 | 2026-10-17T08:16:33Z（created 07:22:43Z） |
| 检出 `package.json` version | `0.2.1-rc.2` |
| release 性质 | Pre-release（本仓 25 个 release 全部是 Pre-release，**不存在正式版**，见 0.2.x 笔记 §一） |
| release notes 正文 | 只有两条新功能：**适配 DeepSeek-V4.1-Flash-1017 上线**、**适配 DeepSeek Search 与 Fetch API** |

官方公众号（`https://mp.weixin.qq.com/s/X-5kbBkedQ5Oct9byUunag`）给了升级的**业务理由**：

- V4.1-Flash-1017 在多个 harness 上达到新的「性能—费用」帕累托点，**明确点名针对 DSH 优化**；
- 官方要求「升级到 **0.2.1-rc.1 及以上**」以获得适配新版模型的最优体验；
- Search/Fetch 接口正式开放：**5 元 / 1000 次**，Search 与 Fetch 各自独立计费、各自 QPS 5；
- **当前在 DSH / Claude Code / Codex 中经 Server 端工具调用打到的 Search/Fetch 暂不计费，
  自北京时间 2026-11-01 00:00 起按次收费。**

⟹ 本次升级的真实驱动是**模型与 API**，不是基座修 bug。**破坏性变化是伴随成本，不是收益。**

### 1.1 与本机口径的冲突点（诚实标注）

- 卡池周期（42 天）本来把这次更新挡在门外；**用户已判定本次非常规放行**。
- 「等 rc 转正」这条判据在 DSH 上**永不成立**（没有正式版），所以「rc 可用」是既定前提。

---

## 二 · 破坏性变更全量（40 条）与本机判定

判定方法（全部可复现）：
`原始代码研究/v0.2.1-rc.2/docs/upgrade-guide/**/guide.zh.md` 逐条读 →
对每条找「本机是否引用该结构」→ 用 `grep -rl` 在**手写配置全集**
（`cordis.yml`、`.agent-presets/`、`patches/`、`profiles/web/cordis.patch.yml`）上验证。

### 2.1 硬命中（A 类）

| # | 变更（guide 目录） | 本机证据 | 处置 |
|---|---|---|---|
| A1 | `v0.2.1-alpha.3/plugin-engines-dsh` | 6 个包不满足 0.2.1-rc.2（§三） | 随迁 6 个版本 + **改体检工具** |
| A2 | `v0.2.1-alpha.1/working-directory`（`{{cwd}}` 移除） | `profiles/web/cordis.patch.yml:272,1020,1955,2745,3540` 五处；`patches/0.1.7-agent-presets/*.patch.yml` 五份源文件各一处 | 依赖 `cwd-fallback.mjs`（它 `ctx.systemPrompt.variable('cwd', …)` 重新注册）；**trial 必须验证**，失败则改写 persona（见 §五.3） |
| A3 | 无 guide（本机结构） | `补丁/Markdown渲染/` 3 项 verify 断言失败 | **重写补丁**或改成客户端插件（§五.4） |
| A4 | 无 guide（启动器机制） | `启动器配置和日志/版本信息说明/` 只有 `v0.1.7-rc.2.toml`、`v0.2.0-rc.2.toml` | 新建 `v0.2.1-rc.2.toml`，否则启动器在「版本说明缺失」处拒绝启动 |
| A5 | 无 guide（构建机制） | 新检出无 `node_modules` / `lib` / `dist` / `system.node` | 走 0.2.x 笔记 §三 的五步（install → build → build:native-system → profile install → 解析拦截层） |

> A2 的机制补充：0.2.0 的 `packages/core/agent-loop/src/index.ts:372` 注册了 `cwd`；
> 0.2.1 的同一文件只剩 `provider`（:389）与 `model`（:390）。
> `system-prompt/src/index.ts:367` 对未注册变量**抛错**，不是降级。
> 而本地 `cwd-fallback.mjs` 的 provider 读的是 `context.agent?.session.header.cwd`，
> 该字段仍在（`working-directory` 只是把「当前目录」另存了一份，`header.cwd` 保留为原始项目）。

### 2.2 软命中（B 类：不改也能起，但有后果）

| # | 变更 | 本机状态 | 建议 |
|---|---|---|---|
| B1 | `v0.2.1-alpha.1/subagent-activations`：删 `backgroundMode` / `enableRunInBackground` / `run_in_background` | 合并后的 patch 里 **10 处** `backgroundMode: continuable`（5 预设 × 2 行），5 份源 patch 同样 | 删。实测 schemastery 对未知键**不抛错**（`vendor/schemastery/src/index.ts:517` `if (!schema) return [data]`），所以留着是**死配置**而不是炸点；语义已内建（spawn/fork 子级默认可续） |
| B2 | `v0.2.1-alpha.1/subagent-preset-composition`：`tool-subagent` **拒绝** `persona`/`toolFilter` | 本机这两项 **0 命中**（`persona` 的 15 处在 `@deepseek-ai/dsh-persona` 行上，不是子代理配置） | 无需动。若将来想给子代理独立人格，改用 `agentPreset`（可选，缺省继承父级 preset） |
| B3 | `v0.2.1-alpha.1/tool-presentation-mode`：`mode: both` 被拒 | `mode: both` / `presentAs` / `DSH_TOOLS_MODE` **0 命中** | 不中招 |
| B4 | `v0.2.1-alpha.1/web-listener-trust-config`：删 `webRuntime` 服务、`host` 必须是具体网卡地址 | **本机配置** 0 命中（但**第三方插件命中**：`dsh-better-sidebar@0.24.1` 注入 `webRuntime` → 实测 pending 不激活，见 §十一）；启动器只传 `--port N --no-open`（`start-web.py:1172`），组合默认 host 两版都是 `127.0.0.1`（`packages/bundle/web-app/cordis.patch.yml:183`） | 配置层不中招；**插件层中招**（better-sidebar → 升 0.28.0）。**反向约束**：以后不能再传 `--host 0.0.0.0`（会被拒） |
| B5 | `v0.2.1-alpha.1/instruction-home-override`：`agent-instructions` 删 `dshHome` | 0 命中 | 不中招 |
| B6 | `v0.2.0-rc.2/remove-runtime-invariants` | `invariant` 仅在 9 月备份的 lock 文件里出现 | 不中招 |
| B7 | `v0.2.0-rc.2/schedule-bundle-retired` | `dsh.profile.bundles` 无 `experimental-schedule-bundle`；patch 无 `time-context`/`ui-schedule` 顶层覆盖 | 不中招（Schedule 由 Web 组合自带） |
| B8 | `v0.2.1-alpha.2/deepseek-account-model-catalog`：`llm-deepseek-account` 的 `models` 字段会让插件**加载即报错** | `llm-deepseek-account` **0 命中**；`models:` 两处在 `llm-deepseek` / `llm-pi-ai` 行上（仍然合法） | 不中招。**但要守住**：别在模型页给账号路由存目录 |
| B9 | `v0.2.1-alpha.2/pi-ai-azure-provider`：`azure-openai-responses` → `azure` | 0 命中 | 不中招 |
| B10 | `v0.2.1-alpha.2/stored-credentials-precedence`：**存储凭据优先于环境变量** | `.credentials.yaml` 只有 `client-connection/browser-session`，**没有 `refs`** ⟹ 当前无效 | 不中招，**但这是一颗新埋的雷**：以后如果在「模型」页保存了 API Key，它会**盖掉**启动器从 `密钥.env` 注入的 `DEEPSEEK_API_KEY`。写进运维纪律 |
| B11 | `v0.2.1-alpha.2/plugin-install-over-installed`：HMR 下安装已装包 → `already-installed` | 本机升级靠改 `package.json` + `pnpm install`，不用插件页「更新」 | 不中招；**顺带强化既有纪律**：插件页「开始更新」不做运行时门禁（0.2.x 笔记 §一 已记事故） |
| B12 | `v0.2.1-alpha.2/from-default-profile-replaces-target` | 不用 `--from-default-profile` | 不中招 |
| B13 | `v0.2.0-rc.2/subpath-plugin-display-manifest` | 本机是使用者；`@deepseek-ai/dsh-tool-subagent-control/list-agents` 子路径行会失去 `package.json` 补全的标题/描述 | 只影响插件管理页的显示文案，不挡启动 |
| B14 | `v0.2.1-alpha.1/job-id-identity`：job id 变 `<kind>-<uuid>` | 工具入参/出参本来就是原样传递 | 不中招；**别写按序号构造 job id 的脚本** |
| B15 | `v0.2.1-alpha.1/new-session-generations`、`terminal-command-labels`、`session-title-*`、`mock-messages-events`、`jsonl-persistence-plugin`、`python-*`、`ssh-helper-launch`、`native-subagent-bundle-tools`、`team-direct-inbox`、`operator-connect`、`desktop-*`、`account-*`、`sdk-minimal-image-compaction` | 均为「插件/客户端作者」或 Desktop/SDK/ACP 路径 | 本机不用这些路径，不中招 |

### 2.3 无 guide 但必须核的三项（已核）

| 项 | 方法 | 结果 |
|---|---|---|
| 会话格式 | 两版 `packages/core/session/src/types.ts` | 都是 `SESSION_FORMAT_VERSION = 4` |
| 持久化契约 | `diff docs/persistence-changes/finalized/v4.json` | **无差异** |
| 检索索引 | 两版 `@deepseek-ai/dsh-session-query-sqlite` | `SCHEMA_VERSION` 都是 8 ⟹ 2.6 GB 索引不重建 |

### 2.4 与第三方包声明相关的两个「假信号」

- 本机多个第三方包有 **`dsh.engines.dsh`**（嵌套在 `dsh` 字段里，如 `@linxin666/dsh-web-all@0.4.6`），
  还有的写 `engines.dsh`（顶层，如 `dsh-context`、`dsh-industry-research`）。
  **preflight 只读顶层 `engines.dsh`**（`packages/boot/app-boot/src/plugin-compatibility.ts:55-64`），
  嵌套那份**完全不参与判定** ⟹ 看到 `dsh.engines` 写 `>=0.2.0-rc.2` 不等于它会被检查。
- `@deepseek-ai/cordis` 不在判定范围（上游只查 `@deepseek-ai/dsh` 与 `@deepseek-ai/dsh-*`）。

---

## 三 · 机械核查：243 个已装包 → 6 个会被静默禁用

### 3.1 新规则（源码实证）

`原始代码研究/v0.2.1-rc.2/packages/boot/app-boot/src/plugin-compatibility.ts`

```
unmetRequirements(manifest, runtime):
  若顶层 engines.dsh 存在  → 只看它（engine 优先，peer 全部忽略）
  否则                    → 逐条检查 @deepseek-ai/dsh / @deepseek-ai/dsh-* peer
  satisfies = semver.satisfies(runtime, range, { includePrerelease: true })
  engines.dsh 为 workspace:* → 不满足（只有 peer 里的 workspace 才视同 runtime）
```

### 3.2 扫描结果（runtime = `0.2.1-rc.2`，扫 `profiles/web/node_modules` 全部 243 个包）

| 包 | 已装 | 违规项 | 可用目标版本 |
|---|---|---|---|
| `@deepseek-ai/dsh-tool-session-query` | 0.2.0-rc.2 | **8 条精确钉版** peer | **0.2.1-rc.2**（唯一正确值，精确钉） |
| `@perrylink/dsh-plugin-kit` | 0.1.9 | peer 上界 `<0.2.0` | 0.1.17 |
| `@perrylink/dsh-skill-pack-security-provider` | 2.2.16 | peer 上界 | 2.2.24 |
| `dsh-industry-research` | 0.3.15 | **`engines.dsh`** | 0.3.19 |
| `dsh-plugin-guide` | 0.3.19 | peer 上界 | 0.3.33 |
| `dsh-research-report` | 0.3.16 | **`engines.dsh`** | 0.3.22 |

**其余 11 个直接依赖 + 236 个间接包全部通过**（含 `@linxin666/*` 全家、`dsh-context`、
`dsh-better-sidebar`、`dsh-deepread`、`dsh-ppt-studio`、`dsh-session-insights`、本地
`dsh-suigintou-ui-patches`）。

### 3.3 必须同步改的工具（否则体检是假绿）

`tools/check-plugin-compatibility.mjs` 目前**只实现 peer 规则**（文件头注释还写着
「上游只查 peer」）⟹ 对 `dsh-industry-research` / `dsh-research-report` 会给出**错误的通过**。
升级前要改三处：
1. 先读 `engines.dsh`，命中则用它判定、忽略 peer；
2. `workspace:*` 出现在 `engines.dsh` 时判**不满足**；
3. `IncompatiblePlugin` / `PluginCompatibility` 的字段 `peers` → **`requirements`**。

另：该工具从**检出目录**解析 semver，而 `v0.2.1-rc.2` 是干净克隆、没有 `node_modules` ⟹
必须等 `pnpm install` 之后才能跑；**在那之前请用 `v0.2.0-rc.2` 检出里的 semver 7.7.4**。

### 3.4 编排工具链的两处变化

| 项 | 0.2.0-rc.2 | 0.2.1-rc.2 | 影响 |
|---|---|---|---|
| `packageManager` | `pnpm@11.7.0`（无哈希） | `pnpm@11.28.5`（无哈希） | 都是 11.x，比上次 12→11 温和；但 corepack 缓存里没有，首次会**联网下载** |
| `engines.node` | `^22.19.0 \|\| >=24.0.0` | 同 | 不变 |
| vendored cordis | 4.0.4 | **4.0.5** | `ctx.effect(fn, label)` 签名不变（`vendor/cordis/src/fiber.ts:415-418`）；生命周期/effect 归属有调整，第三方插件需实测 |
| vendored schemastery | 3.18.4 | 3.18.5 | 未知键仍被忽略 |

---

## 四 · 三项源码补丁的现状

### 4.1 空回复兜底 ✅ 可原样重放

`git apply --check` 两份 `.patch` 全部干净（`messages-adapter` 与 `pi-ai-adapter`），
`manifest.toml` 的 verify 断言在 0.2.1 检出上全部成立。**无需改，重放即可。**

### 4.2 沙盒 scratch 落点 ✅ 可原样重放

三份 `.patch`（sandbox / sandbox-local / sandbox-policy）`git apply --check` 全部通过，
verify 断言成立。**无需改。**

> 但注意：这两份之所以「干净」，是因为它们锚的是**函数名与既有字段**。0.2.1 对
> `sandbox` 体系没有登记破坏性变更，这个结果与事实相符，不是巧合。

### 4.3 Markdown 渲染 ✅ 已按路线 A 重写（2026-10-17）

`python3 tools/dsh-ui-patches.py --checkout 原始代码研究/v0.2.1-rc.2` 报：

```
❌ 上游漂移，3 项核对未通过（用户消息 Markdown 渲染）：
  · MessageItem.tsx 里找不到：projectUserText(text, referenceLabels, skillNames
  · user-text.tsx 里匹配不上正则：if (parts.length === 0) return <span className={css.plainRun}>{text}</span>
  · ui-primitives/src/index.ts 里没有从 export 行出现 projectUserText
```

**根因（源码实证）**：0.2.1 把「用户消息正文」重构成三层：

```
MessageItem.tsx  UserStyleBubble
   └─ renderFactorySlot('conversation.chat.user.content')      ← UserContent.tsx
        └─ renderFactorySlot('conversation.user.text')         ← ui-conversation/UserText.tsx
             ├─ 规则求值（UserTextDocument）：切成 JSON 节点（text / session / skill / goal …）
             └─ 每个节点 renderSlot('conversation.user.text.node', key=节点 id)
                   key 'text' 的默认渲染器 = PlainUserText → <UserTextRun> 裸文本（priority: 100）
```

`projectUserText` 这个「投影函数」被彻底删除，`ui-primitives` 只导出 `UserTextRun` 与 `ReferenceChip`。

**已选并落地：路线 A（源码补丁）**，但**改在节点层**而不是旧的投影层：
`text` 节点直接渲染 `MarkdownText`，引用 chip 仍是独立节点、照旧走 Slot；预览行（`ellipsis`）保持纯文本。
新件 `补丁/Markdown渲染/UserText-0.2.1.patch`，manifest 的 verify 与 build 段已同步（构建命令绕开 pnpm 版本门禁）。
产物 `packages/client/ui-conversation/lib/client.js` 已重建并含补丁。旧件归档在 `历史/`。

（下面是当时的备选，保留供日后参考。）

| | A. 重写源码补丁 | B. 改成客户端插件（推荐） |
|---|---|---|
| 做法 | 在 `UserText.tsx` 的 `PlainUserText`（或 `UserContent.tsx`）里把 `UserTextRun` 换成 `MarkdownText`，重新生成 `.patch` + 更新 manifest 的 verify 断言 | 注册 `conversation.user.text.node` 的 `key: 'text'` 渲染器，`priority < 100` **遮蔽**默认渲染器（`ui-slots/src/index.ts:775` 明确写了「same key + same priority throws；lower priority renders」） |
| 升级成本 | **每次上游动这块就要重写一次**（这次就是第二次） | 跨版本存活，插件不跟源码冲突 |
| 风险 | 低（改点集中） | 需要处理：**队列预览**也走同一个槽（`QueueDock.tsx:230,347`），Markdown 在预览里可能出现样式差异；纯文本节点被切成多段后，跨段的代码块围栏无法闭合（边缘情形） |
| 落点 | `补丁/Markdown渲染/` | `profiles/web/packages/dsh-suigintou-ui-patches`（已有客户端半区，注入 CSS 的地方） |

> 我的建议是 **B**：你每次升级都要重打 markdown 补丁这件事本身，就是「该换实现形态」的信号。
> 但 B 需要一次设计确认（队列预览要不要也 Markdown），所以先摆在这里等你定。

---

## 五 · 手写配置的处置清单（在**源码层**改，别只改合并产物）

本机 preset 的权威来源是 **`patches/0.1.7-agent-presets/*.patch.yml`（5 份）+ 合并后的
`profiles/web/cordis.patch.yml`**；`.agent-presets/<id>/` 是**旧世代遗留**——
0.2.0 与 0.2.1 的源码里**都没有任何读者**（0.2.1 的 `agent-preset/skills/editing-cordis-compositions/SKILL.md:70`
原文：「Nothing reads that directory any more」）。**升级时不要在那里面改。**

### 5.1 `backgroundMode`（B1）

- 位置：`patches/0.1.7-agent-presets/{general,coding,scifi,fantasy,academic}.patch.yml`
  各 2 处 + 合并后的 `profiles/web/cordis.patch.yml` 同 10 处。
- 动作：删除这两行（`tool-subagent` 与 `tool-subagent-fork` 下的 `backgroundMode: continuable`）。
- 语义：0.2.1 中 spawn/fork 子级**默认可续**（`send_message` 可续），所以删掉不丢能力。

### 5.2 `{{cwd}}`（A2）

- 保留，靠 `cwd-fallback.mjs`；**trial 的第一条验收就是它**：
  起一个新会话发一句话，成功即证明变量注册还在。
- 若失败（症状是「本轮运行失败 + unknown prompt variable "{{cwd}}"」），
  退路是把 persona 里那句改成**字面路径**：
  `当前工作目录默认为 $HARNESS（可用 working_directory 切换）`。

### 5.3 `tool-web` 的搜索开关（成本）——**已于 2026-10-17 执行**

- 原状：preset 里 `tool-web` 只有 `fetch: false`（`search` 默认 true）⟹ `web_search` 一直注册着，
  后端是 base 组合的 `searchProvider: deepseek-official`（Messages 服务端搜索）。
- **现状：已加 `search: false`**（5 个预设 × 两套文件共 10 处，含 5 份 `patches/0.1.7-agent-presets/*.patch.yml`
  与合并后的 `profiles/web/cordis.patch.yml`）。`check_patch_layers.py --profile web` 复验通过。
- 理由与回滚见 `用户笔记/部署/搜索成本闸门-禁原生搜索.md`；**这是临时闸门，待搜索代理服务接管**。
- 升级时会随 home 复制自动带过去（见 §七）。

### 5.4 预设的 `includeRuntimeContext: false`

5 个 preset 都是 `complete: true` + `includeRuntimeContext: false`（见 `cwd-fallback.mjs` 文件头 §7）。
0.2.1 新增的 `working_directory` 运行时上下文因此**不会出现在提示词里**——
这不是破坏，但意味着「当前目录」仍然只能靠 `{{cwd}}` 那条线，`cwd-fallback` 的地位更关键了。

---

## 六 · 新 Search/Fetch API：机制、计费与「MCP 优先」怎么落地

### 6.1 官方接口（`https://api-docs.deepseek.com/zh-cn/guides/search`）

| 项 | 值 |
|---|---|
| Search | `POST https://api.deepseek.com/v1/tools/search`（`query`/`count` 1–50/`need_content`/`ori_question`/`localization`） |
| Fetch | `POST https://api.deepseek.com/v1/tools/fetch`（`url`） |
| 计费 | **各 5 元 / 1000 次成功请求**；失败、无结果、超时**不计费**；`count` 不影响单价 |
| 限速 | 每账号 Search / Fetch 各 **QPS 5**，与模型并发独立 |
| 搜索语法 | `site:` / `-site:` / `-词` / `-"短语"` / `"精确短语"` / `lang:` / `after:` / `before:` |
| 结果字段 | `rerank_score`（≥1.5 优质）、`authority`（≥3 极权威）、`summary`（600–800 字，给模型读）、`content`（`need_content`） |
| 计费起点 | **2026-11-01 00:00 北京时间**起，DSH/Claude Code/Codex 里的 Server 端 Search/Fetch 调用开始收费 |

### 6.2 DSH 里的**两条**搜索路（关键区别）

| | `dsh-web-search-deepseek`（已有，0.2.0 起） | `dsh-web-deepseek-api`（**0.2.1 新增**） |
|---|---|---|
| 机制 | 走 Anthropic 兼容 `/messages`，**服务端工具调用**，一次搜索 = **一整轮模型**（延迟 + token） | 直连 `/v1/tools/search`、`/v1/tools/fetch`，**无模型轮次** |
| provider id | `deepseek-official` | `deepseek-search-api` / `deepseek-fetch-api` |
| 默认选中？ | **是**（`packages/bundle/base/cordis.patch.yml` 里 `searchProvider: deepseek-official`，两版取值一致） | 否；需在「插件 → 内置插件配置 → 网页搜索」打开「启用新版 Web 搜索 API」 |
| 计费形态 | 模型 token + （11-01 起）按次 | 按次 |
| 回退 | **不会自动回退到其它 provider**（README 原文） | 同左 |

**推论（这条最重要）**：因为 provider 之间**没有自动回退**，
「MCP 优先、API 兜底」**不可能配置出来，只能靠工具可见性 + 提示词策略**。
可行的三种落地形态：

| 方案 | 做法 | 优点 | 代价 |
|---|---|---|---|
| **S1 只看 MCP（最省）** | preset 的 `tool-web` 改 `search: false`（和 `fetch: false` 并列）⟹ 模型看不到 `web_search`，只剩 `mcp__bingcn__bing_search` / `mcp__cloakbrowser__fetch` | 零计费风险；工具面更干净（少一个会「悄悄烧一轮模型」的坑） | 需要精确语法（`site:`/`lang:`/`after:`）时用不了 |
| **S2 MCP 优先 + API 兜底（符合你的话）** | `search: true`，但在设置里把 provider 切到 `deepseek-search-api`；并在 persona 里写死使用条件：「先 bingcn；**只有** bingcn 报错/空结果，或需要 `site:`/`lang:`/`after:` 这类算子时才用 `web_search`，且每次搜索前先说明理由」 | 兜底能力在；单次成本比 Messages 路低一个量级（无模型轮次） | 仍是**付费**；靠模型自觉，存在误用 |
| **S3 保留 Messages 路** | 什么都不改（现状） | 零改动 | **最贵**：每次搜索 = 一轮模型 + 11-01 起按次计费；且 `maxUses: 5` 一次请求最多 5 次服务端搜索 |

**建议（2026-10-17 更新）**：**先执行 S1 的第一刀**（`search: false` 已落地，见 §5.3 与
`用户笔记/部署/搜索成本闸门-禁原生搜索.md`），**长期目标仍是 S2/S3 之间的「有闸门的兜底」**——
但不是用配置，而是用搜索代理服务（本地网关计量 + 管家插件策略）。在它建好之前，
S1 就是最省心的状态：模型只剩 `mcp__bingcn__bing_search`。
另外无论选哪个，**11-01 前都应把 `web_search` 的 provider 从 `deepseek-official` 换掉或关掉**——
这件事**与是否升级无关**，现役 0.2.0 也吃同一张账单。

### 6.3 与 MCP 的共存

- 两套工具名不同（`web_search` vs `mcp__bingcn__bing_search`），**不会互相覆盖**。
- `mcp-bingcn` 的 `toolCallTimeoutMs: 180000` 等 MCP 配置两版**逐字未变**
  （`packages/mcp/mcp-client/src/index.ts` 无 diff）⟹ 11 个 MCP 服务器不用改。
- 新增的 Search 语法与 bingcn 的能力不重叠（bingcn 不支持 `site:`/`lang:`/`after:`），
  这正是「兜底」的真实价值所在。

---

## 七 · 升级方案（分阶段，含验收判据）

> 原则沿用 0.2.x 笔记：**先备好「升级包」，再动版本；绝不在现役上直切。**

### 阶段 0 · 备份与快照（零风险）

```bash
cd $HARNESS
tools/backup-dsh.sh                      # 全量备份
python3 tools/check-profile-links.py     # 链接护栏
# 快照三件套（回滚要用）
cp dsh-domus-0.2.0-rc.2/profiles/web/package.json   /tmp/.dsh-tmp/snap/
cp dsh-domus-0.2.0-rc.2/profiles/web/pnpm-lock.yaml /tmp/.dsh-tmp/snap/
cp dsh-domus-0.2.0-rc.2/profiles/web/cordis.patch.yml /tmp/.dsh-tmp/snap/
```

### 阶段 0.5 · 先改工具，再做体检（顺序不能反）

1. 按 §3.3 改 `tools/check-plugin-compatibility.mjs`（engines 优先 + `requirements`）。
2. 对新检出跑一遍：

```bash
# 需先完成阶段 1 的 pnpm install（工具要从检出解析 semver）
node tools/check-plugin-compatibility.mjs \
  --profile dsh-domus-0.2.0-rc.2/profiles/web \
  --checkout 原始代码研究/v0.2.1-rc.2
# 期望：恰好报出 §3.2 的 6 个（不多不少）
```

### 阶段 1 · 新基座检出就绪（五步，全部由你执行）

```bash
cd 原始代码研究/v0.2.1-rc.2
corepack prepare pnpm@11.28.5 --activate   # 显式化下载，别让它偷偷下
pnpm install
pnpm run build                             # apps/web/dist + 各 lib（运行必需）
pnpm run build:native-system               # system.node（flock 依赖，缺了第一次开会话才炸）
```

### 阶段 2 · 手写配置预处理（在源码层）

1. 删 `backgroundMode`（5 份 `patches/0.1.7-agent-presets/*.patch.yml`）。
2. 决定 `tool-web` 的 `search`（§6.2 的 S1/S2/S3）。
3. 重新合并进 `profiles/web/cordis.patch.yml`（`tools/merge-017-into-profile.py` 的产物格式；
   **不要**用 `cordis:include` —— 那条路在 preflight 下必被拒，0.2.x 笔记有实测）。
4. 护栏：

```bash
python3 tools/check_patch_layers.py --profile web     # 退出码 0 才可启动
```

### 阶段 3 · 随迁依赖（6 个，一次性换）

`dsh-domus-0.2.1-rc.2/profiles/web/package.json`：

```
@deepseek-ai/dsh-tool-session-query            0.2.0-rc.2 → 0.2.1-rc.2   ← 精确钉，必须逐字一致
@perrylink/dsh-plugin-kit                      0.1.9      → 0.1.17
@perrylink/dsh-skill-pack-security-provider    2.2.16     → 2.2.24
dsh-industry-research                          0.3.15     → 0.3.19
dsh-plugin-guide                               0.3.19     → 0.3.33
dsh-research-report                            0.3.16     → 0.3.22
```

**可选（不做也能过 preflight，但建议评估）**：

| 包 | 已装 | 最新 | 建议 |
|---|---|---|---|
| `dsh-better-sidebar` | 0.24.1（✅ 通过） | 0.28.0 | 0.28.0 的 peer 已推到 `^0.2.1-rc.1`，并**新增 peer `@huanlin/dsh-plugin-better-locale@^0.1.0`**（要一起装）。0.24.1 可能在新 UI 下失锚 → trial 里专测；坏就升 |
| `dsh-context` | 0.56.2（✅） | 0.73.0 | 0.2.1 动了压缩/标题/推理等级相关链路，建议同批升到 0.73.0 |
| `dsh-session-insights` | 0.3.0（✅） | 0.5.2 | 同上，收益在会话统计口径，非必须 |

```bash
cd dsh-domus-0.2.1-rc.2/profiles/web && pnpm install
```

### 阶段 4 · 补丁重放与重写

```bash
python3 tools/dsh-ui-patches.py --checkout 原始代码研究/v0.2.1-rc.2          # 干跑
python3 tools/dsh-ui-patches.py --checkout 原始代码研究/v0.2.1-rc.2 --apply  # 核对 + 重放 + 重建
```

- 空回复兜底 / sandbox-scratch：**直接通过**。
- Markdown：按 §4.3 选 A 或 B，改完后 manifest 的 `verify` 要**同步更新**
  （否则下次开机护栏会一直报漂移，而人会对报警脱敏）。

### 阶段 5 · 建 home + 解析拦截层（最容易漏的一步）

```bash
python3 tools/stage-upgrade-home.py       # 先把 SRC/DST 从 0.1.7→0.2.0 改成 0.2.0→0.2.1，干跑
python3 tools/stage-upgrade-home.py --apply
# 解析拦截层：<home>/profiles/node_modules 的符号链接（pnpm 装不出来）
```

**必须改写的新增绝对路径**：`session-query-sqlite.path`
（`profiles/web/cordis.patch.yml:133` 现写死 `…/dsh-domus-0.2.0-rc.2/cache/session-query.sqlite`）。
两个 home 同时指向同一个索引库 = 两个进程抢同一个 SQLite 索引（0.1.7 那次已经踩过）。

### 阶段 6 · trial（不碰现役，端口自动避让）

```bash
./start-web.py --try v0.2.1-rc.2
```

**验收清单（缺一不可）**：

| # | 判据 | 怎么验 | 期望 |
|---|---|---|---|
| 1 | preflight 没禁人 | 启动日志 `grep -c "disabling profile plugin"` | **0** |
| 2 | 插件页 bundle 数 | 插件管理页 | 17 个（与现役一致） |
| 3 | `{{cwd}}` 活着 | 新会话发一句话 | 正常回复；若报 `unknown prompt variable "{{cwd}}"` → 走 §5.2 退路 |
| 4 | H1 强制生效 | `grep '"event":"force-h1"' <记录目录>/fetch-trace.log \| tail -3` | `"applied":true` 且 argv 指向新检出（0.1.7 那次静默失效过，**这是铁律 2 的 ②**） |
| 5 | 会话与标题 | 打开历史会话 | 标题在（`storages/session_projcache` 必须随迁，见 0.2.x 笔记） |
| 6 | 检索 | `session_event_search` | 有结果（索引库 schema 未变） |
| 7 | Markdown 渲染 | 发一条含 `**粗体**` 的消息 | 渲染成粗体 |
| 8 | 皮肤 | 切 `navia` / `war-thunder` | 背景与 HUD 正常（依赖 `@linxin666` 的 skin-center） |
| 9 | 字体 | 设置 → 通用 | 新官方字体项在；核对与本地 `dsh-suigintou-ui-patches` 有没有打架（§八） |
| 10 | 子代理 | 发一个委派 | 返回子代理 id + 完成通知（不再是 jobId） |
| 11 | 搜索策略 | 让模型查一件小事 | 若 S1：它应只用 bingcn；若 S2：默认 bingcn，兜底才 `web_search` |

### 阶段 7 · 切换与回滚

```bash
# 1) 改两个真相源
#    启动器配置和日志/当前配置.toml      version = "v0.2.1-rc.2"
#    启动器配置和日志/版本信息说明/v0.2.1-rc.2.toml   （新建；required_markers 要能命中 home）
# 2) 重启
./start-web.py
```

回滚 = 三件套快照回填 + `version` 改回 `v0.2.0-rc.2` + 重启。
**注意**：0.2.1 写的会话记录是 v4，0.2.0 也读 v4（契约相同），所以**会话不会因为回滚而打不开**；
但**新版本里改过的 profile 配置/插件版本**必须一起回滚，否则旧基座会禁用那 6 个新版本包
（精确钉反过来咬人：`tool-session-query@0.2.1-rc.2` 在 `0.2.0-rc.2` 下必然被禁）。

---

## 八 · 体检时要顺带看的两个「新能力 vs 本地补丁」冲突

### 8.1 字体设置（0.2.1-alpha.2 起）

官方新增：**界面正文 / 代码与工具输出 / 侧栏终端**三组，各可设字体与字号
（`packages/client/ui-theme/src/theme-settings.ts`：`--dsh-font-family-${kind}`、
`FONT_SIZE_SPECS.text|code|terminal`）。

本地 `dsh-suigintou-ui-patches` 的作用是「正文字族 Source Serif 4 + 代码字号按倍率跟随 +
压制皮肤的 code/pre 声明」，用的是 `!important` 覆盖官方硬编码的 12px/11px。

⟹ **两者可能在同一个面上打架**（本地 `!important` 会盖掉用户在新设置里选的值）。
trial 的第 9 项要专门验；如果官方设置已够用，**这个插件可以退役**（少一处每次升级都要维护的补丁）。
不能退役的部分（思源宋体字族、皮肤压制）再保留。

### 8.2 皮肤锚点

皮肤 CSS 依赖 `html[data-dsh-skin=…]`，而**这个属性不是核心写的**——
核心 0.2.1 源码里 `data-dsh-skin` **0 命中**，它来自 `@linxin666/dsh-client-ui-skin-center`
（随 `dsh-web-all` 家族安装）。⟹ **皮肤能不能用，完全取决于 `dsh-web-all@0.4.6` 在新 UI 下活不活**。
`--dsw-alias-*` 语义 token 仍在（`ui-theme/src/styles/design-platform.css` 命中）。

---

## 九 · 缺口（本次没验的，别当成已验）

1. **`@linxin666/dsh-web-all@0.4.6` 的运行时兼容性**：静态判定通过（peer `>=0.2.0-rc.2`），
   但它是最重的一类 UI 补丁包，且**没有更新版本可选**（0.4.6 就是最新）。0.2.1 重构了
   用户内容渲染、预览、设置页、字号——这是**本次第一风险**，只能 trial 实测。
2. **`dsh-better-sidebar@0.24.1` / `dsh-context@0.56.2`** 的行为兼容性同上（静态通过 ≠ 运行通过）。
3. **`cwd-fallback.mjs`** 的 `system-prompt/assemble` waterfall（`prepend: true`）在 cordis 4.0.5 下
   的求值顺序未实测（事件签名与 `prepend` 选项都在，但顺序语义只有跑起来才算数）。
4. **官方 `docs/postmortem/`** 两版清单**完全相同**（无新增事故复盘），但这不等于 0.2.1 没有问题。
5. **`tool-presentation` 的 `both` 模式**：本机 0 命中，但若某个第三方包内部用了它，会在运行时报错——
   这一点静态查不到（要扫第三方 `lib/`）。
6. **新模型 V4.1-Flash-1017 的实际差异**：模型 id 未变（`deepseek-flash`），只有显示名从
   `DeepSeek-V41-Flash` 改成 `DeepSeek-V4.1-Flash`（`packages/llm/llm-deepseek/src/models.ts:9`）。
   「适配 1017」在代码层的具体改动未逐行核对。

---

## 十 · 证据索引

| 结论 | 证据位置 |
|---|---|
| 40 条破坏性变更 | `原始代码研究/v0.2.1-rc.2/docs/upgrade-guide/{v0.2.0-rc.2,v0.2.1-alpha.1..4}/` |
| 新规则 engines 优先 | `packages/boot/app-boot/src/plugin-compatibility.ts:55-64` |
| 6 个包被禁（243 包扫描） | 本次脚本（见 §3.2 表）；判据同上游 `unmetRequirements` |
| `{{cwd}}` 被删 | `v0.2.0-rc.2/packages/core/agent-loop/src/index.ts:372` 有、`v0.2.1-rc.2` 同文件 :389-390 无 |
| 未注册变量抛错 | `packages/core/system-prompt/src/index.ts:367` |
| 本地 cwd 兜底 | `dsh-domus-0.2.0-rc.2/patches/0.1.7-agent-presets/cwd-fallback.mjs`（`ctx.systemPrompt.variable('cwd', …)`） |
| Markdown 补丁漂移 | `python3 tools/dsh-ui-patches.py --checkout 原始代码研究/v0.2.1-rc.2` 输出 |
| 另两份补丁干净 | `git -C 原始代码研究/v0.2.1-rc.2 apply --check 补丁/{空回复兜底,sandbox-scratch}/*.patch` |
| 会话格式未断代 | 两版 `packages/core/session/src/types.ts`；`finalized/v4.json` 无 diff |
| 索引 schema 未变 | 两版 `@deepseek-ai/dsh-session-query-sqlite` 的 `SCHEMA_VERSION = 8` |
| 默认搜索 provider | `packages/bundle/base/cordis.patch.yml`：0.2.1 第 470 行 / 0.2.0 第 475 行（取值一致） |
| 新版 API 开关 | `packages/web/web-deepseek-api/README.zh.md`「使用此包」 |
| 计费与时限 | 官方公众号 + `https://api-docs.deepseek.com/zh-cn/guides/search` |
| 字号/字体新设置 | `packages/client/ui-theme/src/theme-settings.ts` |
| `.agent-presets` 已无读者 | `packages/preset/agent-preset/skills/editing-cordis-compositions/SKILL.md:70` |
| 槽位遮蔽语义 | `packages/client/ui-slots/src/index.ts:775,1142-1143` |
| MCP 配置未变 | `packages/mcp/mcp-client/src/index.ts` 两版无 diff |
| cordis 4.0.4→4.0.5 | 两版 `vendor/cordis/package.json`；`ctx.effect` 签名 `vendor/cordis/src/fiber.ts:415-418` |

---

## 十一 · 执行记录（2026-10-17，试跑已起）

> 本节的结论都是**实测**，与前面「静态调查」的推断不同；两者冲突时以本节为准。

### 11.1 已完成

| 项 | 结果 |
|---|---|
| 搜索闸门 | `tool-web: search: false` 落在 5 个预设 × 两套文件（共 10 处），`check_patch_layers` 通过；备份 `backups/search-ban-20261017-172539/` |
| 暂存 home | `dsh-domus-0.2.1-rc.2`（418 M），路径重写 27 处、残留 0；`session_projcache`（会话标题）已带 |
| **解析拦截层** | `profiles/node_modules` **265 条**符号链接，隔离门禁 0；两个无法解析的包名正是 0.2.1 删掉的 `dsh-invariants` 与 `dsh-subagent-in-process-driver` |
| 随迁 | 6 个包按 §3.2 升到位；`dsh-better-sidebar` **0.24.1 → 0.28.0**；`dsh-context` 0.73.0；`dsh-session-insights` 0.5.2 |
| preflight | 新 home **244 包 0 禁用**（工具改造后重算） |
| Markdown 补丁 | 路线 A 落地：`补丁/Markdown渲染/UserText-0.2.1.patch`（改 `text` 节点渲染，chip 与预览不受影响）；产物 `ui-conversation/lib/client.js` 已重建 |
| 切换脚本 | `tools/cutover.sh` 泛化：`--to-ver` **必填**、`--from` 取 `当前配置.toml`；旧 `cutover-0.2.0.sh` 删除，三份文档引用同步 |
| 体检工具 | `check-plugin-compatibility.mjs` 改为 **engines.dsh 优先**；新 home 0 个、老 home 6 个（自证判据生效） |
| 死配置 | `backgroundMode` 40 行（两 home × 两套文件）删除；两套配置 YAML 复验通过（237 / 230 个 id） |

### 11.2 实测推翻/确认的判定

1. **`web-listener-trust-config` 在插件层是真命中**：`dsh-better-sidebar@0.24.1` 的宿主半区注入
   `webRuntime`（0.2.1 已删）⟹ 启动日志 `pending (waiting for service: webRuntime)`，
   浏览器端 `/sidebar/ws/agent-opens` 连不上并停止重连。**升 0.28.0 后该告警消失。**
   （§2.2 B4 原判「不中招」只对**本机配置**成立，对第三方插件不成立——已修正。）
2. **`@linxin666/dsh-web-all@0.4.6` 在 0.2.1 上初步可用**：页面、侧栏、皮肤、任务板未见报错；
   控制台的 WebGL/`we-live` 噪声来自壁纸引擎，与本升级无关。
3. **`{{cwd}}` 兜底活着**：`cwd-fallback.mjs` 重新注册的 `cwd` 在 0.2.1 上仍生效（新会话可正常对话）。
4. 会话日志格式未断代在实测上也成立：历史会话、标题、检索索引都正常。

### 11.3 两个新踩的坑（写给下一次升级）

- **拦截层必须在第一次启动之前建**：缺它时 `check_patch_layers` 会把 `dsh-base`/`dsh-web-app`
  报成「无 cordis.patch.yml，跳过」（59 个 id 而非 237），启动链路因此判定需要重建，
  触发 `tsc + tsdown` 全量构建（数分钟、吃满 CPU，体感就是「死机」）。
  ⟹ `stage-upgrade-home.py` 之后**立刻**跑 `repair-profile-links.py`，再 `--try`。
- **pnpm 版本门禁会挡构建**：检出钉 `pnpm@11.28.5`，而本机活跃 pnpm 是 11.7.0 ⟹
  `pnpm exec …` 直接报版本不符（rc=1），**看起来像构建失败**。
  三份 UI 补丁的构建命令已改为直调 `node ./node_modules/...` 与 `npm --prefix … run bundle`，
  与包管理器版本解耦。

### 11.4 转正（2026-10-17 18:44 已完成）

- `./tools/cutover.sh --to-ver v0.2.1-rc.2`：停双方 → 搬 213 个 → 隔离复核 → 通过
- `当前配置.toml` → `v0.2.1-rc.2`；主实例 9007 起于 `dsh-domus-0.2.1-rc.2`
- 复核：`disabling profile plugin` = 0、`did not activate` = 0、9011 已停
- 新 home 已 `git init`（首次提交留给下次开机前的 `commit_home`——运行中提交有半帧风险）
- **用户实测确认（2026-10-17）**：Markdown 渲染生效（查旧对话）；`/humanizer-zh` 技能 chip
  **可点击且能加载技能正文** ⟹ 新补丁的两条边界（渲染正文 / 保留 chip）同时成立。

原始清单（留档）：

1. `./tools/cutover.sh --to-ver v0.2.1-rc.2`（**必须在你自己的终端**；先 `--dry-run`）
2. 改 `当前配置.toml` 的 `version = "v0.2.1-rc.2"`
3. 新 home `git init` + 首次提交（安全网；`.gitignore` 已随迁移复制）
4. 四个面各点一次：皮肤 / 右侧栏 / 任务板 / 设置页；确认「自动化任务」里的旧任务还在
5. 升级报告与本文件回填「已切正」
