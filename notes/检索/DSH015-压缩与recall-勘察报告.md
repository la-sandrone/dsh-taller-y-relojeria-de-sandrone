# DSH 0.1.5 自动压缩 / 会话存储 / recall 通路 —— 源码勘察报告

> ⚠️ **本报告的结论部分已被取代**（2026-09-12）。
> 请以 **《[DSH015-压缩与recall-定案报告.md](DSH015-压缩与recall-定案报告.md)》** 为准。
> 已订正三处（文中都标了【订正】）：① auto-memory 的 0.75 数字；② `lib/index.js` 不是编译产物；
> ③ 「官方工具可按关键词找回被压原文」对**中文不成立**（FTS5 `unicode61` 把整句中文当一个 token）。
> 本文的过程记录（源码定位、实测命令）仍然有效。

> 勘察对象：`原始代码研究/v0.1.5-rc.2`（现役基座）、`<挂载d>:/DataServices/MCP/wrap/{fast_filesystem.py, mcp_recall.py}`
> 勘察方式：源码逐行 + 真机实测（现役 9007 活会话 + 两份导出 jsonl）
> 结论口径：**凡标注「实测」的都有命令与数字；凡标注「源码」的都有 `文件:行`。**

---

## 〇、上下文恢复结论（先说恢复到了什么）

| 来源 | 恢复到的关键内容 |
|---|---|
| `DSH 0.1.1 到 0.1.5 升级.jsonl`（2483 行 / 17.0 MB / 10 次压缩） | 升级主线 10 个话题、关键决策表、8 项产出物、遗留待办 A/B/C；其中 **C 段「recall 修复 A–F 未实施」** 只见条目未见细目（原文在压缩掉的前半段） |
| `scan v3 …jsonl`（7196 行 / 7.2 MB / 未压缩过） | scan v3 八话题全索引 + 关键决策表。**recall 的原始设计假设全部在此**（见第三节） |

两处需要点出的**继承自旧场的错误前提**（本次勘察推翻，详见后文）：

1. 「curl export 实测本机免认证 200」——**在 0.1.5 上已不成立**（实测 401）。
2. 「packChunks 打包单行仍可逐行 json.loads」——那是 v1/v2 **物理解码器**的残留概念，v3 一行一事件，不构成本次问题。

---

## 一、现行自动压缩机制与存储格式（源码实证）

### 1.1 谁来压缩、什么时候压

| 项 | 事实 | 依据 |
|---|---|---|
| 实现包 | `dsh-compaction-basic` | `packages/compaction/compaction-basic/src/config.ts` |
| 触发点 | `agent/pre-step` 串行监听器，**请求派生前**用 `ctx.tokenMeter` 给最新持久 envelope 定价 | `compaction-basic/README.zh.md:112` |
| 阈值 | `thresholdRatio = 0.8`（默认）→ `floor(contextWindow × 0.8)` | `config.ts:20` |
| 保留 | `retainRatio = 0.16`（默认）→ 近期 16% 逐字保留 | `config.ts:23` |
| 摘要输出上限 | `maxTokens = 8192` | `config.ts` resolveConfig |
| 溢出兜底 | `agent/request-error` 监听 `CONTEXT_WINDOW_EXCEEDED`：**绕过阈值**做一次最大平衡头缩减后重试 | `compaction-basic/README.zh.md:112` |
| 手动 | `/compact`（`dsh-command-compact`） | 同上 `:85` |
| 保护 | 选中范围**从第一个非 `system/message` 的 surface 节点起** → 系统提示词永不被遮蔽 | 同上 `:112` |

**装在哪：** base bundle 里 `compaction-basic` / `command-compact` / `tool-result-pruner` 是挂着的（`packages/bundle/base/cordis.patch.yml:320/327/395`），但 **web-app bundle 又把三者 `disabled: true`**（`packages/bundle/web-app/cordis.patch.yml:427/432/440`）——因为 Web 形态把压缩下放到**每 preset**。

