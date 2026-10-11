# TXX 测试 prompt 集 —— 「压缩 → 找回」验收

> 目的：验证**官方只读会话工具**（`session_*`）能否找回被 compaction 压掉的内容，
> 并划清它的能力边界（尤其是：能否枚举"压缩事务"）。
>
> 配合已落盘的 D3 阶段 1 配置（`dsh-domus/profiles/web/cordis.patch.yml`）。

---

## 0. 硬前提（每次开测前确认）

| 项 | 要求 | 为什么 |
|---|---|---|
| **工作区** | 必须在 `<挂载d>:/User Data/Documents/作品/冰质星球与是啊，吃什么` 下开会话 | 官方工具有**工作区授权**：目标会话 cwd 必须等于调用方 cwd，否则 `unauthorizedTarget`（`workspace-access.ts:75-90`） |
| ~~新会话~~ | **已作废**（2026-09-12 实测推翻） | 原以为工具列表按会话快照固化——**实测是每次请求刷新**：同一条会话，配置切换前 170 个工具、切换后 175 个。**不必新开对话** |
| **禁用猜测** | 工具报错就**原样贴出**，不要解释成"大概是…"，不要换一种问法重试后声称成功 | 这是验收测试，伪成功比失败更糟 |

### 夹具（已核实，直接用）

| 别名 | `session_id` | 压缩次数 | 只在被压区出现的关键词 |
|---|---|---|---|
| **主夹具**（落实55） | `session-c08b4248-428f-462d-a733-e612a6262adb` | 6 | `莱杜拉的回忆` / `乌兹别克斯坦` / `普通攻击造成` |
| 备用（含11次压缩） | `session-36cd7c18-15cd-4692-bd7c-0ea19bd6c5f7` | 11 | `钩子回收` / `中微子聚变` / `热液起源` / `阿斯加德` |
| 备用2（落实54） | `session-0825e5e7-04bf-4f7a-9533-32fd378bbe02` | 8 | `民间东正教` / `登月逆向` / `圣母修道院` |

### 主夹具的已知 seq（供 T2/T3/T6 用）

| 类别 | seq | 事件类型 |
|---|---|---|
| **被遮蔽**（应只在 `shadowed` 命中） | `11` / `12` / `19` / `27` | user/message ×2、assistant/message ×2 |
| **未遮蔽**（应只在 `current` 命中） | `902` / `909` / `910` / `915` | assistant/message、user/message |

---

## A. 一次性总测（推荐；一个对话跑完 T0–T6）

> 直接整段粘贴。预期耗时：阶段 1 下约 1–3 分钟（T1/T4/T5 会报索引未开，属**预期**）。

```
【压缩→找回 验收测试】按顺序执行 T0–T6，逐项报告。铁律：
  · 工具报错就原样贴出错误文本，不要改写、不要换问法重试后声称成功、不要推测原因；
  · 每项给出结论：PASS / FAIL / EXPECTED-ERROR，并附你实际调用时的原始参数与原始返回；
  · 不要动用 scan_myfilesystem_indices，本测试只验官方 session_* 工具。

主夹具 session_id = session-c08b4248-428f-462d-a733-e612a6262adb

T0 挂载自检：列出你当前可用的全部 session_* 工具名（只列名）。
T1 被压内容检索：session_event_search(session_id=<主夹具>, query="莱杜拉的回忆", surfaces=["shadowed"])
    期望：命中被压掉的原始消息（不是摘要）。
T2 按 seq 读原文：session_event_read(session_id=<主夹具>, seq=11)
    期望：返回该条完整未删节事件。
T3 负对照：session_event_search(session_id=<主夹具>, query="莱杜拉的回忆", surfaces=["current"])
    期望：应为空或明确不命中（该词不在当前表层）。
T4 压缩事务可枚举性【决策关键】：
    session_event_search(session_id=<主夹具>, event_types=["compaction/summary"], query="user")
    期望：若为空 → 说明官方检索语料剔除了压缩事务，D′ 拿不到"压缩点清单"。
T5 默认 surfaces 行为：同 T1 但不传 surfaces，记录默认是否包含被遮蔽内容。
T6 read 不受 surface 限制：session_event_read(session_id=<主夹具>, seq=902)
    期望：未遮蔽的 seq 同样可读。

最后给一张结论表：T0..T6 × (PASS/FAIL/EXPECTED-ERROR) × 一句话证据。
另附：T1/T2 各自返回的字符数（用于评估"别把上下文灌爆"）。
```

---

## B. 单项复测（定位用；任一失败时单独跑）

### T1 · 被压内容检索（核心）
```
在新会话里只做一件事，不要做别的：
用 session_event_search(session_id="session-c08b4248-428f-462d-a733-e612a6262adb",
query="莱杜拉的回忆", surfaces=["shadowed"]) 检索。
把原始返回**逐字**贴出来（不要摘要、不要截断、不要解读）。
然后回答三问：①有无命中？②命中的是原始消息还是压缩摘要？③命中的 seq 是多少？
```

