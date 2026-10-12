# DSH 公开仓：合集仓 `dsh-taller-y-relojeria-de-sandrone` 与它的导出管线

**日期**：2026-10-11
**起因**：`dsh-sandrone-ui-patches`（0 star）从「单一 UI 补丁包」升级为**对 DSH 的爆改合集**，
顺带解决 GitHub Pin 位不足。旧仓内容全部并入，位置不变的那部分**安装命令继续有效**。

---

## 一、仓名与标题

| | |
|---|---|
| 仓名 | `dsh-taller-y-relojeria-de-sandrone`（西语 `taller y relojería de Sandrone` ＝ 工坊与钟表铺；`y` 是**并列**，对应两类活：改行为 / 改外观） |
| README 标题 | `Nuestra Señora del Trono de Sabiduría, Espejo de Justicia, Salud de los Enfermos, Refugio de los Pecadores, Arca de la Alianza y Estrella de la Mañana`（劳雷托连祷的**六个真称号**串联；取「镜」对应桑多涅的命之座「镜中奇械座」） |
| 目标路径 | `<挂载e>:/公开发布项目/dsh-taller-y-relojeria-de-sandrone`（`<发布项目目录>\…`） |

## 二、管线（两条，各管一半 —— 没有另造等价物）

| 脚本 | 管什么 | 备注 |
|---|---|---|
| `tools/export-to-sandrone.py` | **UI 补丁包**那一半：从 home 里的本地开发包 `dsh-suigintou-ui-patches` 导出为 `dsh-sandrone-ui-patches`（白名单 + 改名 + 残留检查 + node 语法检查） | 2026-10-11 只改了一处：`DST_ROOT` 指向新合集仓 |
| `tools/export-dsh-collection.py` | **其余全部**：补丁 / 笔记 / 工具 / 启动器 / 皮肤 / 生成文件（白名单 + 脱敏 + 四道闸门） | 新增。默认干跑，`--apply` 才写；**不 rmtree**，只覆盖它自己列出的文件 |

`export-dsh-collection.py` **不管**手写资产（`README.md` / `NOTICE.md` / `LICENSE` / `docs/` / `bench/` / `packages/`）——
重跑不会覆盖它们，符合「手写的归手写、派生的归管线」。

## 三、三条关键判据（写进脚本，不靠记性）

1. **零位图**：任何 `png/jpg/jpeg/webp/gif/avif` 都不进仓（例外只有随包字体与 `bench/katex/` 的 KaTeX 字体，
   在 `NOTICE.md` 列明）。⇒ 皮肤背景**自备**；`皮肤/字形证据/` 那 6 张实测截图也因此不发。
2. **只放自己的皮肤**：`skins/` 下**只有 `navia`**（`author: local`）。皮肤中心其余 11 个是他人作品
   （stushansusu / lemonhall / Twelveeee / sclass53 / moeblack / seanchen / dsh-web×4 / oh-wang），
   其中 3 个自带 `LICENSE`/`NOTICE` —— 不可二次分发。
3. **凭据硬失败、身份性信息自动改写**：
   - 凭据正则命中 ⇒ **不自动替换**，打印 `文件: 规则: 片段` 并返回 rc=2，逼人工处置；
     确属误报的要在脚本的 `SECRET_EXEMPTIONS` 里**写明理由**。
   - `$HARNESS` → `$HARNESS`、`~` → `~`、`<user>` → `<user>`，
     每次改写**逐文件记账**。

## 四、本次导出结果（2026-10-11）

- **142 文件 / 3.2 MB**；`patches/` 8、`notes/` 38、`tools/` 7、`skins/` 5、`bench/` 67、`packages/` 6
- 闸门：**零位图 ✓ / 无凭据 ✓ / 无身份性残留 ✓**；10 个 `.py` 语法自检全过；UI 包旧名残留 0、node 语法 ✓
- 脱敏记账共 13 个文件（`$HARNESS` ×27、`~`…、`<user>` ×1）
- git：`git init -b main` + 首提交（作者身份 `Sandrone <49679244+la-sandrone@users.noreply.github.com>`）
- ⚠️ 上列是**首版**数字；至 2026-10-11 晚已增至 **146 文件**（补了启动器的 `启动器配置和日志/版本信息说明/`、`tools/skin-color-probe.py`，以及取色判据 / 可移植化 / 草稿区落点三篇新笔记）
- 启动器在新仓自检：缺 `启动器配置和日志/当前配置.toml` 时**明确报错**（不静默）——仓库里给的是 `.example`

## 五、待办

1. ~~旧仓处置~~ ✅ **已办（2026-10-11）**：本地 `dsh-sandrone-ui-patches` 与 GitHub 上同名仓都已删除
   （SSH 探测返回 `Repository not found`）。
