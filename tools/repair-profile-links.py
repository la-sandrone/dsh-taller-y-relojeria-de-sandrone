#!/usr/bin/env python3
"""把某个 DSH home 的**解析拦截层**对齐到指定的基座检出树（修复 + 从零构建）。

## 这一层是什么

    "The interception layer of a profile is `<profileParent>/node_modules`"
    —— 原始代码研究/<ver>/packages/boot/app-boot/src/profile-resolution/resolver.ts

即 `<home>/profiles/node_modules`。它是一批**符号链接**，把 profile 的模块解析劫持到
基座检出的安装树。**删掉它 = DSH 直接砖**（2026-09-27 实测：276 条断链 → 工具全 never started）。

## 本工具做两件同一件事

| 场景 | 层现状 | 动作 |
|---|---|---|
| **修复** | 已在，但有断链 / 指错树 | 重连（旧版能力，全部保留） |
| **构建** | **根本不存在**（新版本 home） | 从零建 |

判据是同一个：**每条链接都应指向 `--source-checkout`（或留在 home 内）**。

## ★ 隔离铁律（用户 2026-10-08 定调）

**跨版本迁移时绝不复制上一个版本 home 的链接。** 复制 = 把两个版本焊死在同一棵
被 edit/build 的树上 —— 正是 09-27 变砖的同类。必须**按包名在【本版本】检出树里重新解析**。

验完跑门禁（`--gate --gate-against <上一版本的树>`）：
`tools/check-inode-sharing.py` 的判据是——**包字节**（`node_modules/` 内、内容寻址）
共享**是预期的**；**路径寻址的符号链接越界**才要断。

## 需求清单从哪来（`--names-from`）

层不存在时无从知道"该有哪些包名"。取自上一版本 home 的层（那份清单是**实测证明
DSH 需要**的），再逐名在**本版本**检出树里重新解析。解析不到的**明确列出**，不静默跳过。

## ⚠️ 顺序约束（工具自己会证明）

若 `--source-checkout` 还没 `pnpm install`，`apps/cli/node_modules`／根 `node_modules`／
`.pnpm` 都不存在，只有 `packages/**` 可解析 → 绝大多数名字会落进「无法解析」。
这不是 bug，是在提醒：**build 与 install 必须在前。**

用法
----
    # ① 原用途（修现役 0.1.7 的断链）—— 不带任何新参数，行为与旧版一致
    python3 tools/repair-profile-links.py
    python3 tools/repair-profile-links.py --apply

    # ② 新用途：给 0.2.0 建层
    python3 tools/repair-profile-links.py \
        --home dsh-domus-0.2.0-rc.2 \
        --source-checkout 原始代码研究/v0.2.0-rc.2 \
        --names-from dsh-domus-0.1.7-rc.2 \
        --apply --gate --gate-against 原始代码研究/v0.1.7-rc.2

    python3 tools/repair-profile-links.py --restore <manifest.json>

退出码: 0 正常 / 1 有无法解析项（干跑也返回，便于当门禁）/ 2 用法或环境错误
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

# 根目录解析（可移植）：环境变量优先（启动器会给子进程注入 DSH_HARNESS_DIR）
# → 否则由本脚本位置推导（tools/ 的上一级）→ 推不出就报错，不猜一个可能错的根。
def _resolve_harness() -> Path:
    env = os.environ.get("DSH_HARNESS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    guess = Path(__file__).resolve().parents[1]
    if (guess / "tools").is_dir() and (guess / "start-web.py").is_file():
        return guess
    sys.exit(f"找不到 harness 根：设 DSH_HARNESS_DIR，或把本脚本放在 <harness>/tools/ 下"
             f"（当前推导：{guess}）")


HARNESS = _resolve_harness()
# 草稿区名可被 DSH_SCRATCH_DIR 覆盖（发布件里的默认值由导出管线改成中性名）
SCRATCH = HARNESS / os.environ.get("DSH_SCRATCH_DIR", ".dsh-scratch")

DEFAULT_HOME = "dsh-domus-0.1.7-rc.2"
DEFAULT_SOURCE = "原始代码研究/v0.1.7-rc.2"

SKIP_TOP = {".bin", ".pnpm", ".cache", ".modules.yaml"}


def die(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def rp(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else HARNESS / q


def is_within(path: Path | str, root: Path) -> bool:
    try:
        Path(path).relative_to(root)
        return True
    except ValueError:
        return False


# ══════════════════════ 索引：从检出树解析包名 ══════════════════════

def index_dir(mod: Path) -> dict[str, str]:
    """一个 node_modules 目录的 name -> path（浅扫 + scoped 一层）。"""
    out: dict[str, str] = {}
    if not mod.is_dir():
        return out
    for entry in sorted(mod.iterdir()):
        name = entry.name
        if name.startswith(".") or name == "@types":
            continue
        if name.startswith("@"):
            if not entry.is_dir():
                continue
            for sub in sorted(entry.iterdir()):
                if (sub / "package.json").exists():
                    out.setdefault(f"{name}/{sub.name}", str(sub))
        elif (entry / "package.json").exists():
            out.setdefault(name, str(entry))
    return out


def pkg_name_of(path: Path) -> str | None:
    try:
        name = json.loads((path / "package.json").read_text(encoding="utf-8")).get("name")
    except Exception:
        return None
    return name if isinstance(name, str) else None


def workspace_patterns(checkout: Path) -> list[str]:
    """读 `pnpm-workspace.yaml` 的 `packages:` 列表。

    ⚠️ 不硬编码 `packages/*/*`——那会漏掉 `vendor/*`（`@deepseek-ai/cordis`、
    `schemastery`、`cordis-plugin-*` 全在 vendor 下，实测漏掉 9 个名字）、
    `native/system/packages/*`、`apps/*` 等。工作区声明才是唯一真相源。

    刻意**不引入 YAML 依赖**：本工具是停机卡点名的应急工具，要求离线可用；
    pnpm-workspace.yaml 的 `packages:` 是纯字符串列表，定点解析足够且更稳。
    """
    ws = checkout / "pnpm-workspace.yaml"
    pats: list[str] = []
    if ws.is_file():
        in_block = False
        for raw in ws.read_text(encoding="utf-8").splitlines():
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            if not line.startswith((" ", "\t", "-")):        # 顶格 = 另一个键
                in_block = line.split(":", 1)[0].strip() == "packages"
                continue
            if in_block and line.lstrip().startswith("- "):
                val = line.lstrip()[2:].strip().strip("'\"")
                if val:
                    pats.append(val)
    return pats or ["packages/*/*"]


def index_workspace(checkout: Path) -> dict[str, str]:
    """按工作区声明解析所有工作区包（含 vendor / native / apps）。"""
    out: dict[str, str] = {}
    for pat in workspace_patterns(checkout):
        for d in sorted(checkout.glob(pat)):
            mf = d / "package.json"
            if not mf.is_file():
                continue
            name = pkg_name_of(d)
            if name:
                out.setdefault(name, str(d))
    return out


def decode_pnpm(dirname: str) -> tuple[str | None, str | None]:
    idx = dirname.find("@", 1)
    if idx <= 0:
        return None, None
    return dirname[:idx].replace("+", "/"), dirname[idx + 1:]


def ver_key(ver: str):
    nums = re.findall(r"\d+", ver)
    return tuple(int(n) for n in nums[:6]) if nums else (0,)


def index_pnpm(checkout: Path) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    store = checkout / "node_modules" / ".pnpm"
    if not store.is_dir():
        return out
    for d in sorted(store.iterdir()):
        if not d.is_dir():
            continue
        name, ver = decode_pnpm(d.name)
        if not name:
            continue
        cand = d / "node_modules" / name
        if not (cand / "package.json").exists():
            continue
        prev = out.get(name)
        if prev is None or ver_key(ver or "") > ver_key(prev[1]):
            out[name] = (str(cand), ver or "?")
    return out


def build_source_index(checkout: Path) -> dict[str, tuple[str, str]]:
    """name -> (path, 来源标签)。先到先得，顺序 = 解析优先级。"""
    idx: dict[str, tuple[str, str]] = {}
    tables = [
        ("app", {n: p for app in ("cli", "web", "desktop", "desktop-host")
                 if (n := pkg_name_of(checkout / "apps" / app)) and (p := str(checkout / "apps" / app))}),
        ("workspace", index_workspace(checkout)),
        ("apps/cli", index_dir(checkout / "apps" / "cli" / "node_modules")),
        ("root", index_dir(checkout / "node_modules")),
        ("pnpm", {k: v[0] for k, v in index_pnpm(checkout).items()}),
    ]
    for label, table in tables:
        for name, path in table.items():
            idx.setdefault(name, (path, label))
    return idx


# ══════════════════════ 层的扫描（多层，保留旧行为） ══════════════════════

def scan_layers(home: Path, layer_override: Path | None) -> list[Path]:
    if layer_override is not None:
        return [layer_override]
    return [home / "profiles" / "node_modules", home / "profiles" / "web" / "node_modules"]


def iter_entries(mod: Path):
    """yield (名字, 路径)，depth 1 + scoped 一层。"""
    if not mod.is_dir():
        return
    for entry in sorted(mod.iterdir()):
        name = entry.name
        if name in SKIP_TOP:
            continue
        if name.startswith("@") and entry.is_dir():
            for sub in sorted(entry.iterdir()):
                yield f"{name}/{sub.name}", sub
        else:
            yield name, entry


def link_names(mod: Path) -> set[str]:
    return {name for name, p in iter_entries(mod) if p.is_symlink()}


def collect_external(layer: Path, home: Path, source: Path) -> list[tuple[str, Path, str]]:
    """解析成功、但真身既不在 home 也不在 source 内的链接（旧版 WARN 类，保留）。"""
    out = []
    for name, path in iter_entries(layer):
        if not path.is_symlink() or not path.exists():
            continue
        real = os.path.realpath(path)
        if is_within(real, home) or is_within(real, source):
            continue
        out.append((name, path, real))
    return out


def fix_bin(mod: Path) -> tuple[list[tuple[Path, str]], list[str]]:
    """尽力修 .bin 下断掉的 shim（同目录按相对路径找）。旧版能力，保留。"""
    fixes: list[tuple[Path, str]] = []
    notes: list[str] = []
    bindir = mod / ".bin"
    if not bindir.is_dir():
        return [], []
    for shim in sorted(bindir.iterdir()):
        if not shim.is_symlink() or shim.exists():
            continue
        target = os.readlink(shim)
        parts = target.lstrip("./").split("/")
        if parts[:1] == [".."]:
            parts = parts[1:]
        if not parts:
            continue
        pkg = f"{parts[0]}/{parts[1]}" if parts[0].startswith("@") and len(parts) > 1 else parts[0]
        pkg_dir = mod / pkg
        mf = pkg_dir / "package.json"
        if not mf.exists():
            notes.append(f"  .bin/{shim.name}: 宿主包 {pkg} 不在本 node_modules，跳过")
            continue
        try:
            binfield = json.loads(mf.read_text(encoding="utf-8")).get("bin")
        except Exception:
            notes.append(f"  .bin/{shim.name}: {pkg} package.json 不可读，跳过")
            continue
        rel = binfield if isinstance(binfield, str) else (binfield or {}).get(shim.name)
        if not rel:
            notes.append(f"  .bin/{shim.name}: {pkg} 未声明同名 bin，跳过")
            continue
        real_file = pkg_dir / rel
        if not real_file.exists():
            notes.append(f"  .bin/{shim.name}: 声明的 {rel} 不存在，跳过")
            continue
        new_rel = os.path.relpath(real_file, bindir)
        if new_rel != target:
            fixes.append((shim, new_rel))
    return fixes, notes


# ══════════════════════ 写入 ══════════════════════

def atomic_symlink(target: str, link: Path) -> None:
    """原子替换：先建 tmp 再 os.replace（停机卡同款，避免读到半个链接）。"""
    tmp = link.with_name(link.name + ".relink-tmp")
    if tmp.exists() or tmp.is_symlink():
        tmp.unlink()
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, tmp)
    os.replace(tmp, link)


# ══════════════════════ 主流程 ══════════════════════

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore", metavar="MANIFEST")
    ap.add_argument("--show", type=int, default=8)
    ap.add_argument("--home", default=DEFAULT_HOME, help=f"目标 home（默认 {DEFAULT_HOME}）")
    ap.add_argument("--source-checkout", default=DEFAULT_SOURCE,
                    help=f"要指向的基座检出（默认 {DEFAULT_SOURCE}）")
    ap.add_argument("--names-from", action="append", default=[],
                    help="需求清单来源 home（可多次）；层不存在时必需")
    ap.add_argument("--layer", default=None, help="只处理这一层目录（默认两层都扫）")
    ap.add_argument("--no-external", action="store_true",
                    help="不动「解析成功但指向外部树」的链接（旧版开关，保留）")
    ap.add_argument("--no-bin", action="store_true", help="不动 .bin shim")
    ap.add_argument("--gate", action="store_true", help="--apply 后跑隔离门禁")
    ap.add_argument("--gate-against", default=None, help="门禁对照树（上一个版本的树）")
    args = ap.parse_args()

    # ── 回滚 ──
    if args.restore:
        man = json.loads(Path(args.restore).read_text(encoding="utf-8"))
        n = 0
        for item in man.get("mappings", []):
            link = Path(item["link"])
            if item.get("old_target") is None:
                if link.is_symlink():
                    link.unlink()
                continue
            atomic_symlink(item["old_target"], link)
            n += 1
        print(f"已按 manifest 回滚 {n} 条链接（本就缺失的已删除）")
        return

    home = rp(args.home)
    source = rp(args.source_checkout)
    layer_override = rp(args.layer) if args.layer else None
    if not home.is_dir():
        die(f"❌ home 不存在: {home}")
    if not source.is_dir():
        die(f"❌ 检出不存在: {source}")

    idx = build_source_index(source)
    print(f"源检出: {source.name}")
    print("  可解析包名 "
          f"{len(idx)} 个：" + ", ".join(f"{k}={v}" for k, v in sorted(Counter(l for _, l in idx.values()).items())))
    if not (source / "node_modules").is_dir():
        print("  ⚠️ 该检出**没有 node_modules** —— 只有 packages/** 工作区包可解析。")
        print("     通常表示 build/install 还没做；先做，否则大量包名会落进「无法解析」。")

    layers = scan_layers(home, layer_override)
    primary = layers[0] if layer_override is None else layer_override

    # ── 需求清单：目标层现有名 + --names-from ──
    required: set[str] = set()
    for lay in layers:
        got = link_names(lay)
        required |= got
        # 仓外路径（如 --layer /tmp/...）不能 relative_to，退回绝对路径
        try:
            shown = lay.relative_to(HARNESS)
        except ValueError:
            shown = lay
        print(f"  需求清单 ← 目标层 {shown}: {len(got)} 个名字")
    for src in args.names_from:
        sh = rp(src)
        got = link_names(sh / "profiles" / "node_modules")
        required |= got
        print(f"  需求清单 ← {sh.name} 的层: 贡献 {len(got)} 个名字")
    print(f"\n需求清单合计 {len(required)} 个包名")

    # ── 逐名分类 ──
    to_create, to_repair, ok, unresolved = [], [], [], []
    for name in sorted(required):
        link = primary / name
        exists = link.is_symlink()
        real = os.path.realpath(link) if exists else None
        # 「好」= 解析进本检出 或 留在 home 内（与旧版 {HOME, CO17} 口径一致）
        good = bool(exists and link.exists() and real and (is_within(real, source) or is_within(real, home)))
        if good:
            ok.append(name)
            continue
        want = idx.get(name)
        if want is None:
            unresolved.append((name, os.readlink(link) if exists else None))
            continue
        rec = {"name": name, "link": str(link),
               "old_target": os.readlink(link) if exists else None,
               "new_target": want[0], "kind": want[1]}
        (to_repair if exists else to_create).append(rec)

    print(f"\n  ✅ 已正确：{len(ok)}")
    print(f"  🔧 需重连（断链/指错树）：{len(to_repair)}")
    print(f"  ➕ 需新建（层里没有）：{len(to_create)}")
    print(f"  ❓ 无法在源检出解析：{len(unresolved)}")

    for label, rows in (("重连", to_repair), ("新建", to_create)):
        for r in rows[: args.show]:
            print(f"     [{label}][{r['kind']}] {r['name']}")
            print(f"        {r['old_target'] or '（原本不存在）'}")
            print(f"     -> {r['new_target']}")
        if len(rows) > args.show:
            print(f"     …还有 {len(rows) - args.show} 条")
    if unresolved:
        print("\n  ❓ 无法解析（上游可能改名/移除，需人工判定；**不静默跳过**）：")
        for name, old in unresolved[: max(args.show, 10)]:
            print(f"     {name}   （旧指向: {old or '（无）'}）")
        if len(unresolved) > max(args.show, 10):
            print(f"     …还有 {len(unresolved) - max(args.show, 10)} 条")

    # ── 外部指向（旧版 WARN 类）──
    external = []
    if not args.no_external:
        for lay in layers:
            external += collect_external(lay, home, source)
        if external:
            print(f"\n  ⚠️ 解析成功但指向外部树：{len(external)} 条（已按 --source-checkout 重指）")
            for name, link, real in external[: args.show]:
                print(f"     {name} → {real}")

    mappings = to_repair + to_create + [
        {"name": n, "link": str(l), "old_target": os.readlink(l), "new_target": idx[n][0],
         "kind": idx[n][1], "external_before": r}
        for n, l, r in external if n in idx
    ]

    bin_fixes, bin_notes = [], []
    if not args.no_bin:
        for lay in layers:
            f, notes = fix_bin(lay)
            bin_fixes += f
            bin_notes += notes

    stamp = time.strftime("%Y%m%d-%H%M%S")
    manifest = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "home": str(home), "source_checkout": str(source), "layers": [str(l) for l in layers],
        "mappings": mappings,
        "unresolved": [{"name": n, "old_target": o} for n, o in unresolved],
        "bin_fixes": [{"shim": str(s), "new_target": t} for s, t in bin_fixes],
    }
    man_path = SCRATCH / f"profile-links-repair-{home.name}-{stamp}.json"
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nmanifest: {man_path}")

    if not args.apply:
        print("（干跑模式：未改动。加 --apply 应用。）")
        return 1 if unresolved else 0

    done = 0
    for m in mappings:
        atomic_symlink(m["new_target"], Path(m["link"]))
        done += 1
    for shim, new_rel in bin_fixes:
        atomic_symlink(new_rel, shim)
        done += 1
    applied = SCRATCH / f"profile-links-repair-applied-{home.name}-{stamp}.json"
    applied.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✅ 已写入 {done} 条（链接 {len(mappings)} + .bin {len(bin_fixes)}）")
    if bin_notes:
        print(".bin 提示：")
        for n in bin_notes[: args.show]:
            print(n)
    print(f"回滚用: python3 tools/repair-profile-links.py --restore {applied}")

    # ── 复验 ──
    still = [n for n in sorted(required)
             if (primary / n).is_symlink() and (primary / n).exists()
             and not (is_within(os.path.realpath(primary / n), source)
                      or is_within(os.path.realpath(primary / n), home))]
    print(f"复验：层内既不指向本检出也不指向 home 的链接 = {len(still)}"
          f"{' —— ' + ', '.join(still[:5]) if still else ' ✅'}")

    if args.gate:
        if not args.gate_against:
            print("\n⚠️ --gate 需要 --gate-against <上一个版本的树>；本次跳过")
        else:
            print(f"\n{'─' * 62}\n隔离门禁\n{'─' * 62}")
            rc = subprocess.run(
                [sys.executable, str(HARNESS / "tools" / "check-inode-sharing.py"),
                 "--isolate", str(home), str(rp(args.gate_against))],
                cwd=str(HARNESS)).returncode
            print(f"门禁退出码 = {rc}" + ("  ✅ 隔离干净" if rc == 0 else "  ❌ 有越界"))

    if unresolved:
        print(f"\n⚠️ 仍有 {len(unresolved)} 个包名无法解析 —— 先确认 build/install 已做完")


if __name__ == "__main__":
    main()
