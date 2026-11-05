# DSH v0.2.1-rc.2 → v0.2.2-rc.1 升级调查与方案（接口破坏为主）

文件名: 用户笔记/升级/DSH升级-0.2.2-rc.1-调查与方案.md
摘要: 本次升级的判断依据不是"多了什么功能"，而是**插件接口三连改 + Cordis 4.1.0 + PTC 通道换 birpc**——它会打死第三方 bundle 的启动期，而不是让它们降级。方案因此把"现役不动、先建新 home 试跑"作为硬约束；Markdown 补丁本轮**先关**，直接吃上游新行为。
状态: 部分待办 —— §一～§十是动手前调查（2026-11-04 完成）；§十一 执行记录留空待回填。
依赖: `原始代码研究/v0.2.2-rc.1`（tag `dsh-v0.2.2-rc.1`，2026-11-04T13:07:14Z 发布）
      `原始代码研究/v0.2.1-rc.2`（现役基座，shallow clone，2.5 G）
      `dsh-domus-0.2.1-rc.2`（现役 home，**回滚点**；1.2 G）
      `tools/stage-upgrade-home.py`、`tools/repair-profile-links.py`、`tools/check-plugin-compatibility.mjs`、`tools/dsh-ui-patches.py`、`tools/cutover.sh`
调查时间：2026-11-04 CST ｜ 引导笔记：`升级/DSH-0.2.2-alpha.2-调研.md`（11-01，判据已被本次证据部分推翻，见 §1.3）
本轮沿用 2026-10-07 的版本口径：**rc = 稳定，可用于现役；alpha = 仅预览。**

> **纪律**：§一～§十 是动手前的调查（保留原样，便于日后对照判断错了哪里）；§十一 是执行记录与实测结论，**两者冲突时以 §十一 为准**。

---

## 〇 · 结论摘要（先读这一节）

**一句话**：基座这次的增量里，"功能"部分是白送的福利，"接口"部分是必须逐包过的门槛；**现役一秒不停，先建新 home 试跑**。

**四条已定决策**（2026-11-04，见 §11.0）：先只做试跑不动现役 / 升 `dsh-web-all` 全家桶且冲突的先关 / Markdown 补丁先关看情况 / 恢复"先读防护"但接受 Web Fetch 新默认 / `remote-web-ui` 撤销。

**四个本地阻塞项（不先解决，升级会卡在这）**

| # | 事实 | 证据 | 后果 |
|---|---|---|---|
| 1 | `dsh-domus-0.2.1-rc.2` **零提交** | `git ls-files`=0、`status --porcelain` 17 项全 `??`、`.git` 仅 116 K | 没有回档点；搬运对话后出事无路可退 |
| 2 | `版本信息说明/v0.2.2-rc.1.toml` **不存在** | 该目录只有 v0.1.7-rc.2 / v0.2.0-rc.2 / v0.2.1-rc.2 三份 | 新 home 会被 `tools/dsh_config.py` 直接拒绝启动 |
| 3 | `原始代码研究/v0.2.2-rc.1` **不存在** | `ls -d 原始代码研究/v0.2.2*` 无结果 | 阶段 1 的检出+build 全量是几十分钟量级 |
| 4 | 9007 **有监听者但账本判"主实例已死"** | `ss -ltn` 见 `LISTEN 127.0.0.1:9007`；`start-web.py --status` 报"未监听"，并已把 2 条记录搬进 `历史/` | **"停实例"有可能停掉当前界面**；沙箱内 `unshare-pid` 查不到占用者（见 §9 缺口 4） |

**三条纠正（相对 11-01 那份笔记）**

1. **跨行 `$$` 数学块在 rc.1 里仍然不可用** —— alpha.2 修了，**alpha.3 回退了**，rc.1 的 notes 没提。别以为修了。
2. **"皮肤里要撤两条补丁"不成立** —— `skins/` 下 12 套皮肤 **不含** `md-table-wide`，也不含 tooltip 隐藏规则；那类规则实际在本地包 `profiles/web/packages/dsh-suigintou-ui-patches/lib/client.js:252`（`.md-table-wide`），tooltip 那条**全仓找不到**。原笔记记错了位置。
3. **本区间 HTTP/2 零改动** —— `tools/dsh-force-h1.mjs` 不受本次影响，原样保留；§8 的"是否要向上游发主题贴"这条跟进**保持打开，与本次升级无关**。

**风险分级**：A 类（不改就起不来/静默失效）5 条 + B 类（能起但有后果）5 条 + 明确不中招 4 条，见 §二。**唯一能靠运行才知道的那部分（19 个 bundle 里哪几个挂）本轮给不出，必须试跑。**

---

## 一 · 上游事实：这次发了什么

### 1.1 区间与拓扑（区间内**正好 6 个 tag，无隐藏 tag**）

| tag | publishedAt | 基线（Full Changelog 的 a） | 实质内容 |
|---|---|---|---|
| `dsh-v0.2.1-rc.3` | 2026-10-23T15:26:39Z | `dsh-v0.2.1-rc.2` | 左/右栏"更多"菜单（浏览+创建插件）、新会话找回未发送草稿、API Key 适配器模型列表获取对齐登录模式 |
| `dsh-v0.2.1-rc.4` | 2026-10-28T02:49:58Z | `dsh-v0.2.1-rc.3` | 仅 1 条：修复 ACP 模式诊断输出混入 stdout |
| `dsh-v0.2.2-alpha.2` | 2026-10-28T02:50:54Z | `dsh-v0.2.1-rc.4` | **0.2.2 线起点**（无 alpha.1，从 rc.4 切出，**不含 rc.5**）：插件管理+热更新回滚、移动/键盘/触屏、WS 压缩、PTC 执行体系重拆、Cordis Timer/Fiber、Node≥24.9 |
| `dsh-v0.2.1-rc.5` | 2026-10-30T02:12:26Z | `dsh-v0.2.1-rc.4` | 仅 1 条：优化对话中思考内容展示 |
| `dsh-v0.2.2-alpha.3` | 2026-11-03T07:56:48Z | `dsh-v0.2.2-alpha.2` | 统一右键/键盘菜单、文件预览常驻目录树、变更请求+工作树合并、Cordis Core→4.0.0-rc.11、`apply_patch` 新工具、**回退跨行 `$$` 解析** |
| `dsh-v0.2.2-rc.1` | 2026-11-04T13:07:14Z | `dsh-v0.2.1-rc.5` | 汇总 rc.5 以来全部；Cordis Core→**4.1.0** / Loader 1.1.0 / Include 1.1.0；SDK 补齐；自动化任务宿主级化；Session Projection 异步化 |

**两条线是分叉的**（读法决定正确性）：
- 0.2.1 线：rc.2 → rc.3 → rc.4 → **rc.5**（rc.5 从 rc.4 切，不含 alpha.2）
- 0.2.2 线：rc.4 → alpha.2 → alpha.3 → **rc.1**

`gh api .../compare/dsh-v0.2.2-rc.1...dsh-v0.2.2-alpha.3` → ahead 0 / behind 4；`...alpha.2` → ahead 0 / behind 466
⇒ **alpha.2 与 alpha.3 的代码都在 rc.1 里**；`compare rc.5...rc.1` = 2623 commits。

### 1.2 ⚠️ rc.1 的 notes 是**手工汇总稿，有洞**

它**漏写了** alpha.3 的两条（跨行 `$$` 回退、空会话被当"未命名"），而这两条在代码里确实存在。
⇒ **读法是 alpha.2 + alpha.3 + rc.1 三份合并**，只读 rc.1 会漏。**同理，日后 rc.2 的 notes 也不能当唯一真相。**

### 1.3 与引导笔记（11-01）的口径冲突（诚实标注）

| 11-01 的判断 | 本次证据 | 处理 |
|---|---|---|
| "有六条日常磨损级修复，值得破 42 天节奏" | 成立，且在 rc.1 里全部落地 | 结论不变，**触发条件已满足** |
| 预估 rc.1 约 11-11 出 | 实际 11-04 出（比预估早一周） | 无需动作 |
| 跨行 `$$` 已修 | **alpha.3 回退了** | 见 §0 纠正 1 |
| 皮肤补丁两条可撤 | 皮肤里根本没有那两条规则 | 见 §0 纠正 2 |
| `dsh-web-all 0.4.8 → 0.4.11+` | 实测仍 **0.4.8**，未动；`better-sidebar` 已从 0.24.1 → **0.28.0**、`dsh-context` → 0.73.0、`session-insights` → 0.5.2 | 10-17 之后有人升过插件但笔记没回填 ⇒ **包版本以本次实测为准** |

---

## 二 · 破坏性变更与本机判定

### 2.1 硬命中（A 类：不改就起不来 / 或静默失效）

**A1 · PTC 控制通道改用 birpc；自部署 bootstrap 与 SSH helper 必须同步升级，SSH 协议 2 → 3** `@kermanx`
- 原文："PTC Node 控制通道改用 birpc；自部署 bootstrap 与 SSH helper 必须同步升级，SSH 协议从 2 升为 3。"
- 本机判定：**待核（§9 缺口 5）** —— 先确认我们是否自部署了 bootstrap / SSH helper；混用旧 helper 直接不通，这是本次唯一的跨进程协议破坏。

**A2 · PTC 执行器拆分：默认走 native，PTC 变成要显式打开的 overlay（2026-11-04 源码取证，推翻了本笔记初稿）**
- 原文："原生与 PTC 工具执行拆为按 Agent 作用域选择的插件；PTC 通过配置 overlay 启用，旧 `tools.mode` 与 `DSH_TOOLS_MODE` 需迁移。"
- **初稿错在哪**：初稿说 PTC 靠 profile 里 5 处 `workflow-ptc` 条目打开。**错** —— `workflow-ptc` 是 **base bundle 的 config 子条目**（`packages/bundle/base/cordis.patch.yml:400-403`，新旧逐字一致），profile 里那 5 处是**合并产物**，不是手写。**真正变的**是执行器这一层：

  | 项 | 旧 `v0.2.1-rc.2` | 新 `v0.2.2-rc.1` |
  |---|---|---|
  | 执行器 | 无此概念（`grep tool-executor` = 0 命中） | 新增 `tool-executor-native`（**默认启用**）与 `tool-executor-ptc`（**`disabled: true`**），`base/cordis.patch.yml:501-506` |
  | `mode` / `maxParallelSubCalls` | `web-app/cordis.patch.yml:38` 读 `process.env.DSH_TOOLS_MODE` | `tools/src/index.ts:102` 改为 `z.never()`（Removed. Mount a native or PTC tool executor instead.）⇒ **写了会在加载期报错**，不是静默忽略 |
  | 作用域 | — | 执行器挂在 Agent/preset 作用域上（`tools/src/index.ts:352-357` 选最近的 scoped provider） |

  **本机实测**：profile 里 `grep -c tool-executor` = **0**；两个 `mode: normal` 都在 `retryPolicy:` 下（`:185`、`:232`），**不是** `tools.mode` ⇒ 不会触发 `z.never()`。

  ⇒ **后果：不显式配置，升级后 PTC 静默消失**（native 顶替）。**动作**（照上游样本 `apps/cli/config/examples/ptc.yml:1-5`）：

  ```yaml
  - id: tool-executor-native
    disabled: true
  - id: tool-executor-ptc
    disabled: false
  ```


  ⚠️ **不要动** profile 里那 5 处 `workflow-ptc`：base bundle 产物，手改会在下次重合并时漂移。

**A3 · 插件侧接口三处变更（源码级签名对比，2026-11-04 取证）**