2. **建远端 + 推送（未办）**：⚠️ 新仓**也没有远端了** —— 用户把 GitHub 上那个也删了，理由见 §六（历史无法解释 ⇒ 连工作树重开）。现在 `git remote -v` 为空，等新仓建好再接 origin。
3. **README 手改**：现有 README 是自动写的一版，标题与索引已就位，正文可按口味重写
   （重跑管线**不会**覆盖它）。
4. ~~机器路径残留~~ ✅ **已办**：`/mnt/<盘>/` 与 **Windows 盘符路径**（`<D盘>:\User Data\…`、
   `<venv盘>\…`、`<C盘>:/Program Files/…`）都已进 `REDACTIONS`；闸门 3 同时扩成「机器路径全谱」
   （含 `%USERPROFILE%`、`<WSL>\Users` 等形态），实测 73 个文本文件残留 0。
5. **皮肤 `preview`**：发布版 `skin.json` 去掉了 `preview` 字段（原预览图是含插画的截图）。
   后果是皮肤中心可能显示占位缩略图——**本机未实测**，值得在你自己的实例上验一次。

---

## 六、仓的重开（2026-10-11 晚）—— 旧历史作废

**背景**：GitHub 上那个远端**已被删除**（用户处置）。本地那串提交（`89b226e` → `dd84750`，8 条）
对应的远端不复存在 ⇒ **提交记录对外解释不清楚** ⇒ 用户裁定：**连工作树一起重开**。

三件事：

| 做了什么 | 细节 |
|---|---|
| **重开 git** | 删 `.git` → `git init -b main` → **单条首提交 `4d28c43`**（146 文件）。⚠️ **旧 SHA 全部作废**，别在别处再引用 |
| **换 LICENSE** | 改用 **SPDX 公版 MIT 正文**（<https://raw.githubusercontent.com/spdx/license-list-data/main/text/MIT.txt>），只填版权行 `Copyright (c) 2026 la-sandrone`。原来自写那版（MIT 与上游说明混在一起）废弃；上游与第三方授权仍在 `NOTICE.md` 逐项列明 |
| **保留手写件** | `notes/排版/README.md` 保持用户当前写法（只留指路一句）—— 手写资产，管线不生成、也不该覆盖 |

**现状**：本地 **1 条提交 / 146 文件 / 0 待提交 / 无远端配置**（`git remote -v` 为空）。

### 接远端（新仓建好后）

```bash
cd <挂载e>:/公开发布项目/dsh-taller-y-relojeria-de-sandrone
# 让 gh 直接建好并推（需要代理）：
gh repo create la-sandrone/dsh-taller-y-relojeria-de-sandrone --public --source=. --remote=origin --push
# 或远端已建好时：
git remote add origin git@github.com:la-sandrone/dsh-taller-y-relojeria-de-sandrone.git
git push -u origin main
```

### 再发布的三条命令

```bash
cd <挂载e>:/公开发布项目/dsh-taller-y-relojeria-de-sandrone
python3 ~/deepseek-harness/tools/export-dsh-collection.py --apply   # 1) 同步（默认干跑）
git add -A && git commit -m "…"                                     # 2) 入库
git push                                                            # 3) 推送（SSH 走 443）
```

### ⚠️ 三条实测要点（仍然有效）

1. **`api.github.com` 会抽**：`gh repo create` 第一次 `EOF`（重试即成功），随后两次 `gh repo view` 又是 `EOF`。
   ⇒ **远程复核走 SSH**：`git ls-remote origin`（同一分钟内 SSH 三次全通、API 两次 EOF）。
   ⇒ **建仓与推送拆开跑**，否则半途成功后重跑会因「仓已存在」产生歧义。
2. **`gh` 需要代理，`git push` 不需要**：`~/.ssh/config` 已把 `github.com` 指到 `ssh.github.com:443`。
3. **别在公开仓手改管线生成的文件**：`skins/navia/README.md` 这类由管线产出，手改会被下次 `--apply`
   覆盖（2026-10-11 已踩过一次，见四个生成文档头部的提示）。

### 推送前的终检（已固化成命令，见笔记正文）

```bash
git ls-files | wc -l
git ls-files | grep -ciE '\.(png|jpe?g|webp|gif|avif)$'      # 期望 0
git ls-files | grep -ciE '(\.env$|\.cnf$|密钥|\.pem$)'       # 期望 0
git grep -I -c -E '<user>' HEAD | wc -l                   # 期望 0
git ls-files -z | xargs -0 du -h | sort -rh | head -3        # 最大文件应 <1MB
```
