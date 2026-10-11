# 文件名: tools/dsh_instance_env.py
# 摘要: DSH 实例环境净化模块 —— 把「继承来的外来身份」从进程环境里剔除，只留本实例自己声明的身份。
#       本文件是 tools/dsh-instance-env.sh（430 行 bash）的 python 移植，语义逐项对齐。
#       可 import 当模块，也可当命令跑（自检 / 预演 / 导出净化后的环境）。
#
# 依赖: 纯标准库（os / sys / argparse）
#       无项目内依赖 —— 刻意保持如此：它要在「什么都还没起来」的时候可用
#
# ── 为什么需要它（实证，不是推测）────────────────────────────────────
#
# 2026-09-26 实查第二个实例（9009）的 /proc/<pid>/environ：
#
#   DSH_HOME       = .../dsh-domus-0.1.7-rc.2      ← 对的
#   DSH_SESSION_ID = session-97fd36b3-...          ← 错：这是【第一个实例】的会话 id
#   DSH_WEB_URL    = http://127.0.0.1:9007         ← 错：指向第一个实例
#   DSH_SHELL      = 1                             ← 错：继承的会话内标记
#   PATH           = ...v0.1.7/node_modules/.bin : corepack : ...v0.1.5/node_modules/.bin : ...
#                                            ← 两版并存、harness/bin 出现两次
#   NODE_OPTIONS   = --import .../dsh-fetch-trace.mjs --import .../dsh-force-h1.mjs
#                                            ← 旧版两实例同写一个共享日志（现为 per-instance）
#
# 根因：新实例是从旧实例的【会话内 shell】里拉起的。脚本「不加」不等于「清掉」——
# 继承足以击穿规避。只有【净化】才可靠。
#
# ── 刻意不做的事 ────────────────────────────────────────────────────
#
#   · 不动 DSH_HOME / DSH_VERSION —— 那正是实例身份本身，由调用方声明。
#     净化【不猜身份】：两者缺一即返回 2，绝不代调用方决定。
#   · 不动 VIRTUAL_ENV —— 它不在净化名单里，因为**它不该被剥**。
#     2026-10-08 实测定论：真正依赖 ~/ai-services 的消费者**各自带 activate**
#     （mcp-stdio.sh 每个 python 分支 source 一次），不需要启动器代劳。
#     详见 用户笔记/部署/启动器-python重写-庙算与定案.md §五·推翻一。
#
# ── 移植说明：与 bash 原版的已知偏离 ─────────────────────────────────
#
#   1. bash 的 `for entry in $raw` 是**未加引号**的展开 ⇒ 除了按 IFS 切分，
#      还会做 pathname expansion（通配符会被 glob）。本移植**不做 glob**。
#      理由：PATH 条目里出现 `*` 是病态输入，复刻 glob 只会让行为更不可预测。
#      这是**刻意的偏离**，不是遗漏。
#   2. bash 的 `[ -n "${!v:-}" ]` 只删**非空**的 ephemeral 变量（设为空串的会留成空串）。
#      本移植严格保真：只在值非空时 pop。
#   3. bash 的代理变量是**无条件** unset（连空串一起）。本移植同样无条件 pop。
#
# ── 启动门 ──────────────────────────────────────────────────────────
#
# gate() 在净化之后调用：环境不干净就拒绝启动。带外来实例身份启动正是
# 2026-09-26「身份错乱 + 取证串台 + 子 CLI 跨版本」的成因。
# 逃生口 DSH_ALLOW_DIRTY_ENV=1（显式、留痕、自担风险）。

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════════════════════════════

# 会话级身份：只在「某个实例的会话内 shell」里有意义，
# 绝不该传进另一个实例的服务进程。
DSH_EPHEMERAL_VARS: tuple[str, ...] = (
    "DSH_SHELL",
    "DSH_SESSION_ID",
    "DSH_WEB_URL",
    "DSH_PARENT_SESSION_ID",
    "DSH_WORKSPACE",
    "DSH_INSTANCE_LABEL",
)