**你的实际生效配置**（`dsh-domus/.agent-presets/coding/agent.cordis.yml:588-604`）：

```yaml
- id: compaction
  name: cordis:group
  isolate: { compaction: true, toolResultPruner: true }
  config:
    - id: compaction-basic          # 无 config → 吃默认 0.8 / 0.16 / 8192
    - id: command-compact
    - id: tool-result-pruner        # thresholdChars 8192 / head 4096 / tail 1024
```

→ ~~**0.75 vs 0.80 这个数字是真的**（dsh-auto-memory 声称压在宿主 0.80 之下，与源码一致）。~~
**【2026-09-12 订正】**：这句错了。它的分母是 `window − reserve`（源码 `lib/index.js:1904`），
实测在**声明窗口的 47.5%**（≈49.8 万 token）就触发，而宿主在 80%（≈80 万）——**早触发约 45%**。
且 v2.4.2 出厂 `handoffEnabled: false`（`lib/index.js:254`），README「默认开启」是假的。
详见《DSH015-压缩与recall-定案报告.md》。

### 1.2 存储格式：v3 到底变了什么

**文件命名**（`packages/session/session-persistence-jsonl/src/format.ts:57` 的 `generationLogFilename` → `session-format/sessionFormatLogFilename(v)`）：

- `sessionFormatLogFilename(v)`：v0 → `session`（无后缀），v≥1 → `session.vN`
- 所以现役是 `session.v3.jsonl.zstd`（zstd 多帧拼接）
- **迁移保留旧代**：实测会话 `session-db9f2d32…` 目录下**同时存在 `session.v0.jsonl.zstd` 与 `session.v3.jsonl.zstd`**（mtime 差 14 分钟，v3 是活的）→ 任何"按目录取文件"的逻辑必须挑**当前格式版本**，不能取第一个。

**事件封套**（`.agents/notes/implemented/architecture/2026-09-06-v3-canonical-session-envelopes.md`）：

- `system/message` / `user/message` / `assistant/message` / `tool/result` **强制带 `surfaceOp`，且它在顶层**，与 `type/seq/time/data` 平级。
- 实测活会话：`top keys = ['data','seq','surfaceOp','time','type']`，`data keys = ['message','step','stream','turn','usage']`。
- **`assistant/message` 内嵌 provider 原始流 `data.stream`**（v2 引入，"embedded assistant streams"）——这是本次最重要的发现，见第二节。
- v3 **不再允许 `request/header.header.system`**：系统提示词改由 `system/message` 承载。原来"避开 request/header 里 140KB persona"的理由因此失效，但**换了新污染源**（见 1.3）。

**压缩事务**（`packages/compaction/compaction/src/types.ts`，`known-event-types.ts`）：

| 事件 | 语义 |
|---|---|
| `compaction/start` | 上锁，`{compactionId, turn: number\|null}`（null=手动、轮间） |
| `compaction/summary` | 摘要正文在 **`data.summary: ContentBlock[]`**；另有 `shadowedSeqs/shadowedRange/shadowedTokenCount/model/provider/maxTokens/usage`；`rawOutput`/`llmStreamCall` 是审计转储（与 summary 重复） |
| `compaction/end` | 放锁，`error?` 记录失败 |
| `compaction/prune` | **v3 新增**：无模型的"修剪替换"（超大工具输出），只有 `shadowedRange/shadowedSeqs/shadowedTokenCount`，**无 compactionId** |

实测：`compaction/summary` 的 `data.summary` 是 `[{type:'text',...}]`，与 `data.rawOutput` 内容重复；一行 `compaction/summary` 后面紧跟一行 `user/message`（承载摘要的 surface 替换，`surfaceOp: {op:'replace', startSeq, endSeq}`）。

### 1.3 官方工具仍然查不到压缩摘要（0.1.5 未修）

