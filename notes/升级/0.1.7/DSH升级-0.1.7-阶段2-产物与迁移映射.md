# 阶段 2 产物 · v0.1.7-rc.2 的 entry id 全集与 settings 迁移映射

> **用途**：阶段 3「settings.yaml → profile patch」的**唯一输入**。
> **来源**：2026-09-26 14:38 用户实跑的三条 dump（`/tmp/schema-*.json`、`/tmp/tree-domus.txt`）。
> **方法**：读 `schema-domus.json` 的 `x-cordis.entries`（**权威清单**：每条带 `id` / `name` /
> `status` / `configRef`），而不是靠肉眼扫 tree。

---

## 一、三条 dump 的结果

| # | 命令 | 结果 |
|---|---|---|
| (A) | 出厂模板视角 | ❌ **失败**（但原因很干净，一句话可修 —— 见 §四） |
| (B) | 我们 domus 视角 | ✅ **932 KB schema**，226 个 entry |
| (C) | 组装后 profile 树 | ✅ **52 KB**，331 个 `- id:` 条目 / 1500 行 |

### (B) 的体检数字

```
entries 总数      226            complete = False
status: absent 107 / schema 116 / partial 2 / unsupported 1
```

### (B) 的 5 条诊断（`[/NNN]` = `x-cordis.entries` 里的序号，**已逐一归位**）

| 序号 | entry | 诊断 | 判定 |
|---|---|---|---|
| 111 | `ui-settings-account` | `contactFormUrl` 正则需原生校验 | 🟢 官方自身，非我们 |
| **148** | **`ui-chat`** | **`transcriptView` 宽松校验，非法值会被默认值替换** | 🔴 **命中我们**（见 §三） |
| 178 | `preset-standard` | `unrecognized Loader tree carrier` | 🟡 **dump 工具的能力所限**，非运行时错 |
| 179-181 | 其子项 `persona`/`agent-instructions`/`tool-bash` | 同上 | 🟡 同上 |
| 206 | `tool-ask-user` | `Config is not a native Schemastery schema` | 🟡 同上 |

> **178-181 / 206 不是我们的问题**：它们全在 `@deepseek-ai/dsh-agent-preset` 的
> `config.plugins:` 里。0.1.7 的新预设形态把子插件声明在 `config.plugins`（一个普通 YAML 列表），
> 而 dump 工具要求子集合走 `cordis:group` / `cordis:include` 才算"原生 carrier"。
> **运行时由 preset 插件自己解析，不受影响。**
> ——但它告诉我们一件要紧事：**我们的预设也必须写成这个形态**（见 §五）。

---

## 二、🔴 最重要的结论：`coding` 不存在

组合树里总共只有 **4 个预设**，全部来自官方 `@deepseek-ai/dsh-web-app`：

| preset id | entry |
|---|---|
| `standard` | `preset-standard` ← registry 的 `default` |
| `ptc` | `preset-ptc` |
| `minimal` | `preset-minimal` |
| `cordis` | `preset-cordis` |

**`coding` 不在。** 而基线实测：**70 / 70 份会话头的 `agentPreset` 全是 `"coding"`**。
registry 对未知 id 抛 `agent-preset/not-found` → **不声明就是 70 份全打不开**。

---

## 三、settings.yaml 11 节 → 0.1.7 entry 映射表（逐字段实测）

`x-cordis.entries` 里查同名 entry，并逐个字段核对其 Config schema。

### ✅ 7 节有明确归宿

| settings.yaml 节 | 0.1.7 entry | 字段核对 |
|---|---|---|
| `llm-deepseek` | `llm-deepseek`（`@deepseek-ai/dsh-llm-deepseek-api-key`） | ✅ `reasoningEffort`（enum off/low/high/max，volatile）✅ `models`（volatile） |
| `llm-pi-ai` | `llm-pi-ai` | ✅ `providers`（volatile） |
| `ui-theme` | `ui-theme` | ✅ `preference`（enum light/dark/system，默认 system）✅ `fontSize`（默认 14） |
| `agent-default-model` | `agent-default-model` | ✅ `provider` + `model`（**required**）+ `reasoningEffort` |
| `ui-chat` | `ui-chat` | ⚠️ `transcriptView`（默认 `standard`）—— **值要改，见下** |
| `ui-onboarding` | → **`ui-settings-general`** | ✅ `welcomeNoticeVersion`（官方硬编码映射表里的那条） |
| **`agent-presets`** | → **`agent-preset-registry`** | ✅ `default`（required）+ `selectedDefault` |

