#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""皮肤背景图主色探测：判断该配白天还是夜间模式。

用法: python3 skin-color-probe.py <图片路径>...

判断依据（对皮肤背景的实际意义）:
- 感知亮度 luma = 0.299R + 0.587G + 0.114B（0-255）
- 暗部占比 (luma<80) 高 -> 背景偏暗 -> UI 需要浅色文字 -> 夜间模式
- 亮部占比 (luma>200) 高 -> 背景偏亮 -> UI 需要深色文字 -> 白天模式
- 平均亮度落中间 -> 看主色倾向, 输出数据供人判断
- 透明像素 (alpha<128) 直接跳过: 立绘透明区露出的是 UI 底色, 不算背景
"""
import sys
import collections

from PIL import Image


def probe(path: str) -> None:
    img = Image.open(path)
    img = img.convert("RGBA")
    w, h = img.size

    # 降采样到最长边 ~96px 内, 统计量足够且快
    scale = max(w, h) / 96.0
    if scale > 1.0:
        img = img.resize((max(1, int(w / scale)), max(1, int(h / scale))), Image.LANCZOS)

    px = img.load()
    lumas: list[int] = []
    buckets: dict[tuple[int, int, int], list[tuple[int, int, int]]] = collections.defaultdict(list)
    dark = bright = total = 0
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if a < 128:  # 跳过透明像素
                continue
            total += 1
            luma = int(0.299 * r + 0.587 * g + 0.114 * b)
            lumas.append(luma)
            if luma < 80:
                dark += 1
            elif luma > 200:
                bright += 1
            buckets[(r // 32, g // 32, b // 32)].append((r, g, b))

    if total == 0:
        print(f"{path}: 全透明, 无有效像素")
        return

    mean_luma = sum(lumas) / len(lumas)
    dark_pct = dark / total
    bright_pct = bright / total

    # 主色 top5: 桶内均值作代表色
    top = sorted(buckets.items(), key=lambda kv: -len(kv[1]))[:5]
    n = sum(len(v) for _, v in top)

    print(f"== {path}  ({w}x{h})")
    print(f"   有效像素占比: {total / (img.width * img.height):.0%} (透明已跳过)")
    print(f"   平均亮度: {mean_luma:.0f}/255   暗部(<80): {dark_pct:.0%}   亮部(>200): {bright_pct:.0%}")
    print("   主色 (白字/黑字对比度, WCAG 简算):")
    for (br, bg, bb), vals in top:
        r = sum(v[0] for v in vals) // len(vals)
        g = sum(v[1] for v in vals) // len(vals)
        b = sum(v[2] for v in vals) // len(vals)
        share = len(vals) / n
        rel = ((0.299 * r + 0.587 * g + 0.114 * b) / 255.0) ** 2.2
        cw = (1.05) / (rel + 0.05)      # 白字对比度
        cb = (rel + 0.05) / (0.05)      # 黑字对比度
        okw = "✓" if cw >= 4.5 else "✗"
        okb = "✓" if cb >= 4.5 else "✗"
        print(f"     #{r:02x}{g:02x}{b:02x}  rgb({r},{g},{b})  占比 {share:.0%}  白字 {cw:.1f}:1 {okw} / 黑字 {cb:.1f}:1 {okb}")

    # 决策
    if dark_pct >= 0.35:
        verdict = "夜间模式 (暗部占比高, 白字才看得清)"
    elif bright_pct >= 0.35:
        verdict = "白天模式 (亮部占比高, 黑字更清晰)"
    elif mean_luma < 128:
        verdict = "倾向夜间 (平均亮度偏暗), 建议实测"
    else:
        verdict = "倾向白天 (平均亮度偏亮), 建议实测"
    print(f"   建议: {verdict}")
    print()


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for p in sys.argv[1:]:
        probe(p)


if __name__ == "__main__":
    main()