`packages/session-query/session-query/src/extraction.ts` 的 `extractSessionEventText()` **switch 里根本没有 `compaction/*` 分支** → 走 `default: return ''`。

→ **旧场「官方 session-query 对压缩块是盲区」的结论在 0.1.5 依然成立**，自制 recall 的动机未被上游消解。

该文件同时给了两条**权威判据**，正好印证下面要提的修法：

```ts
case 'assistant/message': return contentText(event.data.message.content)   // 只读正文，不读 stream
case 'reasoning': return []                                                // reasoning 不进检索
```

---

## 二、`fast_filesystem.py` 的索引恢复部分：**要改，且有一处实测回归**

### 2.1 必修：v3 的 `stream` 让文本被**整整抄两遍**（实测）

`_jsonl_extract_texts()`（`fast_filesystem.py:1982-2009`）的排除集是：

```python
_AUDIT_KEYS = {"rawOutput", "llmStreamCall"}
```

v3 新增的 `data.stream` 是**同一份 provider 流的副本**，其中 `stream[].chunk.block` 与 `content[]` 里的 text 块**逐字相同**：

```
实测（现役活会话，24 条 assistant/message）：
  line 17: content_text=83B → washed=166B   ratio 2.00  ← 14 条里 5 条如此
```

**在真实索引块上的代价**（`DSH 0.1.1 到 0.1.5 升级.jsonl` 行 2479 的索引消息）：

| | 现行 | 加 `stream` 后 |
|---|---|---|
| 洗出字节 | 15,216 B | **7,608 B** |
| 与官方 `content` 正文一致？ | 否（2×） | **是（完全一致）** |

**整条 scan 的预算影响**（同一文件，`max_results=3`）：

```
现行        ：输出 22,695 B / 48KB 预算
加 stream 后：输出 14,823 B       → 省出 7,872 B（35%）
```

`max_results=0`（全部候选）或 `detail_lines` 提取大消息时，浪费同比放大——**索引块本身 7.6KB 会被算成 15.2KB，直接触发"折叠为行号"**，索引恢复退化。

**修法（一行）**：

```python
_AUDIT_KEYS = {"rawOutput", "llmStreamCall", "stream"}
```

> 判据来源不是猜的：官方 `extractSessionEventText` 也**只读 `data.message.content`，不读 stream**（`session-query/src/extraction.ts`）。

### 2.2 复核：其余部分**不用改**（逐条查过）

| 检查点 | 结论 |
|---|---|
| `_detect_file_format` 认不认 v3 | **认**。v3 首行 `{"type":"session","version":3,…}`，第 2/3 行含 `"seq"` → `jsonl_hits≥2` |
| 候选过滤还成立吗 | **成立**。精确路径要求 `"type":"assistant/message"` + `░ 对话索引 ░`。实测活会话里 `request/header`（工具 description）、`tool/result`、assistant 的 **reasoning 块**都含 `░`，但：reasoning 不被 `_jsonl_extract_texts` 采集（只收 `type=="text"`），其余类型行被类型条件挡掉 → **无假阳性**（专门验证过，0 例） |
| `compaction/prune` 未处理 | **无需处理**。它无 `compactionId`，`_extract_compactions` 按 cid 过滤自然跳过；prune 无摘要可恢复。仅建议：若某会话**只**发生 prune，scan 会报"未发现压缩记录"，措辞可微调 |
| `_extract_compactions` 对 v3 | **实测通过**。对真 v3 文件 `session-db9f2d32…`（2482 行）跑出 **10 条 completed 记录**，首条 `turn=4 / 遮蔽117条 / 77,844 tokens / 摘要12,158B`，与导出件完全一致 |
| 48KB 预算 | 逻辑没问题；瓶颈是 2.1 的重复计数 |
| U+2591 转义 | 有效。**但请注意**：本报告勘察时我用 `zstdcat | python` 打印过原始行，已把字面 `░` 灌进本会话的 `tool/result`（活会话里确有 2 处）——这正是 preset 里那条禁令要防的事，我自己也踩了，后续勘察改用"只打印 JSON 路径"的方式 |

