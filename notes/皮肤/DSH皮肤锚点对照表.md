# DSH 皮肤锚点对照表（升级后重调用）

> **来源**：`<对话导出目录>\对话\折腾记录\Deepseek Harness相关\Deepseek Harness 5.md`
> 最后一场对话索引（行 8633–8673+），8 个话题全是皮肤/CSS 补丁的破案记录
> **可信度**：索引摘要级（话题 4 的三阶段过程在索引里已写得较细）。需要精确 CSS 文本时回原文件。
> **生成时间**：2026-09-11

## ⚠️ 锚点从哪来（2026-09-11 查证：**更正本稿初版的错误标注**）

初版把下列属性标为「全局属性 / 上游」——**错**。它们**全部由插件产出，与 dsh 核心无关**：

| 属性 | 生产者 | 依据 |
|---|---|---|
| `data-dsh-surface` / `data-dsh-part` / `data-dsh-frame` / `data-dsh-skin-layer` / `data-dsh-skin` / `data-dsh-plugin` | **`@linxin666/dsh-client-ui-skin-center`** 的 compat adapter（合并 MutationObserver） | `skin-center/contracts/semantic-attrs-v1.md` |
| `data-pane` | 各插件自用（task-board / ssh / git-graph …） | grep 定位 |
| `data-dsh-responsive-part` | `dsh-web-all` 的 shim | grep 定位 |
| **`data-ds-dark-theme`**（皮肤用得最多，166 次） | **dsh 核心** `ui-layout/theme-presenter`，打在 `<body>` | 核心源码 |
| `class*="newSession"` | **dsh 核心** CSS Module 类名 | 核心源码 |
| `data-dsh-wt-peek` / `data-dsh-xp` | **皮肤私有**（war-thunder / xp 自己） | 两代插件都不产 |

> **→ 皮肤锚点的命运押在 `@linxin666/dsh-web-all` + `skin-center` 上，不在 dsh 核心。**
> 这与初版的判断相反，也是为什么下面要盯契约文件而不是盯 `packages/client`。

## 📄 契约文件（带版本号，可 diff —— 这是权威定义）

`profiles/web/node_modules/@linxin666/dsh-client-ui-skin-center/contracts/`

| 文件 | 内容 |
|---|---|
| ⭐ `semantic-attrs-v1.md` | **L2 语义属性枚举**：surface 8 个 / part 71 行 / plugin 14 个，每个都标 owner + 含义 + 锚定方式 |
| `skin-manifest-v2.schema.json` | 皮肤清单 schema |
| `hooks-api.d.ts` | 皮肤 hooks API |
| `official-tokens-v1.json`、`primary-action-tokens-v1.md` | L1 token 体系 |
| `performance-guidelines-v1.md`、`README.md` | 性能规范 / 说明 |

## ✅ 0.3.6 → 0.3.20 静态验证结果（**已做，零回归**）

| 检查项 | 结果 |
|---|---|
| 契约版本 | **未升版**（仍 `semantic-attrs/v1`） |
| surface 组（8 个）/ **shell 区域 part 组** | **未动**（含 `message-row`/`message-body`/`scrollport`/`composer-input`/`sidebar-entry`/`new-session`） |
| part 组 | 38 → **71** 行，**纯增** |
| plugin 组 | 13 → 14，**只删了已标「停更」的 `aionui-panel`** |
| 其余 6 个契约文件 | **逐字节未变** |
| 锚点属性词表 | 39 → 40，**超集** |
| 关键取值裸串 | `session-title-cluster` **4→4**、`conversation-header` **4→4**、`skin-layer` **2→2**、`message-row` 9→8、`scrollport` 23→21 —— **全存活**（⚠️ **但"裸串存活"≠"打标仍命中目标"**：0.1.7 实测这两族**整族失锚**，见文末「补记 2026-09-26」） |
| adapter 锚定输入 | `newSession` **21→21 完全一致**；`data-slot` 30→32、`data-streaming` 3→3、`data-conversation-scroll` 23→21、`data-chat-flow-kind` 2→30、`data-queue-dock` 1→1、`data-turn-tail` 1→4、`data-shell-overlay` 1→1 —— **全存活** |
| **唯一失效** | 🔴 `data-decoration` **26 → 0**（核心已移除）→ 契约里的 `composer-chip` 失锚；**你的皮肤不用它，影响 0** |

