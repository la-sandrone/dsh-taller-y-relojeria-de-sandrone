# Nuestra Señora del Trono de Sabiduría, Espejo de Justicia, Salud de los Enfermos, Refugio de los Pecadores, Arca de la Alianza y Estrella de la Mañana

## `dsh-taller-y-relojeria-de-sandrone` —— 桑多涅的工坊与钟表铺

对 [DeepSeek Harness](https://github.com/deepseek-ai)（DSH）的**本地爆改合集**：源码补丁、界面补丁包、皮肤、字体方案、启动器，以及把这些东西改出来时踩过的坑和判据。


> 标题是Letanías lauretanas里六个真称号的串联，你去核对原剧情我反正觉得差不多对（草生）
>

---

## ⚠️ 三条前提（先读，能省你很多时间）

1. **本仓零位图**。没有任何 `png/jpg/webp/gif`（唯一例外是随包字体与 `bench/katex/` 里的 KaTeX 字体，都在 [`NOTICE.md`](NOTICE.md) 列明）。皮肤背景请**自备**，见 [`skins/navia/README.md`](skins/navia/README.md)。
2. **皮肤只包含作者自己做的那个**（`navia`）。著名全家桶插件`dsh-web-all`里的其它主题各有作者与各自的授权，不在这里。
3. **补丁是版本耦合的，而且会大声报错**。`patches/*/manifest.toml` 里带着对上游源码结构的断言：**版本对不上就拒绝打补丁并报出漂移点**，不会静默打歪。

---

## 目录

| 目录 / 文件 | 里面是什么 | 怎么用 |
|---|---|---|
| **`patches/`** | 源码补丁的版本无关存档：`manifest.toml` + 可 `git apply` 的 `.patch` + 为什么 | 用 [`tools/dsh-ui-patches.py`](tools/dsh-ui-patches.py) 核对/重放；也可手工 `git apply` |
| **`packages/dsh-sandrone-ui-patches/`** | UI 补丁包：以 **client 半区注入全局 CSS** 的方式改界面（字体方案 / 字号倍率 / 随包可变字体 / 皮肤压制 / 长会话渲染剪枝） | `pnpm add file:packages/dsh-sandrone-ui-patches`（见包内 README） |
| **`skins/navia/`** | 一个皮肤：浅底侧栏 + 深底主区 + 毛玻璃（**图自备**） | 放进 home 的 `skins/` 下，重启 |
| **`notes/`** | 脱敏后的实操笔记：排版、皮肤、升级、部署、issue、提示词、检索 | 读**为什么**；配方数值会随版本过期，判据不会 |
| **`tools/`** | 实用工具：补丁护栏、home 硬链接修复、补丁分层检查、H1 强制，以及**皮肤取色探测** [`skin-color-probe.py`](tools/skin-color-probe.py)（拿一张主题图直接出「该配浅底还是深底」的判决 + 白/黑字对比度） | 直接跑（多为 `--help` 自明） |
| **`start-web.py`** | DSH 启动器：起 / 停 / 查 / 试新版本 / 回收运行记录，实现全在这一个文件 | 先看 [`启动器配置和日志/README.md`](启动器配置和日志/README.md) |
| **`docs/`** | [长会话渲染实测报告](docs/perf-long-session-rendering.md)（含一条方法学教训：`--headless` 不能用来测 layout） | 读结论；复现材料在 `bench/` |
| **`bench/`** | 渲染基准的复现材料（含 KaTeX 字体） | 见报告 |

---

## 两个源码补丁

| 补丁 | 一句话 | 文档 |
|---|---|---|
| **Markdown 渲染** | 让**用户消息**按 Markdown 渲染（这是上游的产品选择，本地选了另一条） | [`patches/Markdown渲染/`](patches/Markdown渲染/) |
| **空回复兜底** | 让「只吐思考链、`finish=stop`」的退化响应变成**可重试的 `EMPTY_RESPONSE`**，而不是一条静默落盘、界面上什么都不显示的空白回复 | [`patches/空回复兜底/dsh-empty-response-content.md`](patches/空回复兜底/dsh-empty-response-content.md) |

后者的排查过程值得单看：一场真实会话 153 轮里 **13 轮**收尾只产出 reasoning 块、正文一个 token 都没生成，而**两层空响应守卫都在问错的问题**（数的是「有没有开过块」而不是「有没有可交付内容」）——其中一处还有一条**把错误行为写成契约的测试**（`keeps a thinking-only stop successful`）。文档里有完整的取证链。

---

## 环境变量与可移植性

这些工具是从我们那台机器上搬出来的，所以**根目录不写死**：

| 变量 | 作用 | 缺省 |
|---|---|---|
| `DSH_HARNESS_DIR` | harness 根目录（启动器给子进程注入的就是它） | 由脚本自身位置推导（`tools/` 的上一级） |
| `DSH_TRACE_LOG` | 取证日志落点（用来实现「每实例一份」） | 启动器按实例路径注入；没走启动器时落 `.dsh-scratch/fetch-trace.log` |
| `DSH_H1_MODE_FILE` | H1 实验的「臂」开关文件 | 随实例记录目录 |

⇒ **把它们放在 `<任意目录>/tools/` 下、旁边有 `start-web.py`，就能自动认祖归宗**；实在推不出来会**报错而不是猜**。

`.dsh-scratch/` 是「没走启动器」时的匿名取证落点（我们那边这个目录叫「草稿纸与垃圾桶」，发布件里换成了中性名）。写日志的 preload 有 `try/catch` 兜底，**目录不存在也不会拖垮宿主**。

⚠️ 仍要说清：`start-web.py` 与 `tools/` 里几个脚本**是按我们自己的工作区布局写的**（`原始代码研究/<版本>/` 检出、`dsh-domus-<版本>/` 实例 home、`启动器配置和日志/`），它们是**参考实现** —— 照这个结构摆能用，扔进别的布局会明确报错。

---

## 授权与素材

- 本仓代码：**MIT**（见 [`LICENSE`](LICENSE)）。文本内容：[`CC BY-SA 4.0`](https://creativecommons.org/licenses/by-sa/4.0/deed.zh-hans)
- 第三方素材（随包字体 SIL OFL 1.1、KaTeX MIT、上游 DSH MIT）：逐项见 [`NOTICE.md`](NOTICE.md)。
- **本仓不含任何插画／摄影素材**，也**不含任何凭据**。所有笔记在发布前经过确定性脱敏（机器路径与用户名已替换），并没有「顺手」保留原文。

> ⚠️ 这是**非官方**的本地改动合集，与 DSH 上游无隶属关系。补丁都是对特定版本的定点修改，升级后请先核对。