| 项 | 旧 | 新 | 插件侧影响 |
|---|---|---|---|
| 工具注册表 | `get(name, scope?)`（`tools/src/index.ts:1238`）、`schemas(scope?)`、`executionMode()`、`presentAs(mode)` | `get(name, scope?, toolSet?)`（`:239`）；**新增** `executable(name, scope?, toolSet?)`（`:251`）与 `async resolve(context): Promise<ResolvedToolSet>`（`:264`）；`presentAs` 消失 → 注册式 `setExecutor(executor)`（`:325`）＋ `ToolExecutor` 接口（`executor.ts:64`） | 用旧 API 的插件**启动期**就炸（不是降级） |
| Session Projection | `register(...): () => void`（`session-projection/src/index.ts:255`） | `register(...): Promise<ProjectionHandle<S>>`（`:340`）；类型图 `SessionProjectionStateMap` → `SessionProjectionMap` | 调用点必须 `await`（上游自己把 session-stats / session-title / working-directory 三处都加了 `await`） |
| Cordis Timer | `throttle/debounce: WithDispose<F>`（`vendor/timer/src/index.ts:9/121/139`） | `Scheduled<F>`（`:9/128/146`）——回调返回值从类型里消失；`interval` 单槽 → 队列；版本 **1.1.7 → 1.2.0** | 类型不兼容即编译/加载失败 |
| 插件 API 版本号 | — | **上游没有这个常量**（`PLUGIN_API_VERSION` / `pluginApiVersion` / `PLUGIN_CONTRACT` / `apiVersion` 四种拼法全仓无命中） | 只能按包版本判断：`@deepseek-ai/dsh-tools`、`dsh-app-boot` 均 `0.2.1-rc.2 → 0.2.2-rc.1` |

- 打击面：19 个 bundle 里碰工具执行/投影/定时的（`dsh-session-insights`、`dsh-context`、`dsh-omnibus-search`、`@perrylink/dsh-plugin-kit`）——**逐包结论只能试跑得出**。

**A4 · Cordis 三件套大版本**：rc.1 记 Core **4.1.0** / Loader **1.1.0** / Include **1.1.0**；alpha.3 记 Core 4.0.0-rc.11 / Loader 1.0.0-rc.8 / Include **1.1.1**
- **已核实，无矛盾**：检出唯一真相是 `vendor/*/package.json:4`（lock 里全是 `link:`）：**cordis 4.1.0 / loader 1.1.0 / include 1.1.0 / timer 1.2.0**；旧为 4.0.5 / 1.0.6 / 1.0.10 / 1.1.7。rc.1 notes 与检出相符；alpha.3 写的 Include 1.1.1 **在检出里不存在**（`grep 1.1.1 vendor/include/package.json` = 0 命中）⇒ §九 缺口 1 关闭。
- 本机判定：4610 行 `cordis.patch.yml`（11 处 MCP insert、`patchReload: live`）全在这一层，**必须重验合并与热加载**。

**A5 · 官方组合包列表改由 `@deepseek-ai/dsh-official-bundles` 导出 —— 已核实为真破坏**
- 新包存在：`packages/util/official-bundles`（`@deepseek-ai/dsh-official-bundles@0.2.2-rc.1`），导出 `PROFILE_TEMPLATES`（`src/bundles.ts:10`）与 `DEFAULT_PROFILE_BUNDLES`（`:44`）。
- **旧入口确实断了**：旧 `app-boot/src/index.ts:71` 导出 `PROFILE_TEMPLATES`，新 `app-boot` 全文 `grep` 该符号 = **0 命中**（上游自己把 `apps/cli/src/profile-boot.ts:34` 的 import 源改成了新包）。
- 本机判定：本地包/皮肤若从 `@deepseek-ai/dsh-app-boot` 导入 `PROFILE_TEMPLATES` 会拿到 `undefined`。试点：`grep -rn dsh-app-boot dsh-domus-0.2.1-rc.2/profiles/web/packages/ 补丁/ 皮肤/`。

**A6 · `run_code` 取消语义：`CODE_RUN_FAILED` → `ABORTED`**
- 本机判定：我们自写的前端/脚本若按旧错误码分类取消，会把"取消"读成"失败"。

**A7 · `agent/request` 不再允许改路由，插件应改用 `agent.model`**
- 本机判定：插件侧迁移项，与 A3 同批过。

### 2.2 软命中（B 类：不改也能起，但有后果）

| # | 变更 | 后果 | 处置 |
|---|---|---|---|
| B1 | **`fs-observation-policy` 行默认 `disabled: true`**（新 `base/cordis.patch.yml:292-294`；旧同文件 `:292-293` 无此行 = 默认开）。该插件**无 Config schema**，开法只能是行级布尔 | 失去“没读就改”的默认拦截：没有它，工具保留 provider 的**无条件写入**行为（`fs/fs-observation-policy/src/index.ts:4-5`），报错码 `FS_NOT_OBSERVED`、文案 `edit requires reading … first`（`:91`） | **决策 D4：显式恢复** —— profile 覆盖层写 `- id: fs-observation-policy` / `disabled: false`（官方文档同口径：`docs/tool-catalog.md:1178`） |
| B2 | **Web Fetch 不再拒绝非公网地址**（可用于代理与内网，部署应自行限制） | 对内网 MCP 链路是利好；SSRF 责任转到部署侧 | **决策 D4：接受新默认**，在本机单用户前提下风险可接受 |
| B3 | 未声明容量的自定义模型默认 上下文/最大输出 = 十进制 1 M / 128 K（原 128 K/8 K） | 小端点若没显式写容量，会被当成 1 M 上下文而**延迟压缩** | 阶段 3 核 `cordis.patch.yml` 里所有 `models:` 是否都写了显式容量 |
| B4 | "自定义插件市场"→"自定义插件索引"（读用户添加的索引文件；生成器排除 private / tag / 默认分支包） | 入口改名 + 数据源变；文档/技能里的操作路径要同步 | 阶段 7 之后改 `用户笔记/`、`skills/` 里的路径 |
| B5 | 插件管理支持**更新第三方插件包**、热更新失败自动回滚旧版 | 这是好事，但**会把我们手工热改的包覆盖掉** | 升级前明确 `remote-web-ui/lib` 那 7 个 `.bak-*` 的去留（决策 D5 后大多作废） |

### 2.3 明确不中招（省掉的动作）

| 项 | 依据 |
|---|---|
| Node.js 下限提到 **24.9** | 本机 `node -v` = **v26.13.0**，已满足 |
| "从 profile 的 `dsh.profile.bundles` 移除 `@deepseek-ai/dsh-experimental-tool-worktree`" | 我们 19 条 bundles 里没有它 |
| HTTP/2 / 代理层 | **本区间零改动**；`tools/dsh-force-h1.mjs` 原样保留 |
| relay / 配对 / 手机 App | **本区间零协议变化**；唯一变量是 WS 压缩默认开启 |

### 2.4 官方 upgrade-guide 逐条判定（2026-11-04 补，**这是权威口径**）

上游把每处对外可感知的破坏性变更登记在 `docs/upgrade-guide/<从哪个版本升>/<topic>/guide.zh.md`。
我们这份是 **27 个目录 / 613 行中文**（我初稿只看到其中一个碎路径，等于没读——教训见 §11.2）。判据基座：本 home 的 `cordis.patch.yml`（记 P）+ `profiles/web/package.json`（20 个 bundle）+ 检出。

| 主题 | 判定 | 判据 / 动作 |
|---|---|---|
| **tool-executor-plugins** | **命中（已处理）** | P:4593/4595 已写 `tool-executor-native: disabled:true` + `tool-executor-ptc: disabled:false`；`start-web.py` 里无 `DSH_TOOLS_MODE` 注入 |
| **conditional-tools** | **命中（行为）** | 原文：步骤中途重新注册工具会让该步尚未开始的调用失败。我们挂 10 个 MCP（P:32/39/47… 共 19 处 `mcp启动器.py`）⇒ **别在会话跑到一半重连 MCP**；重连后该步剩余 MCP 调用会 `UNKNOWN_TOOL`，等下一步再调 |
| **new-session-blank-reuse** | **命中（行为）** | 新会话会复用工作区内第一个未开始、未归档的空白 Session。`@linxin666/dsh-client-ui-browser-view/lib/index.js` 调 `startSession(` ⇒ 要「用某 preset 新开」须显式传 `{ agentPreset }`，否则可能接管别的 preset 留下的空白会话 |
| **pi-ai-protocol-replay** | **需实测** | 原文：工具参数无效 ⇒ `MALFORMED_RESPONSE`，**默认重试策略不重试该码**。我们把 `MALFORMED_RESPONSE` 显式放进 `retryableCodes`（P:241）⇒ 应仍会重试。实测点：坏窗口下是否仍 5 次重试才整轮失败 |

**不命中 23 项**（逐条判据已核，按原因归组）：

- 我们不用那些面：`headless-policy-composition`（跑 `--profile web`）、`sdk-desktop-context`、`sdk-minimal-checkpoints`、`cua-consent-storage`/`cua-preset-scope`/`cua-relative-coordinates`（无 CUA 条目）、`persistent-terminal-controls`（没挂 experimental-terminal-bundle）、`approval-projection-dependency`（不自组 Client/Host）、`auto-review-shutdown`/`auto-review-user-sources`（非 headless、无 Auto overlay）
- 第三方包没碰那些接口：`context-menu-services`（`grep ctx.menus/MenuTargetMap` = 0）、`built-in-japanese`（`addLanguage(` = 0）、`file-drag-callbacks`（`fileDrag` = 0）、`session-store-writes`（`session/created` 只在文档里）、`webserver-index-peer`（remote-bridge 已按 `(peer)` 新签名调用）、`official-bundle-lists`（无人从 `dsh-app-boot` 导入 `PROFILE_TEMPLATES`）
- 我们没做的事：`session-projection-handles`（无自注册；`sessionProjections` 只命中已退役的 sandbox 补丁）、`model-badge-package-removal`（P 从未 override 该行，不会报缺条目）
- 数字/环境已满足：`node-24`（v26.13.0）、`pi-ai-default-capacities`（两个 provider 都显式给量）、`pi-ai-model-catalog`（`deepseek-v4.1-flash 1000000/384000` 仍在册）
- 未选中新路径：`web-fetch-private-destinations`（`web.fetchProvider` 已换 `deepseek-fetch-api`，base 的 `web-fetch-http` 未被选中）、`ptc-script-format`（未用 `programFormat`/`vm-script`，PTC 走 per-call 默认）

---

## 三 · 机械核查（19 个 bundle + 4 条脆依赖）

### 3.1 实装版本（读 `node_modules/*/package.json`，非 semver 声明）

| 包 | 实装 | 本次风险预判（按 A3 打击面） |
|---|---|---|
| `@linxin666/dsh-web-all` | 0.4.8 | **决策 D2：升**；全家桶一起动 |
| `@linxin666/dsh-client-ui-session-id` | 0.4.8 | 随全家桶 |
| `@linxin666/dsh-remote-web-ui` | 0.4.8 | **决策 D5：撤销**（不在 package.json/bundles，仅 patch.yml 引用） |
| `@linxin666/dsh-remote-bridge` | 0.4.8 | **启用**（去掉 `disabled: true`） |
| `dsh-better-sidebar` | 0.28.0 | 中（前端为主，接口风险低） |
| `dsh-context` | 0.73.0 | **高**（碰投影/上下文组装） |
| `dsh-session-insights` | 0.5.2 | **高**（碰投影/工具执行） |
| `dsh-omnibus-search` | 0.1.0 | **高**（工具执行 + `link:` 本地依赖） |
| `@perrylink/dsh-plugin-kit` | 0.1.17 | **高**（插件基座，接口变更首当其冲） |
| `@perrylink/dsh-skill-pack-security-provider` | 2.2.24 | 中 |
| `dsh-industry-research` / `dsh-plugin-guide` / `dsh-research-report` | 0.3.19 / 0.3.33 / 0.3.22 | 中（工具面，若用 `tools.resolve` 则高） |
| `dsh-deepread` / `dsh-ppt-studio` / `dsh-plugin-wallpaper-engine` / `@changfenhuang/dsh-annotation` / `dsh-linkdigest` | 1.0.1 / 1.1.5 / 1.3.1 / 1.4.10 / 1.0.0 | 低—中 |
| `dsh-suigintou-ui-patches` | `file:packages/...` | **自维护**，见 §四 |

