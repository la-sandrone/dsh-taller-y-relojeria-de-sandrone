/* 文件名: 庙算-PaperSearchMCP替代品-v0.1.md
 * 摘要: paper-search-mcp 替代品的开工前庙算。需求收敛 + 官方 API 事实核实
 *       + 架构发现 + 需人工裁决的问题清单。**不含实现决策**，只列决策面。
 * 依赖: 无（纯文档）
 *
 * 核实时间: 2026-10-03
 * 核实方式: 逐家抓官方文档页（cloakbrowser），引文均为官方原文
 * 已有实践参考: ~/ai-services/paper-search-mcp/paper_search_mcp/academic_platforms/
 */

# 庙算：PaperSearchMCP 替代品 v0.1

## 0. 需求收敛

用户原话拆解：

| 要素 | 我的理解 |
|---|---|
| 重点找 **OA** | 给定论文，判定其开放获取状态与位置 |
| 各大**预印本收录情况** | 这篇论文在哪些预印本/仓库里存在，版本是什么 |
| **Unpaywall** | OA 定位器（DOI → 可读全文位置） |
| 也支持 **Crossref** | DOI 权威元数据底座 |
| **不提供下载** | 接口层不存在下载工具，且必须在描述里写清理由 |
| **顶层全局变量挂不挂代理** | 一个全局开关控制是否走代理 |
| **venv 走 ~/ai-services** | 不另开独立 venv |

**待裁决的第一个问题**：「找 OA」的主语是**检索**（给我一批论文）还是**对账**（给我这一篇在各处的状态）？见 §4 Q1。

---

## 1. 官方事实表（已核实）

> 口径：以下全部来自官方文档页，非推测。未取到的一律标「待核实」，不填猜测值。

| 源 | 认证 | 限速（官方） | 端点 | 能回答什么 |
|---|---|---|---|---|
| **OpenAlex** | 无需 key 即可用；免费 key 提额 **10×** | 绝对上限 **100 req/s**；无 key / 有 key 各有一份**日预算**（具体数字待核实） | `api.openalex.org/works` | **OA 状态、最佳 OA 位置、全部收录位置、跨源 ID** |
| **Unpaywall** | **email 必填**（URL 参数 `?email=`） | **100,000 次/天** | `api.unpaywall.org/v2/{doi}` | DOI → OA 状态与位置 |
| **Crossref** | Public 无认证 / Polite 带 `mailto` / Plus 带 API key | **Public 5 req/s，并发 1**；**Polite 10 req/s，并发 3**；Plus 150 req/s 无并发限 | `api.crossref.org/v1/works` | DOI 元数据权威 |
| **arXiv** | 无认证 | **每 3 秒 1 次请求，单连接**，且**对你控制的所有机器合计** | `export.arxiv.org/api/query` | 预印本元数据（元数据为 **CC0 1.0**） |
| **bioRxiv / medRxiv** | 文档未提认证 | 文档未公布（待核实） | `api.biorxiv.org/details/{server}/{doi}/na/json` | 版本历史、license、category、**`published`（→正式版指向）** |
| **Semantic Scholar** | 无 key 可用；key 提额 | **未认证 = 全球共享 1000 req/s**（与他人竞争） | `api.semanticscholar.org/graph/v1` | 元数据 + 部分 OA PDF（214M 篇） |
| **DOAJ** | **API key 只发给向 DOAJ 投稿的出版商 ⇒ 公开 API 免 key** | 未公布 | `doaj.org/api/v4/`（Elasticsearch） | OA 期刊/文章 |
| **Europe PMC** | — | — | — | **抓取被 403，未核实** |

---

## 2. 三条正在发生的官方变更（都落在这两周）

### 2.1 🚨 Unpaywall `/v2/search` 已于 2026-09-18 废止

官方原文：

> `GET /v2/search?query=:your_query` — **Retired 18 September 2026.** This endpoint now returns `410 Gone`.
> Use OpenAlex search instead. **OpenAlex is the successor to Unpaywall, from the same team and the same data**; every result includes `open_access` and `best_oa_location`.

**今天 2026-10-03，这条生效 15 天。**

对已有实践的影响：`academic_platforms/unpaywall.py` 里 `UnpaywallSearcher.search()` **已经是 DOI 走 `get_paper_by_doi`**，没有踩 `/v2/search`——这条侥幸活着。但类注释写的是 "Unpaywall is metadata and OA-location provider. It does not host PDFs."，**与新定位一致，可以留**。

### 2.2 OpenAlex 现在是 Unpaywall 的后继，且数据同源

官方原文（同上）：「**from the same team and the same data**」。

**这句话是本次庙算最重要的输入**——它意味着 OA 定位不再是"两个独立源"，而是"**一个源，两条访问路径**"。

### 2.3 DOAJ 文档已到 v4，我们的实现还在 v2

