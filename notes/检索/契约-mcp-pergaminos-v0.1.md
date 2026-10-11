/* 文件名: 契约-mcp-pergaminos-v0.1.md
 * 摘要: mcp-pergaminos 的接口契约（实现前的共同地基）。工具签名、Work 对象、
 *       provenance 规则、错误码、配置解析、节流与缓存。各源实现按此填空。
 * 依赖: 无（纯文档）。前置：庙算-PaperSearchMCP替代品-v0.1.md（§1-§9 已定案）
 */

# mcp-pergaminos 接口契约 v0.1

**依据**：`庙算-PaperSearchMCP替代品-v0.1.md` §1–§9 的全部裁决
**状态**：待评审。**本文件是各源实现的唯一真相源**——字段语义有争议时以本文件为准。

---

## 1. 工具面（两个，只有两个）

| 工具 | 用途 |
|---|---|
| **`paper_search`** | **检索**：给关键词，跨源找论文 |
| **`paper_oa`** | **对账**：给标识（DOI/arXiv id/标题），报告各源收录与 OA 状态 |

**不存在第三个工具。** 特别地——**不存在任何下载工具**（见 §7）。

---

## 2. `paper_search`

### 2.1 签名

```jsonc
{
  "query":      "string",            // 必填，检索词
  "sources":    ["string"],          // 可选，默认 ["crossref","arxiv","biorxiv","medrxiv"]
                                     //   可选值: crossref | arxiv | biorxiv | medrxiv | openalex
  "per_page":   20,                  // 可选，每源返回条数，默认 20，上限 100
  "year":       "string",            // 可选，如 "2020" / "2016-2020" / "-2015"
  "merge":      false,               // 可选，true = 按 DOI 精确合并（见 §4）
  "abstract_max_chars": 600,         // 可选，摘要截断，默认 600，0 = 不截断
  "cache":      "auto"               // 可选，auto | off | refresh
}
```

### 2.2 返回

```jsonc
{
  "query": "…",
  "sources_asked":    ["crossref","arxiv","biorxiv","medrxiv"],
  "sources_answered": ["crossref","biorxiv","medrxiv"],   // arxiv 失败/超时则不在其中
  "sources_failed":   [{"source":"arxiv","code":"RATE_LIMITED","detail":"…"}],
  "groups": [                        // ← 默认按源分组（A1 裁决）
    {
      "source": "crossref",
      "count": 20,
      "waited_ms": 0,
      "results": [ Work, … ]
    },
    { "source": "arxiv", "count": 20, "waited_ms": 2140, "results": [ … ] },
    …
  ],
  "merged": null,                    // merge=true 时为 Work[]，否则 null
  "provenance": { "fetched_at": "…", "elapsed_ms": 3820 }
}
```

**⚠️ `waited_ms` 是必备字段。** arXiv 官方限速 3 秒/次 ⇒ 检索会等待。
**把这个等待显式回报，模型才知道自己在等什么**（否则会以为工具挂了，重试，然后更慢）。

### 2.3 工具描述（自文档，必须写进 description）

> 检索学术论文，返回**元数据**（题名/作者/年份/摘要/DOI/获取路径），**不下载全文**。
> ⚠️ **arXiv 官方限速为「每 3 秒 1 次、单连接、全机器合计」**，因此含 arXiv 的检索会等待数秒——
> 这是 arXiv 的硬约束，不是本工具的问题。返回体里的 `waited_ms` 会告诉你实际等了多久。
> 各源覆盖边界不同（arXiv 预印本不在 Crossref；bioRxiv/medRxiv 无全文检索），
> 所以默认**按源分组**返回，不做推断式合并。

---

## 3. `paper_oa`

### 3.1 签名

```jsonc
{
  "identifiers": ["string"],   // 必填。混合接受：DOI / arXiv id / 标题
  "sources":     ["string"],   // 可选，默认 ["unpaywall","crossref"]（openalex 仅在配了 key 时可选）
  "cache":       "auto"
}
```

### 3.2 返回