bundles 共 **19 条**（`profiles/web/package.json`），`patchReload: "live"`。

### 3.2 四条脆依赖（重建 home 时最先断的）

1. `dsh-linkdigest` —— `github:` 源
2. `dsh-ppt-studio` —— `github:` 源
3. `dsh-omnibus-search` —— `link:<挂载d>:/...`（**跨 Windows 盘**）
4. `dsh-suigintou-ui-patches` —— `file:packages/...`（随 home 走）

> 顺带：本次上游修了「自托管 Git 插件安装：HTTPS 读不到且 SSH 可用时自动改用 SSH」与「含 prepare 脚本的安装显示授权与重试」——**对我们这四条是利好，但不能当已修**，阶段 3 逐条重装验证。

### 3.3 本 home 里 18 处本地绝对路径（重建时逐条核）

| 位置 | 内容 | 处置 |
|---|---|---|
| `:31,38,46,53,60,67,74,89,98,114` | `<挂载d>:/DataServices/MCP/mcp启动器.py` ×10（全部 MCP） | 原样（`<挂载d>` 仍在） |
| `:150` | `cache/session-query.sqlite`（home 内） | **必须改写**，否则两个 home 抢同一 SQLite 索引 |
| `:271` | `<挂载d>:/游戏/SteamLibrary/...`（壁纸引擎素材） | 原样 |
| `:303,1095,2074,2895,3734` | `home/patches/0.1.7-agent-presets/cwd-fallback.mjs` ×5 | 随 home 复制 |
| `:4542` | `$HARNESS/tools/dsh-instance-identity.mjs` | 原样（仓库工具，活依赖） |

### 3.4 ⭐ 全家桶版本矩阵：**必须按 home 分开**（2026-11-04 补，用户点名）

**耦合机制**：`@linxin666/dsh-web-all` 用**精确钉**（`0.4.15`，非 `^0.4.15`）把 20+ 个子包锁在同一版本号，且每个子包的 `peerDependencies` 都写着 `@deepseek-ai/dsh: >=<某个 DSH 版本>`。
⇒ **web-all 的版本号与 DSH 基座是一对一绑定的，不能跨 home 混用。**

| web-all | peer 要求 | 发布 | 归属 |
|---|---|---|---|
| 0.4.8 | `>=0.2.1-rc.2` | 10-20 | **现役 `dsh-domus-0.2.1-rc.2` —— 锁死不动** |
| 0.4.9 | `>=0.2.1-rc.3` | 10-26 | ⚠️ 装到 rc.2 上即违反 peer |
| 0.4.10 | `>=0.2.1-rc.3` | 10-26 | 同上 |
| 0.4.11 | `>=0.2.1-rc.3` | 10-27 | 同上（**11-01 笔记原打算升到这个，是错口径**） |
| 0.4.12 | `>=0.2.1-rc.3` | 10-29 | 同上 |
| 0.4.13 | `>=0.2.1-rc.3` | 10-31 | 同上 |
| 0.4.14 | `>=0.2.1-rc.3` | 11-02 | 同上 |
| **0.4.15** | **`>=0.2.2-rc.1`** | **11-04 16:03Z** | **新 home `dsh-domus-0.2.2-rc.1` —— 唯一满足 peer 的版本** |

三条推论（都能独立复核）：

1. **0.4.15 在现役上装不了 / 也不该装**（peer 要求 `0.2.2-rc.1`）⇒ **回滚时新 home 的全家桶必须一起换回 0.4.8**，只回滚基座会留下一个 peer 不满足的包（这正是"精确钉反过来咬人"）。
2. **0.4.9–0.4.14 与现役 `0.2.1-rc.2` 全不匹配** ⇒ 11-01 笔记写的「`0.4.8 → 0.4.11+`」是**错的口径**（0.4.11 要求 ≥rc.3）。**这就是"必须分开"的直接证据。**
3. 0.4.15 发布于 rc.1 之后 **2 小时 56 分**（13:07Z → 16:03Z）⇒ 作者已适配，但没有"回头补 0.2.1 线"的版本；两条线各自往下走，**不会再有交叉兼容**。

**`remote-web-ui` 已从全家桶移除（决策 D5 的硬证据）**

| | 0.4.8 | 0.4.15 |
|---|---|---|
| `dsh-remote-web-ui` | ✅ 是依赖 | ❌ **已移除** |
| `dsh-remote-bridge` | ✅ | ✅ 保留（官方入口） |
| 子包总数 | 20 | 23 |

- 0.4.15 **新增**：`dsh-agents`、`dsh-client-ui-browser-view`、`dsh-client-ui-diagrams`、`dsh-client-ui-message-edit`、`dsh-client-ui-task-board-team`、`dsh-task-board-remote`
- 0.4.15 **移除**：`dsh-client-ui-git-graph`、`dsh-remote-web-ui`、`dsh-update`
- ⚠️ **诚实标注**：npm 上 `dsh-remote-web-ui@0.4.15` **仍在发布、且没有 `deprecated` 标记**（peer `>=0.2.2-rc.1`）。所以"上游已放弃"应精确表述为：**它被移出了全家桶依赖、官方入口改走 `remote-bridge`**；包本身还在发。我们按 D5 撤销其配置段。

---

## 四 · 三份源码补丁 + 本地加速包的现状

| 补丁 | 打的上游文件 | 幂等判据 | 本轮判定 |
|---|---|---|---|
| 空回复兜底 | `llm-deepseek/src/translate.ts`（166 行）、`llm-pi-ai/src/stream.ts`（244 行）+ 2 个 spec | `'EMPTY_RESPONSE'` | ✅ **4 文件 / 5 hunk 前像全部命中 ⇒ 能原样重放**；上游**未修**（`translate.ts:148` 仍按块数判定） |
| **Markdown 渲染** | `client/ui-conversation/src/client/user-text/UserText.tsx`（64 行） | `USER_MARKDOWN_LABELS` | ⚠️ **要重写，但只改 2 处锚点**：import 行新增 `HoverCardGroup`（`:4`）、`<span>` → `<HoverCardGroup as=span>`（`:45`）。语义结构未变（`apply.ts:185` 仍默认 `PlainUserText`，上游**没有**用户输入渲染 Markdown 的开关）⇒ 补丁**仍必要** |
| sandbox-scratch | `sandbox/src/index.ts`、`sandbox-local/src/profiles.ts`、`sandbox-policy/src/index.ts` | `policy.scratchRoot !== undefined` | ❌ **建议放弃**：`sandbox-policy` 7 个 hunk **全部 0 命中**；上游原生已有等价能力（`SandboxExecutionPolicy.additionalWritableRoots`、`roots.ts:82`、`--tmpfs /tmp` 之后的 later-wins bind）。且当前**空转**：三个 home 的 `cordis*.yml` 里 grep 不到 `sandbox-policy` 段，`scratchRoot` 从未配置 |

**上游把 4 项隐患全修了（逐项实证）**：裸 URL 与中文标点（`markdown-autolink-literals.client.spec.ts:12-27`，覆盖全角标点）、Windows 反斜杠路径（`windows-path-destinations.ts:32`）、单个 `~`（`parse.ts:23` `singleTilde: false`）、行号容错（`file-link.ts:36-44`），另加一条没预期的：中文紧贴 `**粗体**`（`cjkFriendlyStrong.ts:55-58`）。
⇒ **冲突面从「最高风险」降为「改 2 行锚点」**；但「用户消息里要不要渲染 Markdown」仍是我们的产品选择，上游没给开关，所以补丁不能靠上游代替。

**本地 UI 加速包** `profiles/web/packages/dsh-suigintou-ui-patches`：含 `.md-table-wide`（`lib/client.js:252`、`:260`）。上游这次做了"宽表格在局部容器滚动"，两者**会打架**（压缩 vs 滚动）⇒ 试跑时按现象二选一，见 §八。

---

## 五 · 手写配置处置清单（在**源码层**改，别只改合并产物）

| # | 位置 | 动作 |
|---|---|---|
| 5.1 | `:4571-4572`（`web-ui-remote-web-ui` 段）+ `:4600-4610`（受管块 `remote-web-ui lan-bind block`） | **整段撤销**（决策 D5：上游已放弃该插件）。受管块由插件自动重写，**先删插件段再让新版重写**，别手改块内容 |
| 5.2 | `:4594-4595`（`web-ui-remote-bridge` + `disabled: true`） | **去掉 `disabled: true`**，启用 |
| 5.3 | `:4581`（`# relay: false`）、`:4587`（`requirePairingForLan: false`，全 home 唯一出现处） | 随 5.1 一并删除 |
| 5.4 | `:164`（`llm-deepseek` 插件级 `disabled: true`） | **保留**（已被账户登录接管，属有意为之） |
| 5.5 | `:1058/:2037/:2858/:3697/:4507`（`tool-ralph` 工具级 disabled ×5） | **保留** |
| 5.6 | 5 处 `workflow-ptc`（`:1048/:2027/:2848/:3687/:4497`） | **不动** —— base bundle 产物（`base/cordis.patch.yml:400-403`），手改会在重合并时漂移 |
| 5.6b | **新增**：`- id: tool-executor-native` / `disabled: true`；`- id: tool-executor-ptc` / `disabled: false` | **必须写**，否则 PTC 静默消失（§2.1 A2） |
| 5.7 | **新增**：`- id: fs-observation-policy` / `disabled: false` | **必须写**，否则「没读就改」不再拦（§2.2 B1、决策 D4） |
| 5.8 | `patchReload: "live"` | 重验热加载在 Cordis 4.1.0 下仍成立 |
| 5.9 | `:150` `session-query.sqlite` 路径 | 新 home 里必须指向新 home |

---

## 六 · 本次真正该吃到的收益（对照 11-01 的清单逐条核）

| 类 | 落地情况 |
|---|---|
| 手机/平板输入（少弹软键盘、发送后收起、键盘平移时光标滚动） | ✅ 在 rc.1 里 |
| 触屏动作不被 hover 提示挡住、窄屏设置页全屏+横向导航、触屏输入 16 px | ✅ |
| **WS 压缩默认开启**（减少大量历史传输；`websocketCompression` 可关） | ✅ **默认值反转** |
| **断线/重连期间暂停聊天运行计时**，恢复后按轮次起点显示 | ✅ |
| 停止后补发的插话与新消息按日志顺序显示 | ✅ |
| **工作步骤收起后保留全部助手文字回复，可切"仅最终回答"** | ✅ |
| Web 静态资源 ETag（304） | ✅ |
| 插件管理：更新第三方包 + 热更新失败回滚 + 富文本详情 + 完整诊断与 Host 日志位置 | ✅（B5） |
| 多语言：日/西/法/德/俄/巴西葡 | ✅ |
| 统一右键 + 键盘菜单（会话/工作区/侧栏，开放开发者扩展） | ✅（alpha.3） |
| 文件预览常驻目录树 | ✅（alpha.3） |
| 引用插入输入框 + 完整历史复制为 Markdown | ✅ |
| Markdown 六条修复（`~`、裸 URL 吞中文、Windows 反斜杠、行号容错、代码高亮卡死、行范围） | ✅ **除跨行 `$$`（已回退）** |

