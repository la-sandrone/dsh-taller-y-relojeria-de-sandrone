# 阶段 2 · v0.1.7-rc.2 离线预演（自跑指引）

> **给谁看**：你自己在终端里跑。本文档假设你已读过 `DSH停机卡.md` 与 `DSH升级-回归与重建清单.md`。
> **写于**：2026-09-26。目标检出 `原始代码研究/v0.1.7-rc.2`（`477b4f4`，tag `dsh-v0.1.7-rc.2`）。

---

## 0. 这一步算什么 / 不算什么

**算**：
- 确认 0.1.7 在这台机器上**装得上、构建得出来**（依赖解析 / 原生模块 / 磁盘）
- 拿到 0.1.7 **真实的 entry id 全集** ← 这是阶段 3「settings.yaml 手工迁移」的**唯一输入**

**不算**：
- ❌ 不切版本（`DSH_VERSION` 一行都不改）
- ❌ 不停 9007、不碰 `dsh-domus`
- ❌ 不做任何"顺手修一下"

**现役 9007 全程照跑**，本阶段唯一副作用是 v0.1.7 检出里多出 `node_modules/` 与构建产物。

---

## 1. 前置检查（1 分钟）

```bash
cd ~/deepseek-harness/原始代码研究/v0.1.7-rc.2
node -v                 # 期望 ^22.19 || >=24 —— 本机 v26.8.2 ✅
pnpm -v                 # 必须**在这个目录里**查！见下
git describe --tags     # 期望 dsh-v0.1.7-rc.2
```

### ⚠️⚠️ pnpm 版本：本节初版写错了，2026-09-26 11:50 更正

**初版的错误说法**（已删）：
> ~~"检出里钉的是 `pnpm@11.7.0`，而本机是 12.4.1（大版本差一档）……应急 `corepack prepare pnpm@11.7.0 --activate`"~~

**错在哪**：它暗示"系统 pnpm 12.4.1 会被使用"。**不会。**

实测事实：**PATH 上的 `pnpm` 本身就是 corepack 的 shim**
```
$ readlink -f $(which pnpm)
/usr/lib/node_modules/corepack/dist/pnpm.js
```
所以 `packageManager` 这个 pin 是**强制执行**的，不是建议。

- **在有 pin 的目录里**：corepack 按 pin 提供版本（现在 = `12.6.0`）
- **在没有 pin 的目录里**（如 harness 根）：corepack 用 `lastKnownGood` 兜底
  —— 我初版读到的 `12.4.1` 就是这个兜底值，**与检出无关**

**后果**：我那条"应急手段"如果照做，会把 corepack 钉到 11.7.0，而那恰恰是故障状态
（见下）。**这条错误建议已于 11:50 删除。**

### 实际发生的事（2026-09-26 11:46）

`package.json` 的 pin 被从 `pnpm@11.7.0` 改成了 `pnpm@12.6.0+sha512…`（工作区未提交），
随后一次嵌套的 pnpm 调用拿到的是**改之前**的解析结果 11.7.0 → 版本校验失败：

```
[ERROR] This project is configured to use 12.6.0 of pnpm. Your current pnpm is v11.7.0
```

这是一次**改 pin 过程中的瞬时竞态**。corepack 已在 11:47 拉下 12.6.0，现已自愈：

```bash
cd ~/deepseek-harness/原始代码研究/v0.1.7-rc.2
pnpm -v      # 实测 12.6.0 ✅
```

### 一条纪律

**版本一律在检出目录里查**，不要在 harness 根查——根目录没有 pin，查到的是 corepack 兜底值，
会得出满拧的结论。同理：**不要用 `corepack prepare ... --activate`**，
那会绕开 pin 制造第二套真相。

---

## 1.5 第二次更正：真正的根因与修法（2026-09-26 14:2x）

> 本节曾在 11:50 写过一版「失败在 `build:web`」+「用 `--pm-on-fail=ignore` 绕」的结论。
> **那版是错的**，两点都错：失败点判错、绕行写法也错。以下是实测修正版。

### 真正的根因：`node_modules/.bin/pnpm` 是一根指向 11.7.0 的 shim

```
$ cat node_modules/.bin/pnpm | tail -1
# cmd-shim-target=../.pnpm/pnpm@11.7.0/node_modules/pnpm/bin/pnpm.mjs
```