```jsonc
{
  "items": [
    {
      "input": "10.1038/nature12373",
      "match": {                      // ⭐ 匹配自报家门（A5 裁决）
        "kind": "doi_exact" | "arxiv_id" | "title_fuzzy" | "not_found",
        "confidence": 1.0,            // title_fuzzy 时 < 1.0
        "candidates": [ {title, doi, score} ]   // 仅 title_fuzzy 且多条时
      },
      "work": Work,
      "conflicts": [                  // ⭐ 两方不一致时（Q6 裁决）
        {
          "field": "oa_status",
          "values_by_source": { "unpaywall": "green", "crossref": null },
          "note": "Crossref 不提供 OA 状态"
        }
      ]
    }
  ]
}
```

**`conflicts` 的规则（Q6 裁决的落地）**：
- **两方都给值 → 两个都报，不选**
- **一方缺值 → `values_by_source` 里记 `null`，不算冲突**
- **绝不静默取一个。** 判断权交给人/模型

---

## 4. `Work` 对象（唯一的数据契约）

```jsonc
{
  "ids": {
    "doi":     "10.1038/nature12373",     // 小写
    "arxiv":   "2106.12345",              // 无 "arXiv:" 前缀
    "pmid":    "…", "pmcid": "…", "biorxiv": "10.1101/…",
    "openalex": "W…"                      // 仅 openalex 源可用时
  },
  "title":    "…",
  "authors":  ["…"],
  "year":     2024,
  "venue":    "…",                        // 期刊/会议名
  "type":     "article" | "preprint" | "dataset" | "other",
  "abstract": "…",                        // 已按 abstract_max_chars 截断
  "abstract_truncated": false,

  "oa": {                                 // ← 对账的核心
    "is_oa": true,
    "status": "gold"|"hybrid"|"bronze"|"green"|"closed",   // Unpaywall 五值
    "url": "https://…",                   // best_oa_location 的 url
    "in_repository": true,                // Unpaywall has_repository_copy
    "journal_is_oa": false,
    "journal_is_in_doaj": false
  },

  "locations": [                          // 「收录情况」
    { "source": "arXiv", "host_type": "repository",
      "version": "submittedVersion", "url": "…", "license": "cc-by", "oa_date": "…" }
  ],

  "provenance": {                          // ⭐ 逐字段来源
    "source": "unpaywall",                 // 本条记录的主源
    "endpoint": "GET /v2/10.1038/…",
    "fetched_at": "2026-10-03T12:00:00+08:00",
    "raw_ref": "cache/ab/abcdef…json"      // 可回查原始响应
  }
}
```

### 4.1 ⭐ `provenance` 是强制的

**理由**：本项目已有「数据巴别塔」教训（同一字段多种来源/格式）与「静默指错」故障类。
**每个字段都必须能回答"这是谁说的"。** `raw_ref` 指向缓存文件，使争议可回查原始响应。

### 4.2 OA 分类法的源差异（**必须写进 README 与工具描述**）

| | Unpaywall | OpenAlex（可选时） |
|---|---|---|
| 值集 | `gold` `hybrid` `bronze` `green` `closed`（**5**） | 多一个 **`diamond`**（**6**） |
| 取用 | 默认源 | 仅配 key 时 |

⇒ **契约里 `status` 采用 Unpaywall 的 5 值**；OpenAlex 的 `diamond` **映射为 `gold` 并在 `provenance.raw_ref` 保留原值**，同时在 `conflicts` 里记一条。
**不隐藏这个差异**——它是两个数据源的客观区别，不是我们的 bug。

### 4.3 ⚠️ 预印本 DOI 的坑（OpenAlex 官方原文）

> `doi` — 「A work occasionally has more than one DOI (e.g., **a preprint DOI and a published DOI**); this field always holds the DOI of the published version.」

⇒ **`ids.doi` 是正式版 DOI；预印本 DOI 只能从 `locations[]` 或各预印本源单独取。**
对于 **arXiv 预印本，其 DOI 由 DataCite 注册，不在 Crossref** ⇒ `paper_search(sources=['crossref'])` **查不到 arXiv 预印本**。这条要写进工具描述。

---

## 5. 源清单与角色（方案 C）