# 代理变量：DSH 的 launch-environment 会读 .env 与进程环境，把 https_proxy
# 装成 undici 全局 dispatcher → 进程内所有 fetch() 改道（含 LLM 请求）→ TRANSPORT。
DSH_PROXY_VARS: tuple[str, ...] = (
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
)

# 本仓库自己注入的两个 Node preload（相对 harness 根的路径）。
_OWN_PRELOADS: tuple[str, ...] = (
    "tools/dsh-fetch-trace.mjs",
    "tools/dsh-force-h1.mjs",
)

# bash 版 CLI 的退出码沿用
_EXIT_OK = 0
_EXIT_DIRTY = 1
_EXIT_IDENTITY_MISSING = 2


def _say(msg: str = "") -> None:
    """报告一律走 stderr —— stdout 留给 --dump-env，保持可管道。"""
    print(msg, file=sys.stderr)


# ═══════════════════════════════════════════════════════════════════
#  路径解析
# ═══════════════════════════════════════════════════════════════════

def harness_dir() -> str:
    """解析 harness 根：优先调用方已设的 HARNESS_DIR，否则由本文件位置推（tools/ 的上一级）。"""
    given = os.environ.get("HARNESS_DIR")
    if given:
        return given
    return str(Path(__file__).resolve().parent.parent)


# ═══════════════════════════════════════════════════════════════════
#  PATH 净化
# ═══════════════════════════════════════════════════════════════════

def filter_path(raw: str, harness: str) -> str:
    """过滤继承的 PATH：剔除 harness 下的任何条目，并去重（保留首次出现）。

    为什么只剔 harness —— PATH 里有三类条目，危害各不相同：
      harness/bin                            → bin/dsh 会越界操作别的 home   ★ 必须剔
      原始代码研究/<ver>/node_modules/.bin    → dsh CLI 跨版本串             ★ 必须剔
      ~/.cache/node/corepack/.../node-gyp-bin → 多版本并存只是「第一个赢」，
                                                粗删会断掉原生模块构建      → 保留
    """
    kept: list[str] = []
    seen: set[str] = set()
    for entry in raw.split(":"):
        if not entry:
            continue
        if entry == harness or entry.startswith(harness + "/"):
            continue
        if entry in seen:
            continue
        seen.add(entry)
        kept.append(entry)
    return ":".join(kept)


# ═══════════════════════════════════════════════════════════════════
#  NODE_OPTIONS 净化
# ═══════════════════════════════════════════════════════════════════

def strip_preloads(raw: str, harness: str | None = None) -> str:
    r"""从 NODE_OPTIONS 里剥掉【本仓库自己注入的两个 preload】，其余原样保留。

    为什么不整个 unset：NODE_OPTIONS 也可能承载正当参数（--max-old-space-size、
    --enable-source-maps 等）。粗清会把它们一起干掉 —— 那是静默降低运行规格。

    为什么必须剥：两个 preload 继承来的那份**指向别的实例**。不清就会两个实例
    写同一份取证、且 H1 臂对两者同时生效，实验设计直接作废。

    实现要点：**精确 token 匹配，不用正则**。
      原 bash 版最初写成 `sed -E 's#--import\s+file://[^[:space:]]*/tools/dsh-...'`，
      被回归测试当场抓住：`[^[:space:]]*` 会吞掉任意路径，把**别的仓库**里的同名
      preload 也一并剥掉（strip:foreign 用例）。路径匹配要「等于」而不是「像」。
      本移植沿用精确匹配，并把该用例纳入对拍。

    认四种等价写法：file:// URL 与裸绝对路径，各配空格/等号两种分隔。
    """
    root = harness if harness is not None else harness_dir()
    escaped: set[str] = set()
    for rel in _OWN_PRELOADS:
        full = f"{root}/{rel}"
        escaped.add(full)
        escaped.add(f"file://{full}")

    tokens = raw.split()
    kept: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        # 形态一：--import <path>（空格分隔，连参数一起吃掉）
        if tok == "--import" and i + 1 < n and tokens[i + 1] in escaped:
            i += 2
            continue
        # 形态二：--import=<path>
        if tok.startswith("--import=") and tok[len("--import="):] in escaped:
            i += 1
            continue
        kept.append(tok)
        i += 1
    return " ".join(kept)


