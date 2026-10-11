# DSH / Apache 反代与门户入口 — 研究报告（定稿）

**研究时间**：2026-09-12
**目标**：① `http://localhost/dsh` → `http://localhost:9007` ② 现有 Directory Listing 里加 dsh 入口
**状态**：**仅研究，未实施**（等指令）

---

## 〇、一句话结论

- **反代本身完全可行**（实测：Windows 侧可直连 WSL 的 127.0.0.1 端口）；
- **但 `localhost/dsh` 这个子路径形状做不到**，根因是 dsh 浏览器端把 API 基址写死为 `location.origin`（不含路径）。**Rewrite 解决不了**——它作用在请求到达 Apache 之后，而 API 地址是浏览器 JS 在页面里算出来的；
- 最贴近你原意的可行解：**`http://dsh.localhost/`**（无端口），或退一步 **302 跳转**；
- 列表入口的插入点就是 `directory-listing/header.html` 里那句现成的注释。

---

## 一、现状勘察（全部实测）

### 1.1 Apache

| 项 | 实测值 | 来源 |
|---|---|---|
| 版本 | Apache/2.4.68 (Win64) PHP/8.5.7 | `curl -I localhost` |
| ServerRoot | `<C盘>:/Program Files/Apache24` | `httpd.conf:31` |
| DocumentRoot | **`<D盘>:/DataServices/htdocs`** | `httpd.conf:32` |
| 监听 | `0.0.0.0:80` + `[::]:80` | `netstat -ano` (PID 6152) |
| 服务 | `Apache2.4` RUNNING，**LocalSystem**，AUTO_START | `sc qc` |
| 日志 | `Apache24/logs/{access,error}_log`（777） | ls |
| PHP | `<C盘>:/Program Files/php85/php8apache2_4.dll` | `httpd.conf:193` |

**已加载的相关模块**（无需再 LoadModule）：

```
proxy / proxy_http / proxy_wstunnel / rewrite / headers / filter / alias / dir / autoindex
```

**磁盘上有但未加载**：`mod_substitute.so`（`httpd.conf:127` 被注释）
**已有指令**：`ScriptAlias /cgi-bin/ "${SRVROOT}/cgi-bin/"`（`httpd.conf:388`）
**VirtualHost 数量**：**0 个**

### 1.2 Directory Listing 的真实构成