### 2.3 建议顺手加的两个能力（非必修）

1. **`.jsonl.zstd` 直读**：`_detect_file_format` 对 `.zstd` 二进制会判成 `text` 输出垃圾。加一个后缀短路（`zstdcat`/`zstandard` 解压后再走 JSONL 分支），就能**直接 scan 活会话文件**，省掉"导出→落盘→再扫"全流程。实测 `zstdcat` 可用；`~/ai-services` venv **没有 `zstandard` 模块**，需 `pip install zstandard` 或 shell 调 CLI。
2. **宽松回退的噪声**：`precise==0` 时的回退匹配 `"对话索引" in line`，而 assistant 正文经常提到"对话索引"四个字（比如现在这场）。属可接受降级，仅记录。

---

## 三、mcp-recall：重建思路（三个方案，全部实测过）

### 3.0 先说现状：**它不是"要爆改"，是"已经被认证墙拍死"**

`mcp_recall.py` 的整条通路建立在两个前提上，**两个前提在 0.1.5 都没了**：

| 旧前提 | 0.1.5 现实 | 证据 |
|---|---|---|
| `GET /api/session.export` 本机免认证 200 | **401 Unauthorized** | 实测 `curl` → `http=401 body="unauthorized"` |
| （隐含）ZIP 内文件叫 `session.jsonl` | **`session.v3.jsonl`** | 实测 200 后 `namelist=['session.v3.jsonl']` |

401 的根因是 0.1.5 **新引入**的浏览器会话认证：

- `packages/client/connection/src/browser-auth.ts` —— **0.1.1 根本没有这个文件**（`v0.1.1-rc.2/packages/client/connection/src/` 里无 `browser-auth.ts`）
- `/api/*` 全部走 `requestRejection()`：先 Host/Origin 栅栏（403），再 `browserAuth.isAuthenticated()`（401）——`rpc-host.ts:97-99`
- 启动令牌是 **`randomBytes(32)` 的进程内 WeakMap**，只通过 `authenticatedUrl()` 拼进 `dsh web` 打印的那条 URL（`browser-auth.ts:52-60`，`bundle/web-app/src/index.ts:262-271`），**磁盘上不留**；浏览器用它换签名 cookie。

**环境变量那条路依旧堵着**（旧场结论仍对）：`scrubbedParentEnv()` 删 `DSH_*`，且删 `/KEY|PASSWORD|SECRET|TOKEN/i`（`packages/subprocess/subprocess/src/index.ts:45` 定义、`:67` 过滤循环）。

### 3.1 方案 B：修 HTTP——**用本机持久化的签名密钥自铸 cookie**（实测通）

cookie = `dsh-auth-<b64url(sha256(authority))>` = `v1.<b64url(payload)>.<b64url(HMAC-SHA256(secret, body))>`，
`payload={version:1, authority, issuedAt, expiresAt}`（`browser-auth.ts:126-145, 272-290`）。

签名密钥**明文躺在** `$DSH_HOME/.credentials.yaml` 的 `client-connection/browser-session` 记录里（`payload.secret`，32 字节 base64url）。

**实测结果**：

```
no-cookie     : HTTP 401 body=b'unauthorized'
forged-cookie : HTTP 200 type=application/zip bytes=318051 entries=['session.v3.jsonl']
```

改动量：`_fetch_session_jsonl` 换成「读 yaml 取 secret → 铸 cookie → 带 `Cookie:` 头请求」＋ZIP 条目名优先取 `session.v<当前版本>.jsonl`。
代价：**绑定本机凭据文件、绑定 authority（`127.0.0.1:9007` 换端口即失效）、cookie 有效期上限 `cookieMaxAgeDays=30`**。能用，但脆。

### 3.2 方案 C：**彻底不碰 HTTP**——直读会话日志文件（实测通）