**两条硬编码重命名**（0.1.7 源码 `packages/settings/settings/src/index.ts` 的
`LEGACY_SECTION_ENTRIES`，只有这两条 + `shell`）：
`ui-developer-tools`→`ui-settings`、`ui-onboarding`→`ui-settings-general`。
**`agent-presets`→`agent-preset-registry` 不在表里，必须我们手工改。**

### ⚠️ 一处必须改值：`ui-chat.transcriptView`

- 我们写的是 **`normal`**（0.1.5 的 legacy 值）
- 0.1.7 schema：`default: "standard"`，且标了 **`loose: true`**，限制说明原文是
  *"loose validation can replace invalid values with defaults"*
- ⇒ **`normal` 会被静默替换成 `standard`**。迁移时**直接写 `standard`**，别让它走 legacy 路径。

### ❓ 4 节没有宿主 entry —— 它们的字段住在**客户端 user-settings 命名空间**里

| settings.yaml 节 | 实测归属 | 说明 |
|---|---|---|
| `skin-wallpaper` | 客户端 NS，skin-center 插件读 `deps.getConfig().weLibraryDirs` | 组合树里 `web-ui-skin-center` **只是个 include 壳**：`config: {plugin: '@linxin666/dsh-client-ui-skin-center'}` |
| `skin-custom-theme` | 客户端 NS（`applied`） | 同上 |
| `pet` | 客户端 NS | `web-ui-pet` 同样只是壳：`config: {plugin: '@linxin666/dsh-pet'}` |
| `dsh-better-sidebar` | 客户端 NS `"dsh-better-sidebar"`（插件内 `SIDEBAR_PREFS_NS` + `PrefsSchema`） | 宿主 entry `better-sidebar` 的 Config 是 **另一套**：`readLimit/mediaLimit/uploadLimit/listLimit/terminalsPerSession/reconnectGraceMs/shell/shellArgs` —— **没有 `agentOpenTools`** |

**后果**：官方一次性导入按「section id 即 entry id」逐节 `update()`，
这 4 节**找不到 entry → warn 后丢弃**。

**这正好印证了「不信官方一次性导入、手工转」的决定是对的。**

**待验证的迁移假设**（阶段 4 实测）：把这 4 节的值**并进 include 壳 entry 的 config**，与 `plugin:` 并列：

```yaml
- id: web-ui-skin-center
  config:
    plugin: '@linxin666/dsh-client-ui-skin-center'
    weLibraryDirs: [<挂载d>:/游戏/SteamLibrary/steamapps/workshop/content/431960]
```
依据：插件读的是 `deps.getConfig().weLibraryDirs`，而 include 壳的子插件 config 就是
`config` 去掉 `plugin` 之后的部分。**`dsh-better-sidebar` 那节可能不适用**（它是独立 NS，
不是壳的 config）—— 需实测。

---

## 四、(A) 为什么失败 —— 一句话可修

```
Error: dsh: profile "web" is shipped and cannot be a custom profile target;
       omit --from-default-profile to use it
```

`web` 是**出厂 profile 名**，不能当 `--from-default-profile` 的目标。换个**自定义名**即可：

```bash
rm -rf /tmp/dsh-probe-017
DSH_HOME=/tmp/dsh-probe-017 pnpm dsh --profile probe --from-default-profile web \
    --dump-config-schema > /tmp/schema-base.json 2> /tmp/schema-base.err
```

> 原命令里的 `--profile web --from-default-profile web` 是我写的，**是我写错了**。

---

## 五、阶段 3 的待办（由本文档派生）

| # | 事项 | 依据 |
|---|---|---|
| 1 | **声明 6 个预设**（id 逐字保持 `general/coding/scifi/fantasy/academic/liangshen`） | §二；形态照 `preset-standard`：`@deepseek-ai/dsh-agent-preset` + `config.plugins` |
| 2 | `agent-preset-registry.default` ← 我们原来的 `coding` | §三 |
| 3 | settings 手工转 profile patch：7 节按映射表落位，`transcriptView` 写 `standard` | §三 |
| 4 | 4 个孤儿节：先按 §三 的假设写进 include 壳，阶段 4 实测；不行再议 | §三 |
| 5 | 重跑 (A) 拿到干净基准（换 profile 名） | §四 |
| 6 | ui-chat 源码补丁重打（`projectUserText` 3 参 → 5 参） | 阶段 0 已定 |
| 7 | `@deepseek-ai/dsh-tool-session-query` 换 0.1.7-rc.2 | 阶段 0 已定 |
