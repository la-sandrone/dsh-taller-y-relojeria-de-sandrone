# 速查：search_OMNIA 与 message_context

文件名: 用户笔记/检索/速查-search_OMNIA与message_context.md
摘要: 两个新工具的照抄式用法。目标读者是「要在一堆历史素材里找一句话」的场景
      （写长篇小说 / 设定集 / 世界观）。原理与实测见 `MariaDB-CJK全文检索-落地.md` 第十一节。

---

## 一、一句话分工

| 工具 | 干什么 | 什么时候用 |
|---|---|---|
| `search_OMNIA` | 一次搜完 **草稿纸 + 会话正文 + 压缩摘要**（向量/FULLTEXT/LIKE 三路） | 不知道东西落在哪，先定位 |
| `message_context` | 按 guid 展开某条会话正文的前后文 | 命中会话正文后，看当时怎么定的 |
| `draftpad_find` | 草稿纸精细检索（clue/keyword/condition/rerank/expand） | 已知在草稿纸，且要精确 |
| `archive_find` | 只看压缩摘要 | 只想找「被压掉的上文」 |

**先 `search_OMNIA` 定位，再用对应的精细工具深入**——它不替代后者。

---

## 二、`search_OMNIA`

```
search_OMNIA(query, limit=5, sources="", modes="", per_source_limit=0)
```

| 参数 | 含义 | 缺省 |
|---|---|---|
| `query` | 查询串。中文走 unigram+bigram，**单字也能搜** | — |
| `limit` | **每一路各取多少条**（不是最终返回数） | 5 |
| `sources` | `draftpad,messages,compactions` 逗号分隔 | 全搜 |
| `modes` | `vector,fulltext,like` 逗号分隔 | 三路全开 |
| `per_source_limit` | 覆盖每路取数（一般不用传） | 跟随 limit |

### 关键：返回条数会多于 limit，这是有意的

三路各取 limit → 去重 → **剩多少给多少**，不截断。
`limit=5` 通常拿回 20 出头；`limit=3` 约 15 条；`limit=10` 约 40 条。
这是为了不漏掉「只有某一路命中、分数偏低」的独特结果。

### 照抄示例

```
# 找某个设定/名词在哪儿出现过
search_OMNIA("硅钢片 1000K")

# 找一句旧措辞（记得大概，不确定原话）
search_OMNIA("废热回收 火用")

# 只搜会话正文（草稿纸里肯定没有的东西）
search_OMNIA("MALFORMED_RESPONSE", sources="messages")

# 只要最快的精确匹配（关掉向量和 LIKE）
search_OMNIA("loadThrough", modes="fulltext")

# 想多捞一些，别嫌多
search_OMNIA("月球周期", limit=15)
```

### 返回怎么读

```
命中 23 条 | 按源: 草稿纸=8, 会话正文=10, 压缩摘要=5 | 各路原始命中: vector=10, fulltext=9, like=9

[1] 「草稿纸」score=1.006 路由=vector/fulltext/like
    笔记 #614 · 【口径修正+复算核对·2026-09-16】… · 2026-09-16 16:24:15
    【零·为什么要落这一条】…
```

- **`score`**：融合分，只在本次结果内可比，不要跨查询比。
- **`路由`**：`vector/fulltext/like` 表示三路都命中（可信度最高）；单词 `like` 表示只有字面兜底命中（可能是旧措辞）。
- **按源分布**：一眼看出东西主要落在哪，决定下一步用哪个精细工具。

### 能力边界（必须知道）

- **会话正文没有向量**：`dsh_message` 只走 FULLTEXT + LIKE。语义（模糊）召回由草稿纸和压缩摘要承担。
  所以「记得意思但想不起词」这类查询，别指望它从会话正文里捞出来。
- **压缩摘要有损**（约 35:1）：命中后要走 `archive_expand` → `archive_fetch` 回查原文，别拿摘要当原文回答。
- `like` 在会话正文上是 14 万行全表扫（约 1–3 秒）。嫌慢就 `modes="vector,fulltext"`。

---

## 三、`message_context`

```
message_context(guid, before=3, after=3, max_chars=1200)
```

| 参数 | 含义 | 缺省 |
|---|---|---|
| `guid` | `search_OMNIA` 的「会话正文」命中里带（64 位十六进制） | — |
| `before` / `after` | 前 / 后各取几条（按 line_no 排序的相邻记录） | 3 / 3 |
| `max_chars` | 每条正文截断字符 | 1200 |

### 照抄示例

```
# 看命中那条前后发生了什么
message_context("0c94c08344760d1d…", before=5, after=5)

# 只要前后各一条，快速判断
message_context("<guid>", before=1, after=1)

# 正文很长（工具输出），多给点
message_context("<guid>", before=2, after=2, max_chars=4000)
```

### 返回怎么读

```
会话 session-caaa597c-… · 目标 L2622 · 取回 7 条（前 3 / 后 3）

  L2617 [tool/call/tool-arg] · 2026-10-25 07:51:02
   {"ids": "1875", "text": "【2026-10-25 09:0x 新增 search_OMNIA…"}
▶ L2622 [assistant/message/text] role=assistant · 2026-10-25 07:51:10
   做完了，而且离线验证通过——…
```

- `▶` 是目标行。
- `[事件类型/正文种类]` 告诉你这是工具调用、工具输出、还是模型正文——
  **`tool/call` + `tool/result` 连着看，能还原「当时到底做了什么」**。
- `role=tool` 的是工具输出，不是人说的话，别当结论引用。

### 一个已知的坑（已修，但要知道）

早先的版本按 `line_no ± N` 取窗口，**只返回 1 条**——因为 `line_no` 是事件物理行号，
抄录器跳过 chunk 家族后行号是稀疏的。现在改成「按 line_no 排序取相邻 N 条记录」。
如果你看到「取回 1 条」而 before/after 都非零，说明版本没更新（需重启 MCP）。

---

## 四、几条经验

1. **中文单字也能搜**（bigram 索引 + `min_token_size=1`）。搜「绘」会命中「绘图」「绘画」「绘制」。
2. **查询串别写长句**。`"那个关于月球周期的口径修正到底怎么定的"` 不如 `"月球周期 口径 修正"`——
   bigram 是 AND，词越多命中的交集越小。
3. **`-`、`%` 等特殊字符**在 LIKE 路会被转义，不会出错；但在全文路会被当分隔符（`search-plus` → `search` + `plus`），
   这种精确标识符建议 `modes="like"`。
4. **数据新鲜度**：抄录器 60 秒一轮，本场会话延迟 <1 分钟。刚说的话可能还搜不到。
