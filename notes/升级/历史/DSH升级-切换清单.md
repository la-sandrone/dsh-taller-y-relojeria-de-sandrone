# DSH 升级切换清单：v0.1.1-rc.2 → v0.1.5-rc.2

> **⚠ 2026-10-07 状态说明**：本文是 **0.1.1→0.1.5** 那一轮的历史清单，两个版本均已退役，
> 清单**不可再执行**。文中提到的 `.bak-011rc2` / `.bak-*` 快照已按「备份统一交 git 管理」
> 于当日清退（全仓 163 个），相关路径全部失效——详见 `DSH停机卡.md` 的「残件清退」小节。
> 当前升级路径请看 `DSH升级-0.2.x-调查与方案.md`。

生成于 2026-09-11。依据 = dry run（9009，`dsh-domus-dryrun`）已完成的全部实测验证。

---

## 〇 · 已验证的前提（dry run 实测，可直接信任）

| 项 | 结果 |
|---|---|
| 基座 0.1.5 启动 | ✅ |
| `@linxin666/dsh-web-all` **0.3.20** | ✅ 可跑 |
| 会话 preset 挂载 | ✅（修 `text:` → `prefix:` 之后） |
| 皮肤 8 个话题 | ✅ **全部零回归** |
| 补丁插件（改名后） | ✅ 字体 / 宽表格 / 标题集群 / 分割线全生效 |

## ⚠️ 未覆盖的风险面 —— 切换后最可能出问题的地方

dry run **只装了 4 个 bundle**：
`@deepseek-ai/dsh-base` + `@deepseek-ai/dsh-web-app` + `@linxin666/dsh-web-all` + 补丁插件。

**现役另有 7 个 bundle + 13 个 MCP，从未在 0.1.5 上跑过：**

- bundles：`@noob-stupid/dsh-plugin-console`、`dsh-wsl-bridge`、`dsh-deepread`、
  `dsh-session-insights`、`dsh-context`、`@changfenhuang/dsh-annotation`、`dsh-history-tree`
- `cordis.patch.yml` 的 13 个 `@deepseek-ai/dsh-mcp-client`

**→ 这是切换后第一要查的东西（见 阶段 4.4）。**

---

## 阶段 0 · 切换前存档（9007 照跑，零风险）

- [ ] **0.1 建立 git 回滚点**（`dsh-domus/.git` 工作树当前是干净的）
  ```bash
  cd ~/deepseek-harness/dsh-domus
  git status --short        # 期望：只有 1 个未跟踪文件
  git add -A && git commit -m "chore: 0.1.5 切换前存档"
  git log --oneline -1      # ← 记下这个 SHA，回滚靠它
  ```
  `.gitignore` 已排除 `sessions/ storages/ skin-center/ task-board/ pet.json node_modules
  .credentials.yaml exports/`，其余（`skins/`、`.agent-presets/`、`settings.yaml`、
  `profiles/web/package.json`、`pnpm-lock.yaml`、`packages/`）**全部纳入版本控制**。

- [ ] **0.2 查清那个唯一未入库文件**
  `dsh-domus/patches/ui-conversation-lib-client.patched.from-011rc2.js`
  **确认它是「历史实验」还是「正在生效的补丁」**。若是被手工塞进过 `node_modules`，
  切换时的 `pnpm install` 会把它冲掉。

- [ ] **0.3 记下基线**
  - `DSH_VERSION` = `v0.1.1-rc.2`
  - 现役 bundles = 11 个；MCP = 13 个
  - 活动皮肤 = `navia`（记录在 `dsh-domus/skin-center-active.json`）

- [ ] **0.4 手抄 `DSH_VERSION`**（它在 harness **根目录，不在 git 里**，回滚只能手改）
  回滚值就一行：`DSH_VERSION=v0.1.1-rc.2`

- [ ] **0.5 确认 9007 的全部启动途径**
  - Linux 侧：`~/deepseek-harness/start-web.sh` → `pnpm dsh web --port 9007`
  - **Windows 侧若有自启（PECMD / 计划任务 / 快捷方式），切换期间必须一并停掉**，
    否则会和你手动启动的抢 9007 端口。

---

## 阶段 1 · 预设键名 `text:` → `prefix:` ⚠️ 必须，且必须与切换同时做

**根因**：0.1.5 的 `@deepseek-ai/dsh-persona` schema 把必填键从 `text` 改成 `prefix`
（新增 `suffix` 默认 `''`）。旧键导致**会话挂载直接失败**：

```
agent-presets: preset "coding" failed to mount:
failed to apply loader entry persona (@deepseek-ai/dsh-persona):
invalid config: - $.prefix missing required value (at prefix)
```

**⚠️ 反向不兼容**：0.1.1 要求 `text` 必填 —— 改成 `prefix:` 会让 **0.1.1 也挂掉**。
**→ 所以这一步只能在 9007 停机后做，不能提前。**