- 官方文档页标题：`This page documents v.4.0.0 of the DOAJ API.`
- 已有实践：`doaj.py` 用的是 `https://doaj.org/api/v2`

**版本漂移，待核实 v2 是否仍可用**（可能也 410 了）。

---

## 3. 架构发现：OpenAlex 应当是中枢，不是"又一个源"

OpenAlex `work` 对象上，官方已把我们需要的东西全部定义好了（引原文）：

```
open_access.is_oa                      布尔，官方定义宽：可读即可（不付费、不登录）
open_access.oa_status                  diamond | gold | green | hybrid | bronze | closed
open_access.oa_url                     最佳 OA URL（可能是 PDF 也可能是落地页）
open_access.any_repository_has_fulltext  「shadowed green」——出版方副本存在时会被 oa_status 遮住的那种

best_oa_location  官方打分规则原文：
                  「必须 OA；出版方 > 仓库；publishedVersion > acceptedVersion > submittedVersion；
                    有直链 PDF 优先；主要仓库（PubMed Central、arXiv）排在其它之前」

locations[]        「这篇论文活在世界上的每一个地方」
primary_location   最接近 version of record 的那一份
ids                openalex / doi / mag / pmid / pmcid   ← 跨源 ID 桥
apc_list / apc_paid  APC 费用（含 OpenAPC 实测值）
```

**而且它能批量**：官方 best practice 明写「Batch ID lookups with the OR syntax (**up to 100 values per filter**)」、「`per_page` max 100」。

**⇒ 对账 100 篇论文 = 1 次请求。** 而 Unpaywall 是 1 篇 = 1 次请求。**这是 100× 的效率差，决定了主路径必须走 OpenAlex。**

### 3.1 由此推出的设计原则：聚合器优先，缺口回源

已有实践里有 **22 个源**。但其中 CORE / BASE / OpenAIRE / HAL / Zenodo / DOAJ / CiteSeerX / DBLP / PMC / PubMed / EuropePMC **全都是元数据聚合或子集**，而 OpenAlex 官方定位就是聚合器。

**同时挂"一个聚合器 + 它的一堆上游"是纯冗余。**

但**不能据此断定 OpenAlex 全覆盖**——它对 IACR ePrint、ChemRxiv、SSRN 这类可能稀疏（待核实）。
**所以原则是**：先问 OpenAlex；**它答不了的缺口再回源**。

### 3.2 ⚠️ 一个必踩的字段坑（官方原文）

> 「`doi` — The work's DOI — the canonical external ID for works. A work occasionally has more than one DOI (**e.g., a preprint DOI and a published DOI**); **this field always holds the DOI of the published version**」

**⇒ 预印本 DOI 不在 `doi` 字段里。** 要查"预印本收录情况"，必须走 `locations[]`，或者单独查那个 preprint work。

**这一条直接决定 `check()` 的实现形状**，也是 §4 Q6 契约设计的关键。

---

## 4. 「不提供下载」的官方理由（三条，可引用）

用户要求"说清楚为什么"。**除了工程理由，官方文献给了法律理由。**

### 4.1 版权：arXiv 使用条款明文禁止

官方原文（`info.arxiv.org/help/api/tou.html`）：

> **Things that you must not do:**
> 「Store and serve arXiv e-prints (PDFs, source files, or other content) **from your servers, unless you have the permission of the copyright holder** or are permitted to do so」

> 「You understand that e-prints from arXiv are subject to all applicable copyright protections. **The redistribution of e-prints requires permission from the copyright holder**, which may be the author(s) or publisher. **arXiv is not the copyright holder** on any of the e-prints available through the API.」

**⇒ 我们不是版权持有人，也没有获得许可 ⇒ 不做镜像、不做转存。**

### 4.2 限速：arXiv 的额度根本不允许

官方原文：

> 「make **no more than one request every three seconds**, and limit requests to a **single connection at a time**」
> 「applies to **all of the machines under your control as a whole**. You should not attempt to overcome these limits by increasing the number of machines」

**⇒ 一次全文抓取就吃掉 3 秒额度，且不能并发。** 对账 20 篇 = 60 秒纯等待。

### 4.3 工程：拉取"成功"常常是静默降级

- `toolCallTimeoutMs: 300000`（5 分钟）——挂住就白烧
- 国内网络对出版商站点普遍不可达
- **最恶劣的一种**：HTTP 200 但内容是 **PDF.js 空壳 / 登录墙 / 反爬提示页** ⇒ 模型以为拿到了论文，实际拿到一页 JS，然后**基于它编结论**

**⇒ 按本项目自己的原则「以静默降级为耻」，这个失败模式比崩溃更恶劣，应当从接口层消除。**

### 4.4 三条合并成一句可写进工具描述的话（草稿，待你改）

