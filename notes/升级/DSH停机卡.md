# DSH 停机与回滚卡（离线用 · 不需要 AI）

> **dsh 死了就没法问 AI**。所以这份卡片是可以离线照做的。
> 所有命令都在 **你自己的终端** 里跑（AI 的沙箱 `bwrap --unshare-pid` 看不到宿主进程）。

---

## 一、先判级别：三级处置

| 症状 | 级别 | 动作 |
|---|---|---|
| 控制台开始刷 `sessionController is unavailable`、前台变卡 | **L1 止血** | 把最近改过的配置**还原/注释掉**。热加载会自愈——**已验证有效**（2026-09-12 两次事故都是这样救回来的） |
| 改了配置后启动直接报错（`duplicate loader entry id` 等） | **L1 止血** | 同上：还原配置，再启动 |
| UI 完全没反应、止血也没用、进程假死 | **L2 硬停** | `./start-web.sh --stop`（TERM → 等 20s → 自动升级 SIGKILL → 复验端口） |
| 仍停不掉（输出 `✗ 端口仍占用`） | **L3 强杀** | `./start-web.sh --status` 拿到 pid，再 `kill -9 <pid>` |

**顺序永远是：先 L1（最便宜、已验证有效）→ 不行再 L2 → 最后 L3。**

> **日常结束方式就是前台 `Ctrl+C`**（2026-09-27 定）。SIGINT 直达 host → 优雅退出、退出码立刻可见。
> L2/L3 只为"假死 / 无响应"预备，正常收工不要用。

---

## 二、L1 止血：还原配置

配置是**热加载**的——改完几秒内生效，**不需要重启**。所以：

```bash
cd $HARNESS/dsh-domus-0.1.7-rc.2/profiles/web

# 看现在有哪些版本快照（按时间）
ls -lt cordis.patch.yml*

# 还原到某一个快照（原子替换，避免读到半个文件）
cp cordis.patch.yml.bak-XXX cordis.patch.yml.new && mv -f cordis.patch.yml.new cordis.patch.yml
```

**最快的一招**（当你只想让它别炸）：把出问题的那一行**注释掉**，保存。热加载会重新应用。

### 改配置前必做的事（护栏）

```bash
DSH_HOME=$HARNESS/dsh-domus-0.1.7-rc.2 \
python3 tools/check_patch_layers.py --profile web
# 退出码 0 = 可以启动；1 = 有重复 id，会炸，别启动
```

**为什么必须做**：两份配置**内容相同时，会撞 entry id** → 启动直接崩；若撞在**热加载**路径上，**没有任何预警**，只表现为 `sessionController is unavailable` 无限刷 + 前台假死。这正是 2026-09-12 两次事故的原因。

**规矩**：同一批 entry id（例如那 13 个 `mcp-*`）**只允许在一层定义**。`$DSH_HOME/cordis.patch.yml`（机器级）和 `$DSH_HOME/profiles/<name>/cordis.patch.yml`（profile 级）**不要同时**定义同一批 id。

---

## 三、L2/L3 停机

```bash
cd $HARNESS

./start-web.sh --status              # 看 9007 上是谁 + 环境复核（不动它）
./start-web.sh --stop                # TERM → 等 20s → 自动升级 SIGKILL → 复验端口
./start-web.sh --stop --port 9012    # 停影子实例
```

停机只有一个入口：`start-web.sh --stop`。它是**自包含**的——SIGTERM → 最多等 20 秒 →
升级 SIGKILL → 再等 2 秒复验，并明确回三态之一：`✓ 已退出` / `✓ 已强杀` / `✗ 端口仍占用`。
所以"停不掉"不会再变成一句空话；看到 `✗` 才需要上 L3。

> **为什么撤掉了 `tools/dsh-stop.sh`（2026-09-27）**：它有两个毛病，都属于"看着跑通了"。
> ① 默认端口还停在早已退役的 9009 —— 敲下去只会回"本来就没在监听"，而你以为已经停了；
> ② 它在 `set -euo pipefail` 下写 `PID="$(ss…|grep…|head -1)"`，端口没监听时管道非零 →
> 赋值非零 → **脚本静默中止、零输出**，本该兜底的分支成了死代码。
> `start-web.sh` 的 `pid_on_port` 是同一教训的正解：先把 `ss` 输出整段收进变量再循环，
> 管道退出码不泄进赋值，另配 `/proc/*/cmdline` 兜底。