pnpm 12 的 **`packageManagerDependencies`** 特性会把声明的包管理器**当成项目依赖装进
`node_modules/.pnpm/`**，并在 `.bin/` 放一根 shim。而 `pnpm run <script>` 会把
**`node_modules/.bin` 顶到 PATH 最前面**——于是脚本里那句嵌套的 `pnpm --filter …`
拿到的就是这根 shim。

**状态自相矛盾**（这正是它叫的原因）：

| | 值 |
|---|---|
| `package.json` pin | `pnpm@12.6.0` |
| `pnpm-lock.yaml` 的 `packageManagerDependencies` | `pnpm 12.6.0` |
| **`node_modules/.pnpm/` 里真实装的** | **`pnpm@11.7.0`**（只有这一个） |
| `.bin/pnpm` 指向 | **11.7.0** |

11:48 那次安装按**当时的 pin（11.7.0）**vendored 了包管理器；之后 pin 改成 12.6.0，
**vendored 的那份没跟着重建** → 嵌套 pnpm 自己举报自己。

### 修法（实测有效）

```bash
cd ~/deepseek-harness/原始代码研究/v0.1.7-rc.2
rm -rf node_modules/.pnpm/pnpm@11.7.0 node_modules/pnpm node_modules/.bin/pnpm
pnpm install          # 实测返回 "Already up to date"（28ms），不会重建 —— 这没关系
pnpm run build        # 嵌套调用落到 PATH 上 corepack 的 12.6.0，一致了
```

> **`pnpm install` 不重建 shim 反而是好事**：shim 消失后，嵌套 `pnpm` 会沿 PATH
> 落到 corepack 的 shim，而 corepack 按 pin 给 **12.6.0** —— 全局一致。
> 万一将来 `pnpm install` 又把它装回来，只要 pin 是 12.6.0，装回来的也是 12.6.0。

### 上一版「绕行写法」也错了

```bash
pnpm run build:web --pm-on-fail=ignore     # ❌ 错
```
`pnpm run <script> --flag` 会把 `--flag` **传给脚本**，不是传给 pnpm。
实测就是被 `tsx scripts/build.ts --pm-on-fail=ignore` 吃成
`ERR_PARSE_ARGS_UNKNOWN_OPTION` 的。要传就得放前面：`pnpm --pm-on-fail=ignore run …`。
**但修好 shim 之后根本用不着它，别再往这个方向想。**

### 真正的失败点：不是 `build:web`，是 `build:lib` 的中途

`build:lib` 拆成两半，其中 host 半区**末尾**有一句嵌套 pnpm 调用：

```
build:lib:host   = tsc -b tsconfig.host.json && tsdown --env…host && pnpm --filter @deepseek-ai/dsh-desktop run bundle
build:lib:client = tsc -b tsconfig.client.json && tsdown --env…client        ← 从没跑到
```

那句 `pnpm --filter … desktop run bundle` 命中 11.7.0 → **整个 `build:lib` 中断**
→ **client 半区从未执行**。判据（对照 0.1.5 已建好的检出）：

| 包 | 0.1.5（完好） | 中断后 |
|---|---|---|
| `ui-theme/lib/` | `index.js` `client.js` `client.js.map` `types` | **只有 `types` + tsbuildinfo** |
| `ui-chat/lib/` | 同上四件 | **只有 `types` + tsbuildinfo** |

所以后面 `build:web` 里 vite 报 `Rollup failed to resolve import
"@deepseek-ai/dsh-client-ui-theme/brand-font.css"` —— 那是**症状**，不是病因：
`ui-theme/package.json` 的 `exports` 指向 `./lib/styles/brand-font.css`，而 client 半区
没跑，`lib/styles/` 压根没产出。

### 最终验收（实测通过）

```bash
ls -la apps/web/dist/index.html    # 824 B
du -sh apps/web/dist               # 21 M（0.1.5 是 13 M）
find packages -maxdepth 3 -name lib -type d | wc -l   # 312（中断时 265）
grep -icE "error|failed" /tmp/fullbuild.log           # 0
```

日志尾两条：`build: recorded 343 client artifact(s) with 3 public value(s)` / `✓ built in 3.89s`。

### 一条可复用的判据

**「构建产物里只有 `types/` 没有 `client.js`」= 某个半区没跑完。**
比看日志更快——`ls packages/client/<pkg>/lib/` 一眼就能判。

---

## 2. 安装