第三方主题 [ramlmn/Apache-Directory-Listing](https://github.com/ramlmn/Apache-Directory-Listing)：

- `<D盘>:/DataServices/htdocs/.htaccess`（3414B）—— `Options +Indexes` + `IndexOptions` / `AddIcon*` / `HeaderName` / `ReadmeName` / `IndexStyleSheet`
- `<D盘>:/DataServices/htdocs/directory-listing/`
  - `header.html`（141B）← **表格上方，插入点**
  - `footer.html`（1231B）← 表格下方 + 面包屑 JS
  - `table-automode.css` / `common.css` / `darkmode.css` / `icons/` / `media/`

生成结构（实测 `curl localhost` 5039B）：

```
<body>
  <main>                                    ← header.html 起点
    <h1 class="title">Index of <span class="js-path"></span></h1>
    <table id="indexlist"> ...10 行... </table>   ← autoindex 硬生成，插不了行
  </main>                                   ← footer.html 起点
</body>
```

**表格行插不进去**（autoindex 生成）；**`header.html` 就是官方留的静态插入点**，位于标题与表格之间——视觉上等于列表的第 0 项。

### 1.3 决定性有利条件（实测）

**① Mirrored + hostAddressLoopback 已生效**

`.wslconfig`：

```ini
[wsl2]
networkingMode=Mirrored
[experimental]
hostAddressLoopback=true
```

实测（WSL 内起 `python http.server` 绑 `127.0.0.1:9018`）：

```
WSL   curl 127.0.0.1:9018      → PROBE_OK_9018
Win   curl.exe 127.0.0.1:9018  → PROBE_OK_9018  ✅
Win   curl.exe localhost:9018  → PROBE_OK_9018  ✅
```

**Windows 侧可直达 WSL 的 127.0.0.1 端口 → Apache 反代到 `127.0.0.1:9007` 无需 dsh 改绑定。**

**② `*.localhost` 免 hosts 可用**

实测：`curl.exe http://zzz.localhost/` → **HTTP 200**（命中同一个 Apache）。
Windows 已把任意 `.localhost` 解析到回环，Apache 又监听 `0.0.0.0:80` 接所有 Host。
**白送一个无端口的独立主机名。**

---

## 二、第一问：`localhost/dsh` → `:9007`

### 2.1 三道墙（源码证据）

#### 墙 1 — API 基址 = `location.origin`（**硬约束，非配置问题**）

`packages/client/connection/src/client/rpc.ts:44,108`：

```ts
new URL(`${channel}/${endpoint}`, resolveBase())      // :44
function resolveBase(): string {
  const location = (globalThis as ...).location
  return location?.origin !== undefined && location.origin !== 'null' ? location.origin : INTERNAL_BASE
}                                                       // :108
```

**`location.origin` 不含路径。** 页面挂在 `/dsh/` 下，API 依然打向 `http://<host>/api/...`。

服务端路由是 **prefix** 匹配（`connection/src/index.ts:126-127`，`api-path.ts` 注释）。

| 请求 | 服务端 |
|---|---|
| `/api/xxx` | ✅ 命中（prefix `/api`） |
| `/dsh/api/xxx` | ❌ **不命中** |

而前端实际会发的是 **`http://localhost/api/...`**（丢掉 `/dsh`），也 ❌。

> 注意反直觉点：`apps/web/vite.config.ts:149` 是 `base: './'`，**静态资源是相对路径**（对子路径友好），
> 但**运行时 API 不是**——两套机制，别被前者骗了。

#### 墙 2 — 认证 cookie 名绑定 Host

`packages/client/connection/src/browser-auth.ts`：

```
LAUNCH：GET /?token=<launchToken>  ──► 303 + Set-Cookie: dsh-auth-<base64url(sha256(Host))>=v1.<body>.<hmac>
cookie 体 = {authority, issuedAt, expiresAt} + HMAC-SHA256
属性 = Path=/; HttpOnly; SameSite=Strict
```

- `launchToken` **每次启动随机**，不落盘，只在启动时打印一次
- 签名密钥 = `dsh-domus/.credentials.yaml` → `client-connection/browser-session`（**已确认存在，格式匹配**）
- `Path=/` 对子路径**不是**障碍（`/dsh` 也能带上）；但**名绑 Host**，Host 一变 cookie 立刻作废

#### 墙 3 — Host/Origin 信任栅栏

`packages/client/connection/src/api-request-trust.ts`，每个 `/api` 请求三道检查：

```
1. Host ∈ loopback(127.0.0.1/localhost/::1) 或 显式 trustedHosts
2. sec-fetch-site ≠ cross-site
3. 有 Origin 时，Origin.host === Host.host
```

**`ProxyPreserveHost On` 下 Host 保持 → 天然通过。** 这条墙不是障碍，但**决定了不能随便改 Host**。

### 2.2 Rewrite 大法能行吗？—— 逐条验算

`mod_rewrite` 你手上就有（`httpd.conf:148` 已加载）。三种用法：

**（a）内部代理 `RewriteRule ^/dsh/?(.*)$ http://127.0.0.1:9007/$1 [P,L]`**

```
浏览器 → localhost/dsh/             → index.html 拿到 ✅
页面 → location.origin + '/api/...' → http://localhost/api/...  ❌ 没进 /dsh 规则
```
**败**。规则根本没机会处理那个请求。

**（b）外部重定向 `RewriteRule ^/dsh/?$ http://localhost:9007/ [R=302,L]`**

地址栏变 `localhost:9007/`。**能用，但这是 302，不是你要的形状。**

**（c）`ProxyPass /dsh/ http://127.0.0.1:9007/`（mod_proxy 等价物）**

同 (a)，**败**。

**结论：Rewrite 是"请求到达 Apache 之后"的工具，而 API 地址是"浏览器 JS 在页面里算的"。
这一层错位，Rewrite 怎么组合都补不上：**
- 想给前端改基址 → 得改**响应体**，Rewrite 不碰 body（要 `mod_substitute` / `mod_ext_filter`）；
- 想只代理 `/api` → 那是**整站命名空间**，会污染你现有的 pma / aria2ng 等（且撞 §2.5 的 `/dsh` 别名冲突）。

### 2.3 那 mod_substitute 呢？—— 我查了，**产物里找不到落点**

唯一能让 `localhost/dsh` 成立的路：**响应体注入脚本**，在应用加载前把 API 基址改掉。

`mod_substitute.so` 磁盘上有（20KB），只是 `httpd.conf:127` 注释掉了，启用很容易。

**但实测三处全空**：

| 判据 | index bundle (556KB) | vendor bundle (741KB) |
|---|---|---|
| `location.origin` 出现次数 | **0** | **0** |
| `location[,;)]` 出现次数 | **0** | — |
| `"/api"` 出现次数 | **0** | **0** |
| `client-request` 出现次数 | **0** | **0** |
| `dsh.internal`（INTERNAL_BASE） | 0 | 0 |

sourcemap 佐证：`index-*.js.map` 的 `sources` 只有 25 条，**无 connection / rpc / browser-auth**。
（`.origin` 的上下文全是无关代码：`Symbol.for("cordis.original")`、图表库的 `originX/originY`。）

**即：`resolveBase()` 的编译产物形态不可识别，mod_substitute 没有可靠的替换锚点。**
硬试（拿正则扫）属于靠运气，且**一旦 dsh 升级就失效**——不建议。

### 2.4 可行的三个方案

#### 方案 A — 独立主机名 `dsh.localhost`（**推荐，唯一能去端口**）

浏览器地址：**`http://dsh.localhost/`**

dsh 侧（`start-web.sh` 改 1 行）：

```bash
exec pnpm dsh web --port 9007 --trusted-host dsh.localhost --no-open
```

依据：`packages/bundle/web-app/src/startup.ts:56` —— `--trusted-host <authority...>` 是官方 flag，
可重复，注入 `Config.trustedHosts` → `resolveLanTrust()`。
且 `isTrustedAuthority` 对**不带端口**的条目匹配该主机名的**任意端口**（`api-request-trust.ts` 注释明写）——
所以 `--trusted-host dsh.localhost` 同时覆盖 `:80`（经 Apache）和 `:9007`（直连）。

Apache 侧 —— **用 `<If>` 而不是第二个 `<VirtualHost>`**：

```apache
# httpd.conf 尾部
<If "%{HTTP_HOST} == 'dsh.localhost'">
    ProxyPreserveHost On
    ProxyRequests Off
    # WebSocket（dsh 的 API Gateway 有 WS mux，见 rpc.ts:238）
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteRule /(.*) ws://127.0.0.1:9007/$1 [P,L]
    ProxyPass        / http://127.0.0.1:9007/
    ProxyPassReverse / http://127.0.0.1:9007/
</If>
```

**为什么用 `<If>` 而不是 `<VirtualHost *:80>`**：`httpd.conf` 现在**一个 vhost 都没有**。
引入 `*:80` vhost 后，**第一个 name-based vhost 会成为默认主机**——所有匹配不上 ServerName 的请求都会落到它。
若把 dsh 写在第一个，**你现有的 `localhost/` 列表会被整个劫持**。
`<If>` 是请求级条件，**不动默认主机选择**，零劫持风险。

**首访**：`http://dsh.localhost/?token=<本次启动的 launchToken>` → 换 cookie → 之后 `http://dsh.localhost/` 直接进。
（`start-web.sh` 里那行 `#echo 请自行运行浏览器...` 被注释了，需要恢复成打印 dsh 启动时给的带 token URL。）

#### 方案 B — `localhost/dsh` 做 302 跳转（保留你要的 URL 形状）

```apache
<If "%{HTTP_HOST} == 'localhost'">
    Redirect permanent /dsh http://localhost:9007/
</If>
```

输入 `localhost/dsh` → 跳 `localhost:9007/`。**1 行、零风险**，但地址栏最终带端口。

#### 方案 C — 直接 `http://localhost:9007/`

Apache 什么都不配。§1.3① 已实测 Windows 侧可直达 9007。列表里加个链接即可。

#### 三方案对照

| | 地址栏最终 | 改 Apache | 改 dsh | 风险 | 认证 |
|---|---|---|---|---|---|
| **A** | `dsh.localhost/` | `<If>` 块 | +1 flag | 低（`<If>` 无 vhost 劫持） | 首访带 token，之后免 |
| **B** | `localhost:9007/` | 1 行 | 无 | 极低 | 同 C |
| **C** | `localhost:9007/` | 无 | 无 | 无 | 同上 |

### 2.5 附带发现：`/dsh` 命名空间不干净

`httpd.conf:388` 已有 `ScriptAlias /cgi-bin/`。
Apache 指令优先级 **`Alias`/`ScriptAlias` > `ProxyPass`**，且若 `<D盘>:/DataServices/htdocs/dsh` 存在会给目录列表。
当前 htdocs 下**没有** dsh 目录（暂时不冲突），但说明 `/dsh` 不是干净命名空间——方案 A/B 的价值又高了一分。

### 2.6 关于"必须是 `localhost/dsh`"

技术上只剩**改 dsh 前端基址**一条路（把 `resolveBase()` 从 `location.origin` 改成可由 `globalThis` 注入的基址）。
好消息：dsh 自带注入机制（`packages/host/webserver/src/injections.ts` 的 `webserver/index-inject`，
支持 `{kind:'global'}` → 渲染成 `<script>globalThis[name]=value</script>`），
所以**上游改造是干净的、有官方钩子的**——但那是改源码，升级要重新打，我不建议，要真做先说。

---

## 三、第二问：Directory Listing 里加 dsh 入口

**插入点**：`<D盘>:/DataServices/htdocs/directory-listing/header.html`（141B）

现状全文：

```html
  <main>
    <!--
      Add any static information or notices here
    -->

    <h1 class="title">Index of <span class="js-path"></span></h1>
```

**注释块就是官方留的插入位**。拟插入（href 随方案 A/B/C 定）：

```html
    <div class="dsh-entry">
      <a href="http://dsh.localhost/">
        <img src="/directory-listing/icons/script.svg" alt="[DSH]">
        DeepSeek Harness <small>dsh.localhost</small>
      </a>
    </div>
```

**约束**（实测）：
- `header.html` 是**静态**文件，autoindex 的 `HeaderName` **不解析 SSI** → 里面写不了动态内容。要动态需 `Options +Includes` 并改指 `.shtml`，**不建议**。
- `.htaccess` 有 `IndexIgnore "/directory-listing"`，主题资源本身不进列表，新 div 不受影响。
- 图标直接复用现成 `icons/script.svg`（就是 `.sh/.exe/.bat` 那批用的），**无需新增文件**。

**顺带的小毛病**：每次访问 `error_log` 都刷

```
[authz_core:error] AH01630: client denied by server configuration: <D盘>:/DataServices/htdocs/.htaccess
```

因为 `<Directory />` 是 `Require all denied`，而 `.htaccess` 自身不在任何放行规则里。
**不影响功能**（它本就不该被下载），只是噪音。可选修法：在 `<Directory "${HTDOCSROOT}">` 里加
`<FilesMatch "^\.ht">Require all denied</FilesMatch>`（可选，非必需）。

---

## 四、实施成本与风险

| 步骤 | 文件 | 改动 | 风险 | 回滚 |
|---|---|---|---|---|
| 备份 | `Apache24/conf/httpd.conf` | 复制 | — | 复制回 |
| Apache 改造 | `httpd.conf` 尾部 | +10~15 行 `<If>` | 低 | 注释掉 restart |
| dsh 加 flag | `start-web.sh` | 1 行 | 低 | 删 flag |
| 列表入口 | `directory-listing/header.html` | +6 行 | 无 | 删 div |

**重启需管理员权限**（服务账户 LocalSystem）：
`httpd.exe -k restart` 或 `net stop Apache2.4 && net start Apache2.4`
**改配置前必须先 `httpd.exe -t` 做语法预检**（不启服务，纯校验）。

---

## 五、待决策

1. **地址栏接受度**：`dsh.localhost/`（A）／`localhost:9007/`（B、C）／**必须 `localhost/dsh`**（需改源码）
2. **要不要加 `--trusted-host dsh.localhost`**（仅方案 A）
3. **列表入口 href 指向**（随 1 定）
4. **顺手修 `.htaccess` 的 error_log 噪音？**

---

## 附：本次研究用到的实测命令与结论对照

| 验证项 | 命令 | 结果 |
|---|---|---|
| Windows→WSL 回环 | `curl.exe 127.0.0.1:9018` | `PROBE_OK_9018` ✅ |
| `*.localhost` 解析 | `curl.exe http://zzz.localhost/` | `200` ✅ |
| Apache 版本 | `curl -I localhost` | `2.4.68 Win64 PHP/8.5.7` |
| 代理模块 | `grep ^LoadModule httpd.conf` | proxy/http/wstunnel/rewrite 全在 |
| mod_substitute | `ls modules/` + `grep` | .so 在，**未加载**（:127 注释） |
| 产物锚点 | `grep location.origin / "/api"` | **0 / 0**（两个 bundle） |
| sourcemap | 解析 `index-*.js.map` | 25 sources，**无 connection** |
| API 路径 | `api-path.ts` | `API_PATH='/api'`，服务端 prefix 注册 |
| 基址来源 | `client/rpc.ts:108` | `location.origin`（不含路径） |
| 信任 flag | `web-app/startup.ts:56` | `--trusted-host <authority...>` 官方支持 |
| cookie 密钥 | `dsh-domus/.credentials.yaml` | 存在，格式匹配 |