# ═══════════════════════════════════════════════════════════════════
#  净化主入口
# ═══════════════════════════════════════════════════════════════════

def sanitize(quiet: bool = False) -> int:
    """净化【当前进程】的环境。必须在调用方声明好实例身份【之后】调用。

    返回: 0 成功 / 1 净化后身份丢失 / 2 身份未声明
    """
    harness = harness_dir()

    # ── 断言：身份必须已由调用方声明 —— 净化不猜身份 ────────────────
    if not os.environ.get("DSH_HOME"):
        _say("❌ dsh_env_sanitize: DSH_HOME 未设置。")
        _say("   净化不猜身份 —— 请调用方先设 DSH_HOME=<本实例 home>，再调用。")
        return _EXIT_IDENTITY_MISSING
    if not os.environ.get("DSH_VERSION"):
        _say("❌ dsh_env_sanitize: DSH_VERSION 未设置。")
        _say("   实例必须显式声明基座版本（版本配置只作回落，不在这里读）。")
        return _EXIT_IDENTITY_MISSING

    # ── 1 · 清掉继承的会话身份（只删非空的，保真 bash 的 -n 判定）──
    removed: list[str] = []
    for name in DSH_EPHEMERAL_VARS:
        value = os.environ.get(name)
        if value:
            removed.append(f"{name}={value}")
            del os.environ[name]

    # ── 2 · 清代理（无条件）────────────────────────────────────────
    for name in DSH_PROXY_VARS:
        os.environ.pop(name, None)

    # ── 3 · 剥掉继承来的自家 preload ────────────────────────────────
    # 调用方随后会按【自己的】实例路径重新注入这两个 preload。
    inherited_node_options = os.environ.get("NODE_OPTIONS", "")
    kept_node_options = strip_preloads(inherited_node_options, harness)
    if kept_node_options:
        os.environ["NODE_OPTIONS"] = kept_node_options
    else:
        os.environ.pop("NODE_OPTIONS", None)

    # ── 4 · 重建 PATH ──────────────────────────────────────────────
    raw_path = os.environ.get("PATH", "")
    os.environ["PATH"] = filter_path(raw_path, harness)

    # ── 5 · 断言身份仍在位 ────────────────────────────────────────
    identity_ok = bool(os.environ.get("DSH_HOME")) and bool(os.environ.get("DSH_VERSION"))

    if not quiet:
        _say("── 实例环境净化 ──────────────────────────────")
        _say(f"  harness 根  : {harness}")
        _say(f"  本实例身份  : DSH_HOME={os.environ.get('DSH_HOME', '')}")
        _say(f"                DSH_VERSION={os.environ.get('DSH_VERSION', '')}")
        if removed:
            _say("  剔除继承身份:")
            for item in removed:
                _say(f"    - {item}")
        else:
            _say("  剔除继承身份: 无（环境本来就是干净的）")
        if inherited_node_options != kept_node_options:
            _say("  NODE_OPTIONS  : 已剥离自家 preload")
            _say(f"                  原值: {inherited_node_options}")
            _say(f"                  现值: {kept_node_options or '（空）'}")
        else:
            _say("  NODE_OPTIONS  : 无自家 preload 可剥")
        _say(f"  PATH         : {len(raw_path)} 字符 → {len(os.environ['PATH'])} 字符")
        _say("──────────────────────────────────────────────")

    if not identity_ok:
        _say("❌ 净化后身份丢失 —— 中止")
        return 1
    return 0


