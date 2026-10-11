# 文件名: tools/dsh_config.py
# 摘要: 启动器配置与路径派生的【单一真相源】—— 读 当前配置.toml 与 版本信息说明/<版本>.toml，
#       派生 home / 检出 / 运行记录等全部路径，并校验「声明」与「磁盘上的检出」相符。
# 依赖: 纯标准库（dataclasses / json / os / re / subprocess / tomllib）
#       ../../启动器配置和日志/当前配置.toml
#       ../../启动器配置和日志/版本信息说明/<版本>.toml
#
# ── 为什么要单独一个模块 ────────────────────────────────────────────
#
# 版本 → home 名的派生式（`<前缀>-<版本去掉一个前导 v>`）有两个消费者：
#   start-web.py（起实例）与 bin/dsh（子进程 CLI wrap）。
# 各写一份 = 两处拼写 = 迟早分叉 —— 那正是「版本标记依赖审计」里逐条列出的腐坏形状。
# 所以派生只在这里实现一次，两边 import 同一个函数。
#
# ── 设计约束（来自 用户笔记/部署/启动器-python重写-庙算与定案.md）──
#
#   · D15/D22：配置只放【随环境变的选择】，不放【设计规则】。
#     本模块不持有等待秒数、退避阶梯、退出码 —— 那些是 launcher 的代码常量。
#   · D15：TOML 只读不写。启动器永远不替人改配置文件；要「转正」只打印该改哪一行。
#   · D18：版本信息说明缺失 = 拒绝启动（不是警告）。这里抛 ConfigError，
#     由调用方决定用什么退出码。
#   · D19：「与上游一致」是被【校验】的事实，不是约定的巧合 ——
#     verify_upstream() 会去读检出的 package.json 与 git tag 来对账。
#   · D21：整条链【离线可读】—— 只用标准库读本地文件，不碰网络，不碰数据库。

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════════════════════════════

LAUNCHER_DIR_NAME = "启动器配置和日志"
CONFIG_FILE_NAME = "当前配置.toml"
VERSION_INFO_DIR_NAME = "版本信息说明"
RECORD_DIR_NAME = "运行记录"
RECORD_HISTORY_NAME = "历史"
CHECKOUT_DIR_NAME = "原始代码研究"

# 运行记录目录名：<本地时间>-PID<host pid>
#   为什么用挂钟时间而不是 jiffies 的 starttime：给人看、给排序。
#   但挂钟时间**不可从 /proc 反验**（uptime 精度 + NTP 步进会让重算对不上），
#   所以它是【标签不是指纹】—— 指纹（starttime）存在 instance.json 里，
#   反验时读它。见 定案 D16。
RECORD_DIR_FORMAT = "%Y%m%d.%H%M%S"
_RECORD_DIR_RE = re.compile(r"^(\d{8}\.\d{6})-PID(\d+)$")

# 未完成启动的临时目录前缀（此时 host pid 还不存在，指纹与名字都拿不到）
STARTING_PREFIX = ".starting-PID"


class ConfigError(Exception):
    """配置层面的硬错误。调用方负责转成退出码并原样打印消息。"""


# ═══════════════════════════════════════════════════════════════════
#  基础路径
# ═══════════════════════════════════════════════════════════════════

def harness_dir() -> Path:
    """解析 harness 根：优先调用方已设的 HARNESS_DIR，否则由本文件位置推（tools/ 的上一级）。

    与 tools/dsh_instance_env.py 的 harness_dir() 保持同一套规则 —— 两处不一致
    会让净化器按 A 滤 PATH、启动器按 B 找检出。
    """
    given = os.environ.get("HARNESS_DIR")
    if given:
        return Path(given)
    return Path(__file__).resolve().parent.parent


def home_name(prefix: str, version: str) -> str:
    """home 目录名 = <prefix>-<version 去掉【一个】前导 v>。

    ⚠️ 是「一个」：bash 原来写的是 `${DSH_VERSION#v}`，也只吃一个。
    用 str.lstrip('v') 会吃掉所有前导 v（`vv0.1` → `0.1`），那是另一个语义。
    """
    return f"{prefix}-{version[1:] if version.startswith('v') else version}"


def record_dir_name(started_at: datetime, host_pid: int) -> str:
    return f"{started_at.strftime(RECORD_DIR_FORMAT)}-PID{host_pid}"


def parse_record_dir_name(name: str) -> tuple[datetime, int] | None:
    """解析运行记录目录名。不是本格式（如 历史/、.starting-*）则返回 None。"""
    matched = _RECORD_DIR_RE.match(name)
    if not matched:
        return None
    try:
        started = datetime.strptime(matched.group(1), RECORD_DIR_FORMAT)
    except ValueError:
        return None
    return started, int(matched.group(2))


# ═══════════════════════════════════════════════════════════════════
#  数据结构
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class LauncherConfig:
    version: str
    home_prefix: str
    main_port: int
    try_port_from: int
    archive_ttl_days: int