```
按 id 定位：$DSH_HOME/sessions/*/session-<id>/session.v*.jsonl.zstd
解压读取  ：zstdcat（实测：406 行，首行 {"type":"session","version":3,…}）
```

- **不需要 session 定位的 HTTP 往返、不需要认证、不需要令牌**。
- 会话 id 仍然由模型 `echo $DSH_SESSION_ID` 提供（这条 bash 桥保留）。
- `DSH_HOME` 到不了子进程 → 用 **cordis.patch.yml 的显式 `env`** 绕过：`Config.env = z.dict(String).default({})` 且 `buildChildEnv = {...scrubbedParentEnv(), ...extra}`（`mcp-client/src/index.ts:119`，`transport.ts:20-22`）→ **显式 env 在 scrub 之后合并，一定到得了**。注意**变量名不能用 `DSH_` 前缀、不能含 KEY/TOKEN/SECRET**（会被误删），用 `RECALL_DSH_HOME` 之类。
- 坑1：同目录可能同时有 `session.v0` 和 `session.v3` → **必须取当前格式版本**，或取 mtime 最新。
- 坑2：`~/ai-services` venv **无 `zstandard`**；用 `zstdcat` 或补依赖。
- 坑3：活文件正在追加 → 读到半帧的风险，需容错（按行 json.loads 失败即丢尾）。

### 3.3 方案 D（推荐长期）：**从 MCP 改成 DSH 插件（in-process）**

scrub 和认证墙**都是"进程外"的代价**。0.1.5 官方推荐形态是双半插件（`dsh.bundle.patch` + `dsh.client`），社区两个项目都走这条路。改成插件后：

- 直接拿 `ctx.agent.session` / session store，**没有 env、没有 401、没有 zstd 解压**；
- 可以作为 `agent/pre-step` 钩子，在**宿主 0.8 压缩之前**做事（dsh-auto-memory 就是这么干的）；
- 代价：要写 TS、要 build、要跟 `@deepseek-ai/dsh-*` peer 版本绑定。

### 3.4 顺带逮到的一个悬挂引用

**5 / 6 个 preset 仍在教模型用已卸载的工具**：

```
.agent-presets/{academic,coding,fantasy,general,scifi}/agent.cordis.yml：各 1 处 recall_compactions
.agent-presets/liangshen/：0 处
profiles/web/cordis.patch.yml：mcp-recall 条目已删 → 工具不存在
```

旧场决定「先不挂，免得旧实现干扰」——但 prompt 段（含 `recall_compactions` / `recall_compaction_detail` 用法说明）没同步摘掉。要么复活工具，要么把这段 prompt 一起摘/改。

### 3.5 现有代码可直接复用的部分

`mcp_recall.py` 里**只有取数那一段（`_fetch_session_jsonl`）坏掉**，其余全部可用、且与 scan v3 同源语义：

- `_extract_compactions()` — 与 `fast_filesystem._extract_compactions()` 同构（多了 `time` 字段），实测对 v3 有效
- `_escape_zone()` U+2591 转义 — 保留
- 双工具两段式（list 元数据/开头 + detail 全量）、60s 缓存 — 设计仍然成立（单块摘要实测 **12,158 B**，远在 50KB spill 线下，detail 全量输出安全）

---

## 四、两个项目调研

### 4.1 `Qinling-Melon-Farmers/dsh-memoir`（27★ / TypeScript / Apache-2.0 / v0.7.0）

**定位：本地优先的跨会话"项目记忆"**——不是聊天记录备份，是**被策展的结论库**。零捆绑运行时依赖、无 embedding、无云服务。

