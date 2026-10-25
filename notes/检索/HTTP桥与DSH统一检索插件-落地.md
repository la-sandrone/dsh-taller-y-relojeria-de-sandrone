# HTTP 桥与 DSH 统一检索插件 —— 落地记录（2026-10-25）

文件名: HTTP桥与DSH统一检索插件-落地.md
摘要: melquiades 统一检索如何接进 DSH Web UI：进程内 daemon 线程的 HTTP 桥 + 侧边栏插件，
      以及两个「装不上/不生效」的坑。
依赖: melquiades `omnibus_http.py` / `plugins/dsh-omnibus-search/`；DSH 0.2.1-rc.2。

---

## 一、为什么要在中间加一层 HTTP

`search_OMNIA` 只有模型能调。人和模型的检索入口不对称：想说「这话我之前是不是
说过」，得先让模型代劳。

要给人一个入口，就需要把检索暴露成 HTTP。**但不能让 UI 直连数据库**：

三路候选（vector / fulltext / like）+ RRF 融合 + 归一化排序只有一份实现，在
`omnibus.py`。JS 侧再写一遍 = 第二份真相源 → 必然漂移。本仓真实吃过这个亏
（同一字段 `str()` 与 `json.dumps()` 两种序列化共存两年，15.8 万条要迁移）。

⇒ **Node 只做 UI 与转发，检索永远走 Python。**

## 二、桥：与 MCP 同生共死

不是独立进程，是 **MCP 进程内的 daemon 线程**（照 `harvest/scheduler.py` 的模式）。

```
GET  /health   → {ok, db, port, pid, uptime_s, requests, started_at, sources, modes}
POST /search   → {ok, hits, stats, notes, took_ms, limit_semantics}
POST /context  → {ok, text}
```

| 决定 | 理由 |
|---|---|
| 进程内 daemon 线程 | MCP 起来桥就在，MCP 死桥就没了 → 不留孤儿进程占端口 |
| 端口被占**只告警** | MCP 是本命，桥是附件 |
| 桥**自建** MariaDB 连接 | mariadb 连接对象不是线程安全的；主线程随时在跑工具，共用一个连接会互踩 cursor |
| 零新依赖（标准库 `http.server`） | 核心依赖刻意不含 fastapi（那是 server_bge 的 `embed` extra） |
| 只读 + 只绑回环 + 校验 Host | 防 DNS rebinding |

### 顺带修掉一处「独立进程时看不见」的隐患

`do_context` 原本是「把桥的 db 赋值给 `server._db` 全局，再调 MCP 工具壳」。
独立进程时无害，**进程内模式下是数据竞争**——主线程随时可能读 `_db`，而桥线程刚把它换掉。

改成把查询体抽成 `_message_context_text(db, ...)`，两边各传各的连接：

```python
def message_context(...):  return _message_context_text(_db, ...)      # MCP 工具壳
text = mcp_server._message_context_text(st["db"], ...)                # HTTP 桥
```

## 三、端口发现：不让两处配置人肉对齐

原来的耦合：

| 事实 | 谁知道 | 怎么知道 |
|---|---|---|
| 桥监听哪个端口 | MCP（`config.yaml` 的 `[bridge] port`） | 自己读配置 |
| 插件去哪个端口找 | 插件（`cordis.patch.yml` 的 `endpoint`） | **人肉抄一遍** |

不一致的症状只是「连不上」，而「MCP 没起」「端口被占」「桥线程死了」「配置关掉了」
在插件侧**完全同形**。

⇒ 桥启动时把事实写到 `~/.melquiades/bridge.json`，退出时删。插件每次请求前读它：

| 发现文件 | 插件行为 |
|---|---|
| `ok: true` | 用它的 `base`（**端口以桥为准**，配置写错也不影响） |
| `ok: false` | 桥尝试过但失败了 → 把 `error` 原文给用户 |
| 不存在 | 回退 `endpoint`，报错指向「MCP 可能没起」 |

失败路径也写文件（`_write_bridge_failure`），所以「为什么没起」不必翻日志：

| 报错文本 | 真实死因 |
|---|---|
| `桥启动失败：端口 … 被占用` | 另一份桥占了端口 |
| `桥启动失败：config.yaml 的 [bridge] enabled=false` | 自己关掉的 |
| `发现文件说桥在 X，但连不上` | 桥线程已退出（重启 DSH） |
| `连不上…也没找到 bridge.json` | MCP 没起，或没读这份 config |

## 四、保活：明确不做（这是判断，不是偷懒）

