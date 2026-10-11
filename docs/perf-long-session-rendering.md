# DSH 长会话渲染性能实测：三万个 DOM 节点下的两引擎对照

> 本文是一份**真实场景**的前端渲染性能实测，用于说明 `dsh-sandrone-ui-patches`
> 中 `content-visibility` 补丁的必要性。
> 所有数字均来自可复现的测量，方法与原始读数在文中给出；结论与局限分开陈述。

---

## 摘要

在一条真实的长会话（186 条消息、**30,181 个 DOM 节点**、510 个 TeX 公式）上，
强制触发一次完整的 style + layout：

| 环境 | `content-visibility: off` | `content-visibility: auto` | 收益 |
|---|---|---|---|
| **Firefox 157** | 219 ms | **39 ms** | **−82%** |
| **Edge 154**（Chromium） | 240 ms | **0.8 ms** | **−99.7%** |

**三点结论：**

1. **两个引擎的基线性能相当**（219 vs 240 ms，差 9%）——换浏览器不解决这个问题。
2. **`content-visibility: auto` 在两个引擎上都带来数量级收益**，但 **Chromium 的实现彻底得多**
   （留下 0.3% vs 留下 18%）。
3. DSH 的消息容器**既无虚拟化、也无 `content-visibility`**，这是成本的直接来源。

---

## 1. 背景：问题是什么

DSH（DeepSeek Harness）的会话界面在**长会话**下会明显变卡，典型表现是滚动、
输入、面板切换时的可感知停顿。重度使用者的实际场景：

- 一个对话累计消耗 **2 亿 tokens**（累计口径，非单次上下文）
- 会话导出单文件 **57.55 MB** / 7,694 行
- 内容以**科幻小说创作**为主：高密度 Markdown + **大量数学公式**

这类内容有两个特点，都会放大渲染成本：

| 内容类型 | 放大机制 |
|---|---|
| **TeX 公式**（KaTeX 渲染） | 每个公式展开为几十个 `<span>`，且默认**双份输出**（`.katex-mathml` + `.katex-html`） |
| **长思维链**（reasoning） | 单条可达百万字符，是正文的 7–9 倍 |

---

## 2. 根因定位（源码级）

在 DSH `v0.1.7-rc.2` 源码中核查：

| 检查项 | 结果 |
|---|---|
| 消息列表虚拟化 | ❌ **未实现**。仅 `TurnNavigator`（轮次导航条）用了 `@tanstack/react-virtual` |
| `content-visibility` | ❌ **全仓库未使用** |
| CSS `contain` | 仅 3 处零散使用（`AnimatedRows` / `TurnNavigator` / `ReasoningRow`），**消息主体无** |

而 `packages/client/ui-chat/src/client/chat/ChatView.module.css` 里有一段注释，
等于上游自己承认了方向：

```css
/* Settled-flow identity boundary. It is neutral until it becomes the natural
   measurement/mount unit for a virtualizer without changing the column gap. */
.flowItem { min-width: 0; }
```

> 「**until** it becomes the natural measurement/mount unit for a virtualizer」
> —— 虚拟化的挂载点已经预留好了，但虚拟化本身还没做。

**结论**：`.flowItem` 即官方预留的剪枝边界，`content-visibility` 可以直接挂在它上面，
不需要改动 DOM 结构。

---

## 3. 实验设计

### 3.1 数据集（真实内容，非合成）

从一条真实的创作会话导出中抽取**全部 186 条** assistant 正文块：

| 指标 | 值 |
|---|---|
| 消息条数 | 186 |
| 正文字符数 | 171,233 |
| TeX 公式数 | **510**（display 35 / inline 475） |
| 表格行数 | 1,039 |
| 代码块 | 4 |
| 标题 | 341 |
| reasoning 字符数 | **958,466** |

> **关于 reasoning 数据**：测试页中的 reasoning 内容为**按真实字符数生成的占位文本**，
> 不是原文。理由是 reasoning 的渲染成本只取决于「字符数 + 段落结构」，
> 与具体文字无关 —— 因此测量等价，同时避免把模型思考链纳入公开材料。
> 正文则**逐字保留**。

### 3.2 测试页面

`bench/index.html` —— 单文件页面，不依赖网络（KaTeX 为本地副本）：

- 渲染管线：自实现 Markdown → HTML，TeX 交给 **KaTeX 0.16**（`output: 'htmlAndMathml'`，与 DSH 一致）
- 可切换：`reasoning`（不渲染 / 折叠 / 展开）、`content-visibility`（off / auto / auto+intrinsic-size）、
  公式渲染开关、消息条数