| 源 | 角色 | 认证 | 官方限速 | 默认在检索里？ |
|---|---|---|---|---|
| **Crossref** | 检索主力 + 元数据权威 | 无 / Polite(mailto) | Public 5/s **并发1**；Polite 10/s **并发3** | ✅ |
| **Unpaywall** | OA 骨干（**不能检索**） | email 必填 | 100,000/天 | ❌（仅 `paper_oa`） |
| **arXiv** | 预印本检索 | 无 | **3 秒/次，单连接，全机器合计** | ✅（**默认打，用户裁决 A4**） |
| **bioRxiv / medRxiv** | 预印本 | 无 | 未公布（待核实） | ✅ |
| **OpenAlex** | 可选增强（跨源 ID 桥 / `locations[]` 含付费位置 / 批量 100） | 免费 key | $1/天 | ❌ 仅配了 key 才启用 |

---

## 6. 节流与并发（**跨进程**，这是本契约的关键设计）

### 6.1 为什么不能只用进程内锁

`server_bge.py` 的 `_serial = asyncio.Lock()` 是**进程内**的。
但 **arXiv 的 3 秒是「全机器合计」**，Crossref 的并发限是**按 IP** 计的。

**⇒ 多进程（并行实例/调试）会各自持有独立节流器 ⇒ 实际速率翻倍 ⇒ 违约。**

**证据：本项目自己的配置注释就写着并行实例：**
> `cordis.patch.yml`：「⚠️ 并行测试注意：现役 9007 同时跑着同一套 MCP」

### 6.2 设计：落盘节流 + 文件锁

```
目录:  ${XDG_CACHE_HOME:-~/.cache}/pergaminos/throttle/
文件:  <source>.json    内容: {"last_ms": <epoch_ms>}

取用（每条出站请求）:
    fd = open(file, O_RDWR|O_CREAT)
    flock(fd, LOCK_EX)                       # 阻塞，天然串行 = 「我只一路去」
    last = json.load(fd).get("last_ms", 0)
    wait = max(0, min_interval_ms - (now_ms - last))
    if wait: sleep(wait)
    write(fd, {"last_ms": now_ms})           # 锁内写
    flock(fd, LOCK_UN)
    → 出站请求
```

**性质**：
- **跨进程**成立（文件锁是内核级的）
- **零依赖**（stdlib `fcntl`）
- **天然 FIFO**（按锁的到达顺序）—— 即「任尔几路来我只一路去」
- 状态可读可删（调试友好）

### 6.3 各源的 `min_interval_ms`

| 源 | 值 | 依据 |
|---|---|---|
| **arXiv** | **3000** | 官方「每 3 秒 1 次、单连接」 |
| Crossref | 1000 | Public 5/s ⇒ 保守取 1 次/秒；进 Polite 后提高到 100 |
| bioRxiv / medRxiv | 1000（保守，待核实） | 官方未公布 |
| Unpaywall | 0（不节流，只靠日额度） | 100k/天 |
| OpenAlex | 0 | 100 req/s 上限 + 日预算 |

### 6.4 「Oversize 立即拒绝不排队」（抄自 `server_bge.py`）

单条请求若**在额度上永远无法满足**（例如单次请求需要超过整个日额度），
**必须立即显式报错，不进队列**——因为等待永远不会成功。

---

## 7. 不提供下载（四条理由，进 README 与工具描述）

见 `庙算…§8.2`。**契约层面**：
**不存在任何 `download_*` / `read_*` / `fetch_pdf` 工具。**
**这是靠 schema 而不是靠 prompt 实现的**——模型调不到不存在的工具。

---

## 8. 错误码（开放式字符串，不闭集）

| code | 含义 | 处理 |
|---|---|---|
| `CONFIG_MISSING` | 必需配置缺失（如 Unpaywall email） | **启动即失败**，不延迟到调用 |
| `RATE_LIMITED` | 撞限速或日额度（429/403） | 显式回报 `Retry-After`（若有） |
| `NETWORK` | DNS/TLS/连接失败 | **重试 5 次**（递增 1/2/4/8s），仍失败才报 |
| `TIMEOUT` | 超过 `PERGAMINOS_TIMEOUT_MS` | **不重试**（避免叠加挂住） |
| `NOT_FOUND` | 源明确表示无此记录 | 正常路径，不算错误 |
| `UPSTREAM_CHANGED` | 响应结构不符合预期 | **显式报错**，绝不静默返回空 |
| `AUTH_REQUIRED` | 该源需要 key 但未配 | 提示 `PERGAMINOS_OPENALEX_KEY` 等 |

