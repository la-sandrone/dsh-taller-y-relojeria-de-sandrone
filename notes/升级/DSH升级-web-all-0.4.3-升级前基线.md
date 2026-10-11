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

这三处是 2026-09-26 我们**手工换锚**的产物，上游 0.4.3 恰好也动了锚点（皮肤行重新锚定到原生面板列表），**有被冲掉的风险**。

| 文件 | sha256（升级前） |
|---|---|
| `dsh-domus-0.1.7-rc.2/profiles/web/packages/dsh-suigintou-ui-patches/lib/client.js` | `3d50884d8c0d9b09d4410b327f5756a3a8b0de6d78b8a005982b7ea0f04c0896` |
| `dsh-domus-0.1.7-rc.2/skins/navia/patches.css` | `b06bd8db76e5c583604a3c4e969aba9169b19b1db85872544cdd9934f1b7c37d` |

注意：`dsh-domus-0.1.7-rc.2/profiles/web/cordis.patch.yml` 的哈希**会变**（本次提交已含用户设置漂移 light→dark / low→high），比对时只看那两处换锚文件是否还在，不要整体比对。

## 四、升级后核对清单

1. `for d in profiles/web/node_modules/@linxin666/*/; do grep -m1 version $d/package.json; done` → 应全为 `0.4.3`
2. 上面三个文件 sha256 是否变化；变了要 `git diff` 看是不是被覆盖
3. `git -C dsh-domus-0.1.7-rc.2 status` → 确认没有意外改动
4. 跑 `node tools/verify_suigintou_css.mjs`（注入 CSS 全表核对）
5. 跑 `python3 tools/check-profile-links.py`（profile 链接护栏）
6. 浏览器侧目视：头部标题集群居中 / headerActions 左贴 / crumb 限宽 / navia 毛玻璃 / 壁纸库 inventory.total 应为 78
7. 更新后**立刻复查长文本粘贴截断**是否仍在（0.4.3 可能顺手改掉，也可能无关）

## 五、待办（升级后接着做）

- [ ] 长文本粘贴截断：用 `tools/cut-analysis/` 抓现行（DOM 断点 → Call Stack）
- [ ] hero「探索未至之境」与上边框缺呼吸：先确认那张卡是谁画的（疑为 navia / skin-center 背景层）