**→ 结论：皮肤锚点基础安全。** 优先级从「9 个皮肤需重做」降为「升级后跑一次运行时复核」。

## 🔬 复核方法（静态到此为止，剩下的是运行时）

**为什么静态做不下去**：插件侧是 `setAttribute(name, value)` **运行时**打标，源码里没有 `属性="值"` 连写字面量。用那个模式 grep 会得到「全部失效」的**假警报**——本稿初版就是这么误判的。

**运行时复核**（升级后 F12 Console，对照升级前的数字）：

```js
['data-dsh-skin','data-dsh-part','data-dsh-surface','data-dsh-frame',
 'data-dsh-skin-layer','data-dsh-responsive-part','data-pane','data-ds-dark-theme']
  .forEach(a => console.log(a, document.querySelectorAll('['+a+']').length))
```

## ⚠️ 契约自己声明的长期脆弱点（原文引用）

> 两个产出通道：**compat adapter**（皮肤中心的合并 MutationObserver，为官方 DOM 与未 opt-in 插件补打属性；**非永久公共契约**，官方区域在上游主题缝落地后进入**删除评估**）与组件主动输出。

> **已知脆弱点（上游主题缝 PR 诉求）**：1. AppFrame 三列容器本体只有 hash 类 → 诉求三列自带稳定 data 钩子。2. 侧栏导航行无官方 slot → 诉求 sidebar 导航 list slot。3. 设置模态只有 `role="dialog"` → 诉求设置 dialog 根专属标识。4. list slot 的单 entry 无 DOM 归属标识。

**→ 若新版落地了这些上游缝，adapter 可能停止为对应区域补打属性。本次验证未发现该情况，但这是长期风险源：每次升级都要重跑上面的运行时复核。**

---

## 1. pi-ai 思考档位报错修复

- **现象**：`amici-mei` 手写路由模型报 `UNSUPPORTED_REASONING_EFFORT`
- **根因**：手写模型**无 catalog 可继承**、只支持 `off` 档；provider 级 `reasoning: high` 在**请求发出前**被 dsh 本地校验拒绝（`adapter.ts` → `resolveReasoningLevel`），**不是 API 报错**
- **修法**：依 `llm-pi-ai` 官方 README 的 `reasoningEfforts` 机制声明档位
  - `{off, high, max}`（wire 照 pi-ai catalog 的 deepseek 条目 + DeepSeek 官方映射表）
  - 后补 `low/medium`：`low: low`（真实档）、`medium: high`（名义档，官方映射 medium→high）
  - `vision-exp` 移除（暂不用且不声明思考强度一选就炸）
- **附注**：`baseURL` 含 `deepseek.com` 自动识别方言（pi-ai `detectCompat`），无需手写 compat
- **涉及文件**：`dsh-domus/settings.yaml`、`llm-pi-ai`

## 2. 导出插件安装与导出方案

- **踩坑**：`dsh plugin add dsh-session-export` 报 `ERR_PNPM_GIT_DEP_PREPARE_NOT_ALLOWED`
  （git-hosted 包的 build 脚本需 `allowBuilds` 白名单）→ `pnpm-workspace.yaml` 加**精确键**解决
- **插件用法**：`/session-export` 斜杠命令（markdown/jsonl/pdf，脱敏默认开，PDF 需 Chromium），输出到 `$DSH_HOME/exports/`
- **最终决定**：走**原生 Session Log 下载 JSON + U+2591 索引恢复流程**（与既有 md 存档一致）；
  插件留着不卸，`exports/` 进 `.gitignore`
- **升级关联**：该插件在 `cordis.patch.yml` 里 `disabled: true`；recall 走内置 `/api/session.export`，**不依赖它**

## 3. 字体插件全局生效确认（缓存伪问题）

- **现象**：误以为字体只在 Furina/Navia 生效
- **真相**：**浏览器缓存新旧混杂的假象**；插件注入 `:root` 变量树，**天然免疫皮肤**，无需适配
- **附注**：Firefox 硬刷新快捷键是 **Ctrl+F5**
- **涉及**：`dsh-font-serif`、`--dsw-font-family`