> 判据提醒：**"代码高亮导致页面长时间卡死"与我们诊断过的"网络卡死"症状极像**。升级后若仍卡，先查它，别继续怪 WS。

---

## 七 · 升级方案（分阶段，含验收判据）

> **硬约束：阶段 0–6 全程不碰现役实例。** 现役 `dsh-domus-0.2.1-rc.2` 一秒不停，试跑用 `--try` 自动避让端口。

### 阶段 0 · 备份与快照（零风险）

| 步 | 命令 | 判据 |
|---|---|---|
| 0.1 | `cd dsh-domus-0.2.1-rc.2 && git add -A && git commit -m "pre-0.2.2-rc.1 升级前快照"` | `git log --oneline` 有 1 条提交，`git ls-files \| wc -l` > 0 |
| 0.2 | `tools/backup-dsh.sh` + `python3 tools/check-profile-links.py` | 归档落 `backups/`；链接护栏干净 |
| 0.3 | 三件套快照 `package.json` / `pnpm-lock.yaml` / `cordis.patch.yml` → `/tmp/.dsh-tmp/snap-0.2.1/` | 三份齐 |
| 0.4 | **确认 9007 的真实占用者**（须在你自己的终端，见 §9 缺口 4） | 能说清"谁在跑、停会不会断当前界面"，否则不做阶段 7 |

### 阶段 1 · 新基座检出

```bash
cd $HARNESS
git clone --depth 1 --branch dsh-v0.2.2-rc.1 \
  git@github.com:deepseek-ai/deepseek-harness.git 原始代码研究/v0.2.2-rc.1
```
- **必须在带代理的终端里跑**（用户有代理 + SSH key）。
- ⚠️ **2026-11-04 更正（实测推翻，初稿写错）**：初稿写「本机直连 git-over-https 会挂、得走 `gh` 通道」，**这条是错的**。
  真因是 **agent 沙箱不继承代理变量**（`env | grep -i proxy` 零命中），那次 `git ls-remote` 的
| 只按 release notes 建 §二 的破坏性变更清单就够 | **不够**。官方另有 `docs/upgrade-guide/<从哪个版本升>/<topic>/guide.zh.md`（25 个主题、613 行中文），初稿完全没读；而它也不全（`list-agents` 那条不在里面） | `docs/upgrade-guide/v0.2.1-rc.2/` 目录清单 + `grep -rln list-agents` = 0 |
| 0.2.2 只改 PTC 的挂载方式 | 不止：`tool-subagent-control` 删掉了 `./list-agents` 子路径导出、工具改内部注册 ⇒ 预设里那类独立插件行**全部失效**。凡 `name:` 带子路径的都要逐条核 | 新旧 `package.json` 的 `exports` 对比：旧有 `./list-agents`，新无 |
  `OpenSSL SSL_read: unexpected eof while reading` 是沙箱环境产物，**不是本机网络状况**。
  本机 `git config --global http.version` 已设 `HTTP/1.1`。⇒ 正常 `git clone` 即可。
- **退路 1（免 SSH）**：`git clone --depth 1 --branch dsh-v0.2.2-rc.1 https://github.com/deepseek-ai/deepseek-harness.git 原始代码研究/v0.2.2-rc.1`
- **退路 2（都失败才用）**：`gh api repos/deepseek-ai/deepseek-harness/tarball/dsh-v0.2.2-rc.1 > /tmp/.dsh-tmp/v0.2.2-rc.1.tar.gz` 再解包（失去 `.git`，但 package.json 里的 version 足够构建）
- ⚠️ 需要 `--depth 1`：不加则全历史体积很大（现有检出就是 shallow，`rev-parse --is-shallow-repository` = true）
- 判据：`git -C 原始代码研究/v0.2.2-rc.1 describe --tags` → `dsh-v0.2.2-rc.1`；`package.json` 的 `version` = `0.2.2-rc.1`
- 然后五步：`corepack prepare pnpm@11.28.5 --activate` → `pnpm install` → `pnpm run build` → `pnpm run build:native-system`
  判据：`apps/web/dist` + 各 `lib` + `system.node` 齐（**缺 `system.node` 第一次开会话才炸**）
- ⚠️ 跑 `pnpm`/`node` 会触发取证 preload（`dsh-fetch-trace` / `dsh-force-h1`）；若 build 报奇怪错误，用 `NODE_OPTIONS= pnpm ...` 复跑一次再判断（**待验**）

### 阶段 2 · 体检工具更新 + 机械核查（顺序不能反）

1. ~~先按新版规则更新 `tools/check-plugin-compatibility.mjs`~~ → **取证结论：不用改**。上游判据文件 `plugin-compatibility.ts` 新旧 **diff 为空**（字段仍是 `engines.dsh` → `peerDependencies`，返回键仍叫 `requirements`，不是 manifest 字段），工具已实测跑通（`--checkout 原始代码研究/v0.2.2-rc.1` → exit 0）。可选增补：新版多了一个工具没镜像的闸门 `dsh.bundle.platforms`（`bundle-platform.ts:25`），要覆盖就加在 `check-plugin-compatibility.mjs:141` 之后、复用同一 try/catch
2. `node tools/check-plugin-compatibility.mjs --profile dsh-domus-0.2.1-rc.2/profiles/web --checkout 原始代码研究/v0.2.2-rc.1`
3. 判据：报出的禁用清单**与 §3.1 的"高风险"列能对上**（多了要解释、少了要查规则）
4. 同阶段做：A2 的 `workflow-ptc` 新挂载方式、A5 的 `app-boot` import、B1 的防护键名、B3 的 `models:` 容量

### 阶段 3 · 包与配置预处理

| 步 | 动作 | 判据 |
|---|---|---|
| 3.1 | **新 home 装 `dsh-web-all@0.4.15`**（决策 D2 + D6：唯一满足 `peer >=0.2.2-rc.1` 的版本，见 §3.4）；**现役 home 的 0.4.8 一个字节都不动** | `node -e "console.log(require('@linxin666/dsh-web-all/package.json').version)"` → `0.4.15`；新 home 的 peer 自检不报错；`pnpm-lock` 更新 |
| 3.2 | §五 配置处置清单 5.1–5.9 | `python3 tools/check_patch_layers.py --profile web` **退出码 0** |
| 3.3 | 4 条脆依赖逐条重装验证 | 装得上、能加载 |

### 阶段 4 · 补丁重放（2026-11-04 已静态预判，见 §四）

| 补丁 | 动作 | 判据 |
|---|---|---|
| 空回复兜底 | 干跑 → `--apply` | 4 文件 / 5 hunk 全中；`git -C 原始代码研究/v0.2.2-rc.1 diff --stat` 符合预期 |
| Markdown 渲染 | **改 2 处锚点后重放**（`UserText.tsx:4` 的 import、`:45` 的 `HoverCardGroup`），并同步 manifest 的 `verify` | 打完用户消息里的粗体/列表/代码块渲染正常，`ellipsis` 预览行仍纯文本 |
| sandbox-scratch | **放弃**（manifest 的 `on_drift` 第 2 条即此判据）。将来若真要 scratch 落点，改走上游 `additionalWritableRoots` + 一次 `scratchRoot → additionalWritableRoots` 配置迁移 | 漂移报告里只剩已知项 |
| 纪律 | **不 apply 未经预判的补丁**；apply 完立刻 `git status --porcelain` 留证 | 检出改动只限补丁涉及的文件 |

### 阶段 5 · 建新 home

```bash
python3 tools/stage-upgrade-home.py --src dsh-domus-0.2.1-rc.2 --dst dsh-domus-0.2.2-rc.1          # 干跑
python3 tools/stage-upgrade-home.py --src dsh-domus-0.2.1-rc.2 --dst dsh-domus-0.2.2-rc.1 --apply
python3 tools/repair-profile-links.py --home dsh-domus-0.2.2-rc.1 --checkout 原始代码研究/v0.2.2-rc.1
```
- ⚠️ `stage-upgrade-home.py` 的**默认值仍是 `0.2.0 → 0.2.1`**，必须显式传 `--src/--dst`
- ⚠️ **解析拦截层必须在第一次启动之前建好**（缺它 `check_patch_layers` 只报几十个 id 而非全量 → 触发 tsc+tsdown 全量重建，体感"死机"）
- 判据：路径重写数对得上、残留 0、`session-query.sqlite` 指向新 home

### 阶段 6 · `--try` 试跑（不碰现役）

`./start-web.py --try v0.2.2-rc.1` → 端口自动避让到 9008+

**trial 验收 15 条（11 条沿用 + 4 条本次新增）**

沿用：①`grep -c "disabling profile plugin"` = 0 ②插件页 bundle 数与预期一致 ③`{{cwd}}` 活着 ④`"event":"force-h1"` 的 `"applied":true` 且 argv 指新检出 ⑤历史会话标题在 ⑥`session_event_search` 有结果 ⑦Markdown 粗体渲染 ⑧皮肤 navia / war-thunder 正常 ⑨设置页字体项与本地补丁不打架 ⑩委派子代理返回**子代理 id + 完成通知** ⑪搜索策略符合 MCP 优先

新增：⑫**PTC 还活着**（`run_code` 能跑、5 个预设的 workflow-ptc 都加载）⑬**19 个 bundle 逐个看启动日志**，挂掉的一律关掉登记（决策 D2）⑭**先读防护已恢复**（模型改文件前会被要求先读）⑮**WS 压缩**：长历史推送是否正常（异常先关 `websocketCompression`）

### 阶段 7 · 切正 / 搬对话 / 回滚

| 步 | 动作 | 判据 |
|---|---|---|
| 7.1 | 新建 `启动器配置和日志/版本信息说明/v0.2.2-rc.1.toml`（照 v0.2.1-rc.2 那份结构，`required_markers` 要能命中新 home） | 启动器 preflight 0 |
| 7.2 | 改 `当前配置.toml` 的 `version` | **这一步是人写的决定**，工具不代写 |
| 7.3 | `./tools/cutover.sh --to-ver v0.2.2-rc.1`（**自己的终端 + 先 `--dry-run`**） | 停双方 → 搬对话 → 隔离复核通过 |
| 7.4 | 新 home `git init`（首次提交留给下次开机前 `commit_home`） | 运行中提交有半帧风险，不手工提交 |

**回滚（原文口径）**：三件套快照回填 + `version` 改回 `v0.2.1-rc.2` + 重启。
> 会话记录契约不变（都读 v4），所以**对话不会因为回滚打不开**；但**新版本里改过的 profile 配置/插件版本必须一起回滚**——精确钉反过来咬人：新版专属包在旧基座下会被禁用。
> 停机三级处置见 `升级/DSH停机卡.md`：L1 热加载止血（已验证有效）→ L2 `--stop`（TERM→20 s→SIGKILL）→ L3 `kill -9`。

---

## 八 · 与本地补丁/皮肤的新冲突面

| # | 冲突 | 判据（试跑时看） | 动作 |
|---|---|---|---|
| 8.1 | `.md-table-wide` 强制压缩 **vs** 上游"宽表格局部容器滚动" | 长表格**能不能滚** | 能滚 → 删本地压缩规则（滚动体验更好）；不能滚 → 保留压缩 |
| 8.2 | 原以为皮肤里有 tooltip 隐藏规则，**实际没有** | `grep -rn 'tooltip' skins/` 应零命中 | 无需动作；上游"触屏不被 hover 挡"是纯收益 |
| 8.3 | 新增"统一右键 + 键盘菜单"（会话/工作区/侧栏） | 皮肤在菜单弹出层的样式是否漏底/被裁 | 需要就补一条 `:where(.menu-*) ` 类规则 |
| 8.4 | Markdown 补丁关闭后的渲染回退 | 中文标点吞进 URL、Windows 反斜杠路径、单个 `~` | 任一条劣化 → 启动 D3 的"按路线 A 重写"分支 |

