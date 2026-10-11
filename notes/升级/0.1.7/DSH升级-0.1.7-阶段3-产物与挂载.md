# 阶段 3 产物与挂载（v0.1.7-rc.2）

> 生成于 2026-09-26。生成器：`tools/convert-presets-to-017.py`、`tools/convert-settings-to-017.py`
> 映射依据：`DSH升级-0.1.7-阶段2-产物与迁移映射.md`
> **本文是阶段 4 的操作依据。**

---

## 一、产物清单（全部在 `dsh-domus/patches/`，均为独立文件）

| 文件 | 内容 | 可否单独撤除 |
|---|---|---|
| `0.1.7-agent-presets/{general,coding,scifi,fantasy,academic,liangshen}.patch.yml` | 6 个声明式预设 | ✅ 逐个 |
| `0.1.7-agent-presets/cwd-fallback.mjs` | 5 个预设共用的 `{{cwd}}` 兜底插件 | — |
| `0.1.7-settings.patch.yml` | settings 迁移：已解析的 7 节 | ✅ |
| `0.1.7-orphans-probe.patch.yml` | 4 节无宿主 entry（探针） | ✅ |
| **`0.1.7-includes.patch.yml`** | **挂载点**：8 个 `cordis:include` | ✅ |

`cwd-fallback` 为什么还在：0.1.7 的 `{{变量}}` 插值**仍是严格模式**
（`packages/core/system-prompt/src/index.ts` 里 `value === undefined` 直接 throw），
未选工作目录时会炸。5 份实测 md5 一致，故共享一份。

---

## 二、校验手段 —— 与一个**必须知道的盲区**

### ✅ 已验证（静态，全部只读，现役零改动）

| 手段 | 覆盖什么 | 结果 |
|---|---|---|
| 生成器内建**行级核对** | 预设正文逐行按序、恰好 +10 缩进 | ✅ |
| 生成器内建**回环校验** | 生成的文本再解析回来 == 意图 | ✅ |
| **反缩进逐字节比对** | 预设 plugins 段还原后与源文件**逐字节一致** | ✅ |
| `--patch <8 个文件> --dump-config` | 内容真能组进真 profile | ✅ exit=0，逐项核对通过 |
| `--patch 0.1.7-includes.patch.yml --dump-config` | 挂载点本身能组 | ✅ exit=0，8 个 include 条目就位 |

### ⚠️ 盲区：`--dump-config` **不递归进 include**

实测：挂了 `0.1.7-includes.patch.yml` 之后，树里能看到 8 个 `cordis:include` 条目、
路径与结构都对，**但树行数 1500 → 1540，只有一个 include 段的量**——
**被 include 的文件内容不进 dump**。这是 include 的独立 Loader 树性质决定的。

**后果**：走 include 路线，就**失去了"一条命令静态看到合并结果"的能力**。
两件事因此必须挪到阶段 4 运行时验证：

1. include **确实加载**了那 8 个文件（路径解析对、无 warn/error）
2. `agent-preset-registry` 实际列出了 **10 个预设**（官方 4 + 我们 6）

> **取舍说明**：独立文件 + include 换来了「不干扰现役、可逐文件撤除、以后升级原样复用」，
> 代价就是上面这条盲区。两者不可兼得——**并进 `cordis.patch.yml` 可静态验证，但 diff 脏、不可单撤**。
> 已按你的选择走 include；盲区用阶段 4 的运行时检查补上。

---

## 三、阶段 4 挂载步骤

> **全部由 `tools/switch-to-017.py` 代劳，且已沙盒演练通过。**
> 先看 §三点五的两条硬约束，再动手。

```bash
cd ~/deepseek-harness

# ① 先停 DSH（热加载会在 0.1.5 上加载 0.1.7 独有插件 → 假死）
bash tools/dsh-stop.sh --yes

# ② 干跑看一眼它要做什么（此时才允许，因为已停）
python3 tools/switch-to-017.py

# ③ 真执行
python3 tools/switch-to-017.py --apply

# ④ 起新版
./start-web.sh
```

脚本会依次做：体检 → 备份 4 个文件 → 追加 include 块 → 换 session-query 版本 →
`pnpm install` + cloudflared 回补(md5 校验) → 翻 `DSH_VERSION` → 跑补丁层护栏 →
打印八项运行时检查清单。**每步幂等，可重跑；重跑会被"已是目标版本"挡住。**

### 三点五、两条硬约束

**① 这活不能由会话内的 AI 代跑。** AI 的 bash 是 9007 那个 DSH 进程的子孙——
停 DSH 就停掉它自己，它没法编排自己的死亡。**必须你在终端里跑。**