> 本工具只报告**元数据与获取路径**，不下载全文。三个原因：
> ① **版权**：arXiv 等来源的许可明确禁止第三方转存与再分发；
> ② **限速**：arXiv 为每 3 秒 1 次、单连接，抓全文会耗尽额度；
> ③ **可靠性**：出版商站点在国内常不可达，且失败常表现为「成功返回一个 PDF.js 空壳」——这是静默降级，比报错更危险。
> 拿到 DOI 与路径后，由人决定怎么取。

---

## 5. 需要庙算决定的问题

### Q1 ⭐ 这个工具的**主语**是什么？—— 检索 还是 对账？

这是最根本的一问，其余全依赖它。

- 现状是**检索**：57 个工具 = 22 源 × 3 动词（search / download / read）
- 「**收录情况**」这个词在语义上属于**对账**：给定一篇，报告它在各处的状态

**推荐：两个动词，收敛到同一个对象（Work）**
- `search(query, …)` → Work 列表（进 Crossref / OpenAlex）
- `check(doi | arxiv_id | title)` → **对账报告**（主角）

**要你裁决**：是否接受"check 是主角、search 是配角"？还是你要的是纯检索？

### Q2 Unpaywall 还要不要单独占一个源？

- 官方说 OpenAlex 是它的后继、数据同源 ⇒ 逻辑上冗余
- 但：**Unpaywall 无需注册**（只要 email），**100k/天固定额度**；OpenAlex 免费 key 要注册，无 key 有**日预算**（数字未取到）

**推荐：留，但降级为兜底路径**
- 主路径：OpenAlex（能批量 100）
- 兜底：Unpaywall（当 OpenAlex 额度用尽 / 未配 key 时）

**要你裁决**：你愿意去 openalex.org 注册一个免费 key 吗？**愿意 ⇒ Unpaywall 可以完全不挂；不愿意 ⇒ 必须留它做兜底。**

### Q3 保留哪几个源？—— 从 22 降到 N

**推荐集（5 个）**

| 源 | 角色 |
|---|---|
| OpenAlex | 对账中枢（批量、OA 分类、locations、跨源 ID） |
| Crossref | DOI 元数据权威 + Polite 池（10/s 并发 3） |
| Unpaywall | OA 定位兜底（见 Q2） |
| arXiv | 预印本原生（3s 限速，元数据 CC0） |
| bioRxiv / medRxiv | 预印本原生 + **`published` 字段给出"预印本→正式版"映射** |

**候选删（元数据都在 OpenAlex 里聚合了）**：CORE · BASE · OpenAIRE · HAL · Zenodo · DOAJ（**可用 OpenAlex 的 `listed_in:doaj` 过滤替代**）· CiteSeerX · DBLP · PMC · PubMed · EuropePMC · Semantic Scholar

**必须删（无关或不可行）**：Sci-Hub（版权，你已排除）· Google Scholar（反爬）· IEEE / ACM（付费墙 + 需 key）

**要你裁决**：
- ① 接受 5 个源吗？还是你有必须保留的某个（比如 DBLP 对 CS 的会议收录质量）？
- ② **DOAJ 是否用 `listed_in:doaj` 替代**？（待核实：这个过滤是判"期刊在 DOAJ"，不等于"这篇文章在 DOAJ"）

### Q4 ⭐ 代理的粒度与默认值

你说"支持设置顶层全局变量挂不挂代理"。庙算要点：

**（a）哪些源需要代理？** 上表 5 个源**全部在国外** ⇒ 理论上全需要。

**（b）但有个真问题**：Crossref 和 OpenAlex 的限速是按 **IP** 计的，而代理是**共享出口**。
- 走代理 → 可能和别人的流量抢同一份额度（Semantic Scholar 官方就明说"全球共享 1000 req/s"）
- 不走代理 → 国内可能直连不通

**（c）默认值是什么？** 这是经典的"没有好默认"：
- 默认**挂** → 代理没起时**全部超时**，且报错难辨
- 默认**不挂** → 源不可达时**全部超时**

**推荐**：
- 一个全局变量（你要的）：`PAPERSEARCH_PROXY`（空 = 不挂）
- **但保留按源覆盖**：`PAPERSEARCH_PROXY_BYPASS=arxiv,crossref`
- **默认不挂**（初始态更常见）
- ⭐ **启动时把生效配置打印出来**：每个源 → 走不走代理 → 实际 URL 前缀

**最后一条是重点**：这个项目自己的关键词表里就有「**静默指错**」（melquiades 的 `dsh.home` 写死旧名、preset-key-check 永远扫 0 个）。**代理配置不打印 = 又一次静默指错。**

**要你裁决**：接受"默认不挂 + 启动打印生效配置"吗？还是你要默认挂？

### Q5 ⭐ 限速怎么调度？

三种限速性质完全不同，**不能用一套逻辑**：

