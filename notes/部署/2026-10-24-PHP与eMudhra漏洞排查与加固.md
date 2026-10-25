文件名: 用户笔记/部署/2026-10-24-PHP与eMudhra漏洞排查与加固.md
摘要: 2026-10 两起公开安全事件的本地影响判定与落地处置：PHP 内核 CVE-2026-109618/109619
      （已升级 8.5.7→8.5.12）、eMudhra 中间 CA 私钥泄露（判定本机无影响）；同日两轮收敛
      暴露面 —— 先「只 80 + 仅本地子网」，最终 **Apache 只监听回环**（127.0.0.1 + ::1），
      入站防火墙规则全部停用。
依赖: 无（纯运维记录）

---

# PHP2Shell 与 eMudhra 证书事件：本机判定与处置（2026-10-24）

## 一、结论先说

| 事件 | 本机是否受影响 | 处置 |
|---|---|---|
| PHP CVE-2026-109618 / CVE-2026-109619（"PHP2Shell"，CVSS 9.2） | **是**：Windows 侧 PHP 8.5.7 < 8.5.12，且走的正是 advisory 里最容易触达的 `mod_php` 路径 | **已升级到 8.5.12**（HTTP 层已确认 `PHP/8.5.12`） |
| CVE-2026-115560（session upload progress，8.5.12 未修） | 配置上受影响（默认 On） | `session.upload_progress.enabled = Off` |
| eMudhra CVE-2026-111943 / 111944（8 张中间 CA 私钥可恢复） | **否**：本机不持有任何 eMudhra 证书，Windows 信任库零命中 | 无需动作；Arch 侧顺手 `pacman -Syu` |
| Apache 2.4.68（最新 2.4.69） | 加载了 5 个在 2.4.69 里被修的模块，但均需相应指令才会被打到 | **待办**，未动 |
| 暴露面（被同一轮排查带出来的老问题） | 原本 `Listen 80` = 0.0.0.0 + `[::]`，防火墙对 `httpd.exe` 是「任何端口/公用配置/任何来源」，`/pma` 无登录墙且是 root | **已砍到只剩回环**：`Listen 127.0.0.1:80` + `[::1]:80`，文档根 `Require ip 127.0.0.1 ::1`，两条入站防火墙规则全部停用 |

## 二、纠一个错误前提

原假设「Apache 只监听本地地址，问题不大」——**不成立**。三条证据：

```
httpd.conf:55      Listen 80                       ← 不带 IP = 所有接口
netstat            0.0.0.0:80 / [::]:80  PID 5708  ← IPv4 + IPv6 都在听
旧防火墙规则       "Apache HTTP Server" ×2（TCP/UDP）
                   配置文件=公用、本地端口=任何、远程 IP=任何
                   程序=<C盘>:\program files\apache24\bin\httpd.exe
WLAN IPv6          2409:8a20:7c0:8560:.../64       ← 全局单播，非 ULA
```

即：内网任何人可到 80；且因规则挂在**公用**配置且是「整个程序 + 任何端口」，
换到别的 Wi-Fi（咖啡馆）同样对外开着。

## 三、实际暴露面：只有 phpMyAdmin，而且它原本没门

```
httpd.conf:32   Define HTDOCSROOT "<D盘>:/DataServices/htdocs"
                ├─ 612 MB；除 pma/ 外 0 个 .php（全树 find 核对）
                └─ pma/ = phpMyAdmin 5.2.3
pma/config.inc.php:9   auth_type = 'config'     ← 无登录界面
pma/config.inc.php:7   user = root，口令非空
```

`auth_type=config` 意味着**访问即已登录 root**。这不是 CVE，是配置——但危险性
高于本轮的 PHP 内核漏洞：不需要 PoC，浏览器打开就用。

**用户决定**：既然能限死回环，就**不加密码**（保持「本机打开即用」的便利）。

## 四、本次改动（两轮共 5 项，均已回读验证）

### 1. `/pma` 收成回环专属（httpd.conf，`<Directory>` 之后新增）

```apache
<Directory "${HTDOCSROOT}/pma">
    Require ip 127.0.0.1 ::1
</Directory>
```

