#!/usr/bin/env python3
"""从真实 DSH 会话里抽取正文（assistant text 块），生成渲染基准用的数据集。

· 正文：**原样保留**（含 TeX 公式、表格、代码块），这是被测对象。
· reasoning：**只记录真实字符数**，不复制内容。测试页按该长度生成确定性占位文本 ——
  reasoning 的渲染成本只取决于「字符数 + 段落结构」，与具体文字无关，
  因此测量等价，同时避免把模型的思考链搬进浏览器与公开报告。

用法： python3 extract-render-fixtures.py <session.v4.jsonl.zstd> <out.json> [最多块数]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


def main() -> int:
    src, out = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    p = subprocess.run(['zstd', '-dc', src], capture_output=True, timeout=600)
    if p.returncode != 0:
        print('解压失败', file=sys.stderr)
        return 2

    messages = []
    for raw in p.stdout.split(b'\n'):
        if not raw.strip():
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if d.get('type') != 'assistant/message':
            continue
        content = ((d.get('data') or {}).get('message') or {}).get('content') or []
        text_parts, reason_chars = [], 0
        for b in content:
            if not isinstance(b, dict):
                continue
            s = b.get('text')
            if not isinstance(s, str):
                continue
            if b.get('type') == 'text':
                text_parts.append(s)
            elif b.get('type') == 'reasoning':
                reason_chars += len(s)
        text = '\n\n'.join(text_parts)
        if not text.strip():
            continue
        messages.append({'text': text, 'reasoningChars': reason_chars})

    if limit:
        messages = sorted(messages, key=lambda m: -len(m['text']))[:limit]

    doc = {
        # 会话 UUID 不进公开产物：只留前 8 位便于人工追溯
        'source': (os.path.basename(os.path.dirname(src))[:17] + '…（已脱敏）'),
        'note': ('正文为真实内容；reasoningChars 为真实字符数，'
                 '测试页据此生成占位文本（性能等价，不含思考链原文）'),
        'count': len(messages),
        'totalTextChars': sum(len(m['text']) for m in messages),
        'totalReasoningChars': sum(m['reasoningChars'] for m in messages),
        'messages': messages,
    }
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(',', ':'))

    print(f'  写入 {out}')
    print(f'  消息 {doc["count"]} 条  正文 {doc["totalTextChars"]:,} 字符  '
          f'reasoning {doc["totalReasoningChars"]:,} 字符')
    print(f'  JSON {os.path.getsize(out)/1024:.0f} KB')
    return 0


if __name__ == '__main__':
    sys.exit(main())