**纪律**：
- **网络类错误重试 5 次**（本项目既有网络纪律）；**超时不重试**
- **`ECONNREFUSED 127.0.0.1:<port>`（代理没起）不重试**，直接报「代理未启动」
- **`UPSTREAM_CHANGED` 必须报错，不许吞**——这是本契约里最重要的一条。
  Unpaywall 的 `/v2/search` 15 天前刚 410 过；上游**一定会变**，静默返回空等于伪造"没找到"。

---

## 9. 配置解析（发布导向）

### 9.1 优先级

```
① 真实环境变量
② .env 文件（路径可用 PERGAMINOS_ENV_FILE 指定）
③ Python 顶部常量（**只兜底；不得含凭据/绝对路径/个人身份**）
```

> **修订 2026-10-03：命名空间从 `PAPERSEARCH_` 改为 `PERGAMINOS_`。**
> 理由：`PAPERSEARCH_` 是**上一代项目**（PaperSearchMCP，即 `paper-search-mcp`）
> 的命名空间。两个项目共用前缀本身就是隐患——同名变量互相覆盖，且「这变量归谁」
> 无法从名字上看出来。本项目叫 pergaminos，前缀必须是自己的。
> 实现侧同步收紧：`config.DEFAULTS` 的键**直接写变量全名**（与 .env 逐字一致），
> 不再靠 `f"{ENV_PREFIX}{name}"` 在读取处隐式拼接——隐式拼接正是「字典写
> `OPENALEX_KEY`、.env 得写带前缀的名字」这类两处不一致的温床，一旦不一致，
> 写错的那一边完全静默。另加两道保险：`.env` 里出现「写了但没人读」的变量会
> 在启动打印里以 `UNREAD` 标出并给出正确写法；上一代 `PAPERSEARCH_*` 会被识别
> 为遗留并提示改名。

### 9.2 变量表

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `PERGAMINOS_UNPAYWALL_EMAIL` | ✅ | — | 缺失 ⇒ 启动失败 |
| `PERGAMINOS_CONTACT` | | = `UNPAYWALL_EMAIL` | UA 里的联系方式；**复用时要打印说明** |
| `PERGAMINOS_CROSSREF_MAILTO` | | = `CONTACT` | 进 Polite 池 |
| `PERGAMINOS_OPENALEX_KEY` | | 空 | **空 = 不启用 OpenAlex** |
| `PERGAMINOS_PROXY` | | 空 | `http://…` 或 `socks5://…`；**空 = 不挂** |
| `PERGAMINOS_PROXY_BYPASS` | | 空 | 逗号分隔源名 |
| `PERGAMINOS_TIMEOUT_MS` | | 20000 | **给短值，不留 5 分钟** |
| `PERGAMINOS_PER_SOURCE_TIMEOUT_MS` | | 90000 | 每源总预算（含全部重试） |
| `PERGAMINOS_CACHE_TTL_H` | | 168（7 天） | |
| `PERGAMINOS_LOG_LEVEL` | | `INFO` | |
| `PERGAMINOS_ENV_FILE` | | — | 指定 .env 路径（不进 DEFAULTS，特殊变量） |

**不做缓存目录配置项**（2026-10-03 裁决）。缓存位置固定，要换就在文件系统层
放符号链接——比多一个配置项少一条出错路径。


### 9.3 UA 构造

```
Los-pergaminos-de-Melquiades/1.0 (papersearch; +https://github.com/la-sandrone/mcp-pergaminos; mailto:<CONTACT>)
```

**规则**：
- **只允许 ASCII**（RFC `tchar` 不含非 ASCII）⇒ 重音必须剥离（`Melquíades`→`Melquiades`）
- **必须显式设置**（httpx 默认是 `python-httpx/0.28.1`，部分 CDN 直接 403）
- **不许伪装浏览器**（不写 `Mozilla/…`）