| 源 | 约束性质 | 需要的机制 |
|---|---|---|
| Crossref | **并发**限制（Public 并发 **1**！） | 信号量 |
| arXiv | **频率**限制（3 秒 1 次）且**全局单连接** | 全局节流器（跨请求持久） |
| OpenAlex | 频率上限很高（100/s），但有**日预算** | 批量优先，不必并发 |

**推荐：全部串行 + 批量**
- 对账场景是**几十个 DOI**，不是几十万
- OpenAlex 一次 100 个 ⇒ 串行完全够
- **并发带来的只有 429 和 IP 封禁风险**

**要你裁决**：接受"一律串行"吗？（代价：对账 100 篇时，arXiv 那部分要 300 秒；但 OA 状态查询不受影响）

### Q6 返回契约 —— 字段全链路

按本项目「字段全链路 + 唯一真相源」的要求：

```
Work {
  ids       : { doi, arxiv, pmid, pmcid, openalex, biorxiv, ... }   # 跨源桥
  title, authors[], year, venue, type(article|preprint|...)
  oa        : { is_oa, oa_status(6 值枚举), oa_url, any_repository_has_fulltext }
  best_oa_location : { source, version, url, license } | null
  locations[]      : 全部收录位置（含 version / license / source）
  preprint  : { is_preprint, server, published_doi }   # ← 预印本→正式版映射
  provenance: { source, endpoint, fetched_at, raw_ref }  # ⭐ 每字段的来源
}
```

**`provenance` 是必须的**——否则"这个 OA 状态是 OpenAlex 说的还是 Unpaywall 说的"说不清。
这正是本项目"数据巴别塔"教训的同族问题（同一字段多种格式/多种来源）。

**要你裁决**：
- ① 接受这个契约吗？要不要加/减字段？
- ② **冲突怎么报**：Crossref 和 OpenAlex 的标题/年份不一致时，是**报两方 + 标冲突**，还是**取一个 + 记 provenance**？

### Q7 ⭐ venv 与依赖 —— 这条可能推翻"走 ~/ai-services"

你说 venv 走 `~/ai-services`。但**现状是它走不了**，原因在已有实践里写着：

> papersearch 用独立 venv `~/venv-mcp-papersearch`：上游 `pyproject.toml` 写死 `"mcp[cli]>=1.8.0,<2"`，
> 而 ai-services 的 vllm 0.30.0 声明要 `mcp>=2.0.0` —— **两者共用一个 venv 必冲突**。

**⇒ 冲突的根源不是 papersearch，是 `mcp` 这个库。**

**所以要回答的是**：新的替代品**还用 `mcp` / FastMCP 库吗？**

- **用** ⇒ 必然又是一个独立 venv，**进不了 ~/ai-services**
- **不用**（手写 stdio JSON-RPC）⇒ **零 mcp 依赖，可以进 ~/ai-services** ✅

**已有实践里已经有先例**：`mcp_localgit.py` 的文件头写着「**依赖深度 = 0（仅 mcp 库）**」，而且它自带一套 **mcp 1.x / 2.x 兼容层**（注释：「由 tools/mcp2_migrate.py 生成，勿手改」）。**说明这条路已经走过。**

**推荐：手写 stdio JSON-RPC，不依赖 `mcp` 库**
- 依赖只剩 `httpx`（ai-services 已有）
- 满足你"venv 走 ~/ai-services"的要求
- 不再有 mcp 版本冲突
- 代价：自己实现 JSON-RPC 帧 + 工具 schema 声明（约 150–250 行）

**要你裁决**：接受"不依赖 mcp 库、手写 stdio"吗？

### Q8 待核实项（**不填猜测值**）

| # | 事项 | 为什么重要 |
|---|---|---|
| 1 | OpenAlex **无 key / 有 key 的日预算具体数字** | 决定要不要注册 key（Q2） |
| 2 | DOAJ API **v2 是否仍可用** | 已有实践在 v2，官方已到 v4 |
| 3 | **Europe PMC** 的认证与限速 | 抓取 403 |
| 4 | **bioRxiv / medRxiv** 的限速 | 官方文档未公布 |
| 5 | **DOAJ** 的限速 | 官方文档未公布 |
| 6 | OpenAlex 对 **IACR ePrint / ChemRxiv / SSRN** 的覆盖率 | 决定"缺口回源"要补哪几个 |
| 7 | OpenAlex `listed_in:doaj` 是判**期刊**还是判**文章** | 决定 DOAJ 能否被替代（Q3） |
| 8 | **IACR ePrint** 是否有官方 API（已有实践是 scrape） | 决定这个源能不能留 |

---

## 6. 一句话总结

**官方说法改变了架构**：OpenAlex 不只是"一个源"，它是 **Unpaywall 的后继 + OA 分类法的定义者 + 可批量 100 的聚合器**。