**原则**（沿用 `皮肤/皮肤主题笔记.md`）：**上游在 DOM 层修掉的，CSS 绕过就该撤**；插件只能注 CSS、官方能改 DOM，所以官方修法通常更温和。

---

## 九 · 缺口（本次没验的，别当成已验）

1. ~~Include 版本矛盾~~ → **已关闭**：检出实测 cordis 4.1.0 / loader 1.1.0 / include 1.1.0；alpha.3 的 1.1.1 不存在
2. **rc.1 notes 有洞**：漏 alpha.3 两条（跨行 `$$` 回退、空会话命名），已用 `git compare` 证代码在
3. **19 个 bundle 的运行时兼容性**：加载期全过（无 `did not activate`），**运行期**只有 `dsh-ppt-studio` 确认坏（§11.6，已卸载）；其余未见症状但未逐个点验
4. ~~9007 占用者未知~~ → **已关闭但换了形态**：9007 是我们自己的实例 ⇒ **停实例会断当前界面**，阶段 7 要先「新实例起在 9008、旧实例最后停」
5. **是否自部署了 bootstrap / SSH helper 未核**（A1 的 SSH 协议 2→3 只影响自部署场景）
6. ~~B1 键名未取~~ → **已关闭**：行 id `fs-observation-policy`，无 schema，只能靠行级 `disabled: false`
7. ~~PTC 挂载方式未取~~ → **已关闭**：`tool-executor-native` / `tool-executor-ptc` 两行，见 §2.1 A2
8. **皮肤锚点未验**：新菜单/新设置页图标位是否破坏 12 套皮肤
9. **`patchReload: live` 在 Cordis 4.1.0 下未验**，尤其与 §5.6b 新增的两行执行器叠加时
10. **`web-all 0.4.15` 的 23 个子包没逐个核 peer**：只核了主包与 remote-web-ui / remote-bridge / session-id 三个，其余按「随主包锁定」处理
11. **官方模型的 `defer_loading` 全延期 400 —— 已定位，上游同案**：见 §11.8。机制是核心投影的不变量漏洞（nl 基线与当前活跃工具集不相交时，所有工具都被标延期）；**未修复**，临时对策是这类会话切自定义端点。

---

## 十 · 证据索引（都能独立重跑）

```bash
# 版本拓扑与基线（区间内 6 个 tag，无隐藏 tag）
gh release list --repo deepseek-ai/deepseek-harness --limit 25
gh api "repos/deepseek-ai/deepseek-harness/git/matching-refs/tags/dsh-v0.2" --jq '.[].ref'
gh release view dsh-v0.2.2-rc.1 --repo deepseek-ai/deepseek-harness   # 末行即 Full Changelog 基线
# 包含关系铁证
gh api repos/deepseek-ai/deepseek-harness/compare/dsh-v0.2.2-rc.1...dsh-v0.2.2-alpha.3 --jq '.ahead_by,.behind_by'
gh api repos/deepseek-ai/deepseek-harness/compare/dsh-v0.2.1-rc.5...dsh-v0.2.2-rc.1    --jq '.status,.total_commits'

# 本机事实
git -C dsh-domus-0.2.1-rc.2 log -1               # 零提交
git -C dsh-domus-0.2.1-rc.2 status --porcelain | wc -l
git -C 原始代码研究/v0.2.1-rc.2 rev-parse --is-shallow-repository   # true
grep -rn 'TOOLS_MODE\|tools.mode' start-web.py tools/dsh_config.py  # 零命中
grep -n 'workflow-ptc' dsh-domus-0.2.1-rc.2/profiles/web/cordis.patch.yml
# 全家桶版本矩阵（§3.4）—— 走 npmmirror，不需要代理
curl -sS 'https://registry.npmmirror.com/@linxin666%2Fdsh-web-all' | python3 -c "import json,sys;d=json.load(sys.stdin);[print(v,(d['versions'][v].get('peerDependencies') or {}).get('@deepseek-ai/dsh')) for v in d['versions'] if v.startswith('0.4.')]"
curl -sS 'https://registry.npmmirror.com/@linxin666%2Fdsh-web-all' | python3 -c "import json,sys;d=json.load(sys.stdin);print(list((d['versions']['0.4.15'].get('dependencies') or {}).keys()))"
grep -rn 'md-table-wide' dsh-domus-0.2.1-rc.2/skins/                 # 零命中
grep -rn 'md-table-wide' dsh-domus-0.2.1-rc.2/profiles/web/packages/dsh-suigintou-ui-patches/lib/client.js
ls dsh-domus-0.2.1-rc.2/profiles/web/node_modules/@linxin666/dsh-remote-web-ui/lib/*.bak-*
```

> 数据来源：`gh release view`（6 次）+ `gh api compare` + 本机只读命令，均在 2026-11-04 采集。
> **没有一条结论来自"记忆里的版本说明"**；与 11-01 引导笔记冲突之处已在 §1.3 逐条标注。

---

## 十一 · 执行记录（待回填）

### 11.0 决策记录（2026-11-04，用户口头定）

| # | 问题 | 决定 |
|---|---|---|
| D1 | 节奏 | **升，但先只做试跑、不动现役**（阶段 0–6 全程不碰 0.2.1） |
| D2 | 第三方包 | **升 `dsh-web-all` 全家桶**；启动期冲突的**先关掉**，等作者适配再开 |
| D3 | Markdown 补丁 | **先关**（本轮不重放），试跑后看渲染够不够用再决定是否按路线 A 重写 |
| D4 | 安全默认值 | **恢复"先读/外部修改防护"**；**Web Fetch 接受新默认**（允许非公网） |
| D5 | 远程层 | **`remote-web-ui` 整段撤销**（上游已放弃）；启用 `remote-bridge`。**2026-11-04 已找到硬证据**：web-all **0.4.15 把 `dsh-remote-web-ui` 从依赖里移除了**（0.4.8 还有），见 §3.4 |
| D6 | 全家桶版本 | **按 home 分开，绝不混用**：现役 = `web-all 0.4.8`（peer ≥0.2.1-rc.2，锁死）；新 home = `web-all 0.4.15`（peer ≥0.2.2-rc.1，唯一可选项）。**回滚时全家桶要一起回退** |

**陪跑假设（未单独确认，按此执行）**：除 `dsh-web-all` 全家桶外不主动升其他包；`remote-web-ui/lib` 那 7 个 `.bak-*` 随 D5 作废，不回迁；`dsh-web-all` 之外的皮肤/主题本轮不动。

### 11.1 已完成

| 时间 | 动作 | 结果 |
|---|---|---|
| 2026-11-04 | 用户整盘备份 `<F盘>:\WSL备份 20261104.rar` | ✅ 阶段 0 的「回档点」以整盘备份形式达成（home 自身仍零提交，见 §〇 阻塞 1） |
| 2026-11-04 | `git clone --depth 1 --branch dsh-v0.2.2-rc.1` | ✅ `原始代码研究/v0.2.2-rc.1`，`describe --tags` = `dsh-v0.2.2-rc.1`，`package.json` = 0.2.2-rc.1，244 M |
| 2026-11-04 | `pnpm install --frozen-lockfile --store-dir <工作区>/.pnpm-store` | ✅ **18.1 s**（复用 4.2 G 存储，零下载）→ 2.4 G |
| 2026-11-04 | `pnpm run build` | ✅ **10 gate 全过 / 0 失败 / 136.2 s**（host compiler 55.17s、client compiler 35.56s、web 5.16s） |
| 2026-11-04 | `pnpm run build:native-system` | ✅ `native/system/packages/linux-x64/bin/glibc/system.node` |
| 2026-11-04 | 源码取证（8 问）+ 补丁静态预判 | ✅ 见 §2.1 / §四，**推翻了本笔记三处判断** |
| 2026-11-04 | 补丁：Markdown 重写（`UserText-0.2.2.patch`，+24/−2）+ 空回复兜底重放 | ✅ 两个补丁源与产物都在位；sandbox-scratch 移到 `补丁/历史/`（上游已有 `additionalWritableRoots`） |
| 2026-11-04 | `stage-upgrade-home.py --src 0.2.1-rc.2 --dst 0.2.2-rc.1 --apply` | ✅ 路径重写 27 处 / 残留 0 / 有意保留 5 文件 / `cordis.patch.yml` 新路径 6 处 |
| 2026-11-04 | `repair-profile-links --names-from 0.2.1-rc.2 --apply` | ✅ 写入 265 条拦截链接；1 个包名（`dsh-omnibus-search`）按 `--source-checkout` 重指 `<挂载d>` |
| 2026-11-04 | 新 home 装依赖（`web-all 0.4.15` / `session-id 0.4.15` / `tool-session-query 0.2.2-rc.1`） | ✅ 10.1 s；`dsh-remote-web-ui` **不在** node_modules（全家桶已移除，D5 自然满足） |
| 2026-11-04 | 配置改写：撤 `web-ui-remote-web-ui`、启 `web-ui-remote-bridge`、加 3 行覆盖 | ✅ `check_patch_layers`：248 个 id / 无重复 / 可以启动 |
| 2026-11-04 | `./start-web.py --try v0.2.2-rc.1 --port 9011` | ✅ **起来了**（见 §11.4）；`disabling profile plugin` = 0；`force-h1 applied:true` 且 `dshVersion=v0.2.2-rc.1` |
| 2026-11-04 | 首次试跑：**两个功能坏**（新建会话 `agent-preset/invalid`、历史会话「会话不可用」） | 根因：预设里 5 行 `tool-subagent-list-agents` 指向新版**已删除**的 `./list-agents` 子路径导出（§11.2） |
| 2026-11-04 | 移除 5 行 + 重启（9011） | ✅ **用户实测通过**：新建会话正常、Markdown 渲染正常、皮肤正常（会话自报 `Harness 版本 v0.2.2-rc.1`） |

### 11.2 实测推翻/确认的判定

| 初稿判断 | 实测/取证结论 | 依据 |
|---|---|---|
| PTC 靠 profile 里 5 处 `workflow-ptc` 打开，升级要改这 5 处 | **错**。它是 base bundle 的 config 子条目；要加的是 `tool-executor-ptc` 行（默认 `disabled: true`） | `base/cordis.patch.yml:400-403` vs `:501-506` |
| `check-plugin-compatibility.mjs` 必须先改再体检 | **不必改**。上游判据文件 diff 为空，工具实测 exit 0 | `plugin-compatibility.ts` 新旧 diff 空 |
| 「本机直连 git-over-https 会挂，要走 gh 通道」 | **错**。那是 agent 沙箱不继承代理变量导致的，用户终端正常 | `env \| grep -i proxy` 零命中 |

### 11.3 两个新踩的坑（写给下一次升级）