**手工版**（启动器本身也坏了时的兜底）：

```bash
ss -ltnp | grep 9007          # 输出里找 pid=NNNN
kill <PID>                    # 不行就 kill -9 <PID>
# 或
pgrep -af "bin.ts web"
```

---

## 四、重启

```bash
cd $HARNESS
./start-web.sh
```

浏览器开 **`http://127.0.0.1:9007`**（若提示要认证，用启动输出里那条带 `?token=` 的完整 URL）。

---

## 五、回滚点清单

| 对象 | 回滚点 | 说明 |
|---|---|---|
| profile 配置 | `…/cordis.patch.yml.bak-d3-20260912-114855` | **2026-09-12 事故前的原始版** —— ⚠️ 见下方「残件清退」说明，现已移入归档 |
| profile 配置 | `…/cordis.patch.yml.bak-d3b` | 绝对路径挂载版（含 tool-session-query）—— 同上，已移入归档 |
| profile 配置 | `…/cordis.patch.yml.orig-mcp` | 更早的 MCP 参考版 —— 同上，已移入归档 |
| `fast_filesystem.py` | `cp fast_filesystem.py.pre-d10-d11-debug fast_filesystem.py` | 回到 D10/D11 改动前（干净基线） |
| `fast_filesystem.py` | `git -C <挂载d>:/DataServices/MCP/wrap revert 8e6d8a1` | 同上的 git 版 |
| 影子实例 | `rm -rf dsh-domus-probe` | 消耗品，删了无损失 |
| preset 引擎行（wwt→ptc） | 原 `_scratch/backup-retire-wwt-20260927-071448/`；2026-10-11 随 `_scratch` 退役清掉（**已确认不构成损失**） | 三处替换前原文（5 预设 × id/name 两行），2026-09-27。真要重放，跑 `retire-wwt.py`（本体在 git 历史里）的逆操作 |
| 本地 liangshen 副本 | 原 `_scratch/liangshen-preset-retired-20260927-071444.tar.gz`；2026-10-11 随 `_scratch` 退役清掉（**已确认不构成损失**） | 自己改编的旧副本已退休；上游 `@linxin666/dsh-liangshen` 保留不动 |

