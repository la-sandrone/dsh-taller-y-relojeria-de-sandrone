# MariaDB 中文全文检索落地：unigram + bigram

文件名: 用户笔记/检索/MariaDB-CJK全文检索-落地.md
摘要: 在 `melquiades_medicamento` 上把 `dsh_message` 做成可搜中文单字的全文检索。
      记录两个实测事实（`min_token_size` 按字符计、`SET GLOBAL` 静默忽略）、
      方案依据（Lucene CJKBigramFilter）、以及已知限制。
依赖: `<MariaDB-数据目录>\my.ini`（`innodb_ft_min_token_size=1`）
      `dsh_message.body_tokenized` + `ft_body_tokenized`

---

## 〇、一句话

**中文单字、双字、短语全部可搜，查询 20–80 ms，与 `LIKE` 命中数逐条对拍一致。**

```
绘        720   (=LIKE 720)   33 ms   (LIKE 2069 ms)
会话     8187   (=LIKE 8187)  81 ms   (LIKE 1852 ms)
草稿纸   4774   (=LIKE 4774)  74 ms   (LIKE 1945 ms)
绘图工具    11   (=LIKE 11)    26 ms   (LIKE 1961 ms)
```

---

## 一、为什么不是 jieba

既有 `draftpad` 走的是「jieba 分词 + FULLTEXT」。实测它在本机**几乎不可用**：

| 查询 | jieba FULLTEXT | LIKE |
|---|---|---|
| 草稿纸（3 字） | 67 | 67 ✓ |
| 会话（2 字） | **0** | 110 ✗ |
| 绘图（2 字） | **0** | 1 ✗ |
| 绘（1 字） | **0** | 21 ✗ |

根因是 `innodb_ft_min_token_size = 3`：**长度 <3 字符的 token 在索引时被直接丢弃**。

### 两条必须记住的实测事实

1. **`min_token_size` 按【字符】计，不是字节。** 中文单字 3 字节，照样被丢。
2. **`SET GLOBAL innodb_ft_min_token_size=1` 会静默成功但不生效**——它是启动参数。
   只有改 `my.ini` + 重启才有效。这条比报错更危险：命令返回 0，值仍是 3。

## 二、方案：unigram + bigram（不用词典）