**所以这个替代品的形状不是我原以为的"5 个源各自实现"，而是：**
> **一个以 OpenAlex 为中枢的对账器 + 3 个缺口回源（Crossref 元数据权威 / arXiv+bioRxiv 预印本原生 / Unpaywall 兜底），全部只报路径不取全文。**

**而它能不能进 `~/ai-services`，取决于 Q7（要不要 `mcp` 库）——这一条你可能之前没意识到。**

---

# §7 裁决结果与修订（2026-10-03，第一轮裁决后）

## 7.1 用户裁决

| 问题 | 裁决 |
|---|---|
| **Q1** | **检索！** 「写设定真的要参考」⇒ **主语是检索，对账是附带核验** |
| Q2 | Unpaywall **留**（互相对账）；**会去注册 OpenAlex key** |
| Q3 | 核对官方说法；**DOAJ key 不好搞 ⇒ 接受替代** |
| Q4 | **支持 HTTP 与 SOCKS5**；**所有连接一律 HTTP/1.1** |
| Q5 | **参考 `server_bge.py` 的 RPM/TPM 令牌桶 + 「任尔几路来我只一路去」** |
| Q6 | **两方都报，给 LLM 判断** |
| Q7 | 跟 `~/ai-services` 默认大流 |
| Q8 | 查 |

## 7.2 ⚠️ 最重要修订：OpenAlex 已从「免费无限」变为**按操作计价**

官方定价（`docs.openalex.org/access/example-costs` 与 `/access/pricing`）：

| 操作 | Cost per 1,000 calls |
|---|---|
| **Get single entity**（按 ID 或 DOI） | **Free** |
| List + filter | $0.10 |
| **Search**（全文关键词） | **$1** |
| Semantic search | $1 |
| **Content download**（缓存 PDF） | **$10** |

**免费日额度**：**有 key = $1/天**；**无 key = $0.10/天**。重置时间 **midnight UTC**（= 北京时间 08:00）。

$1/天实际能买到：

| 操作 | 次数 | 结果数 |
|---|---:|---:|
| Get a single entity | **无限** | 无限 |
| List + filter | 10,000 | 1,000,000 |
| **Search** | **1,000** | 100,000 |
| Content download | 100 | 100 PDFs |

### 由此产生的三条硬结论

**① Q2 的答案从「可选」变「必须」**：无 key 只有 $0.10/天 = **100 次检索/天**。
用户已同意注册 ⇒ 必须注册。**key 存仓库外**（同 github PAT 的纪律）。

**② Q1=检索 恰好是唯一收费的操作。** 但 1,000 次检索/天对「个人写设定参考」绰绰有余。
官方 tip 明写：**`per_page=100` 让预算用得更远** ⇒ 一次检索取 100 条。

**③ 官方定价把「下载」定为「检索」的 10 倍。** 这从**经济上**印证了「不提供下载」——
而且 OpenAlex **自己就有内容 API（缓存 PDF）**，是**我们必须显式不碰**的那个操作。

**④ 口径警告**：`openalex.org` **网站浏览吃同一个预算**（匿名 $0.10/天）。官方原文：
「one search on the website is roughly 18 credits, while a programmatic `/works?search=` call is 10 credits」。
⇒ **浏览器里翻 OpenAlex 会在你看不见的地方耗尽当天额度**（又一个「静默」）。

### 批量 DOI 的两条路需选一

| 路径 | 请求数 | 成本（100 个 DOI） | 说明 |
|---|---|---|---|
| 100 次 singleton | **100** | **$0** | 免费，但吃 100 req/s 上限；串行下发会慢 |
| 1 次 OR filter（≤100 值） | **1** | **$0.0001** | 成本可忽略（$1/天 ⇒ 10,000 次） |

**推荐混合**：单个 → singleton；**≥10 个 → OR filter**。

## 7.3 Q3：DOAJ 替代 —— 官方语义已核实 ✅

OpenAlex **source 对象**上（`docs.openalex.org/api-entities/sources/source-object`）：

```
is_in_doaj             Boolean — 该 source 是否被 DOAJ 收录（约 23,000 源）
is_in_doaj_since_year  进入 DOAJ 的年份
is_oa                  「fully OA venue」—— 该刊每一篇都 OA。驱动其内作品的 gold vs hybrid/bronze
type                   journal | conference | repository | ebook platform | book series | ...
```

**原疑问「判期刊还是判文章」有了答案：`is_in_doaj` 是 source 级（判期刊）。**
而 DOAJ 的文章级收录 ⟺ 期刊在 DOAJ 且文章在该刊 ⇒ **等价，替代成立**。
且 work 侧还有 `primary_location.source.listed_in` / `locations[].source.*` / `best_oa_location.source.*` 三条路径取到该 source。

⇒ **DOAJ 独立挂载取消**（用户也确认 key 不好搞）。

## 7.4 Q7：venv 依赖 —— 已实测，结论比预期好 ✅