# ═══════════════════════════════════════════════════════════════════
#  自检 / 启动门
# ═══════════════════════════════════════════════════════════════════

def self_report() -> int:
    """报告当前环境是否干净（**不改动**）。用于启动后自检 / 人工核对。

    返回: 0 干净 / 1 有残留
    """
    harness = harness_dir()
    dirty = False

    _say("── 实例环境自检 ──────────────────────────────")
    _say(f"  DSH_HOME    : {os.environ.get('DSH_HOME') or '（未设置）'}")
    _say(f"  DSH_VERSION : {os.environ.get('DSH_VERSION') or '（未设置）'}")
    _say(f"  DSH_WEB_URL : {os.environ.get('DSH_WEB_URL') or '（未设置 → 干净）'}")

    for name in DSH_EPHEMERAL_VARS:
        value = os.environ.get(name)
        if value:
            _say(f"  ✗ 残留会话身份: {name}={value}")
            dirty = True

    node_options = os.environ.get("NODE_OPTIONS", "")
    if node_options:
        leftover = strip_preloads(node_options, harness)
        if leftover != node_options:
            _say("  ✗ NODE_OPTIONS 里仍有自家 preload（跨实例串台源）:")
            _say(f"      {node_options}")
            dirty = True
        else:
            _say("  · NODE_OPTIONS 非空但无自家 preload（正当参数，保留）:")
            _say(f"      {node_options}")

    # PATH 残留判定要分清三类，否则会把【合法配置】误报成污染：
    #   $harness/bin
    #       → 实例自己的 CLI shim。bin/dsh 已改为「环境优先」，放它是对的。
    #   $harness/原始代码研究/<本实例版本>/…
    #       → 本实例自己版本的检出。`pnpm dsh web` 运行脚本时会把项目
    #         node_modules/.bin 前置到 PATH，属 pnpm 正常行为，不是污染。
    #   $harness/ 下的**其它**条目
    #       → 真残留。典型是【别的版本】检出的 node_modules/.bin ——
    #         跨版本会让子进程解析到错误的 dsh CLI。
    # 这个「版本感知」的区分正是本检查的价值：只看「有没有 harness 条目」会误报，
    # 只看「是不是本实例自己的」才能抓住真问题。
    version = os.environ.get("DSH_VERSION") or "__未声明__"
    own_checkout_prefix = f"{harness}/原始代码研究/{version}/"
    for entry in os.environ.get("PATH", "").split(":"):
        if not entry:
            continue
        if entry == f"{harness}/bin":
            continue
        if entry.startswith(own_checkout_prefix):
            continue
        if entry == harness or entry.startswith(harness + "/"):
            _say(f"  ✗ PATH 残留 harness 条目（跨实例/跨版本风险）: {entry}")
            _say(f"      本实例版本为 {version}，此条目不属于它")
            dirty = True

    _say("──────────────────────────────────────────────")
    if not dirty:
        _say("  ✓ 环境干净（无继承身份；harness PATH 条目仅剩本实例自己的 bin/）")
        return _EXIT_OK
    _say("  ✗ 环境有残留，见上面的 ✗ 项")
    return _EXIT_DIRTY


def gate() -> int:
    """启动门：净化之后调用。环境不干净就【拒绝启动】。

    为什么是拒绝而不是警告：带着外来实例身份启动，正是 2026-09-26
    那次「身份错乱 + 取证串台 + 子 CLI 跨版本」的成因。警告会被忽略，
    静默降级更糟（以静默降级为耻）。所以默认硬拒。

    逃生口：DSH_ALLOW_DIRTY_ENV=1（显式、留痕、自担风险）。
    返回: 0 通过 / 1 拦截
    """
    if os.environ.get("DSH_ALLOW_DIRTY_ENV", "0") == "1":
        _say("⚠ DSH_ALLOW_DIRTY_ENV=1 —— 环境门被显式跳过（自担风险）")
        return _EXIT_OK
    if self_report() == _EXIT_OK:
        return _EXIT_OK
    _say("")
    _say("❌ 环境门未通过 —— 拒绝启动。")
    _say("   上面的 ✗ 项就是从调用方继承来的污染，会让本实例：")
    _say("     · 身份错乱（DSH_WEB_URL / DSH_SESSION_ID 指向别的实例）")
    _say("     · 取证串台（NODE_OPTIONS 里的 preload 写别人的日志）")
    _say("     · 子 CLI 跨版本（PATH 里两版 node_modules/.bin 并存）")
    _say("   确要强行启动：DSH_ALLOW_DIRTY_ENV=1 （自担风险）")
    return _EXIT_DIRTY


