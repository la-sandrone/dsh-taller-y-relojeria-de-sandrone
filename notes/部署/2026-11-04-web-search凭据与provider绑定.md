文件名: 用户笔记/部署/2026-11-04-web-search凭据与provider绑定.md
摘要: web_search 在「已用 DS 账户登录」的情况下仍报「没有 API key」的根因与修法。
     根因不是登录失效，而是搜索凭据被绑在「当前请求的 provider」上：
     账户 token 只在 provider === 'deepseek-account' 时发放，否则回落到
     DEEPSEEK_API_KEY，而该 key 于 2026-11-04 被有意清空。
     修法是往 credentials store 的 refs 补一把 DEEPSEEK_API_KEY ——
     它**不会**产生第二个 DeepSeek 官方模型供应商（附两条依据）。
依赖: @deepseek-ai/dsh-web-search-deepseek（v0.2.1-rc.2）；
      @deepseek-ai/dsh-credentials-local（watcher，热加载）；
      凭据库 <DSH_HOME>/.credentials.yaml（mode 600）

---

# web_search 的凭据链路：为什么「登录了还说没 key」

## 一、现象

DSH 已用 DS 账户登录（`llm-deepseek-account` 接管官方 provider），
但 `web_search` 报：

```
DeepSeek search has no API key for "DEEPSEEK_API_KEY"; store it through the
credentials service (the web Models page writes it), export it in the launching
environment, or set a literal "apiKey" in the web-search-deepseek config;
a conversation using a DeepSeek Account model searches with the account sign-in instead
```

## 二、根因：凭据被绑在「当前 provider」上

`web-search-deepseek/src/index.ts` 有两条**互斥**的凭据路：

```ts
// 路 A：账户 token —— 有硬门槛
resolveAccountToken: async (endpoint) => {
  const provider = ctx.get('agents')?.currentInitiator()?.session.requestContext()?.provider
  if (provider !== 'deepseek-account') return undefined      // ← index.ts:112
  return await ctx.get('deepseekAccount')?.resolveToken(endpoint)
},
// 路 B：API key —— 只查 store，不回退 env
resolveApiKey: async () => {
  const credentials = ctx.get('credentials')
  if (credentials !== undefined) return (await credentials.resolve(apiKeyEnv))?.value
  ...
}
```

⇒ 用 `deepseek-account` 的模型：走账户 token，能搜且不需要 key。
⇒ 切到 `opencode-go` / `amici-mei` 的模型：路 A 被那行判断掐断，路 B 又没 key
⇒ 就是上面那句报错。

**这不是登录问题，是 provider 绑定。** 2026-11-04 两个 provider 并行
（opencode-go 当天 406 次调用、deepseek-account 89 次），来回切时搜索时好时坏。

### 一个容易误判的点

`resolveToken` 的匹配规则是**按 origin**：

```ts
if (destination.origin !== this.inferenceOrigin || ...) return undefined
```

而搜索 endpoint 是 `https://api.deepseek.com/anthropic/v1/messages`，origin 对得上
⇒ **路径不是问题**，卡住的只有 provider 那一道判断。

## 三、为什么 store 里没有 DEEPSEEK_API_KEY

`密钥.env` 自 2026-11-04 起已清空，注释原话：

> DEEPSEEK_API_KEY —— DS 账户登录已接管官方 provider；且 resolveApiKey 在有
> credentials 服务时**只查 store、不回退 env**，本文件里的值从来没有被读到过。

⇒ 启动器文件那层已经失效，凭据只在 `.credentials.yaml`。

## 四、修法：往 refs 补一条，**不动任何 provider**

```yaml
# <DSH_HOME>/.credentials.yaml
refs:
  DEEPSEEK_API_KEY: sk-****          # 新增（2026-11-04，长度 35）
  OPENCODE_GO_API_KEY: oc_sk_****
  AMICI_MEI_API_KEY: sk-****
```

- `credentials.resolve()` 顺序 **file → 进程环境 → fallback**，文件这条优先。
- `credentials-local` 带 watcher（debounce 100 ms）⇒ **改完热加载，不用重启**。
- 文件必须 `600`（每次 reload 都 `assertOwnerOnly`）；nano 存盘后要复核权限。
- 为什么用 nano 而不是命令行：贴 key 到 shell 会进 `.bash_history`。

### 为什么不会多出第二个 DeepSeek 官方供应商

1. **pi-ai 的路由集是结构性的**——`providers` 表的键就是路由集
   （`llm-pi-ai/src/config.ts`：*“the route set is structural”*）。
   当时只有 `amici-mei` / `opencode-go` 两个键，加凭据不会生成键。
2. **会读 `DEEPSEEK_API_KEY` 的那个插件是关着的**——profile 里
   `- id: llm-deepseek` 带 `disabled: true`（2026-11-04 撤的）。
   `llm-deepseek-account` 走账户 token，不读这把 key。

⇒ 这把 key 的唯一消费者是 `web-search-deepseek`。

## 五、将来若要「换一个变量名认」

**不需要改代码**：`apiKeyEnv` 本来就是配置项（默认 `DEEPSEEK_API_KEY`，
`src/index.ts:46` 的 `DEFAULT_API_KEY_ENV`）。在 profile 里加一条同 id 的覆盖即可：

```yaml
- id: web-search-deepseek
  config:
    apiKeyEnv: WEB_SEARCH_API_KEY     # 名字自定
```

两条附带约束：

- 名字必须匹配 POSIX 标识符 `^[A-Za-z_][A-Za-z0-9_]*$`（`credentialRef()` 会拒非法名）；
- 改了名字，`.credentials.yaml` 的 `refs` 里必须有**同名**记录，否则又是「没 key」。

动机（若要做）：`DEEPSEEK_API_KEY` 这个名字容易被误读成「模型供应商的 key」，
而它实际只管搜索。

## 六、验证方法

```bash
# ① 文件与 refs（不打印值，只报长度）
stat -c '%a' <DSH_HOME>/.credentials.yaml
awk '/^[[:space:]]+DEEPSEEK_API_KEY:/{sub(/^[^:]*:[[:space:]]*/,""); gsub(/[[:space:]]/,""); print length}' \
  <DSH_HOME>/.credentials.yaml

# ② key 本身有效（零 token 成本，只打 models 列表）
#    用 refs 里的值发 GET https://api.deepseek.com/models，期望 200
```

2026-11-04 实测：权限 600、长度 35、`GET /models → HTTP 200`（可见 2 个模型）。

**真正验证 API-key 路径的办法**：切到 OpenCode Go 模型搜一次——那条路上
路 A 不发放账户 token，只能用这把 key。用户已在另一对话确认 web_search 可用。

## 七、遗留

- 搜索计费口径仍是 **5 元/千次成功请求**（与账户登录无关，账户登录只在
  走账户 token 时改变凭据来源）。先免费源、内置作兜底的纪律不变。
- `currentInitiator()` 在 **subagent / 后台任务**里能否拿到
  `requestContext().provider`，尚未实测。若将来在子代理里搜索仍报「没 key」，
  这里是第一个要查的位置。