1. **pnpm 11 的 store 里有一个 SQLite 索引**：store 目录不可写时报的是 `[ERR_SQLITE_ERROR] unable to open database file`，**跟网络失败长得完全不像**，容易误判成拉包失败。沙箱里必须 `--store-dir <工作区>/.pnpm-store`。
2. **`NODE_OPTIONS=` 要清**：本工作区挂着两个 node preload，构建期混进输出会把真实错误盖掉；但**不能**给 DSH 实例/启动器清空。
3. **`--try --port N` 会被受管块里的 `webserver: port: 9007` 盖掉** ⇒ 试跑去绑现役端口、`EADDRINUSE`。`--host` 旗标优先，**端口不优先**。试跑前把新 home 的 `webserver` 块端口改掉（该块原由 remote-web-ui 插件维护，D5 撤销后归我们管）。
4. **别在 agent 沙箱里跑 `start-web.py` 的账本类操作**：沙箱是 `bwrap --unshare-pid`，`/proc` 看不到宿主进程 ⇒ 它判定"主实例已死"并把 `运行记录/当前` 搬进 `历史/`。本次因此把 9007 与 9011 的记录都归档了（实例本身没死）。**账本操作只在真实终端做**；沙箱里只能看 `ss -ltn`。
5. **`tsc -b tsconfig.host.json` 默认 4 GB 堆不够**（本仓库 396 个 workspace）：`FATAL ERROR: Ineffective mark-compacts near heap limit`。补丁重建走 `node ./node_modules/typescript/bin/tsc`，不经 pnpm 的内存配置 ⇒ 需要 `NODE_OPTIONS=--max-old-space-size=10240`。
6. **预设里的插件行要用「子路径导出」机械核，不能靠报错一条修一条**：报错只报第一条（`never started`），后面的坑要等下一次重启才暴露。核法：抽出 profile 里全部 `name:`，对每个「包/子路径」查 `package.json` 的 `exports` 有没有该键，新旧一对比就是全集（本次 36 个 name 里只有 1 个真断）。
7. **「会话不可用」不等于会话坏了**：它和「新建会话失败」可以同源——预设无效时历史会话渲染同样失败。先修预设再看会话，别一头扎进 session 格式（实测 `SESSION_FORMAT_VERSION` 新旧都是 4，格式没变）。

### 11.4 离线数据同步：`tools/sync-home-data.py`（2026-11-04 新建）

试跑期现役还在写新会话 ⇒ 需要能**反复**把数据拉过去，而不是每次都重建 home。`stage-upgrade-home.py` 是「造一次」，本脚本是「同步多次」。

```bash
python3 tools/sync-home-data.py                 # 干跑：新增/更新/不变/多余 四个数 + 要写多少字节
python3 tools/sync-home-data.py --apply         # 真做（先写 .sync-tmp 再 os.replace，避免半个文件）
python3 tools/sync-home-data.py --apply --prune # 顺带删目标里源没有的文件（默认不删）
```

| 项 | 内容 |
|---|---|
| 搬什么 | `sessions/`、`attachments/`、`dsh-session-archive/`、`storages/session_projcache`、`storages/workspace.json` |
| 不搬什么 | `cache/`（索引每 home 一份，搬过去会争用）、`node_modules/`（全家桶按 home 锁版本，D6）、`.git/`、`storages/` 其余子域 |
| 离线前提 | 按 AGENTS.md 口径读 `/proc/*/environ` 找活进程 + 探配置端口；不成立则**拒绝执行**（退出码 3），绕过必须 `--force` |
| 幂等 | 按 (size, mtime) 判定，未变的不重写 |
| ⚠️ 沙箱陷阱 | agent 沙箱里会误判「有活实例」（bwrap 自身进程也带 `DSH_HOME`，看到 pid 1/2/4/5）——**真实同步请在真终端跑** |

首次干跑实测（2026-11-04，`--force`）：新增 6 / 更新 18 / 不变 955 / 需写入 9.3 MiB。

### 11.5 转正

**2026-11-05 切正完成**（用户在自己的终端执行，本文档回填实测）。

| 步 | 结果 |
|---|---|
| 停双边 | 9011 试跑实例停；9007 现役停 |
| 最后一次搬家 | `tools/sync-home-data.py --apply`（离线前提成立） |
| 改真相源 | `当前配置.toml` 的 `version` = `v0.2.2-rc.1` |
| 受管块端口 | 新 home 的 `webserver` 块从 9011 改回 **9007** |
| 起现役 | ✅ 本会话即跑在 `v0.2.2-rc.1`（父仓检出面已指向 `原始代码研究/v0.2.2-rc.1`，Web GUI 9007） |

**home 首次入库**（切正后补做：切正时它还不是 git 仓，启动器的「开机前备份」跳过了）

```bash
cd dsh-domus-0.2.2-rc.1 && git init && git add -A && git commit -m '0.2.2-rc.1 home 首次入库'
```


### 11.6 插件清退：`dsh-ppt-studio`（2026-11-05，用户决定先卸载）

**症状**：插件管理页「PPT 工作室」卡片显示 **加载失败**；其他插件未见红灯。

**根因**（逐行核过，不是版本落后）：它的预设组合 `agent-presets/ppt/agent.cordis.yml`（32 个插件行）里有两条 **0.2.2 已删除的子路径导出**：

- `@deepseek-ai/dsh-tool-subagent-control/list-agents` —— 与自家 5 个预设里删掉的是同一条（见 §11.2）
- `@deepseek-ai/dsh-plugin-manager/tools`

预设被判 broken ⇒ 前端选择器只渲染健康预设 ⇒ 卡片显示加载失败。

**关键：升级治不了。** 已把 npm 最新 `1.2.6` 的 tarball 拉下来逐行核过，**同样两条死引用还在**（且 1.2.6 相对 1.1.5 是重写版：组合文件 315 行 → 129 行）。所以这不是装旧了，是作者尚未适配 0.2.2。

**处置**：整包卸载（`profiles/web/package.json` 去掉依赖行 + `dsh.profile.bundles` 去掉条目，再 `pnpm install` 剪枝）。实测 `-47` 个包移除、`pnpm-lock.yaml` 里 0 残留、`node_modules` 已无该目录。

**将来重装的条件**：作者把上面两条子路径改掉（或改成 0.2.2 的挂载方式）之后，`dsh plugin --profile web add dsh-ppt-studio` 装回即可；它的 `dsh.engines` 声明是 `>=0.1.7-rc.1`，preflight 不会拦，**别拿 engines 当适配证据** —— 真正的判据是那两条子路径还在不在。

### 11.7 第三方插件批量升级（2026-11-05，用户判定「0.2.2 无根本问题」后）

10 个落后包一次升到 npm 最新（`profiles/web/package.json` 用 caret，与原有风格一致）：

| 包 | 旧 | 新 | 关键 peer/engine |
|---|---|---|---|
| `dsh-better-sidebar` | 0.28.0 | **0.30.0** | react ^18.2 |
| `dsh-context` | 0.73.0 | **0.81.2** | react ^18.3 |
| `dsh-session-insights` | 0.5.2 | **0.7.0** | `dsh >=0.2.1-rc.2` |
| `dsh-industry-research` | 0.3.19 | **0.3.23** | cordis ^4.0.5-alpha.1 |
| `dsh-plugin-guide` | 0.3.33 | **0.4.3** | `dsh >=0.2.2-0 <0.3.0`（正好契合） |
| `dsh-research-report` | 0.3.22 | **0.3.30** | dsh-data-quality >=0.1 |
| `@perrylink/dsh-plugin-kit` | 0.1.17 | **0.1.26** | cordis ^4.0.5-alpha.1 |
| `@perrylink/dsh-skill-pack-security-provider` | 2.2.24 | **2.2.30** | cordis ^4.0.5 |
| `dsh-plugin-wallpaper-engine` | 1.3.1 | **1.4.0** | cordis ^4.0 |
| `@changfenhuang/dsh-annotation` | 1.4.10 | **1.4.11** | cordis ^4.0.0-rc.7 / ^4.0 |

未升：`dsh-deepread 1.0.1`（已最新）、`dsh-linkdigest`（`github:` 源，按提交不按版本）、`dsh-omnibus-search`（`link:<挂载d>` 本地源）、`@linxin666/*`（0.4.15 已与 0.2.2 对齐）。

**两道门禁都过**（升级后立刻验）：

| 门禁 | 结果 |
|---|---|
| `tools/check_patch_layers.py --profile web` | 254 个 id（原 248）/ 无重复 / 可以启动 |
| `tools/check-plugin-compatibility.mjs` | 检查 230 个包，**没有一个会被 preflight 禁用** |

**副作用**：`profiles/web/pnpm-workspace.yaml` 的 `minimumReleaseAgeExclude` 被 pnpm 自动追加三行（`dsh-context@…||0.81.2`、`dsh-better-sidebar@0.28.0||0.30.0`、`dsh-plugin-guide@0.4.3`）。那是本 profile 的**供应链隔离名单**，发布时间不足 `minimumReleaseAge` 的包默认装不上，必须显式豁免 —— 升级会继续让它变长，是预期行为。

**升级 ≠ 已生效**：只改了文件与 `node_modules`，运行中实例仍持有旧模块；下次启动生效，开机时启动器自动提交 home 仓库。

### 11.8 事故：官方模型下老会话必 400（`defer_loading` 全延期），2026-11-05

**症状**：打开历史会话即整轮失败，报 `tools: at least one tool must have defer_loading=false. All tools cannot be deferred. (INVALID_REQUEST 400)`。用户观察：**官方账户模型必挂，`opencode-go` 不受影响**。

**实证**（会话 `session-272f6bba…`，preset `coding`，cwd `<挂载d>:/User Data/Documents`）

| 时点 | 模型 | 请求里声明的工具 |
|---|---|---|
| `request/header` seq 11 | `deepseek-flash`（官方） | **132 个原生工具** |
| `request/header` seq 2728 | `deepseek-v4.1-flash`（官方） | **1 个：`run_code`（PTC）** |
| `assistant/attempt` seq 2716 | turn 81 / step 1 | 400，`request_id: 158191bb-3e30-46e0-ae84-d19941636ce7` |

**机制**（`packages/llm/llm/src/content.ts:381-405`）

1. `declarations` 以**历史基线**为底（132 个原生工具，见 seq 11）
2. 后来才出现的工具（`run_code`）被写入并标 `deferLoading: true`
3. `addition-only` 分支把**当前不活跃**的名字全部删除 ⇒ 只剩那个迟到且延期的 `run_code`
4. ⇒ 整份 tools 全延期 ⇒ DeepSeek API 拒绝（它要求至少一个非延期）

**为什么和模型强相关**：`defer_loading` 只有**官方 provider 适配器**会发（`packages/llm/llm-deepseek/src/serialize.ts:165`）。自定义端点（`opencode-go` / `amici-mei`，走 `openai-completions`）的 `toolUpdate` 是 `undefined`，代码在 `content.ts:433-434` 直接**剥掉**延期标记 ⇒ 不中招。

**上游同案（社区）**

| 出处 | 关系 |
|---|---|
| `zhu1090093659/dsh-web#1947`（已闭） | **同一条 400**，方向相反：基线 `run_code`（PTC）→ 现在 native 70 个工具 ⇒ 全被算作中途新增。原文：「恢复 ptc 旧会话必 400」 |
| `BotHarness/DeepSeekBot#3137` | 新会话被全延期堵死；期望写的是「host 应至少保留一个常驻工具」 |
| `microsoft/vscode#311946` | 同一不变量在别的客户端也破（只挂 MCP 工具时全延期） |
| `zhu1090093659/dsh-web#1940` | `list-agents` 子路径 —— 与 §2.1 里我们删的那 5 行同源 |

**操作规则（记住这条就够）**

> **工具面中途变过形态的会话（132→1 或 1→70），在官方模型下必然 400。** 要接着跑就切自定义端点（`opencode-go`）；会话本身没坏，能读能搜，只是该后端不许它继续。

**评论处置**：草稿成稿于 `用户笔记/issue/2026-11-05-defer_loading全延期-评论稿-1947.md`（含目标链接与发法）。**未能代发**：`gh` 用的是 fine-grained PAT，`zhu1090093659/dsh-web` 不在其仓库授权范围，`addComment` 被拒（`Resource not accessible by personal access token`）。已在侧栏打开该 issue，待用户粘贴提交。

