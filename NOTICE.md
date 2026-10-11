# NOTICE —— 第三方素材与授权

本仓自身的代码与文字：**MIT**（见 [`LICENSE`](LICENSE)）。
下面是**不是我们写的**东西，逐项列明来源与许可。

---

## 一、随包字体

| 文件 | 许可 | 说明 |
|---|---|---|
| `packages/dsh-sandrone-ui-patches/font/SourceSerif4Variable-Roman.woff2` | **SIL Open Font License 1.1** | Source Serif 4 Variable（全量 426,716 B，保留 `wght 200-900` / `opsz 8-60` 可变轴）。随包分发，许可全文见同目录 `LICENSE-SourceSerif4.md` |

`packages/dsh-sandrone-ui-patches/lib/index.js`（host 半区）为它提供一条前缀路由；
**漏了这个文件会让字体 404** —— 故字体与它的许可全文都在包内，不另行下载。

## 二、KaTeX（基准材料）

`bench/katex/**`（`katex.min.js` / `katex.min.css` / `fonts/*.{ttf,woff,woff2}`）

- 许可：**MIT**，见 <https://github.com/KaTeX/KaTeX>
- 用途：`bench/` 是[长会话渲染实测报告](docs/perf-long-session-rendering.md)的**复现材料**。
  浏览器基准里必须能渲染公式，否则测的就不是真实负载。
- 这些是**字体文件，不是位图**，与下面的「零位图」纪律不冲突。

## 三、上游 DeepSeek Harness

`patches/**` 里的 `.patch` 是**上游源码的差异**，其内容遵循上游许可：

- 项目：DeepSeek Harness（DSH）
- 许可：**MIT**（`Copyright (c) 2026 DeepSeek`；上游另有一份 `THIRD_PARTY_NOTICES.md`）
- 因此本仓的补丁可以与上游同以 MIT 条款分发；补丁**不改变**上游的版权归属。

> 本仓与上游**无隶属关系**，是非官方的本地改动合集。

---

## 四、⚠️ 明确**不在**本仓的东西

1. **任何插画与摄影素材，一张都没有。**
   皮肤原版用的背景图是第三方画作（版权归原画师，**未获授权**），因此**不随仓发布**；
   皮肤在缺图时降级为纯配色主题，想恢复完整效果请自备图（见 `skins/navia/README.md`）。
   同理，本地曾用于字体考证的 6 张**实测截图**也不发布 —— 它们同样是位图。
2. **其它作者的皮肤。** 皮肤中心里的主题各有作者与授权（其中若干自带 `LICENSE` / `NOTICE`），
   本仓只包含作者自己做的 `navia`。
3. **任何凭据。** 发布前经确定性脱敏：机器路径与用户名已替换，`密钥.env` / `*.cnf` 一类文件
   从不进入导出白名单。仓库里的 `启动器配置和日志/当前配置.toml.example` 是**样例**，
   本身不含任何凭据。

---

*本文件随仓库演进；新增任何第三方素材时，**必须**在这里补一行。*