- 测量点：
  - `Markdown + KaTeX 编译` —— 把 markdown+TeX 编译成 HTML 字符串的纯 JS 时间
  - `DOM 构建 + 挂载`
  - **`首次 style + layout`** —— 挂载后读取 `offsetHeight` 强制触发的完整样式计算与布局

> ⚠️ 测试页的自实现 Markdown 渲染器**不等于 DSH 的真实渲染管线**
> （DSH 走 `hast-util-to-jsx-runtime` + React）。因此本文数字应理解为
> **同量级下不同方案的相对比较**，不是 DSH 的绝对帧时间。

### 3.3 环境

| 项 | 值 |
|---|---|
| 浏览器 A | **Firefox 157.0**（Windows，真实 GUI 窗口） |
| 浏览器 B | **Edge 154.0.0.0**（Windows，真实 GUI 窗口） |
| 系统 | Windows on WSL2（Arch Linux） |
| 服务 | Apache（`http://localhost/`） |
| 页面参数 | `reason=collapsed & cv=<off\|auto> & katex=1 & limit=全部 186` |

**测量方式**：人工点「重建并测量」，读取页面输出。每组为单次读数
（非多次取中位）—— 见 §6 局限。

---

## 4. 结果

### 4.1 主矩阵

| 环境 | `cv = off` | `cv = auto` | 收益 |
|---|---|---|---|
| **Firefox 157** | **219.0 ms** | **39.0 ms** | **−82.2%** |
| **Edge 154** | **240.0 ms** | **0.8 ms** | **−99.7%** |

DOM 节点数在两臂间**完全一致**（30,181）—— `content-visibility` 不减少节点，
只让屏幕外内容**跳过样式计算与布局**。

配套读数（同一批次）：

| | Firefox 157 | Edge 154 |
|---|---|---|
| Markdown + KaTeX 编译 | 33.0 ms | 27.1 ms |
| DOM 构建 + 挂载 | 2.0 ms | 1.7 ms |
| JS 堆 | —（Gecko 无 `performance.memory`） | 83.7 MB |

**注意编译耗时的量级**：KaTeX 编译 27–33 ms 是**同步阻塞主线程**的，
但它只有一次；相比 layout 的 219–240 ms，**layout 才是主要瓶颈**。

### 4.2 两引擎的差异在哪

基线相当（219 vs 240），但**加入 `content-visibility` 后差距拉开到 50 倍**
（39 ms vs 0.8 ms）。

合理解释：`content-visibility: auto` 的规范允许实现自行决定「多远的屏幕外内容算不相关」。
**Blink 几乎完全跳过**（连容器的 `offsetHeight` 都可由 `contain-intrinsic-size` 估算，
不需要真实布局）；**Gecko 显然保留了比视口大得多的相关区域**，因此仍付出相当成本。

⟹ 39 ms **不是物理下限**。Gecko 上被跳过的部分还有优化空间，但那是引擎内部的事，
应用侧无法控制。

### 4.3 一个反直觉结果：折叠 reasoning 不省成本

在同一批测量中（Firefox 与 Edge 的真实 GUI 数据未覆盖此项，见 §6）：

`max-height + overflow: hidden` 形式的「折叠」**并不减少布局成本** ——
文本仍被完整布局，只是被裁掉显示。因此：

> **折叠是交互设计，不是性能手段。**

真正的剪枝要靠 `content-visibility`（按**容器**跳过，无论里面是 KaTeX 树还是百万字符文本）。

---

## 5. 结论与建议

### 5.1 对应用侧

给消息容器（上游预留的 `.flowItem`）加：

```css
.flowItem {
  content-visibility: auto;
  contain-intrinsic-size: auto 400px;   /* 值按典型消息高度估，防滚动条跳动 */
}
```

**两个引擎都有数量级收益**，且不需要改动 DOM 结构或 React 代码。

### 5.2 对「换浏览器」的建议

| 问题 | 答案 |
|---|---|
| 不加优化，哪个浏览器好？ | **一样**（219 / 240 ms） |
| 加了 `content-visibility`，哪个好？ | **Chromium 明显更好**（0.8 vs 39 ms） |
| 那该换浏览器吗？ | **不该当作解法** —— 两个引擎都需要这条 CSS，且它才是收益来源 |

### 5.3 本仓库（`dsh-sandrone-ui-patches`）的处置

本插件的职责就是**向 client 注入全局 CSS**，因此上述规则是该插件的自然扩展项，
不需要额外的运行时机制。

**已知副作用（需实测确认，非本文测量范围）**：

