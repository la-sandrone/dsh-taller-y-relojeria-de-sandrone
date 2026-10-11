#!/usr/bin/env python3
# 文件名: check-profile-links.py
# 摘要: profile 链接护栏 —— 检查 <home>/profiles 下两类"看着正常其实在骗人"的链接。
#        ① 硬链接分叉：packages/<pkg>/ 与 node_modules/<pkg>/ 本是同一份字节（pnpm 的
#           "file:" 依赖装法）。一旦被 rename 式写入掰断，就变成"你改了 A、运行时读 B"。
#           2026-09-27 实测踩过：撤销标题居中后界面纹丝不动，改的正是不被读的那一份。
#        ② 符号链接：指**别的版本检出**（那棵树一删就全断）或已经断了。
#           <profiles>/node_modules 这一层在 Node 的向上解析路径上，容易被忽略。
# 依赖: python3 (标准库)
#
# 用法
# ----
#   python3 tools/check-profile-links.py                 # home 按 DSH_VERSION 派生
#   python3 tools/check-profile-links.py --home <dir>
#   python3 tools/check-profile-links.py --profile web
#   python3 tools/check-profile-links.py --strict        # WARN 也返回 1
#   python3 tools/check-profile-links.py --fix           # 只重建"内容相同但 inode 不同"的硬链接
#   python3 tools/check-profile-links.py --show 30       # 每组最多列几条（默认 10）
#
# 退出码: 0 = 无 FAIL（WARN 不影响，除非 --strict）／1 = 有 FAIL（或 --strict 下有 WARN）／2 = 用法/环境错误
#
# 两级严重度
# ----------
#   FAIL = 会让 DSH 起不来，或在你不知情时给你**错的**东西
#          · packages/ 与 node_modules/ 同一相对路径**内容不同** → Node 读的是 node_modules
#            那份，你改的那份没人看 —— 不报错、不警告，只是行为不变。
#          · **断链**（.bin/ 下的 CLI shim 除外）→ 插件行 import 失败 →
#            工具全 `never started` → resume failed → DSH 起不来。
#   WARN = 会响、会断，但看得见，且当前不影响启动
#          · 硬链接断了但内容还一致（下一刀才会静默分叉）
#          · node_modules 缺文件 / 该位置是 symlink 而非硬链接
#          · 符号链接指向 <home> 与【现役检出】之外的树（此刻还能用，但那棵树一删就变断链）
#          · .bin/ 下的断链（只是那条命令用不了，不在模块解析路径上）
#
# ★ 2026-09-27 修正：断链**原本被我定为 WARN**，理由是"require 会报 MODULE_NOT_FOUND，
#   会响，不是静默"。当天现实把它证伪了 —— `原始代码研究/v0.1.5-rc.2` 的 node_modules
#   被清掉后，本解析拦截层 276 条链接成断链，DSH 直接砖（工具全 never started）。
#   "响"响在你根本进不去界面的地方，那就是砖，不是"看得见的错"。故升为 FAIL。
#   注意：**指向外部树（目标尚在）仍保持 WARN** —— 那种状态下系统是能正常跑的
#   （实测跑了一整天），拦启动会把可用系统挡在门外。识别它的意义在于"删那棵树之前先看这条"。
#
# 判据来源（为什么硬链接是"权威"的）
# ---------------------------------
#   <profile>/package.json 里写的是  "dsh-xxx": "file:packages/dsh-xxx"
#   pnpm 对 file: 依赖建的是**硬链接**，于是 packages/ 与 node_modules/ 同 inode 同字节。
#   而插件按**裸包名**挂载 → Node 解析走 node_modules/。

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