- [ ] **1.1 备份 + 改键**（6 个 preset：academic / coding / fantasy / general / scifi / liangshen）
  ```bash
  cd ~/deepseek-harness/dsh-domus/.agent-presets
  for d in */; do cp "$d/agent.cordis.yml" "$d/agent.cordis.yml.bak-011rc2"; done
  ```
  逐个把 `    text:` 改成 `    prefix:`。
  **改前每个文件先用 `grep -c '^\s*text:' <file>` 确认恰好 1 处。**

- [ ] **1.2 用现成工具验**（`tools/preset-key-check.py`，已写好）
  ```bash
  python3 ~/deepseek-harness/tools/preset-key-check.py \
      ~/deepseek-harness/dsh-domus/.agent-presets --target 0.1.5
  ```
  期望：6 个文件全部匹配、退出码 0。

---

## 阶段 2 · 补丁插件改名（"过渡就是直接更换"）

**目标**：`dsh-font-serif` → `dsh-suigintou-ui-patches`。dry run 里已跑通。

- [ ] **2.1 搬包**（推荐：直接拿 dry run 里已改好名的，省得再改 9 处标识符）
  ```bash
  cd ~/deepseek-harness
  rm -rf dsh-domus/profiles/web/packages/dsh-font-serif
  cp -r dsh-domus-dryrun/profiles/web/packages/dsh-suigintou-ui-patches \
        dsh-domus/profiles/web/packages/
  ```

- [ ] **2.2 用 CLI 换依赖**（`dsh plugin` 会同时维护 `dependencies` **和** `bundles`，已实测）
  ```bash
  cd ~/deepseek-harness
  ./bin/dsh plugin --profile web remove dsh-font-serif --store-dir $HARNESS/.pnpm-store
  ./bin/dsh plugin --profile web add file:packages/dsh-suigintou-ui-patches --store-dir $HARNESS/.pnpm-store
  ```
  **⚠️ 顺序要紧**：先 `remove` 旧的，再 `add` 新的。
  **⚠️ 硬链接陷阱**：pnpm 的 `file:` 依赖按 **inode** 绑定文件 ——
  若在重装之后再改包内文件，`node_modules` 那份会留旧内容。**改完必须重装。**

- [ ] **2.3 给 `@linxin666/dsh-web-all` 定版**
  现役写的是 `^0.3.6`。dry run 验的是 **0.3.20**。
  **改成精确 `0.3.20`**，去掉浮动 —— 否则下次安装可能跳到未验证的版本。
  注意 0.3.6 → 0.3.20 的**插件清单会变**：
  - 移除 `dsh-client-ui-aionui-panel`、`dsh-desktop-launcher`、`dsh-perf`（`dsh-perf` 已进
    `RETIRED_PLUGINS` 退休名单，靠跳过守卫静默不加载，无副作用）
  - 新增 `dsh-client-ui-model-capabilities`、`dsh-client-ui-preset-center`、`dsh-i18n`、
    `dsh-session-archive`、`dsh-usage`

- [ ] **2.4 改同步工具**
  `tools/plugin-sync-check.py` 第 **35** 行（`TARGETS`）与第 **40** 行（`NON_REGISTRY`）
  里的 `dsh-font-serif`。

---

## 阶段 3 · 版本切换

- [ ] **3.1 停 9007**（Linux 侧进程 + Windows 侧自启，两处都停）
- [ ] **3.2 执行 阶段 1**（预设键名）
- [ ] **3.3 执行 阶段 2**（插件改名 + 重装）
- [ ] **3.4 改版本真相源**（唯一一行，两个消费方同时生效）
  ```
  ~/deepseek-harness/DSH_VERSION:  DSH_VERSION=v0.1.5-rc.2
  ```
- [ ] **3.5 启动**
  ```bash
  cd ~/deepseek-harness && ./start-web.sh
  ```
  **首次启动会跑 `reconcilePlugins()` 安装/校正依赖 —— 盯住输出，别让它静默失败。**

---

## 阶段 4 · 验证（按此顺序，从硬伤到细节）

- [ ] **4.1 进程起得来吗** —— 9007 端口有响应
- [ ] **4.2 会话能进吗** ← **上次的硬伤**（preset 挂载）。随便开一个旧会话确认
- [ ] **4.3 皮肤八项** —— 复用 9009 上验证过的 snippet（见 `DSH皮肤锚点对照表.md` 末尾）
- [ ] **4.4 ⚠️ 7 个 bundle + 13 个 MCP**（**dry run 未覆盖面**）
  - 插件管理器里 11 个 bundle 是否都在
  - MCP 工具是否都挂上（本会话开头就是从 MCP 工具列表确认环境的）
  - 任何一个挂了，**优先怀疑它，而不是基座**
- [ ] **4.5 新会话 / 旧会话都能正常进出**

---

## 阶段 5 · 回滚（若需要）