- **版本对口**：`package.json` 的 `dsh.engines.dsh = ">=0.1.5-rc.1 <0.1.6-0"`，CHANGELOG 说明 0.7.0 就是**为 DSH 0.1.5-rc.1 做的兼容发布**（0.1.1-rc.2 用户钉 0.5.6，0.1.2 用户钉 0.6.2）。**你要装的话是直接对口的那一档。**
- **形态**：双半插件。Host 半注册 `memoir_record` / `memoir_read` / `memoir_update` 工具 + `/api/dsh-memoir` 面板路由 + turn-end 自动蒸馏监听 + 每项目 system-prompt 公告；Browser 半注册原生「记忆」会话视图与 Settings 分区（走官方 slot，不劫持 DOM）。
- **三层数据**：`~/.dsh/dsh-memoir.json`（SSOT）+ `<项目>/PROJECT_MEMORY.md`（可读可提交投影）+ 检索索引（倒排 + BM25 + 查询缓存）。
- **两个对你有直接启发的设计**：
  1. **Session Snapshot 冻结注入前缀**（`src/host/snapshot.ts`）：同一会话内**首建即冻结**，后续 assembly 一律复用，**新写入只在下个新会话生效**。理由写得很直白——"目标是稳定的模型输入，而不只是快读"，即**最大化 prompt-prefix cache 命中**。这是把"记忆注入"和"KV/前缀缓存"对齐的少见正面案例。反例也写了：v0.4.2 删掉了只用 cwd 的兜底 key，因为会话 A 的冻结快照会被会话 B 领走——**"宁可缓存失效，不可缓存损坏"**。
  2. **相似写入必须显式裁决**：`update`（原地）/ `supersede`（留旧历史标记被替代）/ `force-record`（确认并存），插件只给候选不判真伪。
- **Hot Memory 有硬 token 预算**（默认 900 / 上限 1200），不是把 `PROJECT_MEMORY.md` 整个塞 prompt。
- **已知边界（作者自己写的）**：BM25 是词项召回，跨语言无语义保证；固定质量集 Top-5 命中率 100%，门禁 ≥90%。

### 4.2 `Aik358/dsh-auto-memory`（63★ / JavaScript / BSD-3-Clause / v2.4.2）

**定位：主动联想记忆 + Astra 式上下文管理**。它和你的 recall 诉求**正面撞车**——同一件事的两个方向。

- **核心主张**：*不是压缩，是交接*。上下文将满时在**水位 0.75**（宿主自动压缩线 0.80 之下）写**四段式交接笔记**（任务状态 / 目标 / 已试过的方案与失败原因 / 进度与下一步），合窗翻页；写不进笔记的细节落**本地全量归档，可搜**。它明说边界：「窗口是宿主的领地——她只助产交接，从不越权替宿主做决定」。
- **形态**：双半插件（`pnpm add @a9i5k4/dsh-auto-memory`），Host 半零运行时依赖，可选 Python sidecar（BGE-M3 int8）做语义臂。`cordis.patch.yml` 只有一行 insert。
- **相关能力**：三层记忆（用户级 / 项目笔记 / 每日日志 + 反思层）；`memory_search` 检索**全量归档**、`memory_note` 随手记；技能固化（procedural memory）；日历提醒；跨工具记忆导入（只存路径指针，不复制内容）。
- **值得抄的两点**：
  1. **固定边界注入**：已发出的请求不可改写 → 注入只在固定边界发生，**"前缀缓存永不失效，token 不为回忆买单两次"**。与 memoir 的 snapshot 是同一思想。
  2. **写入门禁**：GBK 乱码 34 项特征、复读退化、连续重复行、外部 AI 画像 JSON 特征、base64 残留——拒写并给中文回执。这条对"记忆/索引类工具"是通用卫生。
- **两条要打折扣的地方**（诚实记录）：
  - `package.json` **没有声明 `dsh.engines.dsh` 版本约束**（只有 `@deepseek-ai/cordis ^4.0.1` peer）。memoir 敢写 `>=0.1.5-rc.1 <0.1.6-0`，它没写 → **0.1.5-rc.2 上能不能跑，需要你自己试**，别当已验证。
  - 架构图里写的是 `DeepSeek Harness (Node, 127.0.0.1:3080)`——默认端口，和你的 9007 不同（应当只是文档没更新，但说明其验证环境未必与 0.1.5-rc.2 对齐）。
  - README 自承限制：「`memory_recall` 会话搜索**依赖已部署的 session-query 索引**」——而 1.3 刚证明 session-query 对 `compaction/*` 是盲区，所以它这条路径**也拿不到压缩摘要**。

