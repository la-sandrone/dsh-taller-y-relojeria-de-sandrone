#!/usr/bin/env python3
# 文件名: tools/dsh-ui-patches.py
# 摘要: UI 补丁的开机护栏 —— 读 `补丁/*/manifest.toml`，核对上游结构、按需重放并重建。
#
# ── 为什么存在 ──────────────────────────────────────────────────────
#
# 这类补丁改的是【基座检出的源码】⇒ **升级 = 新检出 = 补丁消失**。以前的做法是
# 在文档里写一份「版本升级立即排查清单」，靠人每次照着重打 ——
# 用户的原话：「每次升级一次又要到了打 markdown 和其他 ui 补丁的时间」。
#
# 本工具把那份人工清单变成**数据（manifest）+ 断言（verify）**，交给开机护栏跑。
# 与 `guard_cloudflared` 同构：预存件 + 开机幂等安装；只是"预存件"换成了补丁包。
#
# ── 设计要点（每条都是踩过的坑）─────────────────────────────────────
#
# · **判据是结构，不是行号**：`must_contain` / `must_match` / `must_export` 问的是
#   "上游那个结构还在不在"，不是"第几行"。行号每次上游改动都会假报警。
# · **核对不通过就不打**：宁可这次不渲染，也不打出一个行为错误的补丁
#   （比如把 `/` 引用与 skill chip 的点击弄哑）。
# · **幂等**：`applied_marker` 在文件里 ⇒ 认为补丁在，不重复打。
# · **源码不变就不重建**：bundle 比源码新 ⇒ 跳过 pnpm（省掉开机几秒）。
#
# 用法:
#   python3 tools/dsh-ui-patches.py --checkout <检出目录>             # 只核对（缺省）
#   python3 tools/dsh-ui-patches.py --checkout <检出目录> --apply     # 核对 + 重放 + 按需重建
#   python3 tools/dsh-ui-patches.py --list
#
# 退出码: 0 全部就绪（或已自动补上）/ 1 存在上游漂移（需人工重写补丁）/ 2 环境问题

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
PATCH_ROOT = HARNESS / "补丁"


def load_manifests(root: Path = PATCH_ROOT) -> tuple[list[tuple[Path, dict]], list[str]]:
    """返回 (清单, 读不了的清单及原因)。

    ⚠️ 读不了的必须**单独返回**，不能混进"没有清单"里 ——
       第一版就是把解析失败降级成「（没有 manifest.toml）」+ rc=0，
       于是**一份格式写错的清单等于没有补丁、而护栏默许**。
       那是「静默降级」，本仓库明令要治的病。2026-10-08 自测抓出。
    """
    out: list[tuple[Path, dict]] = []
    broken: list[str] = []
    if not root.is_dir():
        return out, broken
    for manifest in sorted(root.glob("*/manifest.toml")):
        try:
            with manifest.open("rb") as fh:
                out.append((manifest, tomllib.load(fh)))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            broken.append(f"{manifest.parent.name}/manifest.toml：{exc}")
    return out, broken


def verify(root: Path, spec: dict) -> list[str]:
    """跑 [verify] 的三类断言，返回失败说明（空 = 全过）。

    ⚠️ 断言**只读**，不修不写 —— 核对与行事必须分开，否则出错时分不清是谁干的。
    """
    bad: list[str] = []
    for item in spec.get("must_contain", []):
        path = root / item["file"]
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            bad.append(f"读不到 {item['file']}（{exc}）")
            continue
        if item["text"] not in text:
            bad.append(f"{item['file']} 里找不到：{item['text']}")
    for item in spec.get("must_match", []):
        path = root / item["file"]
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            bad.append(f"读不到 {item['file']}（{exc}）")
            continue
        if not re.search(item["regex"], text, re.MULTILINE):
            bad.append(f"{item['file']} 里匹配不上正则：{item['regex']}")
    for item in spec.get("must_export", []):
        path = root / item["file"]
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            bad.append(f"读不到 {item['file']}（{exc}）")
            continue
        if not any("export" in ln and item["name"] in ln for ln in lines):
            bad.append(f"{item['file']} 里没有从 export 行出现 {item['name']}")
    return bad


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def artifact_needs_build(root: Path, build: dict, touched: bool,
                         watch: list[str]) -> tuple[bool, str]:
    """源码变了才重建。touched=True 表示本次刚打过补丁 ⇒ 必须重建。

    `watch` 缺省就是 manifest 里的 target 文件 —— 它们正是会改变产物的东西。
    （不把 watch 写进 manifest：那是**可以由 targets 推出来的**，写两处就会漂。）
    """
    if touched:
        return True, "本次刚应用补丁"
    artifact = root / build["artifact"]
    if not artifact.is_file():
        return True, f"产物不存在：{build['artifact']}"
    newest = 0.0
    for target in build.get("watch", watch):
        path = root / target
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
    if newest and newest > artifact.stat().st_mtime:
        return True, "源码比产物新"
    return False, "产物比源码新"