> **⚠ 回退链状态（2026-09-27 收工 · 三件套已删除）**：链接层已**清零**——
> `dsh-domus-0.1.7-rc.2/profiles/` 下已无任何指向 `原始代码研究/v0.1.5-rc.2/` 的链接
> （当日处置：272 条重连到 0.1.7 安装树、11 条死引用清退、本地 liangshen 旧副本与
> `dsh-user-markdown` 遗留目录退休；`check-profile-links.py` 结论=「干净」，0 断链）。
>
> 三件套（`dsh-domus-0.1.5-rc.2/`、`原始代码研究/v0.1.5-rc.2/`、`start-web-015.sh`）
> **已走完"改名试探 → 冷启验证 → 真删"三步，删除完毕**；回退工具
> `tools/restore-015-and-restart.sh` / `restore-015-node-modules.py` 也已退役
> （主仓 `ce9f808` / `43c6c77`）。**回退链只剩备份包**：
> 0.1.7 若整体挂掉，**只能从 `<挂载d>:/` 下的 `dsh-full-*.tar.zst` 恢复**
> （当前可用的那份：`dsh-full-20260927-073333-链接层政策.tar.zst`，含 node_modules + 清单），
> 没有"改个版本号指回去"这条捷径了。
>
> ---
>
> ### ⚠ 残件清退（2026-10-07）—— 单文件回滚点搬家了
>
> 当日按「备份统一交 git 管理」清退了全仓 **163 个 `.bak` 系残件**（`.bak-*` / `.orig-*`
> / `.broken-*` / `.failed-*` / `.myintrusion-*` / `.step1*` / `.pre-update-*` / `.preconfigfix-*`）。
> 其中 **69 个的内容在 git 对象库里**（把残件字节 `git hash-object` 成 blob 后
> `git cat-file -e` 认得——判据是**残件内容**在不在库里，不是"活文件有没有提交历史"），
> 可经 `git log --all -- <活文件路径>` 找回；
> **另外 94 个 git 管不住**（多为从未提交过的改前快照），已整体归档：
>
> ```
> $HARNESS/backups/residue-git-unrecoverable-20261007-230429.tar.zst
> ```
>
> 取用：
>
> ```bash
> cd $HARNESS
> # 看归档里有什么（保留原相对路径，解档即原位还原）
> zstd -dc backups/residue-git-unrecoverable-20261007-230429.tar.zst | tar -t | less
> # 取单个回滚点（例：2026-09-12 事故前原始版）
> zstd -dc backups/residue-git-unrecoverable-20261007-230429.tar.zst \
>   | tar -x -C /tmp/rollback --wildcards \
>     'dsh-domus-0.1.7-rc.2/profiles/web/cordis.patch.yml.bak-d3-20260912-114855'
> ```
>
> **⟹ 上表前三行（`bak-d3-20260912-114855` / `bak-d3b` / `orig-mcp`）的路径已失效，
> 它们现在只存在于这个归档里**（三个都是 IRREPLACEABLE，git 里没有）。
> 恢复配置后务必先跑护栏：`python3 tools/check_patch_layers.py --profile web`。
>
> 体检/清退工具：`tools/audit-backup-files.py`（只读体检）、
> `tools/retire-backup-residue.py`（`--archive` / `--delete` 两阶段）。
>
> 链接层工具仍在（**不是**回退工具，是修当前实例的）：`tools/repair-profile-links.py`
> （默认干跑；`--apply` 应用；`--restore <manifest.json>` 按 manifest 回滚）。
>
> **⚠ 2026-10-08 泛化 + 一处命名变更**：该工具现在也能**从零建层**（旧版只会"修断链"，
> 层不存在时扫到 0 条、静默什么都不做）。新增 `--home` / `--source-checkout` /
> `--names-from` / `--layer` / `--gate`。manifest 文件名**多了 home 名**
> （`_scratch/profile-links-repair-applied-<home>-<时间戳>.json`）——上面的通配
> `profile-links-repair-applied-*.json` 仍然匹配，但**要注意它现在会列出多个 home 的 manifest**，
> 回滚前先看清是哪一个。⚠️ 2026-09 那批旧 manifest 已随残件清退进归档
> （`backups/工作区历史归档-20261008.tar.zst` 的 `_scratch-历史/`），不再在 `_scratch/` 里。
>
> 配套新增隔离门禁：`tools/check-inode-sharing.py`（判据：包字节共享=预期，
> **路径寻址的符号链接越界**才是要断的）。详见 `DSH升级-0.2.x-调查与方案.md` 与
> `dsh-domus-0.2.0-rc.2/升级待办-阶段1.md` §三。
>
> **⚠ 备份政策已改（2026-09-27，血的教训）**：旧的 `dsh-full-*.tar.zst` 全是 **config-only** ——
> `node_modules` 条目为 **0**。当 profile 的解析拦截层被打穿后，`tar -xavf` **抽了全树却救不回来**
> （ctime 指纹 06:43:57–06:44:03 证实抽过）。**能解开 ≠ 能恢复。**
>
> 现在统一走脚本（**含 `node_modules`、含 `_scratch`、随包落链接清单**）：
>
> ```bash
> cd $HARNESS
> tools/backup-dsh.sh                       # → <挂载d>:/dsh-full-<ts>.tar.zst（约 1.8 GiB）
> tools/backup-dsh.sh --verify <归档>       # 校验：流完整性 + 条目数 + node_modules 条目 > 0
> tools/backup-dsh.sh --restore <归档> <目标目录>   # 解包并自动校验链接层
> ```
>
> 随包清单在 `./.dsh-backup-manifest/`：`META`（git HEAD/体量）、`SYMLINKS.tsv`（每条符号链接
> + 当时是否可解析）、`HARDLINKS.tsv`（同 inode 组）、`PROFILE-LINKS.txt`（打包那刻的护栏输出）、
> `PACKAGE-HASHES.txt`（`packages/ ⇄ node_modules/` 哈希，★分叉就是要命的那种）。
> 打包前会先跑链接护栏，**FAIL 的链接层拒绝进包**（`--force` 可越过）。
> 排除的只有 `*/cache/`（搜索索引，可重建且运行中是撕裂快照）——`--with-cache` 可带上。
> **本包含凭据，落盘已 `chmod 600`，别同步到公开位置。**

---

## 六、出事时"我还能干什么"