### T2 · 按 seq 读原文
```
用 session_event_read(session_id="session-c08b4248-428f-462d-a733-e612a6262adb", seq=11)
读一条事件。把返回的前 500 字原样贴出，并回答：这条事件的 type 是什么？内容是否完整（没有被截断的迹象）？
```

### T3 · 负对照（证明 T1 的命中不是巧合）
```
对同一会话同一个词做两次检索，参数只差 surfaces：
  ① surfaces=["shadowed"]，query="莱杜拉的回忆"
  ② surfaces=["current"]，  query="莱杜拉的回忆"
两次原始返回都贴出。结论：这个词是否只存在于被压掉的区间？
```

### T4 · 压缩事务可枚举性（决定要不要再做插件）
```
三步，每步贴原始返回：
  ① session_event_search(session_id="session-c08b4248-428f-462d-a733-e612a6262adb",
      event_types=["compaction/summary"], query="user")
  ② session_event_search(session_id="同上", event_types=["compaction/summary"], query="")
  ③ session_event_search(session_id="同上", event_types=["user/message","assistant/message"], query="user")
问题：你能否仅凭官方工具列出"这个会话发生过几次压缩、每次压掉多少、对应的 compactionId"？
若不能，明确说"不能"，并说明缺哪一类信息。
```

### T6 · read 与 surface 无关
```
分别读 seq=11（被遮蔽）与 seq=902（未遮蔽），各贴原始返回前 300 字。
两者是否都能读出来？如果是，说明 read 不受 surface 限制。
```

---

## C. scan 侧对照（**不依赖官方工具**，任何对话都能跑）

> 用途：① 官方工具没挂上/不可用时的兜底；② 交叉验证官方结果；③ 随时复核 D10/D11。

```
用 scan_myfilesystem_indices 跑下面四项，逐项贴原始输出：
1) debug=stats（主夹具，走 sessions 目录里的 .zstd）：
   path="$HARNESS/dsh-domus/sessions/--mnt-d-User~0020Data-Documents-~4F5C~54C1-~51B0~8D28~661F~7403~4E0E~662F~554A~FF0C~5403~4EC0~4E48--/session-c08b4248-428f-462d-a733-e612a6262adb/session.v3.jsonl.zstd"
   debug="stats"
   看：压缩次数、checkpoint 数、被遮蔽 seq 数、stream 排除的收益百分比。
2) debug=keywords（同上路径，debug="keywords"）：看候选词里有没有"莱杜拉的回忆"。
3) 正常模式 max_results=1（同上路径）：看压缩记录区的"被遮蔽 seq（权威集合）"与
   "⚠️ 有损摘要，可能失真"声明是否都在。
4) path="…/session.v0 或导出 jsonl"（老文件）：确认 debug=stats 是否报 v0 无 stream、
   以及是否对"seq 超出文件行号范围"给出告警。
最后给一张对照表：官方工具能拿到什么 / scan 能拿到什么 / 两者重叠与互补。
```

---

## D. 阶段 2（开索引后重测）

> 前提：在 `cordis.patch.yml` 里追加（**不是我改，是你决定何时上**）：
> ```yaml
> - id: session-query-sqlite
>   config:
>     path: $HARNESS/dsh-domus/storages/session-query.sqlite3
>     openAt: first-search
> ```
>
> ⚠️ **预计第一次搜索会很久**（要为全部历史会话建 FTS 索引，你库里单会话 v0 有 18k 行 / 8MB）。
> 这是"慢"不是"崩"——判据：`storages/` 下出现 `session-query.sqlite3*` 文件即在建索引。
> 若超过 10 分钟无进展，杀掉重启并回滚（配置备份见下面的回滚说明）。

```
索引已开启，重跑 T1 / T3 / T4 / T5，另外加一项：
T2b 索引健康度：再跑一次 T1 的同一检索，比较两次耗时（第一次含建索引/加载）。
把每次调用的耗时与原始返回都记录。
```

---

## E. 判读表（拿到结果后照这张表下结论）

| 观察 | 结论 | 下一步 |
|---|---|---|
| T1 PASS + T3 空 + **T4 空** | D′ 覆盖"按关键词找回被压原文"，**但不覆盖"压缩点清单"** | 用 scan 的"被遮蔽 seq(权威集合)"当清单（D1 已实现），E1/E2 非必需 |
| T1 PASS + T4 **非空** | D′ 全覆盖 | 不做 E1/E2；摘掉 5 个 preset 里的 `recall_compactions` 悬挂引用（D12） |
| T1 报 `SESSION_QUERY_SEARCH_DISABLED` | 阶段 1 的预期行为 | 上阶段 2 |
| T0 就没有工具 | 挂载失败 | 检查 `profiles/web/cordis.patch.yml` 是否含 `tool-session-query` 行；查 dsh 启动日志 |
| T1 报 `unauthorizedTarget` | 工作区不匹配 | 换到作品目录下开会话 |
| T4 报 `query required` 之类参数错 | 空查询不被接受 | 记录为"枚举能力受限"的一条证据 |