> **✅ 已于 2026-09-26 11:46 完成**（`node_modules` 1.9 G）。本节保留为**重装参考**。
> 除非要重装，否则直接跳 §1.5 的续跑，或 §3。

```bash
cd ~/deepseek-harness/原始代码研究/v0.1.7-rc.2
time pnpm install 2>&1 | tail -40
```

### ⚠️ 本次安装留下两处**与上游不同**的未提交改动（需知情）

| 文件 | 改动 | 谁写的 |
|---|---|---|
| `package.json` | `packageManager` 由上游的 `pnpm@11.7.0` → **`pnpm@12.6.0+sha512…`** | 变更 pin 的那次操作（`corepack use` 之类） |
| `pnpm-lock.yaml` | **+158 行**，头部多了 `importers.…packageManagerDependencies: pnpm 12.6.0` 段 | pnpm 12 的 package-manager 自管理特性自动写入 |

**这两处要不要留，是一个真实决策**（阶段 3 处理）：

- **留**：pin 与实际运行的 pnpm 一致，1.9 G 的安装产物与 265 个 lib 都是在这个版本下产出的，不必重来
- **还原**（`git checkout package.json pnpm-lock.yaml`）：回到上游 `11.7.0`，但**得重装一遍**，
  且 11.7.0 正是这次踩坑的那一档

**我的倾向：留，并在基线文档里记一笔。** 但这是你的机器，你说。

**体量参照**：0.1.5 检出的 `node_modules` 是 **1.6 G**。先看盘。

**卡住的话**——按上一次实战结论，**包管理器"卡住"十有八九卡在 postinstall，不是包下载**：

> `pnpm-workspace.yaml` 里的 **`allowBuilds` 清单就是「哪些包有 postinstall」的名单**。

本检出该表现状（已核对，是**合法的 map 格式**，不是数组）：
`esbuild: true` / `lefthook: true` / `node-pty: true` / `koffi: true` / `dsh-subprocess-local: true`，
其余 `@google/genai` / `protobufjs` / `node-addon-require-builtin` / `electron-winstaller` / `msgpackr-extract` 为 `false`。

注意它是**默认拒绝制**：任何带生命周期脚本又不在表里的包 → **hard install error（不是警告）**。
真踩到就按报错把包名补进去（`false` 也要写，写明为什么不跑）。

> **cloudflared 这次大概率碰不到**：它是 `dsh-domus/profiles/web` 的依赖
> （实测装在 `dsh-domus/profiles/web/node_modules/cloudflared/bin/`），
> **不在基座检出里**。那个坑留给阶段 4 的 profile 依赖变更。

---

## 3. 类型检查（便宜的闸门，先跑）

```bash
pnpm run typecheck 2>&1 | tail -30
```

它会先跑 `build:lib:host`（tsc 构建宿主半区），再做 contracts 检查。
**这一步能过 = 源码树自洽**。过不了就先别往下走，把报错回传。

---

## 4. 完整构建

```bash
time pnpm run build 2>&1 | tail -40
```

`build` = `tsx scripts/build.ts`，串起 host / client / web-frontend。

**验收（对照 0.1.5 基准）**：

```bash
find packages -maxdepth 3 -name lib -type d | wc -l   # 0.1.5 是 267；应同量级
ls apps/web/dist/index.html                           # 必须存在（0.1.5 的 dist 是 13M）
```

---

## 5. 【关键产出】dump 出 0.1.7 的真实 entry id

两条命令，**都只读、都不启动、都不碰 9007**。注意：必须用 `pnpm dsh`，
**不要用 `bin/dsh`**（它硬编码 `DSH_HOME=dsh-domus`，会在现役 home 上乱动）。

### (A) 纯基座视角 —— 官方 bundle 提供了哪些 entry id

```bash
cd ~/deepseek-harness/原始代码研究/v0.1.7-rc.2
rm -rf /tmp/dsh-probe-017
DSH_HOME=/tmp/dsh-probe-017 pnpm dsh --profile web --from-default-profile web \
    --dump-config-schema > /tmp/schema-base.json 2> /tmp/schema-base.err
echo "rc=$?  json=$(wc -c < /tmp/schema-base.json)B"
head -c 500 /tmp/schema-base.err
```

（`--dump-config-schema` = 打印 profile 条目与 patch 的 JSON Schema，**不 mount**）

### (B) 我们的视角 —— 合并我们 profile 后的全集 ★ 这个才是要的

