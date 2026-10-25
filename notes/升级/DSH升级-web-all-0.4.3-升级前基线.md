# DSH 升级基线：@linxin666/dsh-web-all 0.4.2 → 0.4.3

> 生成时间：2026-09-27 08:52:49 +0800
> 用途：升级后逐条核对「我们手搓的三处换锚有没有被上游冲掉」。

## 一、升级对象

| 项 | 值 |
|---|---|
| 包 | `@linxin666/dsh-web-all`（19 个家族包的聚合入口） |
| 现版本 | `0.4.2` |
| 目标版本 | `0.4.3` |
| pin 方式 | **精确版本**（`profiles/web/package.json` 第 8 行 `"0.4.2"`，不是 `^`） |
| 冷却 | 手动触发 → **跳过 pnpm 24h 发布冷却**（供应链保护被绕开） |

### 家族 19 包现值（升级前实测）

| 包 | 版本 |
|---|---|
| `dsh-client-ui-community-plugins` | 0.4.2 |
| `dsh-client-ui-git-graph` | 0.4.2 |
| `dsh-client-ui-market` | 0.4.2 |
| `dsh-client-ui-model-capabilities` | 0.4.2 |
| `dsh-client-ui-plugin-manager` | 0.4.2 |
| `dsh-client-ui-preset-center` | 0.4.2 |
| `dsh-client-ui-session-id` | 0.4.2 |
| `dsh-client-ui-skill-explorer` | 0.4.2 |
| `dsh-client-ui-skin-center` | 0.4.2 |
| `dsh-client-ui-task-board` | 0.4.2 |
| `dsh-client-ui-web-ui-settings` | 0.4.2 |
| `dsh-i18n` | 0.4.2 |
| `dsh-liangshen` | 0.4.2 |
| `dsh-pet` | 0.4.2 |
| `dsh-remote-web-ui` | 0.4.2 |
| `dsh-session-archive` | 0.4.2 |
| `dsh-ssh` | 0.4.2 |
| `dsh-usage` | 0.4.2 |
| `dsh-web-all` | 0.4.2 |

## 二、回滚物

| 物 | 位置 / 命令 |
|---|---|
| 定向存档（19 包全量 + 三个清单） | `backups/web-all-0.4.2-pre-update-20260927-085222.tar.gz`（17.4 MB，已校验含 19 包） |
| 离线包源 | pnpm store：`$HARNESS/.pnpm-store/v11` |
| 精确回滚 | 把 `package.json` 的 `"@linxin666/dsh-web-all"` 钉回 `"0.4.2"` 后重装；或直接 `tar -xzf` 上面的存档覆盖 |

## 三、手搓补丁指纹（升级后必须逐条比对）

前两条是 2026-09-26 手工换锚的产物（上游 0.4.3 恰好也动了锚点，皮肤行重新锚定到原生面板列表），**有被冲掉的风险**；
第三条是 2026-10-23 打的移动端适配补丁，**插件更新必丢**。

| 文件 | sha256（升级前） |
|---|---|
| `dsh-domus-0.1.7-rc.2/profiles/web/packages/dsh-suigintou-ui-patches/lib/client.js` | `3d50884d8c0d9b09d4410b327f5756a3a8b0de6d78b8a005982b7ea0f04c0896` |
| `dsh-domus-0.1.7-rc.2/skins/navia/patches.css` | `b06bd8db76e5c583604a3c4e969aba9169b19b1db85872544cdd9934f1b7c37d` |
| `dsh-domus-0.2.1-rc.2/profiles/web/node_modules/@linxin666/dsh-remote-web-ui/lib/client.js` | `50cfee1b63d9eedc27ccfa6d28a621fbbcd630ba8065adb34e252ab4d10f460c`（**改后**；原版 `41984638…` 在 `.bak-frameheight`） |
| `dsh-domus-0.2.1-rc.2/profiles/web/packages/dsh-suigintou-ui-patches/lib/client.js` | `17533f1724dcf29e8b509346a216940cd0a1180e4cad9c14666a173bd4f426dc`（2026-10-24 加第 ⑥ 条：手机端 visualViewport 同步） |

注意：`dsh-domus-0.1.7-rc.2/profiles/web/cordis.patch.yml` 的哈希**会变**（本次提交已含用户设置漂移 light→dark / low→high），比对时只看那两处换锚文件是否还在，不要整体比对。

## 四、升级后核对清单

1. `for d in profiles/web/node_modules/@linxin666/*/; do grep -m1 version $d/package.json; done` → 应全为 `0.4.3`
2. 上面三个文件 sha256 是否变化；变了要 `git diff` 看是不是被覆盖
3. `git -C dsh-domus-0.1.7-rc.2 status` → 确认没有意外改动
4. 跑 `node tools/verify_suigintou_css.mjs`（注入 CSS 全表核对）
5. 跑 `python3 tools/check-profile-links.py`（profile 链接护栏）
6. 浏览器侧目视：头部标题集群居中 / headerActions 左贴 / crumb 限宽 / navia 毛玻璃 / 壁纸库 inventory.total 应为 78
7. 更新后**立刻复查长文本粘贴截断**是否仍在（0.4.3 可能顺手改掉，也可能无关）
8. **手机端 frame 高度 / visualViewport**（2026-10-24 起有两份，过渡期）

   | 方案 | 位置 | 插件更新会丢吗 |
   |---|---|---|
   | **长期** | `profiles/web/packages/dsh-suigintou-ui-patches/lib/client.js` 的 `MOBILE_VIEWPORT_CSS` + `bindVisualViewport()` | 不会（本地包） |
   | 过渡 | `@linxin666/dsh-remote-web-ui/lib/client.js` 的手改（CSS 变量 + `w.__dshVvhBound`） | **会** |

   两份规则写法一致、值相同，共存无害（只是重复绑一次监听）。
   **重启后长期方案生效，届时可回滚过渡方案**（`client.js.bak-vvh` / `.bak-frameheight`）。

   判据：手机端页面底部不露背景；键盘反复弹出收起后也不露。

9. **升级时必须同时盯两个上游**（这是本条最容易被忘的）

   | 上游 | 影响什么 | 怎么发现漂移 |
   |---|---|---|
   | **DSH 官方**（`原始代码研究/v0.2.1-rc.2`） | CSS Modules 类名（`_centerCol` 已在 0.2.1-rc.2 消失）、`_frame_` 命名、布局结构 | 适配层选择器突然失效 → 手机端排版回退 |
   | **`@linxin666/dsh-web-all` 家族** | `remote-web-ui` / `remote-bridge` 的适配层与配对面板、`cordis.patch.yml` 的受管块 | 配对入口变化、`lanBind` 行为变化、适配层重写 |

   **两边的失效模式不同**：官方是「选择器对不上」（静默失效），插件是「直接覆盖你的手改」（文件被换）。
   所以核对要分两处：本地插件的指纹 + node_modules 手改的指纹（§三 表格里都有）。

## 五、待办（升级后接着做）

- [ ] 长文本粘贴截断：用 `tools/cut-analysis/` 抓现行（DOM 断点 → Call Stack）
- [ ] hero「探索未至之境」与上边框缺呼吸：先确认那张卡是谁画的（疑为 navia / skin-center 背景层）