## 4. 宽表格溢出 —— 三阶段折腾，最终选「强制压缩」

| 阶段 | 方案 | 结果 |
|---|---|---|
| ① | 滚动条常驻 `overflow-x: auto !important` | ❌ 无效 |
| ② | Firefox 滚动条显形（`scrollbar-width: auto` + 亮 thumb `#4a5fa8`） | ❌ 仍无滚动条 |
| ③ | **放弃滚动，改强制压缩**（用户拍板） | ✅ 采用 |

**②的根因**：官方 `ui-theme/src/styles/scrollbar.css` 给 Firefox 走 `scrollbar-width: thin` + 暗色 thumb
（furina 下 `#33406a`）→ 视觉隐形；且官方 breakout（`AssistantMarkdown.module.css`）把 `.md-table-wide`
容器撑到 **100cqw transcript 宽** + `max-width: none` → 表格常不溢出

**③的方案细节**：
- 容器收进消息列、留 16px 呼吸（`margin-left/padding-left: 0` 抵消 breakout 负边距）
- `table width: 100%`（覆盖官方 `max-content`）
- `table-layout: auto`（按内容量比例分配列宽）
- `overflow-wrap: anywhere` + `white-space: normal`（物理杜绝溢出）

**规范结论**：`overflow` 只适用于块 / flex / grid 容器，**对 `display: table` 元素无效**
（Firefox F12 提示即规范原文）；**表格滚动必须靠包裹 div**

## 5. 表格分割线加亮（furina / navia 暗背景）

- **根因**：官方 `MarkdownText.module.css` 中 `th` 用 `--dsw-alias-border-l3`、`td` 用 `--dsw-alias-border-l2`；
  furina 重映射为 `#2c3a7338` / `#2c3a7352`（低透明度深蓝）→ 暗底不可见；navia 未重映射但官方默认值在暗底也偏暗
- **修法**：外挂 CSS 用锚点
  ```css
  html[data-dsh-skin="furina"] [data-dsh-part="message-row"] table th, /* 同 navia */
  ```
  覆盖为半透明白（**th 0.35 / td 0.22**）
- **关键**：`data-dsh-*` 是全局属性，**免疫 CSS Module 哈希**

## 6. 新会话按钮字色提亮（navia）

- **现象**："新会话"按钮字色对比度低看不清
- **修法**：换与 commit hash chip 同款颜色 `#f2e8d5`（暖白米色），`navia/patches.css` 追加：
  ```css
  [data-pane="sidebar"] [class*="newSession"] { color: #f2e8d5 !important; }
  ```
- **手法**：属性锚点 + 子串类名匹配，同路数

## 7. 会话标题集群改造（crumbs 居中 + preset 标签左对齐）

- **DOM 结构**：`titleRow` > `titleCluster`（`crumbs` nav + `headerActions` div）+ `headerUtilities`（Session log 按钮）
- **CSS 改法**：
  - `titleCluster` 变 flex + `justify-content: center` → crumbs 居中
  - `headerActions` 绝对定位 `left: 0` 脱离流 → preset 标签贴左，同时腾出宽度给居中标题
- **锚点**：`data-dsh-responsive-part="session-title-cluster"` + 结构选择器 `> div`（避开哈希类名）
- **⚠️ 升级风险最高的一条**：新版有 `2026-09-07-sidebar-responsive-tab-info`、
  `2026-09-08-sidebar-default-pages`、`2026-09-05-sidebar-tab-types-and-navigation`
  三个改造 —— **`data-dsh-responsive-part` 正是新版响应式改造的核心，取值可能已变**

## 8. crumb 按钮限宽放开（长标题省略号根因）

- **现象**："冰质星球与是啊，吃什么：落实（149）"（~240px）被掐成省略号
- **根因**：官方 `ConversationRoot.module.css` 的
  `.crumb { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }`
  —— **与居中无关**，是限宽
- **修法**：
  ```css
  [data-dsh-responsive-part="session-title-cluster"] nav button
  ```
  放开 `max-width: none` + `white-space: normal`（允许换行）+ `word-break: break-all` 兜底
- **附注**：用户确认最长标题约 240px，实际一行完整显示、换行不触发

---

## 升级后复核顺序建议（**按 2026-09-11 静态验证结果重排**）