`~/ai-services` 实测（2026-10-03）：

```
Python 3.12.13
mcp        2.2.0      ← 关键：冲突根源是 papersearch 自己钉 <2，不是 ai-services
httpx      0.28.1     ← 默认 HTTP/1.1，不启 h2 即满足 Q4 要求
httpcore   1.0.9
socksio    1.0.0      ← 已装 ⇒ httpx 原生支持 socks5://
pydantic   2.13.5
vllm       0.30.0     ← 冲突源在这里（要 mcp>=2.0.0）
```

**⇒ 按 `mcp 2.2.0` 写，直接进 `~/ai-services`，不开独立 venv。**
**⇒ SOCKS5 零成本**（socksio 已就位）。
**⇒ HTTP/1.1 是默认**，纪律只剩一条：**任何地方都不许 `http2=True`**。

已有先例：`mcp_localgit.py` 自带 mcp 1.x/2.x 兼容层（注释「由 tools/mcp2_migrate.py 生成，勿手改」），
其 mcp 2.x 形态为 `Server(on_list_tools=..., on_call_tool=...)` + `add_request_handler()`。

## 7.5 Q5：直接复用 `server_bge.py` 的限流器 —— 而且它一箭双雕 ✅

已读 `<数据服务目录>\MCP\memoria-del-hielo\server_bge.py`。核心设计：

```python
class RateLimiter:
    """远端 RPM/TPM 令牌桶（平滑补充）+ 按到达顺序串行转发（FIFO）。
    rpm/tpm = 0 表示不限流（串行锁仍生效：请求按到达顺序排队）。
    配置: 环境变量 REMOTE_RPM / REMOTE_TPM（0=不限，默认 0）。"""
    self._serial = asyncio.Lock()          # ←「任尔几路来我只一路去」
    self._req_tokens = float(rpm)          # RPM 桶
    self._tok_tokens = float(tpm)          # TPM 桶
    # 平滑补充（非窗口重置）：
    min(cap, cur + elapsed * rpm / window)

class RateLimiterOversize:
    """单笔请求 token 数超过整个窗口配额 —— 桶容量上限就是 tpm，
    等待永远不会成功 ⇒ 必须显式拒绝而不是排队。"""
```

**⭐ 关键发现：那把串行锁同时满足两个外部硬约束：**

| 源 | 官方约束 | 由什么满足 |
|---|---|---|
| Crossref Public | **并发 1** | `_serial`（并发天然=1） |
| arXiv | **单连接** | `_serial` |
| 任何源 | 频率 | RPM/TPM 桶 |

**⇒ 「任尔几路来我只一路去」不只是限流，它就是并发约束本身。**

**另外两条要一并抄过来的设计：**
1. **`RateLimiterOversize` 立即拒绝不排队** —— 对应我们要的「不挂住」（5 分钟超时的病根）
2. **`令牌桶 + 真实用量滑窗`** —— 官方注释：「毫秒级就补回…**答不了"这一分钟用了多少"**；滑窗才是答案」
   → 对 OpenAlex 尤其重要：它是**$1/天预算制**，需要的是"今天花了多少"，不是"桶里还剩几个"

## 7.6 Q4：代理细则（已定）

- 支持 `http://` 与 `socks5://`（后者零成本，socksio 已装）
- **所有连接 HTTP/1.1**：httpx 默认即是；纪律 = **永不 `http2=True`**
- 全局变量 + 按源覆盖 + **启动打印每源生效配置**（防「静默指错」）

## 7.7 Q6：冲突处理（已定）

**两方都报，给 LLM 判断。** 契约里 `provenance` 必带；同时保留 `values_by_source`，
不静默取一个。理由：这是「给模型判断」而非「替模型判断」，与用户一贯立场一致。

## 7.8 Q8 剩余待核实（更新后）

| # | 事项 | 状态 |
|---|---|---|
| 1 | OpenAlex 日预算 | ✅ 已核实（$1/天有 key，$0.10/天无 key） |
| 2 | `is_in_doaj` 语义 | ✅ 已核实（source 级） |
| 3 | ai-services 依赖 | ✅ 已实测（mcp 2.2.0 / socksio 1.0.0） |
| 4 | **Europe PMC** 认证与限速 | ❌ 抓取 403，**未核实** |
| 5 | **bioRxiv / medRxiv** 限速 | ❌ 官方文档未公布 |
| 6 | **DOAJ API v2** 是否仍可用 | ❌ 未核实（官方已到 v4） |
| 7 | OpenAlex 对 **IACR / ChemRxiv / SSRN** 的覆盖率 | ❌ 未核实（决定「缺口回源」补哪几个） |
| 8 | **IACR ePrint** 是否有官方 API | ❌ 未核实（已有实践是 scrape） |

## 7.9 修订后的形状（一句话）

