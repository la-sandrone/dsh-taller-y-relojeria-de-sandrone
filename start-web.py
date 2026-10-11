#!/usr/bin/python3
# 文件名: start-web.py
# 摘要: DSH 启动器 —— 唯一入口。主运行版本 / 临时试新版本 / 起停状态 / 运行记录，全在这一个文件里。
#       默认【前台持有】：日志实时打到终端，host 死活一眼可见，Ctrl+C 结束。
#       本文件是 start-web.sh（582 行 bash）的 python 重写，行为契约见
#       用户笔记/部署/启动器-python重写-庙算与定案.md §四。
#
# 依赖: 纯标准库
#       ./tools/dsh_config.py          配置与路径派生的单一真相源
#       ./tools/dsh_instance_env.py    环境净化 + 启动门
#       ./tools/check_patch_layers.py  补丁层护栏
#       ./tools/check-profile-links.py profile 链接护栏
#       ./tools/dsh-fetch-trace.mjs    取证 preload
#       ./tools/dsh-force-h1.mjs       强制 HTTP/1.1 preload
#       ./tools/dsh-ops-daemon.sh     运维守护 —— **按需挂载的调试工具**，不由本脚本拉起
#
# 用法
# ----
#   ./start-web.py                                # 主运行版本（版本读 启动器配置和日志/当前配置.toml）
#   ./start-web.py --try v0.1.8-rc.1              # 临时试新版本（不碰配置文件；端口自动避让）
#   ./start-web.py --try v0.1.8-rc.1 --port 9012
#   ./start-web.py --background                   # 脱离终端（代价：看不到日志与死活）
#   ./start-web.py --status                       # 列出全部实例 + 环境复核 + 对账
#   ./start-web.py --stop                         # 停主运行版本
#   ./start-web.py --port 9012 --stop             # 停指定端口
#   ./start-web.py --version v0.2.0-rc.2 --stop   # 按版本号停（查运行记录）
#   ./start-web.py --gc                           # 列出已过期的运行记录归档（默认干跑）
#   ./start-web.py --gc --apply                   # 真删
#
# 停止方式的唯一真相
# ------------------
#   前台（默认）        ：**Ctrl+C** —— SIGINT 直达同一前台进程组里的 node；
#                        启动器捕获 KeyboardInterrupt，等 host 收尾后打收尾信息再返回。
#                        ⚠️ 启动器**从不给 SIGINT 设 SIG_IGN**：SIG_IGN 会跨 execve 继承，
#                        那会让 host 对 Ctrl+C 完全免疫 —— 等于把前台唯一的停止路径弄死。
#   后台（--background）：起完即脱离终端，只能靠 --stop；**必须**给 --version V 或 --port N。
#
#   为什么 --stop 不能自己推端口（曾经的缺陷）：--try 的端口由 free_port() 自动找空闲挑；
#   事后要停它时它**正在监听**，free_port() 必然算出**另一个**端口 —— 于是
#   `--try V --stop` 停不掉任何东西，还可能把碰巧占用那个端口的无关进程当目标杀掉。
#   所以启动时把 {port,host_pid,mode,...} 落到运行记录目录；--status / --stop 一律**查记录**，
#   查不到就**报错退出，绝不猜** —— 「谁的儿子谁抱回家」。
#
# 退出码: 0 正常结束 / 1 前置拒绝 / 2 环境不干净 / 3 参数错误 / 4 找不到实例记录

from __future__ import annotations

import argparse
import json
import os
import re
import select
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import NoReturn

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tools"))

import dsh_config as dcfg          # noqa: E402
import dsh_instance_env as denv    # noqa: E402

# ═══════════════════════════════════════════════════════════════════
#  常量（设计规则，不进配置文件 —— 见 定案 D22）
# ═══════════════════════════════════════════════════════════════════

EXIT_OK = 0
EXIT_REFUSE = 1          # 前置拒绝（门未通过）
EXIT_DIRTY = 2           # 环境不干净
EXIT_ARGS = 3            # 参数错误
EXIT_NO_RECORD = 4       # 找不到实例记录
EXIT_INT = 130           # SIGINT（Ctrl+C），shell 惯例 128+2
#                          ⚠️ **这不是错误码，是正常停止路径** —— 前台实例就是这么停的。
#                          收尾信息里不许把它当异常展示（2026-10-08 用户指出后修正）。

WAIT_S = 90              # 等端口监听的秒数（冷启含插件索引，给宽些）
TERM_WAIT_S = 20         # SIGTERM 之后等多久升级 SIGKILL
TOKEN_WAIT_S = 15        # 后台模式下等 token 出现在日志里的秒数
FINALIZE_TIMEOUT_S = 30  # Ctrl+C 之后等 host 收尾的上限（不作为 = 会挂死）
READ_CHUNK = 65536       # host 输出搬运的块大小

BASH = "/usr/bin/bash"
SS = shutil.which("ss") or "/usr/sbin/ss"

# 凭据**不在这里**了（2026-10-08 迁出；迁移由 tools/migrate-keys-to-env.py 做，
# 它读值、写文件、**只印长度与不可逆指纹** —— 用户红线：「不要把 key 读出来」）。
#   读法见 load_secrets()：**环境优先**（`export` 一句即可临时覆盖或轮换），
#   回落 `启动器配置和日志/密钥.env`（mode 600、明文、**进 git** —— 本仓库是纯本地
#   安全网、永不公开；凭据要跟着备份走，否则从 git 恢复一个工作区之后开不了机）。
SECRETS_FILE_NAME = "密钥.env"
SECRET_NAMES = ("DEEPSEEK_API_KEY", "DEEPSEEK_API_AMICI_MEI")
# 路径自检用的模式：harness 根下、且首段是 dsh-domus 的绝对路径。
# 与 bash 原式的 `/deepseek-harness/dsh-domus(-[0-9]|/)` 同形（要求 `-数字` 或 `/` 跟随）。
_LEAK_TAIL = r"/dsh-domus(?:-[0-9][A-Za-z0-9._-]*|/)"


def say(msg: str = "") -> None:
    print(msg, flush=True)


def head2(msg: str) -> None:
    print(f"\n── {msg}", flush=True)


