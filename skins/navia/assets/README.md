<!-- ⚠️ 本文件由工作区的导出管线生成（tools/export-dsh-collection.py）。
     要改内容请改生成器里的常量 —— **在本仓手改会在下次导出时被覆盖**（2026-10-11 已踩过一次）。 -->
# assets —— 自备图放这里

需要两个文件（文件名必须一致，CSS 里写死了）：

- `sidebar.webp` —— 侧栏底图，**竖版**（`background-position: center top`）
- `main.webp` —— 主区底图，**横版**（`background-position: center`）

缺了也能用：CSS 里 `url()` 的上一行有兜底色（侧栏 `#e8e2da` / 主区 `#201c15`），
图不存在时自动退化为纯配色主题。

本仓**零位图**：作者的底图有版权，不随仓发布。