- [ ] **5.1 停 9007**
- [ ] **5.2 还原 home**：`git -C ~/deepseek-harness/dsh-domus reset --hard <阶段 0.1 的 SHA>`
- [ ] **5.3 预设键名改回 `text:`**（用 `.bak-011rc2` 覆盖回去）
- [ ] **5.4 `DSH_VERSION` 改回 `v0.1.1-rc.2`**
- [ ] **5.5 重装依赖**（把 `node_modules` 退回 0.1.1 的依赖图）
  ```bash
  cd ~/deepseek-harness
  ./bin/dsh plugin --profile web install --store-dir $HARNESS/.pnpm-store
  ```
- [ ] **5.6 `./start-web.sh`**

**注意**：`storages/`、`sessions/` 都不在 git 里，回滚不动它们 ——
**会话数据本身是跨版本安全的**（迁移是惰性、非破坏性的）。

---

## 阶段 6 · 收尾（确认 9007 稳定之后再做）

- [ ] **6.1 删掉 dry run**（在此之前它是唯一能跑 0.1.5 的参照系 + 回滚保险）
  ```bash
  rm -rf ~/deepseek-harness/dsh-domus-dryrun ~/deepseek-harness/start-web-dryrun.sh
  ```
- [ ] **6.2 `git commit` 切换后的状态**
- [ ] **6.3 删掉 `tools/skin-patch-archive-20260911/`**
  （里面是误判产物 `border-bottom-width: 1px`，已证实无依据）
- [ ] **6.4 （可选）补 skills**：
  `cp -r 插件源码/dsh-deepread/skills/dsh-deepread/ dsh-domus/skills/`

---

## 一句话记住这次的教训

**皮肤层的版本对比，必须在「补丁齐备」的前提下做。**
补丁不在皮肤文件里（在插件里），照着皮肤文件找必然找不到、必然误判成回归。

---

## 附 · 延后处理项

> 用户 2026-09-11 决定：**优先级低于「对话数据一致性」与「迁移」，切换到 0.1.5 之后再处理。**

### 用户气泡 Markdown 渲染（原 `dsh-user-markdown` 补丁）

**性质**：现役 0.1.1 上**正在生效**的手打补丁，目标文件
`原始代码研究/v0.1.1-rc.2/packages/client/ui-conversation/lib/client.js`。

**⚠️ 它为什么需要手工备份**：`lib/` 被 `原始代码研究/*/.gitignore:4` 忽略（构建产物），
**git 对它的改动完全不可见** —— 所以手改必须另外抄一份出来。

| 项 | 值 |
|---|---|
| 备份 | `dsh-domus/patches/ui-conversation-lib-client.patched.from-011rc2.js`（451,093 B，**与源文件逐字节相同**）|
| 文档 | `dsh-domus/patches/dsh-user-markdown.md` |
| 做法 | `projectUserText()` 的「无引用 token」分支里，`MessageText` → `MarkdownText` |

**迁移到 0.1.5 的实测事实：**

| 0.1.5 文件 | 字节 | `projectUserText` | `MessageText` | `MarkdownText` |
|---|---|---|---|---|
| `ui-chat/lib/client.js` | 370,275 | 1 | 0 | **2** |
| `ui-conversation/lib/client.js` | 647,224 | 2 | 0 | 0 |

**→ 用户消息渲染路径已搬到 `ui-chat`；`MessageText` 两处都不再出现。**

**推论（未验证）**：官方可能已原生支持该渲染，**补丁或许已经过时**。

**10 秒判定法**：在 9009 输入框发一条含粗体与行内代码的消息
- 渲染成粗体 / 等宽代码 → 官方原生实现，**补丁作废**
- 显示成字面星号 → 需重打，**目标换成 `ui-chat/lib/client.js`**（`projectUserText` 仍在）

**⚠️ 这是 dry run 的未验证面之一**，与「7 个 bundle + 13 个 MCP 未在 0.1.5 上跑过」同类。

---

## 附 · 0.1.5 的一个启动级雷区（2026-09-12 实测踩到，写脚本时犯的）

**`sessions/<工作区编码>/` 下的任何子目录，都会被当成一条会话去读。**

若目录名与日志头部 `id` 不符 → `assertStoredIdentity()` 抛
`corrupt session log ...: header id "X" and cwd identify "Y"`
→ **`workspace` 是核心插件，异常直接让整个插件树加载失败，dsh 起不来。**

依据 `packages/session/session-persistence-jsonl/src/index.ts:1460`：
它用头部 `id` + `cwd` **反算期望路径**，与实际路径逐字比对；
`cp` 出来的副本连 `sameFile()` 这条逃生通道都不生效。

**⇒ 迁移前必须确认 `dsh-domus/sessions/` 树下没有非法目录名**
（手工备份、`.bak-*`、任何非 `session-<uuid>` 的东西都会被误判）。
已核对：现役与副本当前两棵树都干净。

**⇒ 备份一律放到 `sessions` 树之外**
（本场用 `~/deepseek-harness/session-backups/`）。**且备份不应收录 `session.lock`**
—— 陈旧锁会让回滚后的进程挂起。