> **一个检索器**：以 OpenAlex 检索为主力（`per_page=100`，1000 次/天额度），
> **Crossref / arXiv / bioRxiv+medRxiv 作为源特定的补充检索**，
> **Unpaywall（OA 定位）与 OpenAlex（OA 状态）互为对账**，**两方都报**；
> **不提供下载**（版权 + 限速 + 静默降级 + 官方定价 10 倍，四条理由）；
> **串行令牌桶**统一所有下游；**进 `~/ai-services`，按 mcp 2.2.0 写**。

---

# §8 终局设计（2026-10-03，第二轮裁决后）

## 8.1 用户裁决（第二轮）

| 问题 | 裁决 |
|---|---|
| OpenAlex | **关掉**（顾虑：$1/天是无法加高的硬顶） |
| 方案 | **C** —— Unpaywall + Crossref 为骨干，**OpenAlex 做成可选开关** |
| Unpaywall email 变量 | **`PAPERSEARCH_UNPAYWALL_EMAIL`**（去掉多余的 `_MCP_`） |
| 配置体系 | **一律走 `.env` 或环境变量**；**Python 顶部变量只做兜底** |
| 新增约束 | ⭐ **要考虑发布**（以后推到 GitHub） |

### 8.1.1 一处事实更正（已告知，用户仍选方案 C）

OpenAlex 官方定价页原文：**「no payment method required」** —— **免费层不需要支付方式**。
需要美元渠道的只是**超额后补款**。

⇒ 用户顾虑的**真实理由**不是"要花钱"，而是：**$1/天是一道无法加高的硬顶，撞上就得等 UTC 午夜**。
而 Unpaywall（100k/天）/ Crossref（10 req/s）**都没有这种"撞墙就停"的性质**。
**⇒ 裁决成立，理由应记为「不接受无法自救的硬顶」，不是「买不起」。**

## 8.2 「不提供下载」的四条理由（终版，进 README 作为设计声明）

1. **版权**：arXiv 使用条款「不得做的事」明文禁止第三方转存与再分发
   （「Store and serve arXiv e-prints … from your servers, unless you have the permission of the copyright holder」；且「arXiv is not the copyright holder」）
2. **限速**：arXiv 官方为「每 3 秒 1 次、单连接」，且对**你控制的所有机器合计**
3. **静默降级**：出版商站点在国内常不可达；失败常表现为「HTTP 200 但内容是 PDF.js 空壳 / 登录墙」——
   模型以为拿到了论文，实际拿到一页 JS，然后**基于它编结论**。按本项目原则「以静默降级为耻」，应从接口层消除
4. **经济**（若启用 OpenAlex）：官方定价把 **Content download 定为 Search 的 10 倍**（$10 vs $1 / 1000 次）

**设计声明（README 草稿）**：
> 本工具只报告**元数据与获取路径**，不下载全文。四条理由见上。拿到 DOI 与路径后，由人决定怎么取。

## 8.3 配置体系（发布导向）

### 优先级（高 → 低）

```
① 真实环境变量（最高，可临时覆盖）
② .env 文件（发布项目的推荐入口）
③ Python 顶部常量（**只做兜底**，必须是可公开的安全默认值）
```

**纪律**：Python 顶部常量里**永远不出现凭据、绝对路径、个人身份信息**。
原因：**将来要推到 GitHub**。任何"为了跑得通向里塞一下"的值，都会随发布泄露。

### 环境变量清单（前缀 `PAPERSEARCH_`）

> ⚠️ **本节前缀已作废（2026-10-03）。** 当时定这个前缀是沿用上一代
> PaperSearchMCP（`paper-search-mcp`）的命名空间；但本项目叫 pergaminos，
> 两个项目共用前缀会让同名变量互相覆盖、且无法从名字判断归属。
> 现行前缀为 **`PERGAMINOS_`**，逐条对应关系不变——权威见
> `契约-mcp-pergaminos-v0.1.md` §9。本节保留原文，作为当时的决策记录。

| 变量 | 必填 | 说明 |
|---|---|---|
| `PAPERSEARCH_UNPAYWALL_EMAIL` | ✅ **必填** | Unpaywall 要求 URL 参数带 email |
| `PAPERSEARCH_CONTACT` | 建议 | **User-Agent 里的联系方式**。Crossref 官方 best practice 明写要"specify a User-Agent header that identifies you and your script"；arXiv CoC 同理 |
| `PAPERSEARCH_CROSSREF_MAILTO` | 建议 | 进 **Polite 池**（10 req/s 并发 3，vs Public 的 5 req/s **并发 1**） |
| `PAPERSEARCH_OPENALEX_KEY` | 可选 | **空 = 不启用 OpenAlex**（方案 C 的开关） |
| `PAPERSEARCH_PROXY` | 可选 | **空 = 不挂代理**。支持 `http://` 与 `socks5://` |
| `PAPERSEARCH_PROXY_BYPASS` | 可选 | 逗号分隔的源名，例 `arxiv,crossref` |
| `PAPERSEARCH_TIMEOUT_MS` | 可选 | 单请求超时（默认给一个**短**值，避免 5 分钟挂住） |
| `PAPERSEARCH_ENV_FILE` | 可选 | 指定 `.env` 路径 |
| `PAPERSEARCH_LOG_LEVEL` | 可选 | |

