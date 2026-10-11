#!/usr/bin/env python3
"""统计 DSH 会话导出 jsonl 里各事件类型的字节占比，定位「体积大头」。

用法： python3 profile-session-bytes.py <file.jsonl> [more.jsonl ...]
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict


def iter_raw(path: str):
    """逐行产出原始字节。支持 .jsonl 与 .jsonl.zstd（后者流式解压）。"""
    if path.endswith('.zstd'):
        import subprocess
        proc = subprocess.run(['zstd', '-dc', path], capture_output=True, timeout=600)
        if proc.returncode != 0:
            raise SystemExit(f'zstd 解压失败：{path}')
        for raw in proc.stdout.split(b'\n'):
            yield raw
        return
    with open(path, 'rb') as fh:
        for raw in fh:
            yield raw


def profile(path: str) -> None:
    size = os.path.getsize(path)
    by_type = defaultdict(int)
    count = defaultdict(int)
    total = 0
    header_bytes = 0
    for raw in iter_raw(path):
        if not raw.strip():
            continue
        total += len(raw)
        try:
            d = json.loads(raw)
        except ValueError:
            by_type['<解析失败>'] += len(raw)
            count['<解析失败>'] += 1
            continue
        if not isinstance(d, dict):
            # 会话日志里偶尔出现非对象的裸 JSON 行（数字/字符串/数组），
            # 早期版本会在 .get() 上崩掉 —— 单独归类，不中断统计。
            by_type['<非对象行>'] += len(raw)
            count['<非对象行>'] += 1
            continue
        t = d.get('type', '?')
        by_type[t] += len(raw)
        count[t] += 1
        if t == 'request/header':
            header_bytes += len(raw)

    name = os.path.basename(path)
    print(f'═══ {name}')
    print(f'  文件 {size / 1048576:.2f} MB ／ 读入 {total / 1048576:.2f} MB ／ {sum(count.values())} 行')
    print()
    print(f"  {'事件类型':<34}{'行数':>8}{'字节':>14}{'占比':>9}")
    print('  ' + '─' * 66)
    for t, b in sorted(by_type.items(), key=lambda kv: -kv[1])[:14]:
        print(f'  {t:<34}{count[t]:>8}{b:>14,}{100 * b / total:>8.1f}%')
    print('  ' + '─' * 66)
    print(f'  ★ request/header 冗余量：{header_bytes:,} B = {header_bytes / 1048576:.2f} MB'
          f'（占全文 {100 * header_bytes / total:.1f}%）')
    print()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    for p in sys.argv[1:]:
        profile(p)
