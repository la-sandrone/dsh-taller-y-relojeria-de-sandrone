#!/usr/bin/env python3
"""统计 DSH 会话里**实际会被渲染的内容**的 Markdown / TeX 密度，并估算 DOM 节点数。

口径说明
--------
· 只取 `assistant/message` → `data.message.content[]` 里 type 为 `text` 的块（正文）。
  刻意**不取** `data.stream`（那是同一内容的流式数组，会重复计数）。
  正文之外的 `reasoning` 块另计，因为前端可能折叠渲染。
· TeX 计数：$$…$$ 逐个、$…$ 逐个、\begin{…} 环境逐个。
· DOM 估算是**模型**，不是实测，系数写在 EST 里，可替换。

用法： python3 profile-render-load.py <file.jsonl[.zstd]> [...]
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import defaultdict

# DOM 节点估算系数（每单位产生多少元素节点）——保守取值
EST = {
    'para': 3.0,       # 一个段落
    'table_row': 6.0,  # 一行表格（含 td）
    'code_line': 1.2,  # 代码块每行
    'list_item': 3.0,  # 一个列表项
    'heading': 2.0,
    'tex': 60.0,       # ★ 一个 KaTeX 公式（默认双份 mathml+html，几十个 span）
}

RE_DISPLAY = re.compile(r'\$\$(.+?)\$\$', re.S)
RE_INLINE = re.compile(r'(?<!\$)\$(?!\$)([^$\n]{1,400}?)\$(?!\$)')
RE_ENV = re.compile(r'\\begin\{([a-zA-Z*]+)\}')
RE_CODE = re.compile(r'```')


def open_lines(path: str):
    if path.endswith('.zstd'):
        p = subprocess.run(['zstd', '-dc', path], capture_output=True, timeout=300)
        data = p.stdout
    else:
        data = open(path, 'rb').read()
    return data.split(b'\n')


def analyze(path: str) -> dict:
    stat = defaultdict(float)
    counts = defaultdict(int)
    text_chars = 0
    reasoning_chars = 0

    for raw in open_lines(path):
        if not raw.strip():
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if d.get('type') != 'assistant/message':
            continue
        msg = (d.get('data') or {}).get('message') or {}
        content = msg.get('content')
        if not isinstance(content, list):
            continue
        for blk in content:
            if not isinstance(blk, dict):
                continue
            t = blk.get('type')
            s = blk.get('text')
            if not isinstance(s, str):
                continue
            if t == 'reasoning':
                reasoning_chars += len(s)
                continue
            if t != 'text':
                continue

            text_chars += len(s)
            counts['text_blocks'] += 1

            disp = RE_DISPLAY.findall(s)
            counts['tex_display'] += len(disp)
            stripped = RE_DISPLAY.sub('\x00', s)
            inl = RE_INLINE.findall(stripped)
            counts['tex_inline'] += len(inl)
            envs = RE_ENV.findall(s)
            counts['tex_env'] += len(envs)

            counts['code_fence'] += len(RE_CODE.findall(s))
            counts['table_row'] += sum(1 for ln in s.split('\n')
                                       if ln.lstrip().startswith('|') and ln.count('|') >= 2)
            counts['list_item'] += sum(1 for ln in s.split('\n')
                                       if re.match(r'^\s*([-*+]|\d+\.)\s', ln))
            counts['heading'] += sum(1 for ln in s.split('\n') if ln.lstrip().startswith('#'))
            counts['para'] += max(1, len([p for p in s.split('\n\n') if p.strip()]))

    tex_total = counts['tex_display'] + counts['tex_inline'] + counts['tex_env']
    dom = (counts['para'] * EST['para'] + counts['table_row'] * EST['table_row']
           + counts['code_fence'] * EST['code_line'] * 8
           + counts['list_item'] * EST['list_item'] + counts['heading'] * EST['heading']
           + tex_total * EST['tex'])
    return {'stat': stat, 'counts': counts, 'tex_total': tex_total, 'dom': dom,
            'text_chars': text_chars, 'reasoning_chars': reasoning_chars,
            'size': os.path.getsize(path)}


def report(path: str) -> None:
    r = analyze(path)
    c = r['counts']
    dom_tex = r['tex_total'] * EST['tex']
    print(f'═══ {os.path.basename(os.path.dirname(path))[:44]}  ({r["size"]/1048576:.2f} MB)')
    print(f'  正文 text 块      : {c["text_blocks"]} 个，{r["text_chars"]:,} 字符')
    print(f'  reasoning 字符    : {r["reasoning_chars"]:,}')
    print(f'  ★ TeX 公式        : {r["tex_total"]:,} 个'
          f'（display {c["tex_display"]:,} / inline {c["tex_inline"]:,} / env {c["tex_env"]:,}）')
    print(f'    表格行 {c["table_row"]:,}   代码块 {c["code_fence"]//2:,}  '
          f'列表项 {c["list_item"]:,}   标题 {c["heading"]:,}   段落 {c["para"]:,}')
    print(f'  ★ 估算 DOM 节点   : {r["dom"]:,.0f}')
    print(f'      其中公式贡献   : {dom_tex:,.0f}（{100 * dom_tex / r["dom"]:.1f}%）')
    print(f'  每 1000 字符产节点 : {r["dom"] / max(1, r["text_chars"] / 1000):.0f}')
    print()


if __name__ == '__main__':
    for p in sys.argv[1:]:
        report(p)
