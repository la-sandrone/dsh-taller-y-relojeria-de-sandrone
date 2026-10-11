#!/usr/bin/env python3
"""启动前预检：找出会让插件树加载失败的"重复 entry id"。

为什么需要它（2026-09-12 两次事故的根因）：
  插件树里 entry id 全局唯一。`insert:` 是**新增**行，若某 id 已被更早的层
  定义过，loader 的 EntryGroup.update 会抛：
      TypeError: duplicate loader entry id: <id>
  典型撞法：profile 级与 home 级两份配置**内容相同**（复制/硬链接而来），
  于是同一批 MCP id 被定义两次 → 启动直接崩；
  若发生在**热加载**路径，异常不出现在启动输出里 → 表现为
  "没有预警 + sessionController is unavailable 无限刷 + 前台假死"。

  注意：`--dump-config` **不能**替代本脚本——它只组合并打印，不建 EntryGroup，
  抓不到这个重复。

扫描顺序 = 真实叠加顺序：各 bundle 层 → profile 用户层 → home 用户层。
规则：维护"已定义 id 集合"；
  · 每层的顶层 `- id: X` 行 → X 进入集合
  · 每层的 `insert:` 列表 → 其中每个 row 的 id 若已在集合里 → 💥 冲突
  · group 行（group: true + config 是列表）递归处理

用法：
  python3 tools/check_patch_layers.py                      # 检查本机全部 profile
  python3 tools/check_patch_layers.py --profile web
  python3 tools/check_patch_layers.py --extra /path/to/cordis.patch.yml
        # 把某个候选文件当作 home 级层加进来试算（不落盘、只读）
退出码：0 = 无冲突；1 = 有冲突（可直接接在启动命令前做门禁）
"""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

DSH_HOME = Path(os.environ.get("DSH_HOME", Path.home() / "deepseek-harness" / "dsh-domus-0.1.5-rc.2"))


class DshLoader(yaml.SafeLoader):
    """能吃 DSH 补丁方言的 SafeLoader。

    bundle 的 cordis.patch.yml 里大量使用 `!!js <表达式>`（例如
    `disabled: !!js process.platform === 'win32'`）。PyYAML 默认不认这个 tag，
    会直接抛错——若放任不管，dsh-base / dsh-web-app 这两个**定义最多官方行**
    的层会被整层跳过，预检就成了瞎子。这里把 `!!js` 当作不透明字符串收下：
    本脚本只关心 entry id，不关心配置值，所以不求值反而更安全。
    """


def _opaque(loader: yaml.Loader, suffix: str, node: yaml.Node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    return None


DshLoader.add_multi_constructor("tag:yaml.org,2002:js", _opaque)
DshLoader.add_multi_constructor("tag:yaml.org,2002:", _opaque)   # 其余未知 tag 也兜住


def load_yaml(path: Path) -> list:
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=DshLoader)
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"  ⚠️ 解析失败 {path}: {e}")
        return []
    return data if isinstance(data, list) else []


def collect_ids(entries: list, out: list[tuple[str, str]]) -> None:
    """从一组 entry/patch 行里收集 id。out 收集 (id, 说明)。"""
    for e in entries:
        if not isinstance(e, dict):
            continue
        this_id = e.get("id")
        if this_id and not e.get("group"):
            out.append((str(this_id), "row"))
        # insert 列表里的行 id
        for row in (e.get("insert") or []):
            if isinstance(row, dict) and row.get("id"):
                out.append((str(row["id"]), "insert"))
        # group 行的嵌套 config
        if e.get("group") and isinstance(e.get("config"), list):
            collect_ids(e["config"], out)


def layer_patch_file(bundle: str, profile_dir: Path) -> Path | None:
    """把 bundle 名解析到它的 cordis.patch.yml。"""
    for base in (profile_dir / "node_modules", profile_dir.parent / "node_modules"):
        cand = base / bundle / "cordis.patch.yml"
        if cand.is_file():
            return cand
    return None


def profile_bundles(profile_dir: Path) -> list[str]:
    try:
        m = json.loads((profile_dir / "package.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    return list(((m.get("dsh") or {}).get("profile") or {}).get("bundles") or [])


def check_one(profile_dir: Path, extras: list[Path]) -> bool:
    print(f"\n═══ profile: {profile_dir.name}")
    seen: dict[str, str] = {}          # id → 第一处来源
    conflicts: list[tuple[str, str, str]] = []
    order: list[tuple[str, Path]] = []

    for b in profile_bundles(profile_dir):
        p = layer_patch_file(b, profile_dir)
        if p:
            order.append((f"bundle:{b}", p))
        else:
            print(f"  · bundle:{b}  （无 cordis.patch.yml，跳过）")

    prof_patch = profile_dir / "cordis.patch.yml"
    if prof_patch.is_file():
        order.append(("profile 用户层", prof_patch))

    home_patch = DSH_HOME / "cordis.patch.yml"
    if home_patch.is_file():
        order.append(("home 用户层", home_patch))

    for label, p in extras:
        order.append((f"额外层:{label}", p))

    for label, path in order:
        ids: list[tuple[str, str]] = []
        collect_ids(load_yaml(path), ids)
        added = 0
        for i, (iid, how) in enumerate(ids):
            if how == "insert":
                if iid in seen:
                    conflicts.append((iid, seen[iid], label))
                else:
                    seen[iid] = label
                    added += 1
            else:
                # 顶层 row（bundle 定义的行）——首次出现才算定义
                seen.setdefault(iid, label)
                added += 1
        print(f"  · {label:<34} {len(ids):>4} 个 id  {path.name}")

    print(f"\n  合计定义 id: {len(seen)}")
    if conflicts:
        print(f"\n  💥 发现 {len(conflicts)} 处重复 id —— 启动必崩（或热加载时静默半死）：")
        byid: dict[str, list[tuple[str, str]]] = {}
        for iid, first, second in conflicts:
            byid.setdefault(iid, []).append((first, second))
        for iid, pairs in list(byid.items())[:20]:
            print(f"     {iid}")
            for first, second in pairs:
                print(f"        先定义于 {first} → 又被 {second} insert")
        if len(byid) > 20:
            print(f"     … 其余 {len(byid) - 20} 个")
        return False

    print("  ✅ 无重复 id")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", help="只检查该 profile（默认全部）")
    ap.add_argument("--extra", action="append", default=[],
                    help="额外层文件（可多次），按 home 级之后叠加试算")
    args = ap.parse_args()

    prof_root = DSH_HOME / "profiles"
    if not prof_root.is_dir():
        print(f"❌ 找不到 {prof_root}")
        return 1

    dirs = sorted(d for d in prof_root.iterdir()
                  if d.is_dir() and d.name not in ("node_modules",)
                  and (d / "package.json").is_file())
    if args.profile:
        dirs = [d for d in dirs if d.name == args.profile]
    if not dirs:
        print("❌ 没有可检查的 profile（需要 profiles/<name>/package.json）")
        return 1

    extras = [("home级候选(试算)", Path(p)) for p in args.extra]
    ok = True
    for d in dirs:
        ok = check_one(d, extras) and ok

    print("\n" + ("✅ 全部通过：可以启动" if ok else "❌ 存在冲突：先修再启动"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