依据：Lucene `CJKBigramFilter`（`outputUnigrams=true`）、Elasticsearch 内置 `cjk_bigram`。
学术侧见《Comparing Representations in Chinese Information Retrieval》(SIGIR'98) 与
《Chinese word segmentation and its effect on information retrieval》(2004)：
bigram 与分词效果相当甚至更好，且**不依赖词典**——词典遇到专名、新词、代码标识符会切错。

切分规则（`body_tokenized` 列）：

```
连续汉字串 → 每个字一个 token + 每对相邻字一个 token
              "绘图工具" → 绘 图 工 具 绘图 图工 工具
英文/数字/下划线串 → 原样一个 token
其余字符（标点等）→ 丢弃
```

查询侧（BOOLEAN MODE）：CJK 串取**全部 bigram 做 AND**；单字取 unigram；英文保持原词。

## 三、改动清单

| 位置 | 改动 | 备注 |
|---|---|---|
| `<MariaDB-数据目录>\my.ini` | 加 `innodb_ft_min_token_size = 1` | 备份 `backups/my.ini.bak-20261024-234939` |
| `MariaDB12.3.2` 服务 | 重启（stop 3s / start 2s） | 消费方全是短连接，无影响 |
| `dsh_message` | 加 `body_tokenized MEDIUMTEXT NULL` | `ALGORITHM=INSTANT`，64 ms |
| `dsh_message` | 加 `FULLTEXT INDEX ft_body_tokenized` | `ALGORITHM=INPLACE`，86 s |
| `body_tokenized` | 回填 140,161 行 | 幂等脚本，分批 2000 |
| `melquiades/tokenizer.py` | 新增 `tokenize_cjk_ub()` / `build_cjk_boolean()` | 写入侧与查询侧共用，注释写明依据与前置条件 |
| `melquiades/harvest/message_runner.py` | `INSERT INTO dsh_message` 增加 `body_tokenized` 列 | **改完需重启 MCP 才生效**（stdio，无热加载） |

**规模**：`data=1253 MiB / index=82 MiB`（原 `data=523 MiB`）。正文汉字只占 16.4%
（大量英文与工具输出），所以 unigram+bigram 的 token 总量约 9900 万，比预想小得多。

## 四、工具落点（草稿纸 → 待归位）

验证期脚本先放 `草稿纸与垃圾桶/`，`backfill_tokenized.py` 属**活依赖**，
接抄录器时应迁进 `tools/` 或并入 melquiades。

| 脚本 | 用途 |
|---|---|
| `probe_fulltext_cjk.py` | 三策略探针：jieba / +单字 / +前缀填充 |
| `backfill_tokenized.py` | 幂等回填（base64 通道读正文，绕 CLI 转义层） |
| `verify_cjk_search.py` | FULLTEXT vs LIKE 对拍 + 计时 |
| `verify_tokenizer_consistency.py` | 新函数 vs 已回填值**逐字节比对**（防写入/查询口径打架） |
| `stopword_tfidf.py` | 停止词统计（全量 14 万篇） |

## 五、读正文的两个坑（会咬人）

1. **`mariadb -N --raw` 的输出不能用 `splitlines()` 切**：正文里的 `\x0c`、`\u2028`、
   真实换行都会把一条记录切成多条。首跑把 14 万行算成了 226 万"文档"。
2. **CLI 的 TSV 转义层与 JSON 通道都会被打穿**。最终用
   `REPLACE(TO_BASE64(body), '\n', '')` 走 base64，才稳定。

## 六、已知限制

| 限制 | 表现 | 应对 |
|---|---|---|
| 英文子串搜不到 | `min_token_size` 查不到 `innodb_ft_min_token_size`（105 vs LIKE 230） | 英文标识符查询走 `LIKE` 兜底 |
| 连字符被拆 | `search-plus` → `+search +plus`，AND 后误报 1546 vs 527 | 查询侧改短语 `+"search plus"` |

## 六之二、增量接入（2026-10-25 已改，待重启 MCP 生效）

写入路径已接：

```
harvest/message_runner.py: insert_messages()
    body_tokenized ← tokenizer.tokenize_cjk_ub(body)
```

`message_runner.py` 的 INSERT 已加列，`ON DUPLICATE KEY UPDATE` 也一并更新
`body_tokenized`（覆盖 guid 幂等重写的场景）。

**口径一致性已验证**：用新函数重算 40 条最长正文，与已回填的 `body_tokenized`
**逐字节相同**（`verify_tokenizer_consistency.py`）。这条要定期复查——写入侧与
查询侧口径一旦分叉，症状是「明明有却搜不到」，且不会报任何错。

⚠️ **生效条件**：melquiades 是 stdio MCP 进程，代码改动**不会热加载**。
`body_tokenized` 要等下次 DSH 重启（重新拉起 MCP）后才由抄录器自动填写。
在此之前新增行仍为 NULL，用 `backfill_tokenized.py` 幂等补齐（一次几秒）。

重启后的验证：

```sql
-- 应为 0；若非 0 且持续增长，说明新代码没生效
SELECT COUNT(*) FROM dsh_message WHERE body_tokenized IS NULL;
```

## 七、停止词：数过了，不是杠杆

全量 14 万篇统计（`stopword_tfidf.py`）：token 种类 674,896，总 token 5,265 万。

候选停止词 38 个（`的 是 在 了 与 里 我 有 这 用 把 和 被 但 它 都 上 到 就 已 而 也 你 要 对 个 会 那 后 写 从 可 只 行 为 给 能 时`），
只省 **7.9%** 的出现次数。真正的体积杠杆是「要不要 bigram / 要不要 unigram」，不是停止词。

⚠️ 必须排除 `不`、`无` 等否定词——否则「不支持」与「支持」变成同一个查询。
⚠️ 必须过滤单字母 ASCII（`s` 出现 26 万次、`d` 7.2 万次，是 jieba 切英文的碎片）。

---

## 八、改 `min_token_size` 会波及**所有**旧索引（2026-10-25 连带发现）

`min_token_size` 是**建索引时**读取的参数。改完只影响**将来**新建的索引；
库里已有的 FULLTEXT 索引仍然是旧口径，**必须逐个重建**才生效。

本机受影响清单（13 个索引 / 4 个库）：

| 库.表 | 索引 | 规模 | 处理 |
|---|---|---|---|
| `melquiades.dsh_message` | `ft_body_tokenized` | 140k 行 | ✅ 新建即新口径 |
| `melquiades.draftpad` | `ft_draftpad_content` / `_tokenized` | 1,144 行 | ✅ 已重建（7 s） |
| `melquiades.dsh_compaction` | `ft_compaction_summary` / `_tokenized` | 93 行 | ✅ 已重建（2 s） |
| `memoria.del_hielo.documents_book_chunk` | `idx_ft_chunk_content` / `_tokenized` | **625,705 行 / 1.9+2.1 GB** | ⏳ COPY 重建中（约 30 min） |
| `memoria.documents_chat` / `documents_onenote` | 各 2 个 | 空表 | ✅ 已重建（秒级） |
| `notes_db.notes` | `ft_notes` | 760 行 | ⛔ 无权限（melquiades 只有 SELECT） |
| `chat_pipeline.messages` | `ft_content` | 空表 | ⛔ 无权限 |

### 三个必须记住的操作事实

1. **一条语句里的 `DROP INDEX + ADD INDEX` 会被 MariaDB 优化掉。**
   实测：`ALTER TABLE draftpad DROP INDEX a, ADD FULLTEXT a (...)` 耗时 **0 秒**且不生效
   （定义没变 → 跳过）。**必须分两条 SQL**：先 DROP，提交，再 ADD（7 秒，生效）。

2. **`DROP FULLTEXT INDEX` 走 COPY 算法，不是 INPLACE。**
   小表几乎瞬时；`documents_book_chunk`（15 GB，含 `vector(1024)` + HNSW）实测
   临时表以 **约 9 MB/s** 增长，全量复制约 30 分钟，期间 `state = copy to tmp table`。
   看进度：`ls -la <datadir>/<db>/ | grep sql-alter` 盯 `#sql-alter-*.ibd` 大小。

3. **重建索引只解决「token 进不了索引」，不解决「分词切错」。**
   draftpad 重建后搜「会话」：FULLTEXT 78 vs LIKE 111——差的 33 行是 jieba 把
   「会话」切成了「会 话」。jieba 的切分与用户查询的词边界不一致，这是分词方案的
   固有缺陷，也是 `dsh_message` 改用 unigram+bigram 的原因。
   ⇒ memoria 若要把这 30% 的漏搜补上，得把 `content_tokenized` 用 bigram 重算
   （625,705 行），那是另一件事，不要和"重建索引"混为一谈。

### ⛔ 第四个事实（最贵的一条）：`innodb_ft_cache_size` 会决定大表重建是分钟级还是小时级

`documents_book_chunk` 重建实测 **3 小时 10 分**（00:08 → 03:17），其中：

| 阶段 | 耗时 | 说明 |
|---|---|---|
| DROP（COPY 整表） | 91 min | 15.9 GB + `vector(1024)` + HNSW 一起复制 |
| ADD：copy to tmp table | ~82 min | 再复制一遍 |
| ADD：**Enabling keys** | ~20 min | 建 FULLTEXT 索引本体 |

`Enabling keys` 阶段错误日志持续刷：

```
[Warning] InnoDB: Total InnoDB FTS size 205273693 for the table
`memoria_del_hielo`.`#sql-alter-...` exceeds the innodb_ft_cache_size 67108864
```

**根因**：`my.ini` 里 `innodb_ft_cache_size = 64M`（当时是给批量导入小表配的），
而这张表的 FTS 索引有 **1.7 GB** ⇒ 反复 flush，每次只推进几十 MB。

**下次做同类操作前**：
- 先把 `innodb_ft_cache_size` 调大（重启生效，可设 256M–512M），
- 或者接受它慢，**挑夜间做**。
- 更好的替代：**不要 DROP/ADD，直接 `ALTER TABLE ... FORCE` 或 `OPTIMIZE`** 未必更快
  —— 只要是 FULLTEXT 的 DDL，InnoDB 一律走 COPY。

**代价对比**（这次换来的）：2 字词从 0 命中变成 2375 / 1513 / 21 / 706 条，
查询 20–373 ms。对一个 62 万 chunk 的书库，这个代价值得，但**不能临时起意做**。

---

## 九、官方对「大表 FULLTEXT 构建慢」的建议（2026-10-25 查证并落地）

### 9.1 官方原话

MySQL 8.0 手册 17.6.2.4（MariaDB 的 InnoDB FULLTEXT 与之同源，参数同名同义）：

> 倒排索引被分成**六个辅助索引表**（`fts_*_index_1..6`）以支持**并行**索引创建。
> 默认情况下，**两个线程**对传入文档进行标记化、排序并插入索引表。
> 执行这项工作的线程数可用 `innodb_ft_sort_pll_degree` 配置。
> **在大型表上创建全文索引时，可考虑增加线程数。**

同一节还说明：FULLTEXT 索引通过一个内存缓存批量刷盘，缓存大小由
`innodb_ft_cache_size`（**每表**）控制；缓存满即 flush。缓存越小，flush 越频繁。

### 9.2 本机诊断：12 核机器只用了 2 个线程

重建 `documents_book_chunk` 时（3 小时 10 分）的配置：

| 参数 | 当时 | 12 核机器的合理值 | 后果 |
|---|---|---|---|
| `innodb_ft_sort_pll_degree` | **2**（默认） | 8 | 并行度只有硬件的 1/6 |
| `innodb_ft_cache_size` | 64M | 512M | 日志刷了几百条 `exceeds the innodb_ft_cache_size` |
| `innodb_ft_total_cache_size` | 640M（默认） | 2G | 并发建索引时互相挤 |

### 9.3 已改（2026-10-25 07:20，重启生效）

```ini
innodb_ft_sort_pll_degree = 8
innodb_ft_cache_size      = 512M
innodb_ft_total_cache_size = 2G
```

验证：`SHOW VARIABLES` 已见 `536870912 / 8 / 2147483648`。
备份：`backups/my.ini.bak-20261025-072005-ft-tuned`。

**改参数只影响将来的建索引**，已建好的索引不受影响（也不会变快）——
它是"下次重建的加速器"，不是"现有查询的加速器"。

### 9.4 其他实践（这次没用上，但要知道）

| 实践 | 说明 |
|---|---|
| **先导数据，后建索引** | 批量导入时若有 FULLTEXT，每行都维护索引，慢几个数量级。正确顺序是：建表（无 FULLTEXT）→ 导入 → `ADD FULLTEXT`。我们这次天然满足（表早就有数据）。 |
| **`FTS_DOC_ID` 是隐式列** | 建 FULLTEXT 时 InnoDB 自动加一列；**DROP 索引时它不会被删**（删它要重建表）。所以反复 DROP/ADD 不会反复加列。 |
| **~~`OPTIMIZE TABLE` 未必更快~~（措辞已修正，见 9.4.1）** | ~~只要是 FULLTEXT 的 DDL，InnoDB 一律走 COPY；换命令不改变算法。~~ 准确说法：MariaDB 对 FULLTEXT 的 DDL **一律重建整表**，但算法可以是 INPLACE（允许并发 DML），不是"降级成 COPY"。 |
| **分区表救不了** | MariaDB 不支持在分区表上建 FULLTEXT，别指望靠分区切小重建单元。 |
| **别信 AI 生成的中文教程** | 这次搜到一篇（runebook.dev）明确写「MariaDB 用内置 ngram 解析器」「加 `WITH PARSER ngram`」——**那是 MySQL 的特性，MariaDB 不生效**，正是本文档第 1 节标记为最危险误导的那条。 |

### 9.4.1 为什么「DROP 一个索引」也要复制整表？—— MySQL 与 MariaDB 的根本分歧

这个问题值得单列，因为它决定了「重建该怎么设计」。

**MySQL 8.0 的 Online DDL 矩阵（Table 17.16）**：

| Operation | In Place | Rebuilds Table | Permits Concurrent DML |
|---|---|---|---|
| Dropping an index | **Yes** | **No** | Yes |
| Adding a FULLTEXT index | Yes* | No*（有 `FTS_DOC_ID` 时） | No |

按 MySQL 的设计，删索引是**纯元数据操作**，根本不碰数据。

**MariaDB 的定义完全不同**。它对 `ALGORITHM=INPLACE` 的说明原话是：

> When the `ALGORITHM` clause is set to `INPLACE`… **The table is rebuilt**, which means that
> all of the data is reorganized substantially, and **the indexes are rebuilt**.
> As a result, **the operation is quite expensive**.

也就是说：**MariaDB 的 INPLACE = 重建整表 + 重建索引 + 允许并发 DML**。
它省的是**锁**，不是 **IO**。

**实测佐证**（2026-10-25）：

- 小表（`fts_probe`，2 行）上 `ALTER TABLE ... DROP INDEX ft_c, ALGORITHM=INPLACE`
  **成功、不报错**——所以它不是"不支持 INPLACE 而降级 COPY"；
- 大表（`documents_book_chunk`）上同一条路径，磁盘上出现 **16 GB 的 `#sql-alter-*.ibd`**
  ——这就是整表重写的铁证，耗时 91 分钟。

（我曾误判为"降级 COPY"，此处更正。区别：COPY 全程锁写；INPLACE 允许并发写但照样复制。
`SHOW PROCESSLIST` 里两者都可能显示 `copy to tmp table`，不能据此判断算法。）

**推论**：

| | MySQL | MariaDB |
|---|---|---|
| `ADD FULLTEXT` 不重建表 | 能（有 `FTS_DOC_ID` 时） | **不能** |
| 普通索引 `DROP` 不重建表 | 能 | **不能**（INPLACE 也 rebuild） |
| 大表加/删 FULLTEXT 的代价 | 分钟级 | **小时级，无法绕开** |

所以「换命令让重建变快」在 MariaDB 上是伪命题——`OPTIMIZE` / `DROP+ADD` / `FORCE`
全都落到「重写表」。**唯一能省一趟的是影子表**（见 10.2 修正后的方案）。

### 9.5 下次重建的预期

按 8 线程 + 512M 缓存，同样的 `documents_book_chunk`（15.9 GB / 1.7 GB 索引）
预计从 **3 小时 10 分**降到 **40–70 分钟**（并行度 4 倍 + flush 次数降一个数量级）。
真要重建前，先 `SHOW VARIABLES` 确认三个值，再挑夜间。

---

## 十、两个 MCP 的代码改造（2026-10-25）

### 10.1 melquiades（草稿纸 + 会话正文）—— ✅ 已切并验证

| 文件 | 改动 |
|---|---|
| `tokenizer.py` | 新增 `tokenize_cjk_ub()` / `build_cjk_boolean()`（前文已有） |
| `harvest/message_runner.py` | `dsh_message` 写入带 `body_tokenized`（前文） |
| `db.py` | `_tokenize_cjk()` 由 jieba 改为 `tokenize_cjk_ub`；建表/迁移 DDL 的 `TEXT` → `MEDIUMTEXT` |
| `retrieval.py` | `_fulltext_search`：列选择从 `content`（原文）**改回 `content_tokenized`**，CJK 查询改 `build_cjk_boolean` |

**`retrieval.py` 的旧注释（2026-09-22）被推翻并重写**，原文是：

> jieba 分词列把长串切成 2 字词 ⇒ 全被丢弃 ⇒ `+口径*` = 0 命中 ⇒ 故草稿纸统一用 `content` 列。

现在两个前提都变了（`min_token_size=1` + bigram 切分），分词列重新启用。

**⚠️ `draftpad.content_tokenized` 原为 `TEXT`（65535）**，bigram 让 token 串膨胀
2–3 倍（最长 content 22,116 字符），回填直接报错。已 `ALTER` 为 `MEDIUMTEXT`，
建表 DDL 同步改。**这是新增 token 列时必须先算的一件事**。

**验证（与 LIKE 逐条对拍，全部相等）**：

| 查询 | 改前（jieba） | 改后（bigram） | LIKE |
|---|---|---|---|
| `会话` | 78 | **111** | 111 |
| `绘`（单字） | 搜不到 | **22** | 22 |
| `口径` | — | **706** | 706 |
| `修正` | — | **421** | 421 |

**LIKE 兜底保留不动**（用户明确要求）：草稿纸仅 1,802 行，LIKE 全扫几十毫秒，
按日期倒序兜底比任何索引都可靠。bigram 是"快路"，不是"唯一路"。

### 10.2 memoria-del-hielo（书库 62.5 万 chunk）—— ⏸ 代码已备，回填待窗口

代码改动已完成并验证过语法：
- `src/core/tokenizer.py`：新增同两个函数（**保留**，供回填脚本与下次切换使用）
- `src/core/search.py`：`_book_fulltext` / `_fulltext_search` 两处（**已回滚**）
- `src/importers/*.py` × 3（**已回滚**）

**回滚原因**：`documents_book_chunk` 有 625,705 行 / content 1.93 GB。
直接 `UPDATE content_tokenized` 会触发 FULLTEXT 索引维护，实测 **500 行 14 秒
⇒ 全量约 5 小时**。而代码切成 bigram、数据仍是 jieba 的中间态会让它**搜不到东西**，
所以先把代码退回，保证可用。

**~~正确的切换顺序~~（已废弃）**：

```
✗ 1. DROP 两个 FULLTEXT 索引        -- 91 min
✗ 2. UPDATE 全表 content_tokenized  -- 无索引维护
✗ 3. ADD FULLTEXT 索引             -- 30–60 min
```

**这个方案是错的**，因为第 1 步本身就要求「重写整表 91 分钟」（见 9.4.1：MariaDB 的
INPLACE 也是 rebuild），等于**白白复制一趟数据**。两步合起来要复制表两次。

### 10.2.1 修正方案：影子表（只写一次数据）

```
1. CREATE TABLE documents_book_chunk_new  LIKE 结构但【不带 FULLTEXT/VECTOR 索引】  -- 秒
2. Python 读旧表 content → 算 unigram+bigram → 批量写新表（含 embedding 等其它列） -- 一趟写，40–60 min
3. ALTER TABLE documents_book_chunk_new ADD FULLTEXT ...（8 线程）                -- 30–60 min
   （向量索引同理：ADD VECTOR KEY 也 rebuild，要放这里一次做完）
4. 校验行数 / 抽样对拍
5. RENAME TABLE documents_book_chunk → documents_book_chunk_old,
                documents_book_chunk_new → documents_book_chunk
6. **最后**提交 search.py + importers 的 bigram 改动
7. 与 LIKE 对拍验证；确认后 DROP 旧表
```

关键差别：**数据只搬一次**（第 2 步），索引在目标表上一次建好（第 3 步）。
对比废弃方案要复制表两次（DROP 一次 + ADD 一次），预计从 2.5 小时降到 **1–1.5 小时**。

`tools/backfill-cjk-tokenized.py` 目前是「原地 UPDATE」形态，影子表需要它的
「读旧表 → 写新表」变体（或 `INSERT INTO new SELECT` + 单独回填 token 列）。

**⚠️ 顺序铁律**：第 6 步（提交查询侧代码）必须在第 5 步之后。
反过来就是这次遇到的断裂态——查询用 bigram、数据是 jieba，整库搜不到东西。

**⚠️ 不可在同一张表上「先改数据再建索引」**：只要表上还有 FULLTEXT，
任何 UPDATE 都会维护索引（实测 500 行 14 秒 ⇒ 全量 5 小时）。

**已造成的小偏差**：为测速跑过 500 行（0.08%），它们的 `content_tokenized` 是 bigram
格式。jieba 查询用 `+词*` 前缀匹配，仍能命中其中的 2 字词（bigram 里含该 token），
只有 3 字以上 jieba 词会漏。不影响使用，切换后自然归一。

### 10.3 当前状态（2026-10-25 08:3x）

- **melquiades**：已切 bigram 并验证（Draftpad 对拍全等）。**在跑**。
- **mcp-memoria**：**已在 DSH 侧禁用** —— `profiles/web/cordis.patch.yml` 的
  `mcp-memoria` 条目加了 `disabled: true`（含原因注释）；`mcp服务.toml` 的
  `[services.mcp-memoria]` 段也加了说明（启动器不读 `enabled` 字段，禁用在 DSH 侧）。
  **需要重启 DSH 才生效**。
- memoria 的代码改动：`tokenizer.py` 的新函数**保留**（影子表方案要用）；
  `search.py` + 3 个 importers **已回滚**（保持 jieba 可用态）。
- 恢复 memoria 的条件：影子表切换完成 + 与 LIKE 对拍通过 → 去掉那行 `disabled`。

---

## 十一、`search_OMNIA`：跨源统一检索（2026-10-25 新增）

### 11.1 为什么

写长篇小说/设定集的工作区里，「找一句以前写过的东西」天然跨三处：
**草稿纸**（人写的结论）、**会话正文**（当时怎么讨论的，含工具输出）、
**压缩摘要**（被压掉的上文）。原有 `draftpad_find` / `archive_find` 各搜一处，
得跑三遍再人工合并。

`search_OMNIA` 一次调用搜完三源，**但不替代**那两个工具——精细模式
（vector / fulltext / clue / keyword / condition / rerank / expand）仍在它们里。

### 11.2 能力矩阵（决定了三路覆盖到哪）

| 源 | 向量 | FULLTEXT | LIKE | 规模 |
|---|---|---|---|---|
| `draftpad` 草稿纸 | ✅ `idx_vec_draftpad` | ✅ bigram | ✅ | 1,802 |
| `dsh_message` 会话正文 | ❌ **无 embedding** | ✅ bigram | ✅ | 140,631 |
| `dsh_compaction` 压缩摘要 | ✅ `idx_vec_compaction` | ✅ bigram | ✅ | 181 |

**会话正文没有向量列**：给它补 embedding 是 14 万行的大工程。所以语义（模糊）
召回由草稿纸与压缩摘要承担；会话正文靠精确路（bigram 支持单字/任意子串）+ LIKE 兜底。
工具描述与返回里都会显式写这一条——**不能让人以为"库里没有"**。

### 11.3 融合规则与取数口径

```
每源每路各取 limit 条 → 本路内除以最高分归一化到 (0,1]
总分 = Σ(命中路权重 × 归一化分) + 0.08 × (命中路数 − 1)
权重：vector 0.45 / fulltext 0.40 / like 0.15
去重（按 source+id）→ **剩多少给多少，不截断回 limit**
```

**取数口径是用户 2026-10-25 明确拍板的，别再改回"宽取后窄截"**：

`limit` 的含义是**每一路各取多少条**，不是"最终返回多少条"。
三路各取 limit → 去重 → 全给。

理由：宽取后窄截会把「只有某一路命中、分数偏低」的独特结果挤掉，
而这类结果恰恰最不该漏（例如只有 LIKE 命中的旧措辞、只有向量命中的近义表述）。
代价是返回条数常多于 limit——**这是有意的**。

实测：`limit=3 → 15 条`、`limit=5 → 23 条`、`limit=10 → 41 条`。

多路命中给加成，是为了让「三路都说是它」压过「某一路的极端高分」。
硬上限 `limit × 路数 × 3`（至少 60）只防输出爆炸，正常查询碰不到。

### 11.4 实测（离线探针 `草稿纸与垃圾桶/probe_omnia.py`）

| 查询 | 最终命中分布 | 耗时 |
|---|---|---|
| `口径修正` | 草稿纸 2 / 压缩摘要 4 | 725 ms |
| `抄录器` | 草稿纸 4 / **会话正文 2** | 1,179 ms |
| `科幻` | 草稿纸 3 / 压缩摘要 3 | 418 ms |
| `绘`（单字） | 草稿纸 2 / 压缩摘要 4 | 671 ms |
| `""`（空） | 空 + 提示 | — |

会话正文的 LIKE 是 14 万行全表扫；`modes` 里关掉 `like` 可省这部分。

### 11.5 配套工具 `message_context`（2026-10-25 新增）

`search_OMNIA` 只能给片段，要看清前后文得靠它：

```
message_context(guid, before=3, after=3, max_chars=1200)
```

按 guid 取目标行，并展开**同会话、同代日志**的前后各 N 条，`▶` 标记目标行。

**⚠️ 一个必须记住的取法**：**不能按 `line_no ± N` 取窗口**。
`line_no` 是**事件物理行号**，而抄录器跳过 chunk 家族（`assistant/chunk` 等），
所以行号是稀疏的——实测 `before=2/after=2` 只返回 1 条（目标本身）。

正解是**按 line_no 排序取相邻 N 条记录**：

```sql
-- 向前：line_no <= 目标 的最后 b+1 条（含目标）
ORDER BY line_no DESC, ordinal DESC LIMIT b+1
-- 向后：line_no > 目标 的最前 a 条
ORDER BY line_no ASC, ordinal ASC LIMIT a
```

实测取回 7 条（前 3 / 后 3 + 目标），能看到完整的 `tool/call → tool/result → assistant`
链路——这正是判断「当时为什么这么定」所需要的。

### 11.6 多语言：tokenized 为空 ≠ 全文路失效（2026-10-25 实测纠正）

**曾经的错误判断**：`tokenize_cjk_ub` 的非 CJK 分支只认 `[A-Za-z0-9_]+`（西里尔/
希腊/变音拉丁匹配不到、整段丢弃）⇒ 推断「俄希拉丁的全文路失效」，并计划重建
62.5 万行的 `content_tokenized`。

**实测推翻了它。** `search.py` 的全文路是：

```python
col = "c.content_tokenized" if is_cjk else "c.content"
```

**非 CJK 查询走 `content` 列的 FULLTEXT（MariaDB 默认空格分词），根本不碰
`content_tokenized`。** 实测三组：

| 查询 | 走哪列 | 结果 |
|---|---|---|
| `拜占庭`（中文） | `content_tokenized`（bigram） | ✅ fulltext **316.9** |
| `Византийская библиотека`（俄文） | `content`（原始文本） | ✅ fulltext **48.9** |
| `Πλάτων Πολιτεία`（希腊文） | `content` | ❌ 无命中 → 自动回退向量 |

**已做的修复仍然必要**（写入侧正确性）：tokenizer 改成两段 alternation
（`([CJK]+)|(\w+)`），让 tokenized 也包含俄希拉丁。只是当前查询路径用不到它。

#### 跨语言语义检索本来就该走向量

bge-m3 是多语言模型，语义空间共享。实测用**中文**查
「拜占庭帝国的体育教育与竞技运动」：

```
第1名  《Физическая культура и спорт в Византийской империи》
       heading: "2.2. Физическая культура византийских элит"
       source: vector · score_vec 0.4115
```

**零字面重合，纯语义命中俄文书的对应章节。**

⇒ 所以「重建 tokenized 补俄希拉丁」**不必做**：它只影响「中文查询命中俄希拉丁
内容」的混合场景，而那类场景本来就是向量路的强项。成本 2 小时，收益近零。

#### 真正的残留问题：屈折变化

希腊文/拉丁文是**屈折语**：正文里是 `Πλάτωνος`（属格）、`Πλάτωνι`（与格），
查询 `Πλάτων`（主格）精确匹配不上。这需要**词形还原（lemmatization）**——
是另一件独立工程，**与 tokenized 无关**。

**用户 2026-10-25 决定：这类问题高度复杂，以后再说，写清楚即可。**

#### 架构分工（记这一条就够）

| 路 | 承担什么 | 依据 |
|---|---|---|
| **全文路** | **单语言精确匹配** | CJK → `content_tokenized`（bigram）；非 CJK → `content`（空格分词） |
| **向量路** | **跨语言语义召回** | 多语言共享空间 |
| **LIKE** | 字面兜底 | 特殊符号、连字符标识符 |

### 11.7 HNSW 向量索引的 recall 实测（2026-10-25）

**现象**：拿一条 chunk 的向量做自查询（`ORDER BY VEC_DISTANCE_COSINE(...) LIMIT 3`），
它**没排第一**——第一名距离 0.401，自己不见了。

**排查**（三步排除法）：

| 测试 | 结果 | 结论 |
|---|---|---|
| `IGNORE INDEX (idx_vec_chunk)` 强制全表暴力 | ✓ 自己排第一，距离 −0.000000 | **数据没问题** |
| Python 手算余弦 `1 − a·b/(‖a‖‖b‖)` | ✓ dist(自己,自己) = 0.000000000 | **距离函数没问题** |
| `EXPLAIN` | `type=index, key=idx_vec_chunk`，无 filesort | **确实走了索引** |
| `SET SESSION mhnsw_ef_search` 20→400 | **毫无变化** | 参数未生效（或 12.3.2 未接上） |

⇒ **HNSW 是近似（ANN），给了近似答案。**

**量化**（13 个随机 chunk 自查询，`mhnsw_ef_search=20`）：

```
top-1 命中自己： 12/13 = 92%
自己在 top-10：  13/13 = 100%
第一名距离中位数: 0.0000
```

**结论**：

- 向量路的 **top-k 召回可信**（top-10 100%），适合「找意思相近的」
- **top-1 有约 8% 误差**，所以**绝不要拿向量路做精确查找**（自查询、找重复、去重）
- 精确查找走 FULLTEXT 或 LIKE；这也是三路冗余设计的实际价值所在
- 不要相信「有向量索引 = 结果精确」——ANN 的 recall 是**可以低于 100% 的**，
  而且它**不会告诉你漏了什么**

**另一个坑**：`VEC_DISTANCE`（不带 `_COSINE`）会报 `index is not found`，
必须写全 `VEC_DISTANCE_COSINE`；建索引时 `DISTANCE=cosine` 也必须显式写，
否则静默降级为 `mhnsw_default_distance`（euclidean）。

### 11.8 大坑：带 FULLTEXT 的表，改列注释也要重建整表

**症状**：想改 `content_tokenized` 的列注释（`jieba` → `bigram`），
`ALTER TABLE ... MODIFY COLUMN ... COMMENT '...'` 开始重建 17 GB。

**实测对比**（`ALGORITHM` 由我显式指定）：

| 表 | `ALGORITHM` | 结果 |
|---|---|---|
| **无 FULLTEXT**（试探用） | `INSTANT` | ✅ 成功，**25.9 ms** |
| **有 FULLTEXT**（真实表） | `INSTANT` | ❌ `ERROR 1846` |
| 同上 | `NOCOPY` | ❌ `ERROR 1846` |
| 同上 | `COPY` | ✅ 但重建整表 + 重建 FTS（17 GB → 1–1.5 h） |

**错误里的 Reason 才是关键**：

```
ALGORITHM=INSTANT is not supported.
Reason: InnoDB presently supports one FULLTEXT index creation at a time.
Try ALGORITHM=COPY
```

⇒ **不是「改注释要重建」，是「表上有 FULLTEXT 时 InnoDB 的 ALTER 实现不支持
非 COPY 算法」**。与注释内容、列类型无关。

**注意官方文档的措辞**：`MODIFY COLUMN` 一节只说「保留索引、需指定新列的全部属性」，
**没有任何"会重建"的警告**——这份警告是从实测和 `ERROR 1846` 的 Reason 反推出来的。

**纪律**：

- ❌ 不要为一个注释单独跑 `MODIFY COLUMN`
- ✅ 攒到下次必须重建（改列类型/加索引）时，合并进**同一条 ALTER**，一次 COPY 解决
- ⚠️ 「先删 FULLTEXT 再改注释」更亏——删 FULLTEXT 本身也要 rebuild（实测 91 分钟）
- 📌 当前 `documents_book_chunk.content_tokenized` 注释仍是旧文案，**有意不修**

**通用教训**（比这条具体知识更值钱）：

> **遇到"感觉不对劲"的 DDL，先查官方文档 + 用小表验证算法，再决定要不要在大表上动。**
> 我这次只试了 `INSTANT` 看到报错就断定「必须重建」，既没试 `NOCOPY`（MariaDB 12
> 新增），也没查文档——然后在 17 GB 的表上直接开跑。

### 11.9 用法与边界

```
search_OMNIA(query, limit=5, sources="", modes="", per_source_limit=0)
  limit:   每一路各取多少条（去重后全给，可能多于 limit）
  sources: draftpad,messages,compactions（缺省全搜）
  modes:   vector,fulltext,like（缺省三路；关 like 可省时间）
```

- 跳转指针：草稿纸 → 笔记 id；会话正文 → `session_id + ev_time`；
  压缩摘要 → `record_id`（配 `archive_expand` / `archive_fetch` 回查原文）。
- **压缩摘要有损**（约 35:1），工具返回里带了这条提示。
- 代码：`melquiades/omnibus.py`（约 330 行）+ `server.py` 的注册。
  **需重启 MCP 生效**（stdio 进程无热加载）。