### 11.9 过程事故：**读-改-写整篇会截断长文档**（2026-11-05，写给下一次）

本次把 §11.6–§11.8 写好后，又在下一轮用 `read`（不带 offset，预期读到全文）+ 整篇 `write` 回写，结果**文件从 595 行掉到 552 行，§11.6–§11.8 整段消失**——说明那次 `read` 返回的是**截断视图**，而我把它当成全文回写。

**纪律**：编辑长文档只用**定点增改**（`edit` 精确替换 / 追加），不要「读全文 → 改内存 → 整篇回写」。若必须整篇重写，先 `wc -l` 记下期望行数，写完立刻复核；行数对不上就是被截断了。

### 11.10 自写插件：`dsh-old-session-toolface-guard`（2026-11-05，拦住 defer_loading 400）

**位置**：`dsh-domus-0.2.2-rc.1/profiles/web/packages/dsh-old-session-toolface-guard/`（本地 `file:` 包，随 home 进 git，不依赖 npm）。

**修法与社区那个 guard 不同 —— 这是关键取舍**：

| | 社区 `@argszero/dsh-all-deferred-tools-guard` | 本插件 |
|---|---|---|
| 手段 | 补一个**假占位工具**（`DeferredToolPlaceholder`，空 schema、不可用） | 把**当前活跃的那一个真实工具**（优先 `run_code`）写回会话基线 |
| 结果 | 请求合法，但模型拿不到真工具（半瘫） | 基线 ∩ 活跃 ≠ ∅ ⇒ 投影自然合法，模型拿到它会用的工具 |
| 覆盖面 | peer 上限 `<0.2.2-0`（未测本线） | 只依赖 `llm/stream` 与 `toolHistory` 两个稳定面 |

**两条判据（满足其一即动手）**

1. **预测式（与日期无关）**：复算 `content.ts` 的集合运算，**两种模式各算一遍**——`addition-only` 删光基线才是元凶，只看 `in-history` 会漏判（第一版就写漏了，测试用例当场抓住）。任一命中即视为风险，先补基线再发。
2. **老会话守门**：`createdAt < 2026-11-05T00:00:00+08:00`（= `1793808000000`，绝对偏移，不依赖时区/闰秒口径）⇒ 即使预测没命中，也挂「首块可疑就重派发一次」的兜底。只重派发一次；被拒请求不产生内容块，丢弃首块不丢东西。

**实测（三用例，`node --check` 通过）**

| 用例 | 期望 | 实测 |
|---|---|---|
| 基线 132 工具 / 活跃仅 `run_code` | 注入 1 条非延期声明，单次派发 | 注入 1 条 = `run_code`，`deferLoading` 为空，派发 1 次 ✅ |
| 健康请求（基线已含 `run_code`） | 完全不动 | tools 长度不变，派发 1 次 ✅ |
| 预测未命中但首块是那条 400（老会话） | 丢弃错误块 + 重派发一次并交付内容 | 派发 2 次，输出内容块 ✅ |

**接线**：`profiles/web/package.json` 加 `file:` 依赖（deps 18）+ `dsh.profile.bundles` 加条目（bundles 19）；`pnpm install` 后 `check_patch_layers` = **255 个 id / 无重复 / 可以启动**，`check-plugin-compatibility` = **231 个包无一被禁用**。

**边界（诚实标注）**：改的是**请求**不是历史——会话里那张「全都算中途新增」的表仍在，每次请求靠补一条常驻声明兜住；`in-history` 路由上会多补一条（无害，因为补的是真实活跃工具）；任何内部异常 fail-open，不制造新的失败面。

**补充（2026-11-05）：`cutoff` 改成配置项**

写死在代码里的日期是错的形态——那条分界线会随上游修复和自家迁移再变，改一次就要进 `node_modules` 改 JS。现在改成插件 `Config`：

- **入口**：`profiles/web/cordis.patch.yml` 的「工具面守门」段（profile 用户层，越权覆盖 bundle 默认值），旁边写了逐键说明；旁边还有一句「★ 唯一可调项就在下面这一段」
- **四个键**：`cutoff`（老会话兜底分界线）/ `residentTool`（补回基线的工具名）/ `predicted`（与日期无关的预测式）/ `retryOnRejection`（兜底重派发）
- **时区口径硬约束**：`cutoff` 必须带显式偏移（`Z` 或 `±HH:MM`），否则 **fail-loud 拒绝启动**。理由是时区歧义会让判据悄悄偏移——静默错比报错糟。默认值 `2026-11-05T00:00:00+08:00` = `1793808000000`（用 python 核过）

**用例从 3 个扩到 9 个**（全部通过）：预测式注入 / 健康不动 / 老会话兜底重派发 / `cutoff` 设在过去时**不**挂兜底 / 设在未来时**挂** / `retryOnRejection=false` 关兜底 / `predicted=false` 不注入 / 非法 `cutoff` 抛错 / 默认值可读。

**门禁复验**：`check_patch_layers` 255 个 id 无重复、`check-plugin-compatibility` 231 个包无一被禁用。

### 11.11 重启后的验收靶子（2026-11-05，用户指定）

**靶子 1（用户点名，测判据①「老会话」）**

```
session-e0e777eb-a99d-4b75-a5fb-fa4394ea1e7b
路径 sessions/--home-<user>-deepseek-harness--/session-e0e777eb-…/session.v4.jsonl.zstd
createdAt  1793799021020 = 2026-11-04T21:30:21+08:00   ← 比 cutoff(2026-11-05T00:00+08) 早 2 小时 29 分
preset coding · cwd 工作区根 · model deepseek-flash（官方） · 988 事件 / 3 条 request/header
工具面：seq 12 = 132 个（原生）  →  seq 933 = 131 个（原生）
```

**它测的是哪一条**：`createdAt` 早于 `cutoff` ⇒ **判据①（老会话兜底）命中**，即使预测式不认为有风险，也会挂「首块可疑就重派发一次」。

**诚实标注（重要）**：这条会话当前是**原生面**（131/132 个工具），基线∩活跃基本成立 ⇒ **它本来大概率不会 400**。所以它的验收信号不是「从坏到好」，而是：

- ✅ 重启后能正常打开、正常继续跑（不引入回归）
- ✅ 宿主日志里**没有**出现 guard 的重派发（因为它本来不该被拒）
- ❌ 若它反而失败，说明守门插件本身引入了回归 —— 那就要立刻把 `predicted`/`retryOnRejection` 关掉再验

**靶子 2（判据②的真靶，这才是从坏到好的那个）**

```
session-272f6bba-fba3-41a0-b310-047fd88dbf5d
工具面 seq 11 = 132 个原生  →  seq 2728 = 1 个 run_code（PTC）
turn 81 / step 1 起每轮 400，request_id 158191bb-3e30-46e0-ae84-d19941636ce7
```

**验收判据（两个靶子共用）**

| 检查 | 通过标准 |
|---|---|
| 能打开、能发一轮 | 不再出现 `All tools cannot be deferred` |
| 插件真的在跑 | 启动日志里 `old-session-toolface-guard` 无报错；必要时临时把 `predicted: true` 保持、看请求头里基线是否多了 `run_code` |
| 不误伤新会话 | 新建会话正常（预测式不命中 + 新会话不触发兜底） |
| 切换执行器仍可用 | 重启后 PTC（`run_code`）与 native 两条路径都试一次 |

**注意**：`cutoff` 默认 `2026-11-05T00:00:00+08:00`，靶子 1 恰好卡在它之前 —— 如果之后想缩小兜底范围，只要把 `cutoff` 往前挪（例如改成重启那一刻），靶子 1 就会退回到「仅预测式」保护。

**修订（2026-11-05，首测即挂）：`next()` 只能调一次 + 改成 reset 修法**

首次重启实测直接失败：`本输运行失败 next() called multiple times`。**这是我的实现错误**——`llm/stream` 是 Cordis waterfall，`next` 调第二次就抛这个错；我原来那版「被拒就重派发一次」正好犯它。

顺带被截图证实的诊断：UI 上写着 `工具已更新 · 新增 1 个（run_code），移除 131 个` —— 与 §11.8 的机制完全对上（基线 132、活跃只剩 `run_code`）。

两处改动：

1. **只改派发前的请求，`next()` 恰好一次**；删掉重派发兜底（`retryOnRejection` 键同时废弃）
2. **新增 `repairMode`，默认 `reset`**：把会话基线整体重设为「当前活跃工具、无中途新增、无 `deferLoading`」，`updates` 清空 ⇒ 无论路由走 `addition-only` 还是 `in-history`，声明集 = 活跃集，**必然合法**。`append`（只补一条进旧基线）保留为更保守的选项

`reset` 的代价写进了 README：中途新增的 developer 声明不再进入请求，延迟加载优化随之失效 —— 对已经废掉的老会话，这是拿优化换可用。

**用例扩到 7 个**（全过）：reset 后基线=活跃集且 updates 清空 / append 变 133 / 健康不动 / 老会话判据独立生效 / 开关关掉后不动 / `dryRun` 不修 / 非法 cutoff fail-loud。`check_patch_layers` 仍 255 id 无重复、可启动。

**测量（2026-11-05，用户要求「量上一次正常发送长什么样」）**

对 `272f6bba` 逐条 request/header 量「之后落下多少条成功的 assistant/message」：

| seq | tools | 之后成功的 assistant/message | 含 run_code |
|---|---|---|---|
| 11 | 132 | 1 | 否 |
| 27 | 132 | **137** | 否 |
| 1118 | 131 | 33 | 否 |
| 1368 | 132 | 63 | 否 |
| 1879 | 132 | 41 | 否 |
| 2210 | 132 | 25 | 否 |
| 2419 | 132 | 36 | 否 |
| 2713 | **1** | **0** | 是 |
| 2728 | 1 | 1 | 是 |

首次 400 的 attempt = `seq 2716`，其对应请求面 = `seq 2713`（1 个 `run_code`）。

**结论（并纠正 §11.8 的一处归因）**：400 并不是「基线坏了」造成的长期症状，而是**翻面那一刻才开始的**——翻面前 132 个原生工具跑了 336 步全部正常，翻成 `run_code` 之后每轮 400。先前把 `seq 1118` 误记为失败起点，是归因算法（取最近的前一条 header）算错了。

**因此「老人老办法」= 把翻面前那张面还原**，实现上有个干净的入口：`GenerateOptions.toolHistory` 的契约是「省略 ⇒ 发送完整声明、不带 tool update」⇒

```
options.tools      = 旧基线(132) ∪ 当前活跃(run_code)  // 133 个，全部非延期
options.toolHistory = undefined                       // 关掉中途新增/延期机制
```

新增 `repairMode: restore`（**默认**），`reset`（新人新办法）与 `append` 保留为选项。用例 5 个全过：restore 出 133 个面且无 `deferLoading`、reset 出 1 个、健康不动、老会话判据独立生效、`dryRun` 不修。

**待验的风险（诚实标注）**：还原出来的 132 个工具在当前执行器（PTC）下**是否真的可调用**尚未验证。若模型调用时返回 unknown tool，则说明「声明得回来、执行回不来」，需要的是**按会话把执行器切回 native**（`tools.setExecutor` 的 agent 作用域），而不是只改 wire。

### 11.12 验收结果（2026-11-05）

**靶子 2 通过**：`session-272f6bba-fba3-41a0-b310-047fd88dbf5d`（「DS官方Super Agent品鉴和故障取证」，createdAt 2026-11-01T16:10:02+08:00，preset coding）—— 用户实测「ok」，`repairMode: restore` 生效。

