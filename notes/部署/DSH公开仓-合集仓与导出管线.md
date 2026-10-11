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
- git：`git init -b main` + 首提交 **`89b226e`**（作者身份沿用旧仓：`Sandrone <49679244+la-sandrone@users.noreply.github.com>`）
- 启动器在新仓自检：缺 `启动器配置和日志/当前配置.toml` 时**明确报错**（不静默）——仓库里给的是 `.example`

## 五、待办

1. **旧仓处置**：`<发布项目目录>\dsh-sandrone-ui-patches` 可删（内容已全部并入，仅丢 3 条 commit 历史）；
   GitHub 上的 `la-sandrone/dsh-sandrone-ui-patches` 也需一并处理（新仓建好后推送，再删或改名）。
2. **建远端 + 推送**：新仓尚未设 remote（`git init` 只做了本地首提交）。
3. **README 手改**：现有 README 是自动写的一版，标题与索引已就位，正文可按口味重写
   （重跑管线**不会**覆盖它）。
4. **机器路径残留（报告制，不是闸门）**：`/mnt/[cdefr]/…` 形式的路径在若干笔记里仍有约 20 处
   （最多的是 `notes/升级/0.1.7/DSH升级-0.1.7-基线.md` 7 处）。它们不含身份信息，故未自动改写——
   要不要统一成占位符，是你的取舍。
5. **皮肤 `preview`**：发布版 `skin.json` 去掉了 `preview` 字段（原预览图是含插画的截图）。
   后果是皮肤中心可能显示占位缩略图——**本机未实测**，值得在你自己的实例上验一次。

---

## 六、已发布（2026-10-11）

| 项 | 值 |
|---|---|
| 远端 | `git@github.com:la-sandrone/dsh-taller-y-relojeria-de-sandrone.git`（**public**） |
| 远端 HEAD | `971d6e2` ＝ 本地 HEAD（`main` 已设跟踪，`git status -sb` 干净） |
| 体积/文件 | 142 文件 / 3.3 MB；位图 0、凭据类文件 0、身份残留 0 |
| topics | `deepseek-harness` `dsh` `patches` `ui-theme` `dsh-plugin` |

两次提交：`89b226e` 首版 → `971d6e2` 手改润色（README 标题说明口语化、**皮肤来源更正为 `dsh-web-all` 全家桶**、底图更正为 pixiv 插画、「优雅降级」→「降级」）。

### 再发布的三条命令

```bash
cd <挂载e>:/公开发布项目/dsh-taller-y-relojeria-de-sandrone
python3 ~/deepseek-harness/tools/export-dsh-collection.py --apply   # 1) 同步（默认干跑）
git add -A && git commit -m "…"                                     # 2) 入库
git push                                                            # 3) 推送（SSH 走 443）
```

### ⚠️ 三条实测要点（本次撞到）

1. **`api.github.com` 会抽**：`gh repo create` 第一次 `EOF`（重试即成功），随后两次 `gh repo view` 又是 `EOF`。
   ⇒ **远程复核走 SSH**：`git ls-remote origin`（同一分钟内 SSH 三次全通、API 两次 EOF）。
   ⇒ 首次建仓命令：`gh repo create <owner>/<repo> --public --source=. --remote=origin --push`，
   但**建仓与推送拆开跑**，否则半途成功后重跑会因「仓已存在」产生歧义。
2. **`gh` 需要代理，`git push` 不需要**：`~/.ssh/config` 已把 `github.com` 指到 `ssh.github.com:443`。
3. **旧仓仍在 GitHub**（`la-sandrone/dsh-sandrone-ui-patches`，SSH 探测确认）。本地那份也还在
   `<挂载e>:/公开发布项目/dsh-sandrone-ui-patches`。**两者都待处置**（删除，或把旧仓改名为合集名——后者会留 301 重定向）。

### 推送前的终检（已固化成命令，见笔记正文）

```bash
git ls-files | wc -l
git ls-files | grep -ciE '\.(png|jpe?g|webp|gif|avif)$'      # 期望 0
git ls-files | grep -ciE '(\.env$|\.cnf$|密钥|\.pem$)'       # 期望 0
git grep -I -c -E '<user>' HEAD | wc -l                   # 期望 0
git ls-files -z | xargs -0 du -h | sort -rh | head -3        # 最大文件应 <1MB
```