---

## F. 回滚（任何一步把 dsh 弄挂了）

```bash
cd $HARNESS
cp dsh-domus/profiles/web/cordis.patch.yml.bak-d3-20260912-114855 \
   dsh-domus/profiles/web/cordis.patch.yml
./start-web.sh
```

`fast_filesystem.py` 的回滚点（按时间倒序）：

```bash
cd <挂载d>:/DataServices/MCP/wrap
cp fast_filesystem.py.pre-pointer-fix fast_filesystem.py   # 回到 D1 指针修正前
cp fast_filesystem.py.pre-debug-fix2  fast_filesystem.py   # 回到调试仪表修正前
cp fast_filesystem.py.pre-d10-d11-debug fast_filesystem.py # 回到本次改动前（干净基线）
# 或直接 git revert 8e6d8a1
```

---

## G. 记录表（手工填；建议把结果回贴给我，我做下一步判断）

| # | 测试 | 结果 | 证据（原样） | 备注 |
|---|---|---|---|---|
| T0 | 挂载自检 | | | |
| T1 | 被压内容检索 | | | |
| T2 | 按 seq 读原文 | | | |
| T3 | 负对照 | | | |
| T4 | 压缩事务可枚举性 | | | |
| T5 | 默认 surfaces | | | |
| T6 | read 与 surface 无关 | | | |

---

# 追加 · T7 遮蔽判定（**不需要索引，阶段 1 就能做**）

> 为什么加这一条：`session_event_read(seq=11)` 返回的事件里 `surfaceOp: "append"`——
> 但这记录的是**该事件自己被写入时的操作**，不代表它现在还在表层（被后续 replace 遮蔽是另一回事）。
> 而官方 `session_event_trace` 正是查"直接替换关系"的，且它**不依赖搜索索引**（走 corpus，不走 FTS）。
> 所以这条能在阶段 1 立刻把"shadowedSeqs 到底可不可信"这件事问清楚。

```
T7 遮蔽判定（只调 session_event_trace，不要用 search）：

对同一会话依次调用，参数只有 seq 不同：
  session_id = session-c08b4248-428f-462d-a733-e612a6262adb
  A) seq=11    ← scan 侧自报「被遮蔽」
  B) seq=902   ← scan 侧自报「在当前表层」

把两次原始返回逐字贴出（不要摘要），然后回答：
  ① A 的返回里是否出现"被后续事件替换"的关系（replacement / 替换链）？
  ② B 的返回里是否没有这种替换关系？
  ③ 若 A 也没有替换关系，那么"seq=11 被压掉了"这一说法就不成立，
     需说明 scan 侧那条「被遮蔽 seq（日志自报、未核实）」为什么不可信。

判读：
  · A 有替换关系 + B 无   → shadowedSeqs 可信，D1 指针可用，T4 仍待阶段 2
  · A 无替换关系          → shadowedSeqs 不可信（疑与 v0→v3 迁移期重编号有关），
                           D1 指针必须改用别的锚（如按 checkpoint 的行号区间）
  · 两者都报错            → 记录原始错误，本项未决
```

## 附：三条已知限制（写进结论，别丢）

1. **search 侧整体关闭**（阶段 1 设计如此）：`Error: session search is disabled in this deployment`
   对应源码 `tool-session-query/src/service-boundary.ts:76` 对 `SESSION_QUERY_SEARCH_DISABLED`
   的渲染，根因是 `session-query-sqlite` 仍为 `path:':memory:'` + `openAt:never`。
   → T1/T3/T4/T5 是**同一根因的四个副本**，不是四条独立证据。
2. **read 返回整条事件，且无裁剪参数**：实测 `seq=902` 的返回体包含 `stream` 里逐 token 的
   `dt`/`texts` 双数组，体量远大于 `seq=11`。工具签名只有 `session_id/seq/before/after`，
   `before/after` 只会**增加**上下文。→ 按 seq 定向读之前必须先估规模；D5 的
   「索引+摘要优先、原文按需展开」由此得到实证支持，不是纸面原则。
3. **本机全部带压缩的会话都是 v0→v3 迁移产物**：6/6 如此，0 个原生 v3。
   这意味着 `compaction/summary` 的 payload 可能是迁移期重编号的结果，
   用它当 seq 指针必须先在原生 v3 会话上复核。