def die(msg: str, code: int = EXIT_REFUSE) -> NoReturn:
    print(f"❌ {msg}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def _emit(chunk: bytes, log) -> None:
    """一块 host 输出 → 终端与日志各一份，两边都立刻 flush。

    日志必须随时可 grep（token 就靠它取），所以不做任何缓冲。
    """
    sys.stdout.buffer.write(chunk)
    sys.stdout.buffer.flush()
    log.write(chunk)
    log.flush()


# ═══════════════════════════════════════════════════════════════════
#  解释器断言（定案 D2）
# ═══════════════════════════════════════════════════════════════════

def assert_interpreter() -> None:
    """本脚本必须跑在【系统 python】上。

    shebang 是绝对的 `#!/usr/bin/python3`，直接执行时没问题；但有人手动
    `python3 start-web.py` 时会拿到 PATH 里第一个 —— 而 PATH 第一顺位可能是一个
    uv venv（实测本机第一顺位曾是 ~/ai-services/bin/python3 3.12）。那时会拿到
    【另一个解释器】跑同一份代码，且悄无声息。故当场拒绝，不静默换解释器。
    """
    if sys.prefix != sys.base_prefix:
        die("本脚本必须用系统 python 运行，当前在虚拟环境里：\n"
            f"   sys.prefix      = {sys.prefix}\n"
            f"   sys.base_prefix = {sys.base_prefix}\n"
            "   修法：直接用 ./start-web.py（shebang 是绝对路径 /usr/bin/python3）")
    if not str(Path(sys.executable).resolve()).startswith("/usr/"):
        die(f"本脚本必须用 /usr 下的 python 运行，实际是 {sys.executable}\n"
            "   修法：直接用 ./start-web.py")


# ═══════════════════════════════════════════════════════════════════
#  进程与端口探测
# ═══════════════════════════════════════════════════════════════════

def proc_starttime(pid: int) -> int | None:
    """读 /proc/<pid>/stat 第 22 字段（starttime，jiffies since boot）。

    它是【进程身份指纹】：pid 会回绕，`/proc/<pid>` 存在不等于那就是你要找的进程。
    ⚠️ 第 2 字段 (comm) 可能含空格与括号，故不能用 split() 数位置 ——
    必须从【最后一个 ')' 之后】开始数；此时第 3 字段落在索引 0，故第 22 字段 = 索引 19。
    """
    try:
        raw = Path(f"/proc/{pid}/stat").read_bytes()
    except OSError:
        return None
    close = raw.rfind(b")")
    if close < 0:
        return None
    fields = raw[close + 2:].split()
    try:
        return int(fields[19])
    except (IndexError, ValueError):
        return None


def is_alive(pid: int | None, starttime: int | None) -> bool:
    """进程还活着【且就是那一个】。指纹缺失时退化为只判存活。"""
    if not pid or pid <= 0:
        return False
    current = proc_starttime(pid)
    if current is None:
        return False
    if starttime is None:
        return True
    return current == starttime


def pid_on_port(port: int) -> int | None:
    """谁在监听这个端口。先问 ss（权威），再退化为扫 /proc 的 cmdline。"""
    try:
        out = subprocess.run([SS, "-ltnp"], capture_output=True, text=True, timeout=15)
        for line in out.stdout.splitlines():
            if f":{port} " not in line:
                continue
            matched = re.search(r"pid=(\d+)", line)
            if matched:
                return int(matched.group(1))
    except (OSError, subprocess.SubprocessError):
        pass
    # 退化路径：ss 没给 pid（无权限 / 旧内核）时按 cmdline 找 host 进程
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = entry.joinpath("cmdline").read_bytes().replace(
                b"\0", b" ").decode("utf-8", "replace")
        except OSError:
            continue
        if "bin.ts web" in cmdline and f"--port {port}" in cmdline:
            return int(entry.name)
    return None


def free_port(start: int, span: int) -> int | None:
    """从 start 起找第一个没被监听的端口。"""
    for port in range(start, start + span):
        if pid_on_port(port) is None:
            return port
    return None


def port_listening(port: int) -> bool:
    """端口上有没有监听者（不看 pid，只看 socket）。

    与 pid_on_port() 分开：ss 在拿不到 pid 时（别的用户持有的 socket）仍需能判
    「端口被占」，否则启动会撞上去。
    """
    try:
        out = subprocess.run([SS, "-ltn"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    return any(f":{port} " in line for line in out.stdout.splitlines())


def port_line(port: int) -> str:
    try:
        out = subprocess.run([SS, "-ltnp"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return "     （ss 查不到详情）"
    rows = [l for l in out.stdout.splitlines() if f":{port} " in l]
    return "\n".join("     " + r for r in rows) or "     （ss 没给出条目）"


# ═══════════════════════════════════════════════════════════════════
#  运行记录（取代 _scratch/instances/<版本>.json）
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Instance:
    dir: Path
    version: str
    home: str
    port: int
    mode: str
    launcher_pid: int
    launcher_starttime: int | None
    started_at: str
    host_pid: int | None = None
    host_starttime: int | None = None
    archived_at: str | None = None

    def to_json(self) -> str:
        # 刻意【不】落盘 dir：目录会改名（.starting-* → <时间>-PID<host>），
        # 落盘就成了过时事实。dir 由读取方从实际路径填。
        payload = {k: v for k, v in self.__dict__.items() if k != "dir"}
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)

    def representative(self) -> tuple[int | None, int | None]:
        """代表本实例存活的那个 pid 及其指纹：优先 host，其次 launcher。

        前台模式下 host 是 pnpm 的孙进程，启动器在拿到它的 pid 之前先记 launcher；
        后台模式下 launcher 起完即退，所以【代表实例存活的只能是 host】。
        """
        if self.host_pid:
            return self.host_pid, self.host_starttime
        return self.launcher_pid, self.launcher_starttime

    def alive(self) -> bool:
        pid, starttime = self.representative()
        return is_alive(pid, starttime)


def _write_instance(inst: Instance) -> None:
    target = inst.dir / "instance.json"
    tmp = inst.dir / "instance.json.tmp"
    tmp.write_text(inst.to_json(), encoding="utf-8")
    os.replace(tmp, target)


def _read_instance(record_dir: Path) -> Instance | None:
    path = record_dir / "instance.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return Instance(
            dir=record_dir,
            version=str(data["version"]), home=str(data["home"]),
            port=int(data["port"]), mode=str(data.get("mode", "?")),
            launcher_pid=int(data.get("launcher_pid") or 0),
            launcher_starttime=data.get("launcher_starttime"),
            started_at=str(data.get("started_at", "")),
            host_pid=data.get("host_pid"), host_starttime=data.get("host_starttime"),
            archived_at=data.get("archived_at"),
        )
    except (KeyError, TypeError, ValueError):
        return None


def scan_records(paths: dcfg.Paths) -> tuple[list[Instance], list[Path]]:
    """扫描运行记录根目录。返回（可解析的实例, 认不出的目录）。"""
    instances: list[Instance] = []
    unknown: list[Path] = []
    if not paths.record_root.is_dir():
        return instances, unknown
    for entry in sorted(paths.record_root.iterdir()):
        if not entry.is_dir() or entry.name == dcfg.RECORD_HISTORY_NAME:
            continue
        inst = _read_instance(entry)
        if inst is None:
            unknown.append(entry)
        else:
            instances.append(inst)
    return instances, unknown


def archive_instance(paths: dcfg.Paths, record_dir: Path, why: str) -> Path | None:
    """把一条记录搬进 历史/（**不删** —— 崩溃现场最需要留档）。"""
    if not record_dir.is_dir():
        return None
    paths.record_history.mkdir(parents=True, exist_ok=True)
    stamped = datetime.now().isoformat(timespec="seconds")
    inst = _read_instance(record_dir)
    if inst is not None:
        inst.archived_at = stamped
        _write_instance(inst)
    else:
        (record_dir / "archived-at.txt").write_text(
            f"archived_at={stamped}\nwhy={why}\n", encoding="utf-8")
    target = paths.record_history / record_dir.name
    n = 1
    while target.exists():
        target = paths.record_history / f"{record_dir.name}.{n}"
        n += 1
    os.replace(record_dir, target)
    # `当前` 若正指着这条刚归档的记录，就把链接删掉 —— 它的语义是"指向活着的那个"，
    # 留个悬空链接只会让人以为还有实例活着 ✗
    link = paths.record_root / "当前"
    try:
        if link.is_symlink() and link.resolve() == target.resolve():
            link.unlink()
    except OSError:
        pass
    return target


def reconcile(paths: dcfg.Paths, quiet: bool = False) -> tuple[int, int]:
    """惰性对账：把死掉的记录搬进 历史/。返回（归档数, 认不出的目录数）。

    为什么是「惰性」而不是退出钩子：后台模式下 launcher 起完即退，**没人看着 host**；
    被 SIGKILL 的也来不及挂钩子。所以统一在「启动第一步」与「--status」时对账 ——
    一个机制同时处理正常退出、崩溃、强杀、断电四种情况。
    **顺序很要紧**：对账在前、建目录在后；这同时也防住了跨 boot 的同名覆盖。
    """
    archived = 0
    instances, unknown = scan_records(paths)
    for inst in instances:
        if inst.alive():
            continue
        pid, _ = inst.representative()
        archive_instance(paths, inst.dir, why=f"pid {pid} 已不在")
        archived += 1
        if not quiet:
            say(f"  · 归档 {inst.dir.name}（{inst.version} 端口 {inst.port}，pid {pid} 已不在）")
    for entry in unknown:
        archive_instance(paths, entry, why="无法解析 instance.json")
        archived += 1
        if not quiet:
            say(f"  · 归档 {entry.name}（无有效 instance.json）")
    return archived, len(unknown)


def _when_of(entry: Path) -> tuple[str, datetime | None]:
    """一条归档的（来源说明, 归档时刻）。优先 instance.json 的 archived_at。"""
    inst = _read_instance(entry)
    if inst is not None and inst.archived_at:
        try:
            return "instance.json", datetime.fromisoformat(inst.archived_at)
        except ValueError:
            pass
    marker = entry / "archived-at.txt"
    if marker.is_file():
        for line in marker.read_text(encoding="utf-8").splitlines():
            if line.startswith("archived_at="):
                try:
                    return "archived-at.txt", datetime.fromisoformat(line.split("=", 1)[1])
                except ValueError:
                    break
    parsed = dcfg.parse_record_dir_name(entry.name)
    if parsed is not None:
        return "目录名（回落到启动时刻）", parsed[0]
    return "未知", None


def history_entries(paths: dcfg.Paths) -> list[tuple[Path, str, datetime | None]]:
    result: list[tuple[Path, str, datetime | None]] = []
    if not paths.record_history.is_dir():
        return result
    for entry in sorted(paths.record_history.iterdir()):
        if not entry.is_dir():
            continue
        source, when = _when_of(entry)
        result.append((entry, source, when))
    return result


def expired_history(paths: dcfg.Paths,
                    ttl_days: int) -> list[tuple[Path, str, datetime]]:
    cutoff = datetime.now() - timedelta(days=ttl_days)
    out: list[tuple[Path, str, datetime]] = []
    for entry, source, when in history_entries(paths):
        if when is not None and when < cutoff:
            out.append((entry, source, when))
    return out


# ═══════════════════════════════════════════════════════════════════
#  目标解析（--stop / --status 共用）—— 严格优先级，绝不猜
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Target:
    port: int
    source: str
    instance: Instance | None


def find_instance(paths: dcfg.Paths, *, port: int | None = None,
                  version: str | None = None) -> Instance | None:
    instances, _ = scan_records(paths)
    for inst in instances:
        if port is not None and inst.port != port:
            continue
        if version is not None and inst.version != version:
            continue
        return inst
    return None


def resolve_target(args, paths: dcfg.Paths, config: dcfg.LauncherConfig) -> Target:
    """1) --port N（永远可用，不做推导）
       2) --try V / --version V（查记录；**查不到即报错退出 4，绝不回落 free_port()**）
       3) 都不给（主实例 = 配置里的 main_port）
    """
    if args.port is not None:
        return Target(args.port, f"--port {args.port}",
                      find_instance(paths, port=args.port))

    want = args.try_version or args.version
    if want:
        inst = find_instance(paths, version=want)
        if inst is None:
            die(f"找不到 {want} 的运行记录：{paths.record_root}/ 下没有它\n"
                "   可能原因：① 它以【前台】方式起过，而那个终端已退出（前台记录随退出归档）；\n"
                "             ② 从没起过；③ 版本号写错。\n"
                "   先看有哪些实例：  ./start-web.py --status\n"
                "   或按端口直接定位：./start-web.py --port N --stop\n"
                "   绝不会退回去猜一个空闲端口 —— 那正是旧实现会误杀无关进程的原因。",
                EXIT_NO_RECORD)
        return Target(inst.port, f"记录 {want}", inst)

    return Target(config.main_port, "主实例（当前配置派生）",
                  find_instance(paths, port=config.main_port))


# ═══════════════════════════════════════════════════════════════════
#  --status
# ═══════════════════════════════════════════════════════════════════

def report_instance(port: int, label: str) -> bool:
    pid = pid_on_port(port)
    if pid is None:
        say(f"  {label} 端口 {port}: 未监听")
        return False
    say(f"  {label} 端口 {port}: 监听中 (pid={pid})")
    try:
        blob = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        say(f"      （读不到 /proc/{pid}/environ，跳过环境复核）")
        return True
    pairs: dict[str, str] = {}
    for item in blob.split(b"\0"):
        key, sep, value = item.partition(b"=")
        if sep:
            pairs[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")
    for key in ("DSH_HOME", "DSH_VERSION", "DSH_HARNESS_DIR"):
        if key in pairs:
            say(f"      ✓ {key}={pairs[key]}")
    residual = [k for k in ("DSH_SHELL", "DSH_SESSION_ID", "DSH_WEB_URL") if k in pairs]
    if residual:
        say(f"      ✗ 有 {len(residual)} 个继承身份残留（{', '.join(residual)}）"
            " —— 说明环境净化没生效，报告给我")
    else:
        say("      ✓ 无继承身份残留")
    return True


def show_url(port: int, inst: Instance | None) -> None:
    log = (inst.dir / "web.log") if inst is not None else None
    text = ""
    if log is not None and log.is_file():
        text = log.read_text(encoding="utf-8", errors="replace")
    matched = re.search(rf"http://127\.0\.0\.1:{port}/\?token=[A-Za-z0-9_-]+", text)
    say("")
    if matched:
        say("  访问地址（复制到浏览器，务必带 token，否则 401）：")
        say(f"    {matched.group(0)}")
    else:
        say("  ⚠ 日志里还没有 token —— 冷启可能要再等几秒。")
        if log is not None:
            say(f"      日志：{log}")


def human_size(size: int) -> str:
    val = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if val < 1024 or unit == "GiB":
            return f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} GiB"


def trace_inventory_status(paths: dcfg.Paths) -> None:
    """取证日志库存（CPU 上只 stat 磁盘）—— 「不许静默占磁盘空间」的那一半。

    刻意**不碰 MariaDB**：启动器的诊断路径必须离线可用（停机那一刻，
    网络与数据库可能正好都不可用）。真正的库存明细、滞后与两档清理在
    `tools/dsh-trace-ingest.py`（它懂游标，也只有它该懂游标）。
    """
    head2("取证日志库存（离线统计）")
    scratch = paths.harness / ".dsh-scratch"   # `_scratch` 的继任者（2026-10-11 退役）
    groups = [
        ("草稿区遗留 sink（已退役结构）", [scratch / "fetch-trace.log"]),
        ("草稿区旧 per-port 目录", sorted(scratch.glob("trace-*/fetch-trace.log"))),
        ("运行记录里（随记录 TTL 归档/GC）",
         sorted(paths.record_root.glob("*/fetch-trace.log"))
         + sorted(paths.record_history.glob("*/fetch-trace.log"))),
    ]
    total = 0
    for label, files in groups:
        live = [f for f in files if f.is_file()]
        size = sum(f.stat().st_size for f in live)
        total += size
        say(f"  {label:<34} {human_size(size):>10}（{len(live)} 份）")
    say(f"  {'合计':<34} {human_size(total):>10}")
    say("  明细与清理：")
    say("    python3 tools/dsh-trace-ingest.py --status          # 库存 + 游标滞后（要 DB）")
    say("    python3 tools/dsh-trace-ingest.py --trim  --apply   # 第一档：回收磁盘，留证据")
    say("    python3 tools/dsh-trace-ingest.py --purge --apply   # 第二档：连库里的证据一起扔")
    say("  · 草稿区里非日志的余项未统计（不由启动器管）：du -sh .dsh-scratch/* 看明细")


def ops_daemon_status(paths: dcfg.Paths) -> None:
    """报告运维守护的状态（**按需挂载的调试工具**，缺席是正常的）。

    为什么这一行重要：把守护改成手动之后，「没人起它」会成为常态 ——
    那么**它的缺席必须是可见的**，否则就是从「有人记」变成「静默没人记」。
    顺带照出「环境冻结」那个陷阱：守护是常驻进程，它带着**挂上去那一刻**的环境，
    不会跟着版本切换走（实测 2026-10-08：pid 602 带着 v0.1.7 的环境跑了 3.9 天，
    完整跨过 0.1.7 → 0.2.0 切换）。
    """
    head2("运维守护（按需挂载的调试工具，不自动起）")
    daemons: list[tuple[int, str, dict[str, str]]] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = entry.joinpath("cmdline").read_bytes().replace(
                b"\0", b" ").decode("utf-8", "replace").strip()
        except OSError:
            continue
        if "dsh-ops-daemon.sh" not in cmdline:
            continue
        env: dict[str, str] = {}
        try:
            for item in entry.joinpath("environ").read_bytes().split(b"\0"):
                key, sep, value = item.partition(b"=")
                if sep:
                    env[key.decode("utf-8", "replace")] = value.decode(
                        "utf-8", "replace")
        except OSError:
            pass
        daemons.append((int(entry.name), cmdline, env))

    instances, _ = scan_records(paths)
    current = instances[0] if instances else None

    if not daemons:
        say("  未运行")
        if current is not None:
            say(f"    挂到当前实例（{current.version}）上：")
            say(f"      bash tools/dsh-ops-daemon.sh --log {current.dir / 'fetch-trace.log'}")
        else:
            say("    挂到某个实例上："
                "bash tools/dsh-ops-daemon.sh --log <记录目录>/fetch-trace.log")
        say("    它不在场时：数据不会丢（游标在 MariaDB，晚挂能补全），")
        say("                但**实时报警会漏**（哨兵只看挂载之后的增量）。")
        return

    for pid, cmdline, env in daemons:
        say(f"  运行中 pid={pid}")
        say(f"    {cmdline}")
        version = env.get("DSH_VERSION")
        home = env.get("DSH_HOME")
        if version:
            say(f"    它带着的环境：DSH_VERSION={version}  DSH_HOME={home or '（无）'}")
            if current is not None and version != current.version:
                say(f"    ⚠ 与当前实例（{current.version}）不一致 —— 守护是常驻进程，"
                    "环境冻结在挂上去的那一刻。建议停掉重挂。")
        else:
            say("    它没有继承实例身份（手动挂载的正常状态）")


def do_status(args, paths: dcfg.Paths, config: dcfg.LauncherConfig) -> int:
    head2("对账（把死掉的记录搬进 历史/）")
    archived, _ = reconcile(paths, quiet=False)
    if archived == 0:
        say("  · 无需归档")

    head2("所有实例")
    any_live = report_instance(config.main_port, "主实例       ")
    instances, _ = scan_records(paths)
    for inst in instances:
        if inst.port == config.main_port:
            continue
        if report_instance(inst.port, f"{inst.version:<12}"):
            say(f"      mode={inst.mode}  home={inst.home}")
            say(f"      记录目录={inst.dir}")
        else:
            say("      （记录仍在但端口没人听 —— 会在下次对账时归档）")
        any_live = True
    if not any_live:
        say("  （没有任何实例在监听）")

    ops_daemon_status(paths)
    trace_inventory_status(paths)

    expired = expired_history(paths, config.archive_ttl_days)
    if expired:
        say("")
        say(f"  历史归档里有 {len(expired)} 条已过期（>{config.archive_ttl_days} 天）：")
        say("    ./start-web.py --gc            # 列出（干跑）")
        say("    ./start-web.py --gc --apply    # 真删")

    say("")
    say("  停止方式：")
    say("    · 前台起的 → 回那个终端按 Ctrl+C（SIGINT 直达 host，启动器会打收尾）")
    say("    · 后台起的 → ./start-web.py --version <版本> --stop")
    say("    · 任意     → ./start-web.py --port <端口> --stop")

    target = resolve_target(args, paths, config)
    say("")
    say(f"  本次目标：{target.source} → 端口 {target.port}")
    if pid_on_port(target.port) is not None:
        show_url(target.port, target.instance)
    return EXIT_OK


# ═══════════════════════════════════════════════════════════════════
#  --stop
# ═══════════════════════════════════════════════════════════════════

def do_stop(args, paths: dcfg.Paths, config: dcfg.LauncherConfig) -> int:
    target = resolve_target(args, paths, config)
    head2(f"停 端口 {target.port} （目标：{target.source}）")

    pid = pid_on_port(target.port)
    if pid is None:
        say(f"  · 端口 {target.port} 本来就没在监听")
        if target.instance is not None:
            say("  ⚠ 但记录仍在（stale）—— 一并归档")
            archive_instance(paths, target.instance.dir, why="端口无监听")
        return EXIT_OK

    say(f"  → SIGTERM {pid}")
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    for _ in range(TERM_WAIT_S):
        if pid_on_port(target.port) is None:
            break
        time.sleep(1)
    if pid_on_port(target.port) is not None:
        say(f"  ⚠ {TERM_WAIT_S}s 未退出，升级 SIGKILL")
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        time.sleep(2)
        if pid_on_port(target.port) is not None:
            say("  ✗ 端口仍占用，请人工检查")
            return EXIT_REFUSE
        say("  ✓ 已强杀")
    else:
        say("  ✓ 已退出")

    # 「谁的儿子谁抱回家」：后台模式连带收掉 launcher 包装进程，不留孤儿。
    # 前台模式不这么做 —— 那个进程正是持终端、把 SIGINT 转给同组 node 的角色，
    # 而前台实例的正常停止方式是 Ctrl+C，不是 --stop。
    inst = target.instance
    if inst is not None and inst.mode == "background" and is_alive(
            inst.launcher_pid, inst.launcher_starttime):
        say(f"  → 一并收掉 launcher 包装进程 {inst.launcher_pid}（后台模式，避免留孤儿）")
        try:
            os.kill(inst.launcher_pid, signal.SIGTERM)
        except OSError:
            pass

    if inst is not None:
        archive_instance(paths, inst.dir, why="--stop")
        say(f"  ✓ 记录已归档（{inst.dir.name}）")
    return EXIT_OK


# ═══════════════════════════════════════════════════════════════════
#  --gc（删除 —— 与对账严格分界：自动的只搬不删，删的必须显式）
# ═══════════════════════════════════════════════════════════════════

def do_gc(args, paths: dcfg.Paths, config: dcfg.LauncherConfig) -> int:
    ttl = config.archive_ttl_days
    head2(f"运行记录归档清理（保留 {ttl} 天，自归档时刻起算）")
    entries = history_entries(paths)
    expired = expired_history(paths, ttl)
    total_bytes = 0
    for entry, _src, _when in expired:
        for item in entry.rglob("*"):
            try:
                if item.is_file():
                    total_bytes += item.stat().st_size
            except OSError:
                pass

    say(f"  归档总数 : {len(entries)}")
    say(f"  已过期   : {len(expired)}")
    say(f"  占用     : {total_bytes / 1024 / 1024:.1f} MiB（仅过期项）")
    if not expired:
        say("  ✓ 没有过期项，无需清理")
        return EXIT_OK

    for entry, source, when in expired:
        say(f"    · {entry.name}  归档于 {when:%Y-%m-%d %H:%M}（{source}）")

    if not args.apply:
        say("")
        say("  这是【干跑】—— 什么都没删。确要删除：")
        say("      ./start-web.py --gc --apply")
        return EXIT_OK

    removed = 0
    for entry, _source, _when in expired:
        try:
            shutil.rmtree(entry)
            removed += 1
        except OSError as exc:
            say(f"  ✗ 删不掉 {entry}：{exc}")
    say("")
    say(f"  ✓ 已删除 {removed}/{len(expired)} 条")
    return EXIT_OK if removed == len(expired) else EXIT_REFUSE


# ═══════════════════════════════════════════════════════════════════
#  启动门序列（必须在开跑之前逐道通过）
# ═══════════════════════════════════════════════════════════════════

def guard_base_home(paths: dcfg.Paths, info: dcfg.VersionInfo) -> None:
    """门 0 · 基座 ↔ home 配套断言（数据驱动，见 定案 D18）。

    为什么需要：版本与 home 名是两个独立真相源。2026-09-26 那次翻车
    （插件禁用风暴 + 「对话全空」）就是只改了版本、home 没跟上，
    于是 0.1.7 基座去加载 0.1.5 的 profile —— 门把那条教训变成断言。
    """
    if not paths.home_dir.is_dir():
        die(f"home 不存在：{paths.home_dir}\n"
            "   若这是 --try 的新版本，先准备一份同名 home：从现有 home 整体复制一份"
            "（cp -a），再按需要对它做迁移。\n"
            "   ⚠️ 新旧 home 必须各自独立 —— 绝不能共用同一个索引库路径"
            "（每个索引路径只能由一个进程持有）。")
    profile = paths.home_dir / "profiles" / "web" / "cordis.patch.yml"
    if not profile.is_file():
        die(f"找不到 {profile}")
    text = profile.read_text(encoding="utf-8", errors="replace")
    missing = [m for m in info.required_markers if m not in text]
    if missing:
        die(f"基座 {paths.version} 要求 profile 具备这些标记，但 {paths.home_name} 里没有：\n"
            f"   {missing}\n"
            "   这正是 2026-09-26 翻车的组合（新基座 + 旧 home 配置）—— 拒绝启动。\n"
            f"   声明来源：{paths.version_info_file} 的 [profile] required_markers")
    say(f"✓ 基座↔home：{paths.version} + {paths.home_name}")


def guard_path_leak(paths: dcfg.Paths) -> None:
    """门 1 · 路径自检：本实例绝不能读另一个 home 的配置。

    实证教训：副本会继承指向旧 home 的绝对路径，其中 session-query-sqlite 会让
    两个进程抢同一个 SQLite 索引库（规则：每个索引路径只能由一个进程持有）。

    ⚠️ bash 原版（start-web.sh:375-384）这道自检是**结构性死检查**：
       它 `grep -rl` 拿的是**文件名**，再用 `grep -v "/$HOME_NAME/"` 过滤 ——
       而候选文件全在当前 home 内，文件名必然含 `/<HOME_NAME>/`，故**永远返回空**。
       2026-10-08 实测复刻确认（绝对路径下 LEAK 恒为空）。
    本移植改成**内容层面**判定，且只认【绝对路径】而不是「提到了某个 home 名」：
       实测本 home 的配置里提到 dsh-domus-0.1.7-rc.2 / 0.1.5-rc.2 各一次，
       但那是注释里的散文，不是路径 —— 按名字判会把现役实例挡在门外。
    """
    own = f"{paths.harness}/{paths.home_name}"
    pattern = re.compile(re.escape(str(paths.harness)) + _LEAK_TAIL)
    candidates = [paths.home_dir / "profiles" / "web" / "cordis.patch.yml"]
    patches = paths.home_dir / "patches"
    if not patches.is_dir():
        # bash 原版这里只点名一个硬编码文件，并用 2>/dev/null 吞掉缺失；
        # 本移植改成 glob，并把「目录不存在」报出来（缺失即报错，不静默跳过）。
        die(f"找不到 patches 目录：{patches}")
    candidates.extend(sorted(patches.glob("*.yml")))
    candidates.extend(sorted(patches.glob("*.yaml")))

    leaks: list[str] = []
    for path in candidates:
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(content.splitlines(), start=1):
            for matched in pattern.finditer(line):
                found = matched.group(0)
                if found == own or found.startswith(own + "/"):
                    continue
                leaks.append(f"{path}:{lineno}\n       {found}")

    if leaks:
        say("")
        say("❌ 配置里指向了【别的】home 的绝对路径：")
        for item in leaks:
            say(f"     {item}")
        say("   为什么是硬错：两个实例会抢同一个 SQLite 索引库"
            "（每个索引路径只能由一个进程持有）。")
        die("拒绝启动。")


def guard_prereqs(paths: dcfg.Paths, port: int) -> None:
    """门 2 · 前置自检：检出存在 / 已构建 / 端口空闲。"""
    if not paths.checkout_dir.is_dir():
        die(f"基座检出不存在：{paths.checkout_dir}")
    dist_index = paths.checkout_dir / "apps" / "web" / "dist" / "index.html"
    if not dist_index.is_file():
        die(f"基座未构建（缺 {dist_index}）——先 cd {paths.checkout_dir} && pnpm run build")
    if port_listening(port):
        say(f"❌ 端口 {port} 已被占用：")
        say(port_line(port))
        say(f"   停法：./start-web.py --stop --port {port}")
        raise SystemExit(EXIT_REFUSE)


# ═══════════════════════════════════════════════════════════════════
#  环境组装
# ═══════════════════════════════════════════════════════════════════

def load_secrets(launcher_dir: Path) -> tuple[dict[str, str], list[str]]:
    """加载 LLM 凭据：**环境优先，回落密钥文件**；两处都没有则**拒绝启动**。

    ⚠️ 本函数**绝不打印值** —— 只回报「每个凭据来自哪里、多长」。
       用户红线（2026-10-08）：「注意不要把 key 读出来，这玩意真是生产环境」。

    为什么环境优先：轮换或临时覆盖时 `export` 一句就生效，不必改文件 ——
    与 `bin/dsh` 的 `:=` 是同一优先级约定。

    文件格式：`NAME=value`，支持 `#` 注释与空行，值两端引号会被剥掉。
    **不做变量展开** —— 密钥文件该是能直接照着读的，不该有第二层解释。
    """
    report: list[str] = []
    from_file: dict[str, str] = {}
    path = launcher_dir / SECRETS_FILE_NAME
    if path.is_file():
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name = name.strip()
            if name:
                from_file[name] = value.strip().strip('"').strip("'")
    else:
        report.append(f"⚠ 找不到凭据文件 {path} —— 只能靠环境变量")

    secrets: dict[str, str] = {}
    for name in SECRET_NAMES:
        env_value = os.environ.get(name, "")
        if env_value:
            secrets[name] = env_value
            report.append(f"{name}: 来自环境变量（{len(env_value)} 字符）")
        elif from_file.get(name):
            secrets[name] = from_file[name]
            report.append(f"{name}: 来自 {SECRETS_FILE_NAME}（{len(from_file[name])} 字符）")
        else:
            die(f"凭据 {name} 没配：既不在环境变量里，也不在 {path} 里。\n"
                "   配法二选一：\n"
                f"     · 写进 {path}（一行 NAME=value）\n"
                f"     · 或 export {name}=… 再启动（临时覆盖走这条）")
    return secrets, report


def build_instance_env(paths: dcfg.Paths, record_dir: Path) -> None:
    """声明实例身份 → 环境净化 → 启动门 → 注入自家 preload 与 bin/。就地改 os.environ。

    ⚠️ 顺序不可换：preload 与 PATH 的注入**都在净化之后** ——
       先注入等于白注入（会被 sanitize 剥掉）。
    """
    # 身份声明（必须在净化之前）
    os.environ["DSH_HARNESS_DIR"] = str(paths.harness)
    os.environ["DSH_VERSION"] = paths.version
    os.environ["DSH_HOME"] = str(paths.home_dir)
    os.environ["DSH_TRACE_LOG"] = str(record_dir / "fetch-trace.log")
    os.environ["DSH_H1_MODE_FILE"] = str(record_dir / "h1-mode")

    before = dict(os.environ)
    if denv.sanitize(quiet=True) != 0:
        raise SystemExit(EXIT_DIRTY)
    after = dict(os.environ)

    # env-diff：只记键名与长度，**不记值**（净化前那份环境里有 API key）
    rows = ["# 净化改动了哪些环境变量 —— 只记键名与长度，不记值"]
    for key in sorted(set(before) | set(after)):
        a, b = before.get(key), after.get(key)
        if a == b:
            continue
        left = "（无）" if a is None else f"{len(a)} 字符"
        right = "（删除）" if b is None else f"{len(b)} 字符"
        rows.append(f"{key}: {left} → {right}")
    (record_dir / "env-diff.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")

    if denv.gate() != 0:
        raise SystemExit(EXIT_DIRTY)

    # ── 凭据注入 ────────────────────────────────────────────────────────
    # ⚠️ 这里**曾经是死代码**：移植时把两个常量定义了却从没注入，而旧 bash 版是
    #    `export` 的 —— 于是新启动器起的实例里，只有调用方 shell 恰好 export 过的
    #    那个 key，`DEEPSEEK_API_AMICI_MEI` **次次缺席**。2026-10-08 实测发现。
    #    （教训：端口移植时，`source → return → save → get → render` 每一跳都要确认，
    #      「定义了」不等于「用上了」。）
    # ⚠️ 刻意放在**净化之后**：净化目前不碰 DEEPSEEK_*，但万一将来它的规则扩展到
    #    凭据，注入的 key 不会被自己的净化剥掉。
    secrets, secret_report = load_secrets(paths.launcher_dir)
    os.environ.update(secrets)
    head2("凭据来源（只报来源与长度，不报值）")
    for line in secret_report:
        say("  " + line)

    own = os.environ.get("NODE_OPTIONS", "")
    os.environ["NODE_OPTIONS"] = (
        f"{own} --import file://{paths.harness}/tools/dsh-fetch-trace.mjs"
        f" --import file://{paths.harness}/tools/dsh-force-h1.mjs")
    os.environ["PATH"] = f"{paths.harness}/bin:{os.environ.get('PATH', '')}"


def guard_proxy(paths: dcfg.Paths) -> None:
    """门 4 · 代理守卫：代理会被装成进程级全局 dispatcher，改道所有 fetch()。"""
    marker = re.compile(r"^[ \t]*(export[ \t]+)?(https?|all)_proxy[ \t]*=", re.IGNORECASE)
    for envfile in (paths.home_dir / ".env", paths.checkout_dir / ".env"):
        if not envfile.is_file():
            continue
        for line in envfile.read_text(encoding="utf-8", errors="replace").splitlines():
            if marker.match(line):
                die(f"{envfile} 里有生效的代理变量"
                    " → DSH 内所有 fetch() 会被改道报 TRANSPORT")
    for name in denv.DSH_PROXY_VARS:
        os.environ.pop(name, None)


def guard_cloudflared(paths: dcfg.Paths) -> None:
    """门 5 · cloudflared 二进制兜底（postinstall 产物，pnpm 一动就没）。"""
    target = (paths.home_dir / "profiles" / "web" / "node_modules"
              / "cloudflared" / "bin" / "cloudflared")
    staged = paths.harness / "tools" / "cloudflared-linux-amd64.staged"
    if not os.access(target, os.X_OK) and staged.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(staged, target)
        os.chmod(target, 0o755)
        say("ℹ️  cloudflared 缺失，已从暂存件补回")


def run_guard(name: str, cmd: list[str], record_dir: Path) -> int:
    """跑一道护栏脚本：输出落盘到 guards/<name>.txt，并原样回显。"""
    guards = record_dir / "guards"
    guards.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    body = proc.stdout + proc.stderr
    (guards / f"{name}.txt").write_text(
        f"# {' '.join(cmd)}\n# 退出码: {proc.returncode}\n\n{body}", encoding="utf-8")
    if body.strip():
        say(body.rstrip())
    return proc.returncode


def guard_ui_patches(paths: dcfg.Paths, record_dir: Path, python: str) -> None:
    """门 7 · UI 补丁护栏：把「每次升级都要重打 markdown 补丁」变成自动的。

    为什么需要它（2026-10-08 查实）：这类补丁改的是**基座检出的源码** ⇒
    **升级 = 新检出 = 补丁消失**。以前靠文档里一份「版本升级立即排查清单」手工重打，
    而用户**大量依赖 markdown 语法输入** ⇒ 每次升级都得重做一遍。

    与 `guard_cloudflared` 同构（预存件 + 开机幂等安装），只是「预存件」换成了
    `补丁/<slug>/manifest.toml` + `.patch`，并多了一层**上游漂移核对**：
    核对不过就**不打** —— 宁可这次不渲染，也不打出行为错误的补丁
    （少传参数会把 `/` 引用与 skill chip 的点击弄哑）。

    退出码约定与 `guard_patch_layers` 相同：
      0 = 已就绪（或已自动补上）/ 1 = 上游漂移，需人工重写（**大声报，但不挡开机**）
      其它 = 护栏自身出错 → 放行并告警（一个护栏 bug 不该把 DSH 锁死在门外）
    """
    rc = run_guard("ui_patches",
                   [python, str(paths.harness / "tools" / "dsh-ui-patches.py"),
                    "--checkout", str(paths.checkout_dir), "--apply"],
                   record_dir)
    if rc == 0:
        return
    if rc == 1:
        say("  ⚠ 有 UI 补丁因**上游漂移**未能应用 —— 不挡开机，但这次它不会生效"
            "（用户消息的 Markdown 渲染会缺）。人工重写提示见 guards/ui_patches.txt。")
        return
    say(f"  ⚠ UI 补丁护栏自身退出码 {rc} —— 放行（护栏 bug 不该把 DSH 锁死在门外）")


def guard_patch_layers(paths: dcfg.Paths, record_dir: Path, python: str) -> None:
    """门 6 · 补丁层护栏：重复 id 会让 cordis 静默丢层。

    退出码既非 0 也非 1 → 放行并告警：一个护栏 bug 不该把 DSH 锁死在门外。
    """
    rc = run_guard("check_patch_layers",
                   [python, str(paths.harness / "tools" / "check_patch_layers.py"),
                    "--profile", "web"], record_dir)
    if rc == 0:
        return
    if rc == 1:
        die("补丁层有重复 id，拒绝启动（见上）")
    say(f"⚠ 补丁层护栏自身异常（退出码 {rc}）—— 放行，请人工看一眼")


def guard_profile_links(paths: dcfg.Paths, record_dir: Path, python: str) -> None:
    """门 6b · profile 链接护栏：让「起不来」在启动前就报出来。

    退出码契约（判据与两级严重度的定义全在 check-profile-links.py 头部注释里）：
      0 = 通过（可能有 WARN）
      1 = FAIL（分叉或断链）→ 拒绝启动
      其它 = 护栏自身异常 → **放行并告警**
        理由：一个护栏 bug 不该把 DSH 锁死在门外（dsh 起不来就问不了 AI，
        那是停机卡要对付的最坏情形）。护栏自己是离线的，拒启动时给出的修复
        命令不依赖 DSH 运行 —— 这一点是「敢拦」的前提。
    """
    rc = run_guard("check_profile_links",
                   [python, str(paths.harness / "tools" / "check-profile-links.py"),
                    "--home", str(paths.home_dir), "--show", "5"], record_dir)
    if rc == 0:
        return
    if rc == 1:
        die("profile 链接层有问题（分叉或断链，见上）"
            " —— 会静默骗人或让 DSH 起不来，拒绝启动。\n"
            f"     修：{python} tools/repair-profile-links.py --apply   （断链重连，默认干跑）\n"
            f"         {python} tools/check-profile-links.py --fix      （只重建内容相同的硬链接）")
    say(f"⚠ profile 链接护栏自身异常（退出码 {rc}）—— 放行，请人工看一眼")


# 门 7（运维守护）**已取消** —— 它的状态由下面的 ops_daemon_status() 报告。
# 它改为「按需挂载的调试工具」：像 F12 —— 出问题或要查什么的时候才挂上，
# 挂在具体的实例上，挂完就关。理由与代价（丢实时报警、不丢数据）写在
# tools/dsh-ops-daemon.sh 的头部注释里。启动器**不再**拉起它。


# ═══════════════════════════════════════════════════════════════════
#  开跑
# ═══════════════════════════════════════════════════════════════════

def spawn_host(paths: dcfg.Paths, port: int, log_handle=None) -> subprocess.Popen:
    """起 host。

    log_handle 给了 → stdout/stderr 直通那个文件（后台模式，没人看着）。
    没给          → 走管道交给调用方搬运（前台模式，要双写）。
    """
    pnpm = shutil.which("pnpm")
    if not pnpm:
        die("PATH 里找不到 pnpm —— 无法启动 host。\n"
            "   净化会把本仓库的 PATH 条目剔掉；本机上 pnpm 来自 /usr/bin/pnpm（corepack）。")
    common = dict(cwd=str(paths.checkout_dir), stdin=subprocess.DEVNULL)
    args = [pnpm, "dsh", "web", "--port", str(port), "--no-open"]
    if log_handle is not None:
        return subprocess.Popen(args, stdout=log_handle, stderr=subprocess.STDOUT, **common)
    return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            bufsize=0, **common)


def normalize_rc(rc: int | None) -> int:
    """python 对「被信号杀死」报负值（SIGINT → -2），shell 惯例是 128+n（→ 130）。

    不换算的话 sys.exit(-2) 会被截成 254 —— 退出码契约就坏了。
    """
    if rc is None:
        return EXIT_INT
    return 128 - rc if rc < 0 else rc


def new_record(paths: dcfg.Paths, port: int, background: bool) -> Instance:
    """先建 .starting-* 目录（此时 host pid 还不存在，指纹与名字都拿不到）。"""
    record_dir = paths.record_root / f"{dcfg.STARTING_PREFIX}{os.getpid()}"
    record_dir.mkdir(parents=True, exist_ok=True)
    inst = Instance(
        dir=record_dir, version=paths.version, home=paths.home_name, port=port,
        mode="background" if background else "foreground",
        launcher_pid=os.getpid(), launcher_starttime=proc_starttime(os.getpid()),
        started_at=datetime.now().isoformat(timespec="seconds"))
    _write_instance(inst)
    return inst


def write_identity(paths: dcfg.Paths, record_dir: Path, port: int) -> None:
    """把实例身份写进记录目录，并让 `运行记录/当前` 指向它。

    ── 为什么必须有这个文件 ────────────────────────────────────────────────
    MCP 服务拿到的环境是**被净化过的**：harness 的 `buildChildEnv()` 就一句
        return { ...scrubbedParentEnv(), ...extra }
    ⟹ `DSH_*` 一个都传不过去 ✗。而 MCP 服务确实需要知道"我在伺候哪个实例"：
      · melquiades 的 `resolve_dsh_home()` 第 ①b 档要 `DSH_HARNESS_DIR` +
        `DSH_VERSION` 才能派生 home；缺了就一路回落到 `~/.dsh`（不存在）
        ⟹ 收割静默 `files=0/0`（它自己的注释：「看起来像没新数据，实则断流」）
      · 取证日志要有实例归属，否则症状哨兵看的是**片面信号**
    ⟹ 所以把身份落成**文件**，让 MCP 管家（`mcp启动器.py`）去读。

    ── 格式为什么是 KEY=value 而不是 TOML ──────────────────────────────────
    它本质就是一份 env ✓：shell 能 `. file`、python 三行能解析、别的工具也认这个
    约定 ✓ —— 而 TOML 会逼着每个消费者都带一个解析器 ✗。

    ⚠️ `当前` 指向**最近一次 finalize 的实例**；归档时若正指着它就把链接删掉
       （留个悬空链接只会让人以为还有实例活着 ✗）。
    """
    body = {
        "DSH_VERSION": paths.version,
        "DSH_HARNESS_DIR": str(paths.harness),
        "DSH_HOME": str(paths.home_dir),
        "DSH_TRACE_LOG": str(record_dir / "fetch-trace.log"),
        # 下面三个不是给 MCP 用的，是给人排查用的
        "LAUNCHER_PORT": str(port),
        "LAUNCHER_RECORD": str(record_dir),
        "WRITTEN_AT": datetime.now().isoformat(timespec="seconds"),
    }
    lines = ["# 活实例身份 —— 由 start-web.py 写，供 MCP 管家与其他工具读。",
             "# ⚠️ 别手改：每次开机重写。", ""]
    lines += [f"{k}={v}" for k, v in body.items()]
    (record_dir / "identity.env").write_text("\n".join(lines) + "\n", encoding="utf-8")

    link = paths.record_root / "当前"
    tmp = paths.record_root / f".当前.tmp{os.getpid()}"
    try:
        if tmp.is_symlink() or tmp.exists():
            tmp.unlink()
        os.symlink(str(record_dir), str(tmp))
        os.replace(tmp, link)       # 原子换链接（rename 换的是链接本身，不是它的目标）
    except OSError as exc:
        say(f"  ⚠ 建 `当前` 符号链接失败（{exc}）—— 身份文件已写好，不影响开机")


def finalize_record(paths: dcfg.Paths, inst: Instance, port: int) -> Instance | None:
    """拿到 host pid 后把目录改名成最终名字（原子）并把身份写全。"""
    host_pid = pid_on_port(port)
    if host_pid is None:
        return None
    inst.host_pid = host_pid
    inst.host_starttime = proc_starttime(host_pid)
    final_dir = paths.record_root / dcfg.record_dir_name(
        datetime.fromisoformat(inst.started_at), host_pid)
    if final_dir != inst.dir:
        candidate = final_dir
        n = 1
        while candidate.exists():
            candidate = final_dir.with_name(f"{final_dir.name}.{n}")
            n += 1
        os.replace(inst.dir, candidate)
        inst.dir = candidate
    _write_instance(inst)
    # 身份落盘 + `当前` 符号链接 —— 必须在**改名之后**（链接要指向最终目录名）
    write_identity(paths, inst.dir, port)
    return inst


def announce(paths: dcfg.Paths, port: int, is_try: bool, record_dir: Path) -> None:
    say("")
    say("  临时试版本 —— **不是主运行版本**" if is_try else "  主运行版本")
    say(f"    基座     = {paths.version}")
    say(f"    home     = {paths.home_name}")
    say(f"    端口     = {port}  → http://localhost:{port}")
    say(f"    记录     = {record_dir}")


def run_background(args, paths: dcfg.Paths, config: dcfg.LauncherConfig, port: int,
                   inst: Instance, is_try: bool) -> int:
    """脱离终端：关掉终端不带走它，代价是看不到日志、也不知道死活。"""
    announce(paths, port, is_try, inst.dir)
    head2("后台启动")
    log_path = inst.dir / "web.log"
    log = log_path.open("wb")
    child = spawn_host(paths, port, log_handle=log)

    started = False
    for _ in range(WAIT_S):
        if pid_on_port(port) is not None:
            started = True
            break
        time.sleep(1)
    if not started:
        log.flush()
        log.close()
        child.poll()
        say(f"  ✗ {WAIT_S}s 内端口未监听 —— 启动失败。日志尾部：")
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]:
            say(f"    | {line}")
        archive_instance(paths, inst.dir, why="启动失败：端口未监听")
        return EXIT_REFUSE

    inst = finalize_record(paths, inst, port) or inst
    # ⚠️ 目录一旦改名，任何【先前绑定的路径】全部失效 —— 必须重算。
    #    文件句柄不受影响（改名不动 inode），所以 log 继续可写。
    #    2026-10-08 实测踩到：不重算则后面 grep token 时 FileNotFoundError。
    log_path = inst.dir / "web.log"
    say(f"  ✓ 端口 {port} 已监听")
    say(f"  ✓ 已记录运行实例：{inst.dir}")
    say(f"    停止方式：./start-web.py --version {paths.version} --stop")

    for _ in range(TOKEN_WAIT_S):
        if "token=" in log_path.read_text(encoding="utf-8", errors="replace"):
            break
        time.sleep(1)
    log.close()
    do_status(args, paths, config)
    say("")
    say("  ⚠ 后台模式下你看不到日志、也不知道它死没死 —— 想盯着就别加 --background。")
    return EXIT_OK


def run_foreground(args, paths: dcfg.Paths, config: dcfg.LauncherConfig, port: int,
                   inst: Instance, is_try: bool) -> int:
    """前台持有：字节级双写日志，Ctrl+C 结束。"""
    announce(paths, port, is_try, inst.dir)
    log_path = inst.dir / "web.log"
    say("")
    say(f"  日志双写：本终端 + {log_path}")
    say("  结束方式：Ctrl+C —— SIGINT 直达 host，不需要再跑 --stop")
    say("  host 一退出本命令就返回，你会立刻看到退出码")
    say("")
    say("  ───── 以下为 host 输出 ─────")
    say("")

    log = log_path.open("wb")
    child = spawn_host(paths, port)
    assert child.stdout is not None
    fd = child.stdout.fileno()
    finalized = False

    def drain() -> None:
        while True:
            try:
                chunk = os.read(fd, READ_CHUNK)
            except OSError:
                return
            if not chunk:
                return
            _emit(chunk, log)

    try:
        while True:
            try:
                ready, _, _ = select.select([fd], [], [], 0.5)
            except InterruptedError:
                continue
            if ready:
                chunk = os.read(fd, READ_CHUNK)
                if chunk:
                    _emit(chunk, log)
                    continue
            if not finalized and pid_on_port(port) is not None:
                finalized = True
                inst = finalize_record(paths, inst, port) or inst
                # ⚠️ 目录改名后先前绑定的 log_path 失效，必须重算（句柄仍可写）
                log_path = inst.dir / "web.log"
                say(f"  已记录运行实例：{inst.dir}")
                say("  （--status 能看到它；停止方式仍是 Ctrl+C）")
                say("")
            if child.poll() is not None:
                drain()
                break
    except KeyboardInterrupt:
        # Ctrl+C：host 在同一前台进程组，也收到了 SIGINT，正在退出。
        # ⚠️ 这里**不**给 SIGINT 设 SIG_IGN（那会跨 execve 继承，把 host 对 Ctrl+C
        #    弄成免疫）。改为带超时等待：既保证收尾信息打得出来，又不会挂死。
        say("")
        say("  收到 Ctrl+C —— 等 host 收尾…（再按一次可不再等）")
        try:
            child.wait(timeout=FINALIZE_TIMEOUT_S)
        except KeyboardInterrupt:
            say("  不再等 —— host 仍在运行，日志见下")
        except subprocess.TimeoutExpired:
            say(f"  ⚠ {FINALIZE_TIMEOUT_S}s 内 host 未退出 —— 可能在收尾，也可能忽略了 SIGINT")
    finally:
        log.flush()
        log.close()

    rc = normalize_rc(child.poll())   # 仍活着（拒绝再等）时 poll() 为 None → 130

    head2(f"端口 {port} 已退出")
    if rc == EXIT_INT:
        say("  停止方式 : Ctrl+C（SIGINT）—— **这是正常停止路径**，前台实例就是这么停的")
    say(f"  退出码 : {rc}")
    say(f"  日志   : {log_path}")
    if rc not in (0, EXIT_INT):
        say("")
        say(f"  非零退出（{rc}）—— 日志尾部 20 行：")
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]:
            say(f"    | {line}")
    archive_instance(paths, inst.dir, why=f"退出码 {rc}")
    return rc