# ⚠️ 默认值可移植：环境变量优先 → 本脚本位置推导（tools/ 的上一级）→ 都失败才退回 CWD。
#    （--harness 显式覆盖永远优先。）
def _default_harness() -> Path:
    env = os.environ.get("DSH_HARNESS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    guess = Path(__file__).resolve().parents[1]
    return guess if (guess / "tools").is_dir() else Path.cwd()


HARNESS_DEFAULT = _default_harness()
SKIP_DIRS = {"node_modules", ".git", ".pnpm", "__pycache__", ".cache"}
SYMLINK_SCAN_DEPTH = 2  # node_modules/<pkg> 与 node_modules/@scope/<pkg>
SAMPLE_LIMIT = 4


def die_usage(msg: str) -> None:
    # 注意：sys.exit("字符串") 的退出码是 **1**，不是 2 —— 想把"用法/环境错误"
    # 与"发现 FAIL"分开，就必须显式给码。这条是本脚本负向测试抓出来的。
    print(msg, file=sys.stderr)
    sys.exit(2)


def read_version(harness: Path) -> str | None:
    """当前生效版本 —— 取自 `启动器配置和日志/当前配置.toml`（元数据的**唯一真相源**）。

    2026-10-08 起不再读仓库根的 `DSH_VERSION`：那个文件是「全局单版本」时代的产物，
    随启动器移植退役。它既表达不了多实例，又会误导 —— 第二个实例会把第一个实例的
    检出当成自己的（`dsh-force-h1.mjs` 与 `bin/dsh` 都踩过这个坑）。

    ⚠️ 刻意**不**回落读环境变量 `DSH_VERSION`：本脚本要检查哪个 home 由调用方
       用 `--home` 明说；版本只用来推「默认 home 名」。若这里吃环境变量，
       从另一个实例里跑本脚本就会去检查错的 home —— 正是上面那个坑的翻版。
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import dsh_config
        return dsh_config.load_config(harness).version
    except Exception:
        return None


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_package_files(pkg_dir: Path):
    for root, dirs, files in os.walk(pkg_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            full = Path(root) / name
            if full.is_symlink():
                continue
            yield full.relative_to(pkg_dir)


class Report:
    def __init__(self) -> None:
        self.fail: list[str] = []
        self.warn: list[str] = []
        self.ok_files = 0
        self.repaired: list[str] = []

    def fail_(self, msg: str) -> None:
        self.fail.append(msg)

    def warn_(self, msg: str) -> None:
        self.warn.append(msg)


def print_group(title: str, items: list[str], marker: str, show: int) -> None:
    if not items:
        return
    print(f"\n  {marker} {title}（{len(items)}）")
    for line in items[:show]:
        print(f"      {line}")
    if len(items) > show:
        print(f"      …还有 {len(items) - show} 条（--show 0 显示全部）")


# ── ① 硬链接一致性 ───────────────────────────────────────────────
def check_hardlinks(profile: Path, rep: Report, fix: bool) -> None:
    pkgs_dir = profile / "packages"
    nm_dir = profile / "node_modules"
    if not pkgs_dir.is_dir():
        print(f"\n── {profile.name}：packages/ 不存在，跳过硬链接检查")
        return
    print(f"\n── {profile.name}：硬链接一致性（packages/ ⇄ node_modules/）")

    for pkg in sorted(p for p in pkgs_dir.iterdir() if p.is_dir()):
        dst_root = nm_dir / pkg.name
        if not dst_root.exists():
            rep.warn_(f"{pkg.name}：node_modules 里没有（既没装也没挂载，声明可能已过期）")
            continue
        for rel in iter_package_files(pkg):
            src, dst = pkg / rel, dst_root / rel
            label = f"{pkg.name}/{rel}"
            if not dst.exists():
                rep.warn_(f"{label}：node_modules 里缺这个文件")
                continue
            if dst.is_symlink():
                rep.warn_(f"{label}：node_modules 侧是符号链接，不是硬链接")
                continue
            try:
                s, d = src.stat(), dst.stat()
            except OSError as exc:
                rep.warn_(f"{label}：stat 失败 {exc}")
                continue
            if (s.st_dev, s.st_ino) == (d.st_dev, d.st_ino):
                rep.ok_files += 1
                continue
            if s.st_size != d.st_size or sha256_of(src) != sha256_of(dst):
                rep.fail_(
                    f"{label}：★内容分叉★ packages={s.st_size}B(inode {s.st_ino}) "
                    f"｜ node_modules={d.st_size}B(inode {d.st_ino}) —— 运行时读 node_modules 那份"
                )
                continue
            if fix:
                try:
                    dst.unlink()
                    os.link(src, dst)
                    rep.repaired.append(label)
                except OSError as exc:
                    rep.fail_(f"{label}：重建硬链接失败 {exc}")
                continue
            rep.warn_(f"{label}：硬链接已断（内容还一致，下一刀就静默分叉）—— 修：ln -f {src} {dst}")

    print(f"      ✓ 同 inode 一致：{rep.ok_files} 个文件")


# ── ② 符号链接指向 ───────────────────────────────────────────────
def scan_symlinks(nm_dir: Path, label: str, home: Path, live_checkout: Path, rep: Report) -> None:
    if not nm_dir.is_dir():
        return
    print(f"\n── {label}：符号链接指向")

    dangling: list[str] = []
    foreign: dict[str, list[str]] = {}

    def scan(entry: Path, depth: int) -> None:
        if depth > SYMLINK_SCAN_DEPTH:
            return
        try:
            children = list(os.scandir(entry))
        except OSError:
            return
        for child in children:
            p = Path(child.path)
            if child.is_symlink():
                target = os.readlink(p)
                resolved = Path(os.path.normpath(
                    (p.parent / target) if not os.path.isabs(target) else Path(target)))
                rel = p.relative_to(nm_dir)
                if not resolved.exists():
                    dangling.append(f"{rel} → {target}")
                    continue
                real = resolved.resolve()
                if _is_under(real, home) or _is_under(real, live_checkout):
                    continue
                foreign.setdefault(_group_of(real, live_checkout), []).append(f"{rel} → {target}")
                continue
            if child.is_dir(follow_symlinks=False):
                scan(p, depth + 1)

    scan(nm_dir, 0)

    # 断链 = FAIL（除非是 .bin 的 CLI shim）。判据在 2026-09-27 被现实改写了一次：
    # 原以为"断链会让 require 报 MODULE_NOT_FOUND，会响，不是静默"，故定为 WARN；
    # 实测是本 profile 的解析拦截层被打穿 → 插件行 import 失败 → 工具全 never started
    # → resume failed → **DSH 直接起不来**。"响"响在你进不去界面的地方，那就是砖。
    for item in dangling:
        if _is_bin_shim(item):
            rep.warn_(f"断链（.bin CLI shim，不拦启动）：{item}")
        else:
            rep.fail_(
                f"断链：{item} —— 插件解析会失败（never started）"
                f"；修：python3 tools/repair-profile-links.py --apply"
            )

    if not dangling and not foreign:
        print("      ✓ 无断链、无指向外部的链接")
        return

    for group, items in sorted(foreign.items(), key=lambda kv: -len(kv[1])):
        rep.warn_(f"{label}：{len(items)} 个链接指向外部树 {group}（那棵树一删/改名就全断）")
        print(f"      ! 指向外部树 {group} —— {len(items)} 个（那棵树一删/改名就全断）")
        for s in items[:SAMPLE_LIMIT]:
            print(f"          {s}")
        if len(items) > SAMPLE_LIMIT:
            print(f"          …还有 {len(items) - SAMPLE_LIMIT} 个（--show 0 显示全部）")
    if dangling:
        shims = sum(1 for d in dangling if _is_bin_shim(d))
        print(f"      ✗ 断链 {len(dangling)} 个（FAIL {len(dangling) - shims}，.bin shim {shims}）")


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _is_bin_shim(rel_display: str) -> bool:
    # 传进来的是 "相对路径 → 目标" 这种展示串，取箭头前那段。
    # .bin/ 下是 pnpm 建的 CLI shim，断了只是那条命令用不了，不在模块解析路径上。
    return rel_display.split(" → ", 1)[0].startswith(".bin/")


def _group_of(real: Path, live_checkout: Path) -> str:
    # 只取顶层那一段：按整包切会碎成几百组各 1 个，没法读。
    # 我们要回答的是"它指的是哪棵树"，不是"具体哪个包"。
    for base, tag in ((live_checkout.parent, "原始代码研究/"), (Path("/mnt/d"), "<挂载d>:/")):
        try:
            return tag + real.relative_to(base.resolve()).parts[0]
        except (ValueError, IndexError):
            continue
    return str(real.parent)


def main() -> int:
    ap = argparse.ArgumentParser(description="profile 硬链接 / 符号链接护栏")
    ap.add_argument("--home", type=Path, default=None, help="DSH_HOME（默认按 DSH_VERSION 派生）")
    ap.add_argument("--harness", type=Path, default=HARNESS_DEFAULT, help="harness 根目录")
    ap.add_argument("--profile", default=None, help="只查这个 profile")
    ap.add_argument("--strict", action="store_true", help="WARN 也返回 1")
    ap.add_argument("--fix", action="store_true", help="只重建「内容相同但 inode 不同」的硬链接")
    ap.add_argument("--show", type=int, default=10, help="每类最多列几条（0=全部）")
    args = ap.parse_args()

    version = read_version(args.harness)
    home = args.home or (args.harness / f"dsh-domus-{version.lstrip('v')}" if version else None)
    if home is None:
        die_usage(f"❌ 读不到 {args.harness / '启动器配置和日志/当前配置.toml'}"
                  "，用 --home 显式指定")
    if not home.is_dir():
        die_usage(f"❌ home 不存在：{home}")

    profiles_root = home / "profiles"
    if not profiles_root.is_dir():
        die_usage(f"❌ {profiles_root} 不存在")

    live_checkout = args.harness / "原始代码研究" / version if version else Path("/nonexistent")
    print(f"DSH_HOME   = {home}")
    print(f"现役检出   = {live_checkout}")
    print(f"profile 根 = {profiles_root}")

    show = args.show if args.show > 0 else 10 ** 9
    profiles = sorted(p for p in profiles_root.iterdir() if p.is_dir() and (p / "package.json").is_file())
    if args.profile:
        profiles = [p for p in profiles if p.name == args.profile]
        if not profiles:
            die_usage(f"❌ 没有名为 {args.profile} 的 profile（有："
                     f"{', '.join(sorted(p.name for p in profiles_root.iterdir() if p.is_dir()))}）")

    rep = Report()
    for profile in profiles:
        check_hardlinks(profile, rep, args.fix)
    for profile in profiles:
        scan_symlinks(profile / "node_modules", f"{profile.name}/node_modules", home, live_checkout, rep)
    # 父级 node_modules 在 Node 的向上解析路径上，最容易漏
    scan_symlinks(profiles_root / "node_modules", "profiles/node_modules（父级，在解析路径上）",
                  home, live_checkout, rep)

    print("\n" + "=" * 74)
    if rep.repaired:
        print(f"本次重建的硬链接：{len(rep.repaired)} 个")
        for label in rep.repaired[:show]:
            print(f"      ln -f 重建：{label}")
    print_group("FAIL —— 会在你不知情时给你错的字节", rep.fail, "✗", show)
    print_group("WARN —— 会响/会断，但看得见", rep.warn, "!", show)

    if rep.fail:
        print(f"\n结论：{len(rep.fail)} 项 FAIL —— 修完再启动")
        return 1
    if rep.warn and args.strict:
        print(f"\n结论：{len(rep.warn)} 项 WARN（--strict 下视为失败）")
        return 1
    if rep.warn:
        print(f"\n结论：无 FAIL；{len(rep.warn)} 项 WARN（当前不影响正确性，都是隐患）")
        return 0
    print("\n结论：干净")
    return 0


if __name__ == "__main__":
    sys.exit(main())