### 9.4 ⭐ 启动必须打印生效配置（防「静默指错」）

```
[conf] unpaywall  proxy=(none)  email=set(自有)     throttle=0ms
[conf] crossref   proxy=(none)  mailto=set(复用CONTACT)  throttle=1000ms  pool=Polite
[conf] arxiv      proxy=(none)                      throttle=3000ms (官方硬约束)
[conf] biorxiv    proxy=(none)                      throttle=1000ms (待核实)
[conf] openalex   DISABLED (no key)
[conf] ua         Los-pergaminos-de-Melquiades/1.0 (…)
[conf] cache      /home/x/.cache/pergaminos  ttl=168h
```

**未打印 = 配置没生效你不知道。** 这是本项目已发生过的故障类（melquiades `dsh.home` 写死旧名 → `files=0/0` 退出码 0）。

---

## 10. 缓存

- **形式**：JSON 文件，按 `sha256(source + "|" + 规范化请求)` 命名，两级目录 `ab/abcdef….json`
  （与 `attachments/v1/objects/<hash>` 同一形状，沿用本项目既有约定）
- **内容**：原始上游响应 + 元信息（`fetched_at` / `source` / `endpoint`），**不是加工后的 Work**
  ⇒ 加工逻辑改了不用清缓存
- **TTL**：默认 168h；`cache=refresh` 强制重取；`cache=off` 完全旁路
- **`raw_ref`** 指向缓存文件 ⇒ `provenance` 可回查
- **它是纯派生物**：随时可删可重建 ⇒ 用文件而非 DB（无查询需求，且失败了不藏事）

---

## 11. 测试

| 层 | 内容 | CI |
|---|---|---|
| **默认** | 全部基于**手工构造的最小 fixture**（录制的 HTTP 响应） | ✅ 跑 |
| **live** | `tests/live/`，需 `PERGAMINOS_LIVE=1` + 真实 email | ❌ 不跑 |

**纪律**：
- **绝不提交真实检索痕迹**（真实 DOI 列表 / 真实摘要）——既是隐私也是版权
- **fixture 不得含个人路径、真实 email**
- 每个错误码至少一个 fixture 用例（尤其 `UPSTREAM_CHANGED`）

---

## 12. 发布契约

| 项 | 值 |
|---|---|
| 仓库 | `github.com/la-sandrone/mcp-pergaminos` |
| 自用目录 | `<挂载d>:/DataServices/MCP/mcp-pergaminos` |
| 导出版 | `<挂载e>:/公开发布项目/mcp-pergaminos` |
| serverName | `pergaminos` ⇒ 工具前缀 `mcp__pergaminos__*` |
| 代码许可 | **AGPL-3.0**（`LICENSE`） |
| 数据 | **README 声明**：arXiv 元数据 CC0；Crossref / Unpaywall 数据适用各自条款；**本工具只转发、不存储、不代持** |
| 导出方式 | **白名单脚本**（`tools/export_to_public.sh`），**不是 `cp -r`**；从第一天就写 |
| wrapper | `mcp-stdio.sh` 加 `pergaminos)` 分支：只 `source ~/ai-services/bin/activate` + exec，**不碰代理** |
| venv | `~/ai-services`（`mcp 2.2.0` / `httpx 0.28.1` / `socksio 1.0.0`） |

**`export_to_public.sh` 白名单**：
```
README.md  LICENSE  .env.example  .gitignore  pyproject.toml
pergaminos/  tests/  tools/export_to_public.sh
```

---

## 13. 仍未核实（照旧不填猜测值）

| # | 事项 | 影响 |
|---|---|---|
| 1 | bioRxiv / medRxiv 限速 | 节流值暂取保守 1000ms |
| 2 | Europe PMC 认证与限速 | **建议直接放弃这个源**（OpenAlex/PMC 有覆盖） |
| 3 | DOAJ API v2 是否可用 | **不需要**——`journal_is_in_doaj` 已在 Unpaywall 里 |
| 4 | OpenAlex 对 IACR / ChemRxiv / SSRN 的覆盖率 | 仅在启用 OpenAlex 后才有意义 |
| 5 | IACR ePrint 是否有官方 API | 若有价值可加源；否则不做 |