| 我想做什么 | 不靠 AI 的做法 |
|---|---|
| 看某个工具到底有没有挂上 | `DSH_HOME=$HARNESS/dsh-domus-0.1.7-rc.2 python3 tools/list_tools.py --grep <名字>` |
| 看某次会话里工具调用报了什么错 | `python3 tools/session_tool_audit.py --session <id> --errors-only` |
| 查配置会不会撞 id | `python3 tools/check_patch_layers.py --profile web` |
| 查改配置的代价（会不会卡很久） | `python3 tools/session_index_survey.py` |

---

## 七、四条最容易踩的坑（血泪）

1. **`bin/dsh` 是「环境优先」的**（2026-09-26 已修）—— 调用方的 `DSH_HOME`/`DSH_VERSION` **原样继承**，只有缺身份时才回落到 `dsh-domus-0.1.7-rc.2`。起影子实例前仍建议显式 `export DSH_HOME`，但忘了也不会被踩回默认实例。（旧版是无条件 `export` 覆盖，会让第二个实例去操作第一个实例的 home——这正是当时"分治没做干净"的第 1 处漏点。）
2. **`cordis.patch.yml` 是热加载的** —— 保存即生效，没有"先存盘再挑时间重启"这个缓冲。**编辑它就是一次线上变更。**
3. **profile 里的插件有「两份」，运行时只读 `node_modules/` 那份** —— `profiles/web/packages/<pkg>/`
   与 `profiles/web/node_modules/<pkg>/` 之间是 pnpm 对 `file:` 依赖建的**硬链接**（同 inode 同字节）；
   而插件按**裸包名**挂载，Node 解析走 `node_modules/`。用 **rename 式编辑器**（写临时文件再改名）
   改 `packages/` 那份会**掰断硬链接** → 只有那一份变、`node_modules/` 留在旧字节 →
   **"改了没生效"，且不报任何错、连浏览器缓存都背锅**。（2026-09-27 实测踩过一整个来回。）
   **改完 UI 补丁没反应，先跑这条再怀疑别的**：

   ```bash
   cd $HARNESS
   python3 tools/check-profile-links.py            # FAIL=内容分叉（你改的那份没人读）
   python3 tools/check-profile-links.py --fix      # 只重建"内容相同但 inode 断了"的，绝不碰分叉的
   ```

   `start-web.sh` 启动时已自动跑一遍，有分叉会直接拒绝启动。

4. **profile 的依赖来自「解析拦截层」`<home>/profiles/node_modules`，不是 `profiles/web/node_modules`** ——
   官方 `resolver.ts` 的判据就是 **`<profileParent>/node_modules`**（即 `profiles/node_modules` 这一层，
   在 `profiles/web/` 的**外面**，常规检查容易漏）。那层的链接**大多指向 `/原始代码研究/<版本>/…`**。
   于是：**动那棵树的 `node_modules`（哪怕只是"清理旧档"）＝把这层打穿** → 插件行 import 失败 →
   工具全 `never started` → resume failed → **DSH 直接起不来**。
   *2026-09-27 实测*：清掉 `原始代码研究/v0.1.5-rc.2` 的 node_modules → 276 条断链 → 砖；
   而且 `tar -xavf` 回档也救不回（备份是 **config-only**，node_modules 条目为 0）。

   ```bash
   cd $HARNESS
   python3 tools/check-profile-links.py                # 断链=FAIL；start-web.sh 会因此拒绝启动
   python3 tools/repair-profile-links.py               # 干跑（默认）：看清楚要重连什么
   python3 tools/repair-profile-links.py --apply       # 按包名重连（本版本检出树优先）
   python3 tools/repair-profile-links.py --restore <上一次 --apply 打印的 applied manifest>
   ```

   > **版本切换期**多一条隔离门禁（防两棵树被焊死）：
   > ```bash
   > python3 tools/check-inode-sharing.py --isolate <新 home> <旧版本的检出树>
   > ```

   **★ 断链已由 WARN 升为 FAIL**：当初定成 WARN 的理由是"require 会报 MODULE_NOT_FOUND，会响，
   不是静默"——当天被证伪。响是响了，但响在**你根本进不去界面的地方**，那就是砖。
   （`.bin/` 下的 CLI shim 断链仍是 WARN：只是那条命令用不了，不在模块解析路径上。）