**② 必须在 DSH 停止状态下跑。** `profiles/web/cordis.patch.yml` 是 cordis **热加载**的
（停机卡第二节）。我们要追加的 include 指向的是 `@deepseek-ai/dsh-agent-preset`
——**0.1.7 才有的包**。在 0.1.5 活着时写进去，热加载会立刻找不到它 →
`sessionController is unavailable` 无限刷 + 前台假死（2026-09-12 那两次事故的形态）。
⇒ 脚本**第一条安全闸门就是检测 9007 是否在监听，在跑就拒绝执行**。

### 三、原分步说明（脚本已自动化，留作人工兜底）

#### 3.1 挂载点（1 处追加）

把 `dsh-domus/patches/0.1.7-includes.patch.yml` 里那一整段 `- insert:`（8 个 include 条目）
**追加到 `dsh-domus/profiles/web/cordis.patch.yml` 末尾**。

追加后先跑护栏：`python3 tools/check_patch_layers.py --profile web`

#### 3.2 profile 依赖换版（1 处）

```bash
cd ~/deepseek-harness/dsh-domus/profiles/web
# 改 package.json： "@deepseek-ai/dsh-tool-session-query": "0.1.5-rc.2" → "0.1.7-rc.2"
pnpm install          # ⚠️ 会抹掉 cloudflared 二进制，见下
```

**`cloudflared` 回补**：
```bash
ls node_modules/cloudflared/bin/cloudflared || \
  install -m 755 ~/deepseek-harness/tools/cloudflared-linux-amd64.staged \
          node_modules/cloudflared/bin/cloudflared
```
版本 **2026.9.0**，大小 39,838,050，md5 `1d0ea8cd29387b0050075c5aca1485ae`。

> **换版理由**：现钉 `0.1.5-rc.2`。其 peer 是 `^0.1.5-rc.2`，
> 按 `includePrerelease:true` 对 0.1.7-rc.2 **判定为兼容**——所以**不会**被兼容性检查拦住。
> 换版是**降低风险**（0.1.7 改了客户端 session / 历史读取 API），不是硬性要求。

#### 3.3 基座追加：ui-chat 补丁已重打

`原始代码研究/v0.1.7-rc.2/packages/client/ui-chat/src/client/chat/MessageItem.tsx`
已改（+56/−3，4 处），`lib/client.js` 已重建（537,726 B，含 `projectUserContent` ×3）。
**这是检出内改动，切 `DSH_VERSION` 即生效**，无需额外动作。

### 三点六、回滚

```bash
cd ~/deepseek-harness/dsh-domus/patches/switch-backup-<时间戳>/
cp cordis.patch.yml package.json pnpm-lock.yaml ../../profiles/web/
# 再把 DSH_VERSION 改回 v0.1.5-rc.2，然后 ./start-web.sh
```

---

## 四、阶段 4 必须跑的运行时检查（补 §二 盲区）

| # | 检查 | 怎么查 | 期望 |
|---|---|---|---|
| 1 | include 是否真加载 | 启动日志里无 include 相关 warn/error | 无 |
| 2 | **预设是否 10 个** | Web 端预设选择器；或 `dsh --profile web --dump-config` 看 registry | 官方 4 + 我们 6 |
| 3 | **老会话能否打开** ★ | 打开任意一份 `agentPreset: coding` 的老会话 | 能打开（否则 `agent-preset/not-found`） |
| 4 | `{{cwd}}` 兜底是否在 | 开一个**没选工作目录**的临时会话，看 prompt 是否渲染成功 | 不炸 |
| 5 | settings 取值 | 设置页读一遍：主题 dark/16px、默认预设 coding、transcriptView standard | 一致 |
| 6 | **探针三节** | 看 `weLibraryDirs` / `pet` / `agentOpenTools` 是否生效 | 决定探针文件去留 |
| 7 | ui-chat 补丁 | 发一条带 markdown 的消息，看气泡是否渲染 | 渲染；且含 `@文件` 的消息**退回纯文本**（防腰斩） |
| 8 | 铁律 2 | `tools/DSH-升级铁律.md` 的五项核对表 | 全绿 |

---

## 五、日常维护

改了 `.agent-presets/<id>/` 或 `settings.yaml` 之后，**重跑两个生成器**即可：
```bash
python3 tools/convert-presets-to-017.py --apply
python3 tools/convert-settings-to-017.py --apply
```
两个脚本默认只预览，且都带自检（行级核对 / 回环校验），**核对不过拒绝写入**。