@dataclass(frozen=True)
class VersionInfo:
    version: str
    upstream_version: str
    upstream_git_tag: str
    required_markers: tuple[str, ...]


@dataclass(frozen=True)
class Paths:
    harness: Path
    launcher_dir: Path
    config_file: Path
    version_info_dir: Path
    version_info_file: Path
    record_root: Path
    record_history: Path
    version: str
    home_name: str
    home_dir: Path
    checkout_dir: Path


# ═══════════════════════════════════════════════════════════════════
#  读取
# ═══════════════════════════════════════════════════════════════════

def _read_toml(path: Path, what: str) -> dict:
    if not path.is_file():
        raise ConfigError(f"{what}不存在：{path}")
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{what}解析失败：{path}\n  {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"{what}读不了：{path}\n  {exc}") from exc


def _require(data: dict, key: str, kind: type, where: str):
    """取一个必需字段并校验类型。缺了或类型不对都 fail-loud —— 不猜默认值。

    注意 bool：它是 int 的子类，`isinstance(True, int)` 为真。
    main_port = true 这种写法必须被挡掉，故 int 一档单独排除 bool。
    """
    if key not in data:
        raise ConfigError(f"{where} 缺 {key}")
    value = data[key]
    if kind is int and isinstance(value, bool):
        raise ConfigError(f"{where} 的 {key} 是布尔，期望整数")
    if not isinstance(value, kind):
        raise ConfigError(f"{where} 的 {key} 类型不对：期望 {kind.__name__}，实得 {type(value).__name__}")
    return value


def load_config(harness: Path | None = None) -> LauncherConfig:
    """读 当前配置.toml。任何缺失或类型错误都 fail-loud（不猜默认值）。"""
    root = harness if harness is not None else harness_dir()
    path = root / LAUNCHER_DIR_NAME / CONFIG_FILE_NAME
    where = f"{CONFIG_FILE_NAME}"
    data = _read_toml(path, "启动器配置")
    return LauncherConfig(
        version=_require(data, "version", str, where),
        home_prefix=_require(data, "home_prefix", str, where),
        main_port=_require(data, "main_port", int, where),
        try_port_from=_require(data, "try_port_from", int, where),
        archive_ttl_days=_require(data, "archive_ttl_days", int, where),
    )


def load_version_info(version: str, harness: Path | None = None) -> VersionInfo:
    """读 版本信息说明/<版本>.toml。

    缺失即 ConfigError —— 这是定案 D18 的那道门：新版本必须先写下你【知道】的事，
    才允许启动。「加版本 = 加数据」在这里从口号变成硬约束。
    """
    root = harness if harness is not None else harness_dir()
    path = root / LAUNCHER_DIR_NAME / VERSION_INFO_DIR_NAME / f"{version}.toml"
    if not path.is_file():
        raise ConfigError(
            f"缺少版本信息说明：{path}\n"
            f"   基座版本 {version} 没有配套声明，无法判断它要求 home 具备什么 —— 拒绝启动。\n"
            f"   修法：照着同目录现有文件的样子新建一份（至少要有 version / "
            f"[upstream] / [profile] required_markers 三段）。"
        )
    where = f"{VERSION_INFO_DIR_NAME}/{version}.toml"
    data = _read_toml(path, "版本信息说明")

    declared = _require(data, "version", str, where)
    if declared != version:
        raise ConfigError(
            f"{where} 里的 version 与文件名不符：文件名={version!r} 文件内={declared!r}\n"
            f"   两者必须逐字节相同。"
        )

    upstream = data.get("upstream")
    if not isinstance(upstream, dict):
        raise ConfigError(f"{where} 缺 [upstream] 段（需要 version 与 git_tag 两项）")

    profile = data.get("profile")
    if not isinstance(profile, dict):
        raise ConfigError(f"{where} 缺 [profile] 段（需要 required_markers）")

    markers = profile.get("required_markers")
    if not isinstance(markers, list) or not all(isinstance(m, str) for m in markers):
        raise ConfigError(f"{where} 的 profile.required_markers 必须是非空字符串数组")

    return VersionInfo(
        version=declared,
        upstream_version=_require(upstream, "version", str, f"{where} [upstream]"),
        upstream_git_tag=_require(upstream, "git_tag", str, f"{where} [upstream]"),
        required_markers=tuple(markers),
    )


def derive(config: LauncherConfig, version: str | None = None,
           harness: Path | None = None) -> Paths:
    """派生全部路径。version 给了就用它（--try 的情形），否则用配置里的。"""
    root = harness if harness is not None else harness_dir()
    effective = version if version else config.version
    launcher = root / LAUNCHER_DIR_NAME
    home = home_name(config.home_prefix, effective)
    record_root = launcher / RECORD_DIR_NAME
    return Paths(
        harness=root,
        launcher_dir=launcher,
        config_file=launcher / CONFIG_FILE_NAME,
        version_info_dir=launcher / VERSION_INFO_DIR_NAME,
        version_info_file=launcher / VERSION_INFO_DIR_NAME / f"{effective}.toml",
        record_root=record_root,
        record_history=record_root / RECORD_HISTORY_NAME,
        version=effective,
        home_name=home,
        home_dir=root / home,
        checkout_dir=root / CHECKOUT_DIR_NAME / effective,
    )