**判别原则**：皮肤补丁分两类——**① 靠 skin-center 契约锚定的**（已静态验证，零回归，风险低）；**② 靠 dsh 核心官方 CSS / 组件结构锚定的**（**不在契约保护内**，而核心改了 1,521 个文件 → 风险高）。

| 序 | 话题 | 风险 | 依据 |
|---|---|---|---|
| 1 | **话题 4** 宽表格 | 🔴 **最高** | 依赖官方 `ui-theme/scrollbar.css` + `AssistantMarkdown.module.css` 的 breakout 结构（`100cqw` / 负边距），**不受契约保护** |
| 2 | **话题 5** 表格分割线 | 🟠 高 | 依赖官方 `MarkdownText.module.css` 的 `--dsw-alias-border-l3/-l2`；新版有 `ui-primitives` 重构 |
| 3 | **话题 7 / 8** 标题集群 | 🟡 中 | `data-dsh-responsive-part="session-title-cluster"` **静态 4→4 存活** ✅，但 `nav button` 结构选择器依赖 DOM 层级 —— ⚠️ **0.1.7 下这条静态结论被证伪：该锚整族失锚，见文末「补记 2026-09-26」** |
| 4 | **话题 1** pi-ai 档位 | 🟡 中 | 与 `settings.yaml` 校验器一起跑；纯配置，坏了看得见 |
| 5 | **话题 6** 新会话按钮 | 🟢 低 | `[class*="newSession"]` **静态 21→21 完全一致** ✅ |
| 6 | **话题 3** 字体 | 🟢 低 | `:root` 变量树免疫皮肤，只需 Ctrl+F5 清缓存 |
| 7 | **话题 2** 导出插件 | ⚪ 可忽略 | 已 `disabled: true`；走原生 Session Log + U+2591 流程 |

**唯一已确认失效**：`data-decoration`（核心 26→0）→ 契约里的 `composer-chip` 失锚，**你的皮肤不用它，影响 0**。

---

## 🎯 升级后运行时复核结果（2026-09-11 实测，基座 v0.1.5-rc.2 / 副本 9009）

**方法**：把「外挂 CSS」原件（原 `dsh-font-serif`，已改名为 `dsh-suigintou-ui-patches`）
装入 dry run，重启后在 9009 上读 computed style。

### 逐话题结论

| # | 话题 | 上文预估风险 | 实测 | 结论 |
|---|---|---|---|---|
| 1 | pi-ai 档位 | 🟡 中 | 档位可选 | ✅ 零回归 |
| 2 | 导出插件 | ⚪ | `disabled: true`，不用它 | ⚪ 不适用 |
| 3 | 字体全局生效 | 🟢 | `--dsw-font-family` = `'Source Serif 4 Display'…` | ✅ 零回归 |
| 4 | 宽表格 | 🔴 **最高** | `maxW = calc(100% - 16px)`（原 `none`）、宽 665px 收进消息列 | ✅ **零回归** |
| 5 | 表格分割线 | 🟠 高 | `0.6px solid rgba(255,255,255,0.35)` —— **与 9007 逐字相同** | ✅ **零回归** |
| 6 | 新会话按钮 | 🟢 | 静态 21→21；**未运行时验证** | 🟡 待补 |
| 7 | 标题集群 | 🟡 中 | `display: flex` / `justify: center` / `position: relative` | ✅ **零回归** |
| 8 | crumb 限宽 | 🟡（`nav button` 结构选择器） | **`nav button 命中 = true`** | ✅ **零回归** |

### 🚨 结论：8 个话题，**零个真回归**

下方「升级后复核顺序建议」那张表的风险排序（🔴🟠🟡）**整体偏高** ——
它假设锚点可能随官方重构失效，**实测四个锚点全部存活**。

### ⚠️ 重要更正：话题 5 的「宽度被砍半」是误判（同表 话题 5 段落作废）

上文 话题 5 曾据 `MarkdownText.module.css` 源码 diff 判为 `1px → 0.5px`。
**实测推翻**：9007（0.1.1）与 9009（0.1.5）的 `th border-bottom` **都是 `0.6px`**
（= `0.5px` × 用户 120% 页面缩放），颜色也都是 `rgba(255, 255, 255, 0.35)` —— **逐字相同**。