### ⭐ 启动时**必须**打印生效配置（防「静默指错」）

本项目已有「静默指错」这一故障类（melquiades `dsh.home` 写死旧名 → `files=0/0` 退出码 0）。
**代理配置不打印 = 又一次静默指错。** 启动时逐源打印：

```
[conf] unpaywall   proxy=(none)     email=set        pool=- 
[conf] crossref    proxy=http://…   mailto=set       pool=Polite(10/s, conc 3)
[conf] arxiv       proxy=(none)     min_interval=3.0s
[conf] openalex    DISABLED (no key)
```

## 8.4 方案 C 的源清单与角色

| 源 | 角色 | 认证 | 限速（官方） | 备注 |
|---|---|---|---|---|
| **Unpaywall** | **OA 骨干**：`oa_status` / `oa_locations[]` / `best_oa_location` / **`journal_is_in_doaj`** / **`has_repository_copy`** | email 必填 | 100,000/天 | 无检索能力（`/v2/search` 已 410） |
| **Crossref** | **检索主力 + 元数据权威** | 无 / Polite(mailto) | Public 5/s **并发1**；Polite 10/s **并发3** | ⭐ **免费且无硬顶** |
| **arXiv** | 预印本检索 | 无 | **3 秒 1 次，单连接**，全机器合计 | DOI 由 **DataCite** 注册 ⇒ **Crossref 搜不到** |
| **bioRxiv / medRxiv** | 预印本 | 无 | 未公布（待核实） | 返回 **`published`** ⇒ 预印本→正式版映射 |
| ~~OpenAlex~~ | **可选开关**（配 key 才启用） | 免费 key | $1/天 | 启用后补：跨源 ID 桥 / `locations[]` 含付费位置 / 批量 100 |

### 8.4.1 检索的现实约束（必须写进 README）

- **Unpaywall 不能检索**（`/v2/search` 410 Gone）
- **Crossref 是元数据检索**（题名/作者/期刊/摘要），**不是全文检索**
- **arXiv 的 DOI 走 DataCite，不在 Crossref** ⇒ 预印本必须单独走 arXiv API
- **bioRxiv/medRxiv 没有全文检索**（只有日期区间 / DOI 单查）

**⇒ 检索要"多源并行 + 结果合并"**，且必须在描述里说清各源的覆盖边界。

## 8.5 发布准备清单（GitHub）

**参照既有待办**：草稿纸 `id=1103`（key `todo-export-github-public`）已有同族清单
（「公开前的凭据/绝对路径/私人语料清理清单」）。本条为本项目的实例化版本。

| # | 项 | 检查方式 |
|---|---|---|
| 1 | **无凭据入库** | 全历史扫描（不是只看 HEAD）；`.env` 必须 gitignored |
| 2 | **`.env.example` 随仓发布** | 只含占位值 + 注释说明 |
| 3 | **无绝对路径** | 全仓 grep `/mnt/`、`/home/`、`<D盘>:\\`、`<C盘>:\\` |
| 4 | **无私人语料** | 本项目不该含任何语料；检查测试 fixture 是否夹带真实 DOI 列表/摘要 |
| 5 | **无个人身份** | 默认 User-Agent / email 占位，不得写死 |
| 6 | **`LICENSE`** | 待定（注意：依赖方 arXiv 元数据是 CC0，Crossref 数据有自己的条款） |
| 7 | **README 写清四条「不下载」理由** | 见 §8.2 —— 这是公开项目的**设计声明**，不是免责 |
| 8 | **依赖最小化** | 只需 `mcp>=2.2` + `httpx`（+ httpx 的 socks 支持） |
| 9 | **git 历史干净** | 若曾提交过凭据，**必须重建历史**，不是删文件了事 |

## 8.6 待你最后的三个命名决定

| # | 项 | 待定选项 |
|---|---|---|
| 1 | **仓库名** | `dsh-papersearch` / `papersearch-mcp` / 其它 |
| 2 | **MCP serverName** | 影响工具前缀 `mcp__<serverName>__*`。沿用 `papersearch`？ |
| 3 | **工具名** | 建议 `paper_search`（检索）+ `paper_oa`（OA 与收录对账），待定 |

## 8.7 剩余未核实（照旧不填猜测值）

Europe PMC（403）· bioRxiv/medRxiv 限速 · DOAJ API v2 状态 · IACR ePrint 是否有官方 API