# ═══════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════

_USAGE = """
tools/dsh_instance_env.py —— DSH 实例环境净化（bash 版的 python 移植）

  python3 tools/dsh_instance_env.py --self-report   # 报告当前环境是否干净（不改动）
  python3 tools/dsh_instance_env.py --dry-run       # 在副本环境里预演净化效果（不改当前环境）
  python3 tools/dsh_instance_env.py --dump-env      # 净化，再按 env -0 格式导出（排序、NUL 分隔）
  python3 tools/dsh_instance_env.py -h | --help

  作为模块：
      from dsh_instance_env import sanitize, gate
      sanitize(quiet=True)   # 必须先由调用方设好 DSH_HOME / DSH_VERSION
      gate()                 # 0 通过 / 1 拒绝启动

--dump-env 的用途（不是给人日常看的）：
  · 与 bash 原版做【双实现对拍】——同一份合成脏环境喂两边，逐字节比较
  · 排查「净化到底改了什么」——它本来的失败模式就是不可见
  输出按 key 排序（环境变量顺序无语义），NUL 分隔（值里可以有换行）。
"""


def _dump_env() -> int:
    """先净化，再把结果按 env -0 格式写到 stdout：KEY=VALUE\\0，按 key 排序。

    净化失败（身份未声明）时【不输出】、直接返回其退出码 —— 与 bash 侧
    `dsh_env_sanitize quiet || exit $?` 对齐，使双实现对拍能同时比较退出码。
    """
    rc = sanitize(quiet=True)
    if rc != 0:
        return rc
    out = sys.stdout.buffer
    for key in sorted(os.environ):
        out.write(key.encode("utf-8", "surrogateescape"))
        out.write(b"=")
        out.write(os.environ[key].encode("utf-8", "surrogateescape"))
        out.write(b"\0")
    out.flush()
    return _EXIT_OK


def _dry_run() -> int:
    """在副本环境里预演净化（不改当前环境），与 bash 版 --dry-run 等价。"""
    _say("── 净化预演（在副本环境里跑，不改当前环境）──")
    _say("")
    _say("【当前环境】")
    self_report()
    _say("")
    _say("【净化后】")

    snapshot = dict(os.environ)
    try:
        os.environ["DSH_HOME"] = snapshot.get("DSH_HOME") or "/dummy/home"
        os.environ["DSH_VERSION"] = snapshot.get("DSH_VERSION") or "v0.0.0-dummy"
        sanitize(quiet=False)
        _say("")
        _say("净化后 PATH 首三段：")
        for entry in os.environ.get("PATH", "").split(":")[:3]:
            _say(f"    {entry}")
    finally:
        os.environ.clear()
        os.environ.update(snapshot)
    return _EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(_USAGE.strip())
        return _EXIT_OK
    cmd = args[0]
    if len(args) > 1:
        _say(f"未知参数: {' '.join(args[1:])}（-h 看用法）")
        return 2
    if cmd == "--self-report":
        return self_report()
    if cmd == "--dry-run":
        return _dry_run()
    if cmd == "--dump-env":
        return _dump_env()
    _say(f"未知参数: {cmd}（-h 看用法）")
    return 2


if __name__ == "__main__":
    sys.exit(main())