- **→ 官方并未改动该边框；话题 5 完全零回归。**
- **→ 曾据此写出的 `border-bottom-width: 1px` 属误判产物，已归档、未采用：**
  `tools/skin-patch-archive-20260911/`。

### 🔑 本轮真正的方法论收获

**整张皮肤回归清单被污染的根因**：皮肤测试期间**插件全关**，
于是 9007 vs 9009 实际比的是「**有补丁的 0.1.1**」vs「**没补丁的 0.1.5**」。

**→ 皮肤层的版本对比，必须在「补丁齐备」的前提下做。**

而「外挂 CSS」**不在皮肤文件里**（在 `dsh-font-serif` 插件里），
所以照着皮肤文件找补丁，必然找不到、必然把它误判成回归。

---

## 📌 补记 2026-09-26：升至 v0.1.7-rc.2 后的实测（**本表部分静态结论在此被证伪**）

**基座**：9007 / `v0.1.7-rc.2`（`dsh-domus-0.1.7-rc.2`）。**方法**：源码比对 + F12 运行时实测。

### 一、`data-dsh-responsive-part` 头部系**整族失锚**（本表话题 7/8 的静态结论作废）

实测取值分布（非空态会话）：

```
{"sidebar-toggle":1, "sidebar-entry":18, "code":6, "composer":4}
```

**头部系五个锚点全部不在**：`conversation-header` / `session-title-cluster` /
`session-title-row` / `session-utilities` / `session-tablist`。
旁证：真 titleCluster 的 `justify-content` = **`normal`** ⇒ 我们的居中规则**从未生效**。

**根因**（`原始代码研究/v0.1.7-rc.2/packages/client/ui-conversation/src/client/skeleton/`）：
0.1.7 把会话头部整体重构，三处叠加：

1. **新增 `ConversationHeader.tsx`** —— `<header>` 搬到**新槽 `conversation.header`**（root scope），
   挂在 `ConversationMainPanel.tsx` 的 `div.root` 下、与 `conversation.content` 平级；
2. **旧头部内容改返回 Fragment** —— 不再有 `<header>`；它只在旧槽
   `conversation.session.header` 里产出 `div.titleRow` + `div.tabs`；
3. header 首子变成新插入的 `div.headerLeading`。实测 DOM：
   `HEADER wOuVoW_header` 的子元素 = `[0] wOuVoW_headerLeading`、`[1] (无 class 的 slot wrapper)`。

而打标方 `@linxin666/dsh-web-all`（**0.4.2**，engines 已声明 `>=0.1.7-rc.2`）的 shim 仍是 0.1.5 形状：

```js
const slottedHeader = conversation.querySelector('[data-slot="conversation.session.header"]')
                        ?.querySelector(':scope > header') ?? null;   // 恒为 null（改动 2）
const siblingHeader = scrollport?.previousElementSibling ?? null;     // scrollBody 是 body 首子 → null
if (conversationHeader !== null) { … mark(titleCluster, "session-title-cluster") … }
```

两条路全断 ⇒ 打标块**整块跳过**。（即便找到 header，`header.firstElementChild`
现在也是 `headerLeading` 而非 `titleRow` —— 双重错位。）
`session-title-cluster` 在 web-all 里只出现 2 处（1 条 CSS + 1 个 mark 调用），
在 skin-center 包里 **0 处** ⇒ **唯一生产者，现已全灭**。

### 二、受影响的自有资产与已采用的新锚

| 资产 | 旧锚（死） | 新锚（实测命中） |
|---|---|---|
| `profiles/web/packages/dsh-suigintou-ui-patches/lib/client.js`（居中） | `[data-dsh-responsive-part="session-title-cluster"]` | `[data-slot="conversation.session.header"] [class$="_titleCluster"]` |
| 同上，headerActions 左贴 | `… > div` | `… > [class$="_headerActions"]` |
| 同上，crumb 限宽放开 | `… nav button` | `… [class*="_crumb"]:not([class*="_crumbSeg"]):not([class*="_crumbSep"])` |
| `skins/navia/patches.css:213`（header 毛玻璃） | `[data-dsh-responsive-part="conversation-header"]` | `[data-slot="conversation.header"] header, header[class*="_header"]` |