- 屏幕外元素高度未知 → **滚动条长度会跳**；`contain-intrinsic-size` 用于缓解
- **Ctrl+F 页内查找**可能找不到尚未渲染的屏幕外内容
- 锚点 / 跳转定位可能要求目标先渲染

---

## 6. 局限与未完成项（诚实声明）

1. **单次读数**。每组为一次测量，未做多次取中位与方差分析。
2. **§4.3 的支撑数据来自 headless 环境，方法不可靠**（见附录 A），
   因此该结论标注为「待真实环境复测」。
3. **测试页的渲染管线是自实现的**，与 DSH 真实的 React + `hast-util-to-jsx-runtime`
   管线不同。绝对数值不可直接外推到 DSH，**相对比较**有效。
4. **未测 paint / composite 成本**。本文只测 style + layout。
   `content-visibility` 同时也会减少 paint，实际收益可能更大。
5. **未测滚动过程中的帧率**。首次布局成本与持续滚动成本是两回事。
6. **未覆盖 Firefox 在 `cv=auto` 下的 `contain-intrinsic-size` 影响**。
7. 数据集来自**单一会话**，未做跨会话统计。

---

## 附录 A：方法学陷阱 —— `--headless` 不能用来测 layout

本文早期版本使用 `msedge.exe --headless=new --disable-gpu --virtual-time-budget=N`
从 Linux 侧批量驱动测量。该方法的读数为 **1,094 ms（cv=off）**，
而真实 GUI 窗口为 **240 ms** —— **高估 4.5 倍**。

更危险的是，曾用「四种 headless 配置互相对照」来验证方法可靠性：

| 启动配置 | 读数 |
|---|---|
| `--headless=new --disable-gpu` + virtual-time | 1035.8 ms |
| `--headless=new`（不禁 GPU） | 1074.1 ms |
| `--headless=old --disable-gpu` | 985.4 ms |
| `--headless=new`（不用 virtual-time） | 1060.4 ms |

四组读数高度一致（<10% 离散），**但全部是错的** —— 因为它们在同一个有偏方法内部互比。
**方法内部一致性不能证明方法正确。**

同时注意偏差**不是常数**：

| 模式 | headless | 真实 GUI | 偏差 |
|---|---|---|---|
| `cv = off` | 1,094 ms | 240 ms | **+4.5×** |
| `cv = auto` | 0.8 ms | 0.8 ms | **×1.0** |

⟹ **无法事后校正**，只能整体作废。

**可用替代**：真实窗口 + CDP `Performance` 域；或至少在真实窗口中测量。

---

## 附录 B：复现

### B.1 生成数据集

```bash
python3 extract-render-fixtures.py <session.v4.jsonl.zstd> data.json
# 输出：消息条数 / 正文字符数 / reasoning 字符数 / 文件大小
```

### B.2 启动测试页

将 `bench/` 放到任意 HTTP 静态服务下（**不要用 `file://`** —— 本文混用 `fetch`/Worker 的场景会受限）：

```
http://<host>/bench/index.html?reason=collapsed&cv=auto&katex=1
```

### B.3 读判据

页面顶部输出：

```
数据集 / 本次渲染 / 公式数 / DOM 节点
Markdown+KaTeX 编译 / DOM 构建+挂载 / 首次 style+layout
模式 / 引擎
```

**关注 `首次 style+layout`**，并**务必在真实浏览器窗口中读取**（见附录 A）。

---

## 附录 C：命名说明

本项目的两个名字指同一件事：

| 场合 | 名称 |
|---|---|
| **仓库 / 公开发布** | `dsh-sandrone-ui-patches`（桑多涅） |
| **本地开发 / 安装** | `dsh-suigintou-ui-patches`（水银灯） |

差异来源是早期注册时的命名习惯，**功能与代码完全相同**，不是两个包。

---

## 附录 D：测量原始读数

| # | 环境 | 模式 | 节点 | 编译 | 挂载 | style+layout |
|---|---|---|---|---|---|---|
| 1 | Firefox 157 | cv=off | 30,181 | 33.0 ms | 2.0 ms | **219.0 ms** |
| 2 | Edge 154 | cv=off | 30,181 | 27.1 ms | 1.7 ms | **240.0 ms** |
| 3 | Firefox 157 | cv=auto | 30,181 | 48.0 ms | 2.0 ms | **39.0 ms** |
| 4 | Edge 154 | cv=auto | 30,181 | 27.1 ms | 1.7 ms | **0.8 ms** |

（全部为 `reasoning=collapsed`、`katex=1`、`limit=186`、真实 GUI 窗口、单次读数）