**这条验收同时解决了一个悬而未决的风险**：还原出来的 132 个原生工具在 **PTC 执行器**下**确实可以正常调用**，不会出现 unknown tool。也就是说「声明得回来、执行回不来」的担心没有发生——`toolHistory` 置空 + 完整声明的路子，既能合法化请求，也能正常执行。

**靶子 1 未单独复验**：`session-e0e777eb-a99d-4b75-a5fb-fa4394ea1e7b`（「为模型供应商配置专属代理」，createdAt 2026-11-04T21:30:21+08:00）本来到期就是健康面，属回归观察项而非修复靶子。

**最终形态**（`repairMode` 三档，默认 `restore`）：

| 模式 | 做法 | 适用 |
|---|---|---|
| `restore`（默认） | 旧基线 ∪ 当前活跃，`toolHistory` 置空 ⇒ 完整声明、无 `defer_loading` | 老人老办法，实测通过 |
| `reset` | 基线 := 当前活跃集 | 新人新办法，留作兜底 |
| `append` | 只补一条进旧基线 | 最小改动 |

**纪律沉淀**：`AGENTS.md` 新增两条 —— 「上游反馈纪律」（必查 Discussions）、「报会话 id 必须带标题」（配 `tools/session-title.py`）。

### 11.13 System Prompt 的正身在哪（2026-11-05，纠错）

**先犯错**：我把「沙盒草稿区」那节写进了 `dsh-domus-*/.agent-presets/*/agent.cordis.yml`（5 份），
以为那就是活配置。**用户当场纠正**：要落回 `profiles/web/cordis.patch.yml` 才叫生效。

**核实（不是听说，是查）**：

- harness 检出里搜 `.agent-presets` —— **零命中**（`grep -rn '\.agent-presets' packages apps`）；
- `profiles/web/cordis.patch.yml:249` 有 `agent-preset-registry`，`:292` 起是各 preset 行，`:306` 是 `- id: persona`；
- 导出管线的 `extract` 规则 `home_src` 指向的也正是这份 profile patch —— 它本来就是按「活配置」设计的。

⇒ **`.agent-presets/` 只是镜像/staging（`tools/stage-upgrade-home.py` 会拷它），真正被加载的是 profile patch 里的 `persona` 块。**
现在两处都同步了（镜像保持对齐，若哪天重跑 staging 也不会退回旧文本）。

**三条配套纪律**：

1. **改提示词就改 `profiles/web/cordis.patch.yml` 的 persona 块**（16 空格缩进，块标量内）；
2. **语法检查必须放行 `!!js`**：`yaml.safe_load` 一定失败，要用多构造器兜住 `tag:yaml.org,2002:js`；
   而真正权威的解析器是项目自带的 `tools/check_patch_layers.py`（它跑通才算能启动）。
3. **那份文件里全是手改**：只做**增量插入**，改完用 `diff | grep -c '^<'` 证明**删除行数为 0**（本次 5 处插入、+50 行、0 删除）。

### 11.14 失败现场两个会话，与「fork 的 createdAt 骗人」（2026-11-05）

**原始失败现场**：`session-f0435754-4d36-4831-a274-2234f2bc758d`（「整理素材（2）」），
创建 2026-10-20、preset `coding`、cwd `<D盘>:\User Data\Documents\简历`，11043 事件 / 24.4 MB。

```
turn 432 正常 completed   ← 此前 432 轮全好，工具面始终 131/132 原生
turn 433 / step 1         ← INVALID_REQUEST 400
  tools: at least one tool must have defer_loading=false. All tools cannot be deferred.
  request_id: 044bcbc1-22bb-4c1b-b17e-73129d3f7dab
```

对照：`0.2.1-rc.2` home 里同名会话的副本停在同一位置且**只有 turn 432**（11027 事件），
`0.2.2-rc.1` 这份多出 turn 433 与这次 400 ⇒ **是「在 0.2.2 上重开这个老会话」才炸的**。
注意：**失败的请求没有留下 `request/header`**（最后一条 header 是 seq 10936，reason `resume`，132 工具），
所以那一轮的真实活跃工具面只能靠推断，不能从日志直接读出。

**实验用失败现场（用户已备好）**：`session-fb560d75-d88a-4164-8df8-95241cf7b92e`
（「整理素材（2）（失败现场备份1）」）

| 字段 | 值 | 含义 |
|---|---|---|
| `isSeeded` | **true** | fork：结算后的种子历史（继承 11031 条事件） |
| `createdAt` | 2026-11-05T16:14:41+08 | **分叉时刻，不是历史年龄** |
| 未结束的 turn | 0 | 末事件是 `session/end-seed` 与两次 `session/title` |
| 继承来的 header | 22 条（`initial`/`series`/`resume`/`change` 俱全） | 工具面在历史里反复重开过 series |

⇒ **「干净环境发一下就触发」基本成立**：第一条 live 消息会拿继承来的 132 工具史去投影，
只要当前活跃面与它不同，就是全延期 ⇒ 400。

**但这带出一个判据错误（我先前写的那条在这里失效）**：

> 我原本用 `createdAt < 2026-11-05T00:00+08` 判「老会话」。
> **fork 的 createdAt 是分叉时刻** —— 这个备份会话 createdAt 就在当天 16:14，
> 按日期判它「不老」⇒ 兜底不触发。**日期不能代表历史年龄。**

改法（已落地）：判据加上 `header.isSeeded === true` —— 带种子历史的分叉会话一律算「老」。

**仍未定的一件事**：`f0435754` 那轮，插件到底有没有跑。已给插件加诊断日志
（每次 `llm/stream` 写一行 JSON 到 `<home>/logs/toolface-guard.log`，fail-open、1 MB 截断），
**重启后发一条消息即可判定**：

| 观察 | 结论 |
|---|---|
| 完全没有 `skip`/`restore` 行 | 插件没被调用 ⇒ 查 bundle roster 与模块解析 |
| 有 `skip` 行且 `seeded:true`/`createdAt` 为 null | 判据仍落空 ⇒ 改判据 |
| 有 `restore` 行但请求仍 400 | 投影发生在改写之外 ⇒ 换缝（`resolvedOptions` 链路） |

### 11.15 结论：`llm/stream` 这条路走不通 —— 请求对象是**冻结**的（2026-11-05）

**日志证据**（`dsh-domus-0.2.2-rc.1/logs/toolface-guard.log`，7 行，全部同一形态）：

```json
{"sid":"…fb560d75…","k":"restore","flipped":false,"faceSize":0,"changed":false,
 "before":{"tools":1,"base":1,"adds":1},"createdAt":1793866481510,"seeded":true}
```

- `seeded:true` ⇒ 新加的 **isSeeded 判据确实生效**（按日期它会被判成「不老」，因为 fork 的 createdAt 是分叉时刻）；
- **但 `changed:false`、`faceSize:0` ⇒ `restoreFace()` 一行都没改** —— 它抛了异常，被我的 fail-open 咽掉；
- 而 `base:1` / `tools:1` ⇒ 该请求本来就只有 1 个工具、基线也是 1 ⇒ **本来就不会全延期**。

**根因（源码级，不是猜）**：

```ts
// packages/core/agent-loop/src/agent.ts:733-741
return markAgentLoopRequest(Object.freeze({
  ...header.config, messages: boundaryMessages,
  toolHistory: session.toolHistory(),   // ← 且 toolHistory 自身是 deepFreeze 过的
  ...header.tools !== undefined ? { tools: header.tools } : {},
  sessionId: this.session.id, signal,
}))
```

⇒ **`options` 顶层冻结、`toolHistory` 深度冻结**；ESM 是严格模式，`options.toolHistory = undefined` 直接抛 TypeError。
**任何「在 `llm/stream` 里改请求」的修法，本质上都不可能生效** —— 社区那个占位符插件同理（它靠重派发，而重派发已证明会抛 `next() called multiple times`）。

**之前两次「ok」要重新归因**：`272f6bba` 与 `fb560d75` 都是**请求本来就合法**（基线 = 活跃 = 1 个 `run_code`），
不是插件救回来的。这条必须写清楚，否则会留下一个「看起来修好了」的假象。

**400 的真实机制（从 `buildRequest` 读出，`agent.ts:673-700`）**：

1. 当前 header 与基线不同 ⇒ 追加 `request/header {reason:'change'}` —— **`change` 不会重开 series**；
2. 差的工具写进 `developer/message` 的 `tool-addition` / `tool-removal`；
3. 投影：removal 把基线里的 131 个删掉，剩下的 `run_code` 是 addition ⇒ 标 `deferLoading`；
4. ⇒ 声明集只剩延期项 ⇒ 400。**重开 series 就能解**（`reason:'series'`/`startsSeries` 会把基线重置为当前 header）。

**因此出路只剩三条**（都要用户定）：

| 方案 | 做法 | 代价 |
|---|---|---|
| A. 执行器固定 native | 关掉 `tool-executor-ptc`，全用原生面 | 新会话工具多、token 高；但**面不再翻转**，老会话随便续 |
| B. 执行器固定 PTC | 现状 | 所有 **PTC 之前**的老会话一续就 400（除非换自定义端点） |
| C. 上游修投影 | 往 `#11475` 补这次的精确触发链 | 等发版 |

**插件该何去何从**：现状是「诊断有用、修复无效」。要么缩成纯诊断（保留 `logs/toolface-guard.log`），
要么按 A/B 的选择改写成**执行器层**的东西（那是另一个层级的改动）。**不能留着冒充「已经修好了」。**

### 11.16 结论：源码级补丁生效（2026-11-05 收尾）

**验证会话**：`session-9b7fdf6d-55d3-4592-bc61-0317edc96ec6`（「整理素材（2）（失败现场备份3） (2)」）

```
seeded: true · 11079 事件 · 末条 request/header = seq 11053, reason=resume, tools=1
error 回合数: 0        ← 与三次失败现场（同一条 header 形态）唯一的不同是：打了补丁
```

即：**同样的「基线 132 / 当前面 1」形状，这次请求合法了**。补丁位置与内容见
`补丁/defer全延期兜底/defer全延期兜底.md`（含四步机制、三份实测 request_id、验证输出）。

**为什么最终是源码补丁而不是插件** —— 三条插件路线全部撞墙，且都能说清原因：

| 路线 | 死因 |
|---|---|
| `llm/stream` 里改 options | `Object.freeze`（`agent.ts:733-741`），严格模式赋值抛异常，被我自己的 fail-open 咽掉 |
| 被拒后重派发 | waterfall `next()` 只能调一次 ⇒ `next() called multiple times` |
| `agent/pre-step` 追 `request/header{reason:'series'}` | `ctx.tools.schemas(agent)` 给的是**注册表**（158），不是执行器呈现面（1）⇒ 反而刷出 158 条 removal，把正常会话也污染了 |

**教训（写给下一次）**：

1. **先确认能改**，再设计改法。`Object.freeze` 一读就知道，我却先写了三轮修复；
2. **API 的语义要靠调用点确认**：`schemas(scope)` 名字像"当前面"，实际是注册表 —— 看 `buildRequest` 收到的是 `assembly.tools` 才准；
3. **诊断日志先于修复**：`logs/toolface-guard.log` 那 7 行直接把「没生效」摊开，比再改一版有用得多；
4. **别把"看起来好了"当验收**：`272f6bba` / `fb560d75` 两次「ok」都是请求本来合法，与插件无关。

**当前状态**：插件已降为 `repairMode: observe`（只写诊断、不动手）；真正的修复在检出源码里，
由 `补丁/defer全延期兜底/manifest.toml` 在每次开机核对/重放。插件是否正式退役待定。