**两个坑记下来**：

- ⚠️ 0.1.7 把**当前 crumb 由 `<button disabled>` 改成 `<span>`**（官方注释：darwin 拖拽行的原因）
  ⇒ 就算锚点修好，`nav button` 结构选择器**仍会漏掉当前 crumb**，长标题省略号会复发。
  必须改按类名匹配（并排除 `_crumbSeg` / `_crumbSep` 包装）。
- ⚠️ navia 的 header 锚**不能用** `[class$="_header"]`：header 在 blank/sessionless 状态会追加
  `_headerBlank` / `_headerSessionless`，后缀匹配会失效。用 tag 限定 `header[class*="_header"]`
  可免疫（`_headerLeading` / `_headerUtilities` 都是 div，不会误伤）。

提交：`920523c`（home 仓）。草稿纸 **id=1185**。

### 三、🔑 方法论修正（**本表最该记住的一条**）

上面那套复核办法有结构性缺陷：

1. **静态数裸串（本表 46 行那张表）会给出假安全感。**
   `session-title-cluster` **4→4 存活**是真的——但它数的是「字符串还在不在」，
   **数不出「运行时打标路径是否还能命中目标」**。本次它整族失锚，而静态检查全绿。
2. **只数锚点总数同样会误判。** 本次 `data-dsh-responsive-part` 总数 = **25**（不是 0），
   乍看"活着"；**要看的是取值分布**，才看得出「哪一族整族消失」。
3. **第三方 shim 产物不受 skin-center 契约保护。**
   本表第 8 行已写明 `data-dsh-responsive-part` 的 owner 是 `dsh-web-all` 的 shim，
   风险却只评 🟡 中——因为把「契约里的取值存活」误当成「锚点存活」。
   **→ 凡 owner 是 shim 的锚点，升级后一律按 🔴 对待。**
4. **本表「🔬 复核方法」一节当初就写对了**（要跑 F12、要对照数字），
   但这条**从未执行**——两代升级因此都走在同一个盲区里。
   **→ 清单上写着「待运行时复核」的项，等于没做。**

### 四、补记之二：`weLibraryDirs` 层级错误 ⇒ 壁纸库**静默清空**（非锚点，但同属静默失效）

- **症状**：skin center 壁纸库空，**无任何报错**。
  `GET /api/skin-center/we/inventory` → `{"total":0,"wallpapers":[]}`，
  而配置指向的创意工坊目录 `<挂载d>:/游戏/SteamLibrary/steamapps/workshop/content/431960`
  实际有 **78** 个条目。
- **根因**：0.1.7 把三个皮肤设置命名空间合并成 `web-ui-skin-center` 的**一个分区嵌套 Config**：

  ```js
  // @linxin666/dsh-client-ui-skin-center/lib/index.js:9508
  const Config = z.object({
    "skin-background":   SkinBackgroundConfigSchema,
    "skin-custom-theme": SkinCustomThemeConfigSchema,
    "skin-wallpaper":    SkinWallpaperConfigSchema      // ← weLibraryDirs 属此分区
  });
  ```

  官方注释：「the same names this package registered as settings namespaces
  before 0.1.7, now sections of one Config.」
  0.1.5→0.1.7 的迁移脚本做了**半吊子扁平化**：`skin-custom-theme` 正确保留嵌套，
  却把 `skin-wallpaper.weLibraryDirs` 拍平到顶层。zod 用**默认 strip 语义**
  （无 `passthrough` / `catchall` / `.strict()`），**顶层未知键被静默丢弃**
  ⇒ 插件 `deps.getConfig().weLibraryDirs` 得 `[]`。
- **改法**：`weLibraryDirs` 归位到 `skin-wallpaper` 分区，删掉顶层孤儿 `applied`。
- **验证**：热加载后 `total` **0 → 78**（5 秒内），首条为真实场景壁纸。
- **教训**：分区嵌套 schema 的配置迁移，**扁平化必须整层做，不能只做一半**；
  未知键被 schema strip 掉是完全静默的 ⇒ **必须用接口实测兜底**
  （本例：`inventory.total`），不能靠「YAML 解析通过」或「插件不报错」判定迁移成功。

提交：`fe71eda`（home 仓）。草稿纸 id=1185。
