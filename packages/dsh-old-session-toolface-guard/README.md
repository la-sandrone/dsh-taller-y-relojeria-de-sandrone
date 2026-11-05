# dsh-old-session-toolface-guard

拦住「工具面翻转 ⇒ 全部 `defer_loading` ⇒ DeepSeek 永久 400」。**只改派发前的请求，`next()` 只调一次。**

## 它拦的是什么

会话历史基线（`request/header` 里那张 tools）与当前活跃工具集不相交时，
`packages/llm/llm/src/content.ts` 的 `toolDeclarations()` 把当前工具全标成「中途新增 + 延期」，
`addition-only` 分支又删光基线 ⇒ 请求里 0 个可加载声明 ⇒ `INVALID_REQUEST 400`，该会话此后每轮都失败。

UI 上的特征很直白：`工具已更新 · 新增 1 个（run_code），移除 131 个`。

## 铁律：`next()` 只能调一次

Cordis 的 `llm/stream` 是 waterfall，监听者拿到的 `next` 是「往下走一跳」，**调第二次直接抛 `next() called multiple times`**，把整轮打成失败（2026-11-05 实测）。
所以本插件不做「被拒就重派发」，只在派发前就地改请求。

## 修法

| `repairMode` | 做什么 | 保证 |
|---|---|---|
| `reset`（默认） | 基线 := 当前活跃工具（去掉 `deferLoading`），`updates` 清空 | 两种投影模式下都必然合法（声明集 = 活跃集，无延期、无中途新增） |
| `append` | 只把一条活跃工具（默认 `run_code`）补进旧基线 | 依赖补的位置；更保守，改动更小 |

`reset` 的代价：那些「中途新增」的 developer 声明不再进入请求，附带的延迟加载优化随之失效——对已经废掉的老会话，这是拿优化换可用。

## 配置（唯一入口）

改 `<home>/profiles/web/cordis.patch.yml` 的「工具面守门」段，**不要改本文件里的默认值**：

```yaml
- id: old-session-toolface-guard
  config:
    cutoff: '2026-11-05T00:00:00+08:00'   # 判据①：会话早于此刻 ⇒ 无条件补/重建一次
    residentTool: run_code                 # append 模式下补的那条真实工具
    predicted: true                        # 判据②：与日期无关的投影复算
    oldSessionProactive: true              # 判据①开关
    repairMode: reset                      # reset | append
    dryRun: false                          # 只判定不修（排查用）
```

`cutoff` **必须带显式时区**（`Z` 或 `±HH:MM`）；不带偏移会 fail-loud 拒绝启动——时区歧义会让判据悄悄偏移，那比报错更糟。

## 边界

- 改的是**请求**不是历史：会话里那张「全都算中途新增」的表仍在，靠每轮重设基线兜住。
- 不注册工具、不写盘、不读会话文件；只做纯对象运算，`next()` 恰好一次。
- 任何内部异常 **fail-open**（原样放行），不制造新的失败面。