- 父级 `${HTDOCSROOT}` 有 `Require all granted`；实测子目录的 `Require` **会覆盖**
  父级而不是被合并成 `RequireAny`（双侧实测见第五节），所以不需要 `<RequireAll>` 包裹。
- **没有**改 `auth_type`，也没设密码——按用户要求保留便利。

### 2. PHP 8.5.7 → 8.5.12（含 `php8apache2_4.dll`）

- 来源：`https://windows.php.net/downloads/releases/php-8.5.12-Win32-vs17-x64.zip`
  （**非** `-nts`，Apache 必须用 TS 版；36,446,352 字节；`unzip -t` 通过，
  sha256 `660f3ff6ccbdf60f9607ef54bdba85ee22a58d61fd3633b38a93d57fb7c3d184`）
- 文件集与 8.5.7 只差 3 个新增的 `extras/sbom/*`，故直接覆盖即可
- **保留了 `php.ini`**（zip 里只有 `php.ini-development/production`，不含 `php.ini`）
- 回滚路径：`.../releases/archives/php-8.5.7-Win32-vs17-x64.zip` 实测 200 可下载

### 3. php.ini：关上传进度

```ini
session.upload_progress.enabled = Off      ; CVE-2026-115560 官方缓解
```

`fatal_error_backtraces` **保持默认 On**——理由：根因已由 8.5.12 修掉，
而 backtrace 对写 PHP 客户端时的排错有用。若后续要更保守，改成 Off 即可。

未采用 CNVD 的 `MaxConnectionsPerChild=1`（mod_php 下对应 mpm_winnt 的
`MaxConnectionsPerChild`）：那是**未升级时**的兜底，会让每个连接换一次进程；
既然已升到 8.5.12，代价不值。

### 4. 防火墙：任何端口 → 只 80 + 仅本地子网

| 规则 | 改前 | 改后 |
|---|---|---|
| TCP | 本地端口=任何，远程 IP=任何 | **本地端口=80，远程 IP=LocalSubnet**，程序仍限 `httpd.exe` |
| UDP | 启用，任何端口 | **已停用**（httpd 不需要 UDP；那是首次监听时被系统顺手建的） |

注意：`netsh advfirewall firewall set rule` **不支持改端口**（只支持
enable/profile/localip/remoteip/program/service）。改端口只能
`delete rule` + `add rule`，原来的「边缘遍历=遵从用户」随之重置为「否」（更安全）。

> ⚠️ 本节是**第一轮**的做法，已被下面的 §5 取代（规则现为停用态）。

### 5. 追加（同日第二轮，用户决定）：Apache 只监听回环

用户实测**公网 IPv6 打不进来**，据此把暴露面一次砍到底：

```apache
Listen 127.0.0.1:80
Listen [::1]:80
```

外加纵深防御——把文档根目录的来源也锁死（原为 `Require all granted`）：

```apache
<Directory "${HTDOCSROOT}">
    Require ip 127.0.0.1 ::1
</Directory>
```

于是 §4 那条「只 80 + 仅本地子网」的入站规则也**一并停用**——服务已经不在
非回环地址上监听，留着规则只是给未来的自己挖坑。两条 Apache 入站规则现在
**都是「已启用: 否」**。

**为什么敢这么砍（判据，不是感觉）**：

- 手机与远程访问由隧道 + DSH 自有入口承担——`用户笔记/部署/启动器绑定地址与远程访问砖.md`
  写明「远程访问**只走隧道**，不碰局域网绑定」（`autoTunnel: true` + `lanBind: false`）
- `httpd.conf` 里**没有任何 `ProxyPass` 反代残留**（早年的 `/aimeus` 已不在），
  不存在「只留回环就断内网依赖」的问题
- 站点内容 `htdocs` 全是静态文件 + `/pma`，而 `/pma` 本来就已回环专属

**恢复局域网访问要改三处**（故意的，少改一处就不生效）：
`Listen` 改回 `Listen 80` → 文档根改回 `Require all granted` → 启用防火墙规则
「Apache HTTP Server (80/local subnet)」。

## 五、验证记录（双向，不只看一侧）