# ═══════════════════════════════════════════════════════════════════
#  与上游对账
# ═══════════════════════════════════════════════════════════════════

def verify_upstream(paths: Paths, info: VersionInfo) -> list[str]:
    """校验「版本信息说明里的 [upstream] 声明」与「磁盘上的检出」相符。

    返回：警告列表（软检查失败）。硬检查失败直接抛 ConfigError。

    检查强度刻意分两级 —— 判据不同，结论该有不同分量：
      · package.json 的 version       → 硬。这是上游权威的版本号本体；
        它对不上，说明我们对自己的版本拼写有根本性误解。
      · git tag --points-at HEAD       → 软。git 状态可以合法地不同
        （浅克隆、游离 HEAD、本地改动），不该让它把可用的系统挡在门外。
      · 检出不存在                      → 不检查，但**明说**跳过了（不静默）
    """
    warnings: list[str] = []
    if not paths.checkout_dir.is_dir():
        warnings.append(f"检出不存在，跳过上游对账：{paths.checkout_dir}")
        return warnings

    package_json = paths.checkout_dir / "package.json"
    if not package_json.is_file():
        warnings.append(f"检出里没有 package.json，跳过版本号对账：{package_json}")
    else:
        try:
            declared = json.loads(package_json.read_text(encoding="utf-8")).get("version")
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"读不了 {package_json}（{exc}），跳过版本号对账")
        else:
            if declared != info.upstream_version:
                raise ConfigError(
                    f"版本声明与检出不符：\n"
                    f"   {paths.version_info_file} 的 upstream.version = {info.upstream_version!r}\n"
                    f"   {package_json} 的 version            = {declared!r}\n"
                    f"   改哪一边都行，但两边必须一致 —— 这行声明是【被校验的事实】，"
                    f"不是约定的巧合。"
                )

    if (paths.checkout_dir / ".git").exists():
        try:
            proc = subprocess.run(
                ["/usr/bin/git", "-C", str(paths.checkout_dir), "tag", "--points-at", "HEAD"],
                capture_output=True, text=True, timeout=15,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            warnings.append(f"git 查 tag 失败（{exc}），跳过 tag 对账")
        else:
            if proc.returncode != 0:
                warnings.append(f"git 查 tag 非零退出（{proc.returncode}），跳过 tag 对账")
            else:
                tags = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
                if info.upstream_git_tag not in tags:
                    warnings.append(
                        f"HEAD 上的 tag 与声明不符：声明 {info.upstream_git_tag!r}，"
                        f"实测 {tags or '（无 tag）'}"
                    )
    else:
        warnings.append(f"检出不是 git 仓库，跳过 tag 对账：{paths.checkout_dir}")

    return warnings


def describe(config: LauncherConfig, paths: Paths) -> str:
    """渲染一份人类可读的解析结果（--show 与调试用）。"""
    lines = [
        "── 启动器配置 ────────────────────────────────",
        f"  harness      : {paths.harness}",
        f"  配置文件     : {paths.config_file}",
        f"  版本         : {paths.version}",
        f"  home 前缀    : {config.home_prefix}",
        f"  home 名      : {paths.home_name}",
        f"  home 目录    : {paths.home_dir}",
        f"  检出目录     : {paths.checkout_dir}",
        f"  主端口       : {config.main_port}",
        f"  试运行端口   : 从 {config.try_port_from} 起（共 60 个）",
        f"  归档保留     : {config.archive_ttl_days} 天（自归档时刻起算）",
        f"  运行记录根   : {paths.record_root}",
        f"  归档目录     : {paths.record_history}",
        "──────────────────────────────────────────────",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("-h", "--help"):
        print("tools/dsh_config.py [--show] [--version V]")
        print()
        print("  --show          打印解析后的配置与全部派生路径（默认行为）")
        print("  --version V     用 V 覆盖配置里的版本（--try 的情形）")
        return 0
    version = None
    if args and args[0] == "--version":
        if len(args) < 2:
            print("--version 需要一个版本号", file=sys.stderr)
            return 2
        version = args[1]
        args = args[2:]
    if args and args[0] != "--show":
        print(f"未知参数: {args[0]}（-h 看用法）", file=sys.stderr)
        return 2
    try:
        config = load_config()
        paths = derive(config, version)
        info = load_version_info(paths.version)
        print(describe(config, paths))
        print(f"  上游版本号   : {info.upstream_version}")
        print(f"  上游 tag     : {info.upstream_git_tag}")
        print(f"  profile 必含 : {list(info.required_markers)}")
        print("──────────────────────────────────────────────")
        for warning in verify_upstream(paths, info):
            print(f"  ⚠ {warning}")
    except ConfigError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