```bash
DSH_HOME=$HARNESS/dsh-domus \
    pnpm dsh --profile web --dump-config-schema \
    > /tmp/schema-domus.json 2> /tmp/schema-domus.err
echo "rc=$?  json=$(wc -c < /tmp/schema-domus.json)B"
head -c 800 /tmp/schema-domus.err
```

### (C) 组装后的 profile 树（最直观，能直接看出哪个 entry 没了）

```bash
DSH_HOME=$HARNESS/dsh-domus \
    pnpm dsh --profile web --dump-config > /tmp/tree-domus.txt 2>&1
echo "rc=$?"; tail -60 /tmp/tree-domus.txt
```

---

## 6. 预期会看到什么（**别急着修**）

| 命令 | 预期 |
|---|---|
| (A) | 应当**干净通过**。它用的是出厂模板（`@deepseek-ai/dsh-base` + `@deepseek-ai/dsh-web-app`） |
| (B)(C) | **大概率报错或大量缺失** —— 因为 `settings.yaml` 与 `.agent-presets/` 还是 0.1.5 形态，且 profile 里的插件包还是 0.1.5 版 |

**这正是阶段 2 要的信息，不是失败。** 把报错**原样**回传，别自行修。
尤其留意这两类：

- `agent-preset/not-found` 或 preset 相关警告 → 印证「70 份会话全用 `coding`」那条红线
- **`duplicate loader entry id`** → 我们两层配置撞了（`$DSH_HOME/cordis.patch.yml` 与
  `profiles/web/cordis.patch.yml`，见 `DSH停机卡.md` 第二节的老问题），回传

---

## 7. 取证打包（回传给我）

```bash
tar czf /tmp/phase2-evidence.tar.gz -C /tmp \
    schema-base.json schema-base.err schema-domus.json schema-domus.err tree-domus.txt 2>/dev/null
ls -la /tmp/phase2-evidence.tar.gz
```

再附上这三条的原始输出：

```bash
cd ~/deepseek-harness/原始代码研究/v0.1.7-rc.2
git describe --tags && node -v && pnpm -v
du -sh node_modules
find packages -maxdepth 3 -name lib -type d | wc -l
```

---

## 8. 明确不要做的事

| | |
|---|---|
| ❌ 改 `DSH_VERSION` | 那是阶段 4。改了现役立刻换基座 |
| ❌ 跑 `bin/dsh` | 硬编码 `DSH_HOME=dsh-domus`，会和现役打架。用 `pnpm dsh` |
| ❌ 对 `dsh-domus/profiles/web` 跑 `pnpm install` / `pnpm add` | 会抹掉 cloudflared 二进制，且动到**现役** profile |
| ❌ 停 9007 / 重启 DSH | 本阶段完全不需要 |
| ❌ 在 domus 维度"顺手修一下" | 阶段 2 **只观察不修改**。任何改动都要落到阶段 3 的独立提交 |

---

## 9. 回滚

**无需回滚**——本阶段没有改动任何被依赖的东西。

真要清干净：
```bash
cd ~/deepseek-harness/原始代码研究/v0.1.7-rc.2
git clean -xdf     # ⚠️ 会删掉该检出下一切未跟踪文件（含 node_modules 与构建产物）
git status --short # 应只剩本地补丁（若有）
```

---

## 10. 卡壳时的诊断四步（上次实战提炼）

1. `wc -c < 目标文件>` **隔 20s 测两次** —— 数字在变 = 没死，只是慢
2. `ss -tnp | grep -v 127.0.0.1` —— `ESTAB` 指向 CDN = 在传；`SYN-SENT` 挂着 = 被墙
3. **分项测网络**，别只测"能不能上网"（上次实测 `npmjs` 200 而 `github.com` 超时，是两条不同的路）
4. **读那个卡的脚本** —— 上次读到 `createWriteStream(to)` 无 Range 请求 → 直接断定不能续传，省下徒劳重试

---

## 附：本阶段在五阶段里的位置

```
阶段 0 ✅ 重估 ui-chat / 工具预算换轴
阶段 1 ✅ 冻结备份点（dsh-domus fa4bca5）+ 基线文档
阶段 2 ← 你在这里：离线预演（构建 + dump entry id）
阶段 3    迁移物准备（预设声明 / settings 转 patch / ui-chat 补丁重打）← 需要本阶段产出
阶段 4    切换 + 运行时验收
阶段 5    下游收敛（melquiades 预算复核、v4 抽取规则）
```