`serve_forever()` 是稳定循环，**不会自己退出**；唯一会死的是「启动时端口被占」，
而那重试也无用——占用者可能是手动跑的 standalone，反复重试只会变成两家抢端口。

⇒ 不做看护线程，改做**可观测性**：把死法如实写进发现文件。

「它死了没人管」不是主要痛点；「它死了你不知道为什么」才是。

## 五、插件：几处刻意的设计

- **结果在 tab 内自包含展开，不跳转聊天记录**。DSH 客户端没有「定位到某条消息」的
  公开 API（`anchorSeq` 在客户端包里零命中），硬做要改核心 UI；自包含展开的代价
  小一个数量级。
- **三层开关**：patch 行注释 / `config.enabled=false` / `better-sidebar` 缺失（只 warn 不崩）。
- **竞态**：请求序号，只认最后一次响应（比 AbortController 省事，桥是本地回环）。
- **高亮**：切段渲染 `<mark>`，不用 `dangerouslySetInnerHTML`。

## 六、两个坑

### 坑 1：`webRuntime` → `webStartup`（症状是 HTTP 405）

DSH `0.2.1-alpha.2` 起 `webRuntime` 服务被移除。官方原文：

> A profile, overlay, or `--patch` file that injects `webRuntime` now **waits for a
> service that never mounts**

插件 `inject: ['webServer', 'webRuntime']` ⇒ 永久挂在等待态 ⇒ `apply()` 从未执行
⇒ `/omnia/api` 从未注册 ⇒ 请求落到静态 dist 兜底（对 POST 返 405、body 是 HTML）
⇒ 界面显示裸 `HTTP 405`。

**误导点**：我代码里确实有一处会回 405（非 POST 方法），但它返回的是
`{ok:false,error:'method not allowed'}` —— **合法 JSON**。看到的是裸状态码，
恰恰证明那个响应不是我的代码发的。这条线索当时被我忽略了。

同类错误还有两处：`dsh.client.inject` 声明了两个从未 import 的包、
`peerDependencies` 里放了没用到的 schemastery。
**共同点是「声明了自己并不使用的东西」**——它们不会报错，只会安静地等/被拒。

### 坑 2：`require` 在 ESM 里不存在（静默降级）

`readDiscovery()` 最初写成：

```js
const fs = require('node:fs')   // host 是 ESM，require 不存在
```

异常被本函数的 `catch { return null }` 吞掉 → 永远返回 `null` → **发现机制看似实现、
实际从不生效**。所有测试第一次都「通过」，只是那条分支永远走不到。

教训与「以静默降级为耻」同源：`catch { return null }` 这类兜底，必须在注释里写清
「什么情况下允许它发生」。这次是靠断言 `discovery.ok === true` 才抓出来的。

## 七、验证

| 组 | 内容 | 结果 |
|---|---|---|
| 进程内桥 | 起得来 / health / context 不改 `server._db` 全局 / 停掉后端口不响应 / 端口被占降级不抛 | 6/6 |
| 发现机制 | 桥写文件 / health 新字段 / 插件忽略过时 endpoint / 三种死法可分辨 / 退出清理 | 8/8 |
| 插件静态 | 导出面 / 路由注册 / 四种非法配置加载期抛错 / loader 加载 / tab 描述符 / locale | 17/17 |
| 转发 e2e | health / search 转发 / 空 query 400 / context / 404 / cross-site 403 / 非 JSON 400 / 桥不可达诊断 | 9/9 |
| 全链路 | 真桥 + 真 DB + 真向量：中文查「拜占庭」→ 命中俄文书那场对话 | 5/5 |
| 既有回归 | melquiades `tests/` | 69/69 |

实测耗时：全路首次 2.0s（embedding 冷启动），之后 ~174ms；纯文本 118ms。

## 八、操作要点

- 桥随 MCP 起，**不需要单独起进程**。手动 `melquiades-http --port 9010` 只作调试，
  两种模式不要同时开（会抢端口，后起的只告警不启动）。
- 装插件：`dsh plugin --profile web add link:<melquiades>/plugins/dsh-omnibus-search`
- 装完重启 DSH + 硬刷新浏览器。
- **`link:` 装的是符号链接**，改源码后只需重启，不用重装。
- 改桥的 Python 代码必须重启 DSH 才生效（MCP 不会热重载模块）。

## 九、待办

- `server_bge`（9005/9006）挂掉目前只体现为「向量路不可用」一行小字，**没有同款发现机制**。
  它已经真实挂过一次（2026-10-25 14:20 被连带停），排查时先查它是本能的下一步。
- 希腊/拉丁词形还原（`Πλάτων` vs `Πλάτωνος`）——全文路对这类屈折变化仍会 miss。