### 4.3 对你的选型意义

| 你的诉求 | memoir | auto-memory |
|---|---|---|
| 解决"压缩丢掉的东西拿不回来" | ❌ 不解决（它只存策展结论） | ⚠️ **看似解决，实为打折**：出厂 `handoffEnabled:false`；窗口数学早触发 45%；其 `memory_recall(scope='sessions')` 依赖 **session-query**——而后者中文检索不可用（见定案报告 §1.2） |
| 0.1.5 兼容性 | ✅ 明文声明 `>=0.1.5-rc.1` | ⚠️ 未声明，需实测 |
| 需要 embedding / 大模型下载 | ❌ 零依赖 | 可选（130MB / 563MB） |
| 能当"in-process 插件形态"的参考实现 | ✅ TS，代码量适中，有 test/ | ⚠️ `lib/index.js` **476KB / 8163 行，手写 ESM**（**不是**编译产物——此处原文写错，2026-09-12 订正），是一个 god-file |
| 与你的 scan / recall 是否重复 | 部分（都有本地检索） | **高度重复**（都做归档检索 + 压缩前介入） |

**结论**：两者都不必装。**memoir 读来当"插件怎么读会话、怎么冻前缀缓存"的范本**（`src/host/dsh-home.ts`、`snapshot.ts`、`retrieval.ts` 都很干净，共 ~30KB）；**auto-memory 读来当"压缩前抢救"的产品设计范本**——它证明了你这条 recall 路线的终点不是"事后挖压缩摘要"，而是**"压缩前就交接"**。

---

## 五、建议的下一步（按性价比排序）

| # | 动作 | 工作量 | 依据 |
|---|---|---|---|
| 1 | `fast_filesystem.py`：`_AUDIT_KEYS` 加 `"stream"` | 1 行 | §2.1，实测省 35% 预算且与官方口径对齐 |
| 2 | `fast_filesystem.py`：`.jsonl.zstd` 直读 | ~30 行 | §2.3，扫活会话不再需要导出中转 |
| 3 | 决定 recall 走哪条路：**C（直读文件）** 还是 **D（改插件）** | C 小 / D 大 | §3.2 / §3.3 |
| 4 | 清理 preset 里的 `recall_compactions` 悬挂引用（或随 #3 一起复活） | 5 个 yaml | §3.4 |
| 5 | 若要修旧实现：`mcp_recall.py` 只换取数段 + ZIP 条目名 | ~40 行 | §3.5 |
| 6 | `DETAIL_HEAD_CHARS`/预算类魔法数收进配置 | 小 | 项目规范 |

> **未取证事项**：旧场遗留的「recall 修复 A–F」细目（在压缩掉的前半段），本次未定位到原文；如需，可从 `DSH 0.1.1 到 0.1.5 升级.jsonl` 的压缩点 1–3 摘要里再挖。

---

## 附：勘察痕迹与复现命令

```bash
# 活会话（多帧 zstd）
D=$DSH_HOME/sessions/--home-<user>-deepseek-harness--/session-<id>/session.v3.jsonl.zstd
zstdcat "$D" | head -3

# 导出端点认证现状（401）
curl -s -o /dev/null -w '%{http_code}\n' "http://127.0.0.1:9007/api/session.export?sessionId=<id>"

# 自铸 cookie 后（200，ZIP 内 session.v3.jsonl）—— 见报告 §3.1 的 cookie 构造
```

- 本项目勘察临时目录：`_scratch/gh/`（两个项目的 README 与关键源文件，公开材料，可留可删）
- 本报告未写入任何密钥、令牌或凭据明文。