def home_is_live(home: Path) -> int | None:
    """这个 home 上有没有活着的 host 进程？返回 pid，没有返回 None。

    ⚠️ **为什么不看运行记录**（第一版就是这么写错的）：记录是**新启动器**的机制，
    而实例可能是**旧启动器**起的 —— 它写的是 `_scratch/instances/`，新结构里没有记录。
    2026-10-08 实测：`commit_home` 的守卫因此失效，在一个运行中的实例上做了真提交
    （502 文件 / 118 万行）—— 那正是它要防的事（可能抓到半个 zstd 帧）。

    所以直接读 `/proc`，判据与任何记录机制无关：
      · 该进程 environ 里有 `DSH_HOME=<本 home>`（精确整项匹配，不是子串）
      · 且 argv[0] 的 basename 是 `node`（排掉 shell：我的命令行里也会出现
        `bin.ts web` 这样的字样，用 argv[0] 就把这种自匹配挡掉了）
      · 且 argv 里同时有 ` web` 与（`bin.ts` 或 `dsh`）
    """
    want = f"DSH_HOME={home}"
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            environ = entry.joinpath("environ").read_bytes()
            cmdline = entry.joinpath("cmdline").read_bytes()
        except OSError:
            continue
        try:
            env_items = [x for x in environ.decode("utf-8", "replace").split("\0") if x]
        except (UnicodeDecodeError, ValueError):
            continue
        if want not in env_items:
            continue
        argv = [x for x in cmdline.split(b"\0") if x]
        if not argv or not os.path.basename(argv[0]).startswith(b"node"):
            continue
        joined = b" ".join(argv)
        if b" web" in joined and (b"bin.ts" in joined or b"dsh" in joined):
            return int(entry.name)
    return None