def handle(manifest: Path, spec: dict, root: Path, apply: bool) -> tuple[str, str]:
    """处理一个补丁。返回 (判定, 说明)。判定 ∈ {ok, applied, drift, error}。"""
    targets = spec.get("target", [])
    name = spec.get("patch", {}).get("name", manifest.parent.name)

    # ① 先核对上游结构 —— 不通过就不动手
    bad = verify(root, spec.get("verify", {}))
    if bad:
        hint = spec.get("on_drift", {}).get("hint", "").strip()
        lines = [f"上游漂移，{len(bad)} 项核对未通过（{name}）："]
        lines += [f"  · {b}" for b in bad]
        if hint:
            lines += ["", hint]
        return "drift", "\n".join(lines)

    # ② 该打就打（幂等：marker 在就不动）
    touched = False
    notes: list[str] = []
    for target in targets:
        path = root / target["file"]
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return "error", f"读不到 {target['file']}（{exc}）"
        if target["applied_marker"] in text:
            notes.append(f"✓ 已在位：{target['file']}")
            continue
        if not apply:
            notes.append(f"· 待应用（缺 marker）：{target['file']}")
            continue
        patch_file = manifest.parent / target["patch"]
        rc, out = run(["git", "apply", "--verbose", str(patch_file)], root)
        if rc != 0:
            return "error", f"git apply 失败（rc={rc}）{target['patch']}：\n{out}"
        touched = True
        notes.append(f"✓ 已应用：{target['patch']} → {target['file']}")

    # ③ 按需重建
    build = spec.get("build", {})
    if build and apply:
        need, why = artifact_needs_build(root, build, touched,
                                         [t["file"] for t in targets])
        if need:
            for cmd in build["run"]:
                rc, out = run(cmd.split(), root)
                if rc != 0:
                    return "error", f"构建失败（rc={rc}）：{cmd}\n{out[-1500:]}"
            notes.append(f"✓ 已重建 {build['artifact']}（{why}）")
        else:
            notes.append(f"· 跳过重建（{why}）")
    elif build:
        notes.append("· 待重建（干跑）")

    verdict = "applied" if touched else "ok"
    return verdict, f"{name}：\n" + "\n".join(f"  {n}" for n in notes)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkout", type=Path, help="基座检出目录（如 原始代码研究/v0.2.0-rc.2）")
    ap.add_argument("--patch-root", type=Path, default=PATCH_ROOT,
                    help=f"补丁清单所在目录（缺省 {PATCH_ROOT.name}）；给测试用，免得往真清单里塞合成件")
    ap.add_argument("--apply", action="store_true", help="真做：重放补丁并按需重建（缺省只核对）")
    ap.add_argument("--list", action="store_true", help="只列出补丁清单")
    args = ap.parse_args()

    patch_root = args.patch_root if args.patch_root.is_absolute() else HARNESS / args.patch_root
    manifests, broken = load_manifests(patch_root)

    if broken:
        print(f"❌ {len(broken)} 份清单读不了 —— **不当作「没有补丁」放行**：", file=sys.stderr)
        for why in broken:
            print(f"   · {why}", file=sys.stderr)
        print("   修好清单再跑（TOML 的 inline table `{...}` 不许跨行是最常见的一处）。",
              file=sys.stderr)
        return 2

    if args.list or not manifests:
        print(f"补丁目录：{patch_root}")
        for manifest, spec in manifests:
            meta = spec.get("patch", {})
            print(f"  · {manifest.parent.name:<16} {meta.get('name','?')}")
            if meta.get("why"):
                print(f"      为什么：{meta['why']}")
        if not manifests:
            print("  （没有 manifest.toml）")
        return 0

    if not args.checkout:
        print("ERR 需要 --checkout", file=sys.stderr)
        return 2
    root = args.checkout if args.checkout.is_absolute() else HARNESS / args.checkout
    if not root.is_dir():
        print(f"ERR 检出目录不存在：{root}", file=sys.stderr)
        return 2

    print(f"检出：{root}")
    print(f"模式：{'应用（重放 + 按需重建）' if args.apply else '只核对（干跑）'}")
    verdicts: list[str] = []
    for manifest, spec in manifests:
        verdict, detail = handle(manifest, spec, root, args.apply)
        verdicts.append(verdict)
        mark = {"ok": "✅", "applied": "🔧", "drift": "❌", "error": "⚠"}[verdict]
        print()
        print(f"{mark} {detail}")

    if "error" in verdicts:
        return 2
    if "drift" in verdicts:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