```
HTTP 层版本      Server: Apache/2.4.68 (Win64) PHP/8.5.12
探针实测         php=8.5.12 zts=1 upload_progress='' backtraces='1'
                 ini=<C盘>:\Program Files\php85\php.ini
/pma ← 127.0.0.1        200（且页面标题 = 127.0.0.1 / MariaDB 12.3，说明真的进了库）
/pma ← 192.168.10.229   403 Forbidden      ← 回环限制生效
站点根 ← 192.168.10.229 200                 ← LAN 访问没有被误伤
httpd -t                 Syntax OK
服务                     Apache2.4 = RUNNING
```

第二轮（只监听回环）后的监听表与访问矩阵。**必须在 Windows 侧测**：WSL 的 `::1`
与 Windows 的 `::1` 不是同一个栈，在 WSL 里访问 `http://[::1]/` 会**假失败**
（127.0.0.1 走镜像网络是通的，所以更要用 Windows 侧的 `curl.exe` 复核）：

```
netstat（Apache 全部监听项）   127.0.0.1:80  pid=96244
                                [::1]:80    pid=96244      ← 只剩这两个

Windows 侧 curl.exe：
  127.0.0.1        200           ::1            200
  localhost        200           [::1]/pma/     200
  192.168.10.229   000（连不上）                    ← 局域网入口已死
httpd -t           Syntax OK
```

探针 `htdocs/_vcheck.php` 用完即删（已确认不存在）。

## 六、遗留风险 / 待办

1. ~~**公用配置文件下的咖啡馆场景**~~ **已随第二轮解决**：Apache 不再监听非回环地址，
   咖啡馆同网段的人连都连不上，`Options +Indexes` 的目录列表自然读不到。
   （背景：家宽 `CMCC-e7vS 2` 被判为**公用**配置，所以当时不能靠「仅专用配置」收紧。）
2. ~~**公网 IPv6 入向**~~ **已实测：打不进来**（用户手机蜂窝数据外部验证）。
   这条实测也是敢把 Apache 砍成只听回环的直接依据。
3. **Apache 2.4.68 → 2.4.69**：2.4.69 修了 13 个 CVE；本机**已加载**且受影响的模块有
   `mod_vhost_alias`（CVE-2026-63292 栈溢出）、`mod_xml2enc`（63686 崩溃）、
   `mod_proxy_uwsgi`（63718 响应走私）、`mod_proxy_ftp`（63045 PASV）、
   `mod_proxy_html`（56449 崩溃）。都需要相应指令/用法才会被打到，
   故列为 P2；升级需换整套 Apache（Apache Lounge VS18），比 PHP 麻烦。
4. **Arch 侧**：`ca-certificates-mozilla 3.131-1` 里仍锚着 `emSign ECC Root CA - G3`
   （Mozilla 已撤信）。Arch 没装 PHP，只有本地 OpenSSL 客户端（curl/python/git）
   在「碰上伪造链且不查吊销」时理论可中招。`pacman -Syu` 顺手处理。

## 七、来源

- CNVD-2026-41674 / 41675 公告（影响区间、修复版本、mod_php 缓解项）：
  cert.org.cn，2026-10-21
- PHP 官方安全发布与 GHSA-6wmf-4rv5-p3rp（producer/consumer 机制、mod_php 下
  `.htaccess`/`php_value` 在 `php_request_startup()` 之前生效）：
  php.net/archive/2026.php#2026-10-21-5、github.com/php/php-src/security/advisories
- CVE-2026-115560（session upload progress，未修，官方给的 `upload_progress=0` 缓解）
- eMudhra：CVE-2026-111943 / 111944；8 张中间 CA、P-384 弱密钥熵 3–8 bit、
  6 TLS + 2 代码签名、Chrome/Mozilla/Apple/微软封禁、Google 移出 emSign ECC Root CA G3；
  来源 Qualys 博客（2026-10-23）与 eMudhra 官方声明
- CISA KEV 全量 JSON 核对：上述 5 个 CVE 编号**零命中**（截至 2026-10-24，尚无在野利用记录）

## 八、备份

改动前原件（就地留档，Apache/PHP 都不会读它们）：

```
<C盘>:\Program Files\Apache24\conf\httpd.conf.20261024-bak
<C盘>:\Program Files\php85\php.ini.20261024-bak
```