def commit_home(paths: dcfg.Paths, record_dir: Path) -> None:
    """开机前把本实例 home 的**对话记录**提交进它**自己**的 git 仓库。

    时机不是随便挑的（2026-10-08 用户定案：「先提交再开机」）：
      session 是 append-only 的 `.jsonl.zstd`，**实例运行中**提交可能抓到
      **半个 zstd 帧** —— 那正是对话迁移那次踩过的「最后一个会话打不开」。
      开机前那一刻，上一次运行已经结束，所有帧都是完整的。

    为什么 home 要自成仓库（用户定案）：**这样 tar.zstd 一份就能回档** ——
      仓库与工作树在同一个目录里，一次归档就是一份自足的、可恢复的快照。

    三条纪律（这套机制的全部风险面，都显式写在这里）：
      ① 本 home **已有活实例** → 跳过，并**说明为什么跳**（文件可能正在被追加）
      ② 不是 git 仓库 / 没有改动 → 什么都不做（不产生空提交）
      ③ git 失败 → **告警但继续开机**：一个备份失败不该把 DSH 锁死在门外
         （与护栏那条同一哲学：dsh 起不来就问不了 AI，那是最坏情形）
    """
    home = paths.home_dir
    if not (home / ".git").is_dir():
        say(f"  · {paths.home_name} 不是 git 仓库 —— 跳过对话备份")
        return

    instances, _ = scan_records(paths)
    live = [i for i in instances if i.home == paths.home_name and i.alive()]
    pid_live = home_is_live(home)
    if live or pid_live:
        pid = pid_live or (live[0].host_pid or live[0].launcher_pid)
        say(f"  · 本 home 已有活实例（pid {pid}）—— **跳过对话备份**"
            "（session 可能正在被追加，提交会抓到半个帧）")
        return

    def run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    try:
        dirty = run(["git", "-C", str(home), "status", "--porcelain"], 300)
    except (OSError, subprocess.SubprocessError) as exc:
        say(f"  ⚠ 查 git 状态失败（{exc}）—— 跳过对话备份，继续开机")
        return
    if dirty.returncode != 0:
        say(f"  ⚠ git status 非零退出（{dirty.returncode}）—— 跳过对话备份，继续开机")
        return
    if not dirty.stdout.strip():
        say("  · home 仓库没有改动 —— 无需备份")
        return

    message = (f"开机前自动备份（{paths.version} ｜ {paths.home_name} ｜ "
               f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")
    trace: list[str] = []
    for cmd in (["git", "-C", str(home), "add", "-A"],
                ["git", "-C", str(home), "commit", "-q", "-m", message]):
        try:
            proc = run(cmd, 1800)          # 首次提交可能很大（几百 MB），给足时间
        except subprocess.TimeoutExpired:
            say(f"  ⚠ 对话备份超时（{' '.join(cmd[3:])}）—— **继续开机**")
            return
        trace.append(f"$ {' '.join(cmd)}\n{proc.stdout}{proc.stderr}")
        if proc.returncode != 0:
            (record_dir / "home-commit.txt").write_text("\n".join(trace), encoding="utf-8")
            say(f"  ⚠ 对话备份失败（rc={proc.returncode}）—— **继续开机**，"
                f"详见 {record_dir / 'home-commit.txt'}")
            return

    stat = run(["git", "-C", str(home), "show", "--stat", "--oneline", "HEAD"], 120)
    (record_dir / "home-commit.txt").write_text("\n".join(trace) + "\n" + stat.stdout,
                                                encoding="utf-8")
    summary = [ln.strip() for ln in stat.stdout.splitlines() if "changed" in ln]
    say(f"  ✓ 已备份对话记录 → {paths.home_name} 自己的仓库"
        f"（{summary[-1] if summary else '已提交'}）")


def run_instance(args, paths: dcfg.Paths, config: dcfg.LauncherConfig, port: int,
                 is_try: bool) -> int:
    inst = new_record(paths, port, args.background)
    # 「先提交、再开机」—— 此刻上一次运行已结束，session 帧都是完整的
    head2("开机前备份对话记录（home 自己的 git 仓库）")
    commit_home(paths, inst.dir)
    build_instance_env(paths, inst.dir)
    guard_proxy(paths)
    guard_cloudflared(paths)
    python = sys.executable
    guard_patch_layers(paths, inst.dir, python)
    guard_ui_patches(paths, inst.dir, python)
    guard_profile_links(paths, inst.dir, python)
    if args.background:
        return run_background(args, paths, config, port, inst, is_try)
    return run_foreground(args, paths, config, port, inst, is_try)


# ═══════════════════════════════════════════════════════════════════
#  参数解析
# ═══════════════════════════════════════════════════════════════════

class _Parser(argparse.ArgumentParser):
    """argparse 默认用退出码 2 报参数错，而本启动器的 2 是「环境不干净」。

    这个撞车必须显式拆开：参数错一律 3（与 bash 版一致，停机卡与工具按这套码行事）。
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"❌ 参数错误：{message}（-h 看用法）", file=sys.stderr)
        raise SystemExit(EXIT_ARGS)


def build_parser() -> _Parser:
    parser = _Parser(
        prog="start-web.py", add_help=True,
        description="DSH 启动器 —— 主运行版本 / 临时试新版本 / 起停状态 / 运行记录。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="退出码: 0 正常结束 / 1 前置拒绝 / 2 环境不干净 / 3 参数错误 / 4 找不到实例记录")
    parser.add_argument("--try", dest="try_version", metavar="V",
                        help="临时试新版本（不碰配置文件；端口自动避让）")
    parser.add_argument("--version", dest="version", metavar="V",
                        help="按版本号停（查运行记录）")
    parser.add_argument("--port", dest="port", type=int, metavar="N", help="指定端口")
    parser.add_argument("--stop", action="store_true", help="停实例")
    parser.add_argument("--status", action="store_true", help="列出全部实例 + 环境复核")
    parser.add_argument("--background", action="store_true", help="脱离终端")
    parser.add_argument("--gc", action="store_true",
                        help="清理过期的运行记录归档（默认干跑）")
    parser.add_argument("--apply", action="store_true", help="--gc 时真删（否则只列出）")
    return parser


def main(argv: list[str] | None = None) -> int:
    assert_interpreter()
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)

    if args.apply and not args.gc:
        die("--apply 只能与 --gc 一起用（对账的搬移是自动的、无损的；删除必须显式）",
            EXIT_ARGS)
    if args.stop and args.status:
        die("--stop 与 --status 不能同时给", EXIT_ARGS)
    if args.try_version and args.version:
        die("--try 与 --version 不能同时给（前者是起，后者是停）", EXIT_ARGS)

    try:
        config = dcfg.load_config()
        is_try = bool(args.try_version)
        paths = dcfg.derive(config, args.try_version if is_try else None)
        info = dcfg.load_version_info(paths.version)
        for warning in dcfg.verify_upstream(paths, info):
            print(f"⚠ {warning}", file=sys.stderr)
    except dcfg.ConfigError as exc:
        die(str(exc))

    # ── 查询模式先返回 ─────────────────────────────────────────────
    if args.status:
        return do_status(args, paths, config)
    if args.stop:
        return do_stop(args, paths, config)
    if args.gc:
        return do_gc(args, paths, config)

    # ── 启动路径 ───────────────────────────────────────────────────
    head2("对账（对账在前、建目录在后）")
    archived, _ = reconcile(paths, quiet=False)
    if archived == 0:
        say("  · 无需归档")

    if args.port is not None:
        port = args.port
    elif is_try:
        chosen = free_port(config.try_port_from, 60)
        if chosen is None:
            die(f"在 {config.try_port_from}–{config.try_port_from + 59} 里找不到空闲端口，"
                "请用 --port 指定")
        port = chosen
    else:
        port = config.main_port

    guard_base_home(paths, info)
    guard_path_leak(paths)
    guard_prereqs(paths, port)
    return run_instance(args, paths, config, port, is_try)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断（Ctrl+C）", file=sys.stderr)
        sys.exit(130)
