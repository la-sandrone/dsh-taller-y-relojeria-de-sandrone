文件名: 用户笔记/部署/2026-10-24-Firefox与Edge强制HTTP11.md
摘要: 让浏览器只用 HTTP/1.1 的落地记录。Firefox 有两个 pref（名字不对称，易错一个字）；
      Edge 没有 H2 策略，只有启动参数 `--disable-http2`（已 A/B 实测有效），
      配一个专用启动器 + 桌面快捷方式；H3 用企业策略 QuicAllowed=0 兜底。
依赖: Edge 156.0.4314.42 / Firefox 158.0；本机 Clash·Proxifier 均为旁路，与此无关

---

# 强制 HTTP/1.1：Firefox 与 Edge（2026-10-24）

## 一、为什么需要

链路每两分钟左右一次 TLS 抖动。H2 把故障域从"一条流"放大到"整个会话"
（连接级有状态：HPACK 动态表 + 双层流控，坏了不能热修）；QUIC/H3 走 UDP，
在运营商 QoS 与 NAT 超时下更糟。**国内站点照样抖**——所以问题不在代理，在链路本身，
浏览器的协议选择是真正起作用的那一层。

## 二、Firefox：有 pref，已由用户自行配置

从 mozilla-central 的 `StaticPrefList.yaml` 取到的现行名字与默认值：

| pref | 默认 | 设成 |
|---|---|---|
| `network.http.http2.enabled` | `true` | `false` |
| `network.http.http3.enable` | `true` | `false` |

⚠️ **不对称陷阱**：HTTP/2 是 `enabled`（**带 d**），HTTP/3 是 `enable`（**不带 d**）。
在 `about:config` 里输错一个字母**不会报错**，只会静默无效。

另有 `network.http.http3.fallback_to_h2_on_error`（默认 `true`），关掉 H3 后自然回落。

持久化的三条路（用户已用第一条，其余备查）：

- `about:config` 直接改（重启仍在，但"恢复默认"就没了）
- profile 下放 `user.js`
- `<C盘>:\Program Files\Mozilla Firefox\distribution\policies.json` 用 `Preferences` 策略锁定

## 三、Edge：没有策略，只有启动参数（已实测）

### 先确认有没有这个开关（不靠传闻）

Edge 156 的 `msedge.dll` 里直接找字符串字面量：

```
disable-gpu       命中      ← 正对照（确定存在的开关）
disable-http2     命中      ← 目标
disable-quic      命中
disable-http3     未命中
bogus-switch-zzz9 未命中    ← 负对照（确定不存在）
```

### 再确认它真的生效（A/B 实测）

用 CDP 读 `Network.responseReceived` 里的 `protocol` 字段，两个站点交叉验证：

| 目标 | 不加开关 | 加 `--disable-http2` |
|---|---|---|
| `https://www.taobao.com/` | **h2** | **http/1.1** |
| `https://www.cloudflare.com/` | **h2** | **http/1.1** |

（第一次拿 baidu.com 测是无效实验：对照组本身也是 http/1.1，说明该节点不走 h2。
**A/B 的对照组必须先证明"默认走 h2"，否则实验无意义。**）

### 企业策略里有什么

抓 Microsoft Learn 的 Edge 策略全文检索，**跟协议栈有关的只有 `QuicAllowed`**：

- 关 HTTP/3：`QuicAllowed = 0` —— 有官方策略，对所有启动方式生效
- 关 HTTP/2：**没有任何策略**，只能靠启动参数

### 已落地的配置

1. **策略**（注册表，已写入并回读确认）：

```
HKLM\SOFTWARE\Policies\Microsoft\Edge
    QuicAllowed  REG_DWORD  0x0
```

2. **启动器**：`<C盘>:\Users\Administrator\AppData\Local\Programs\EdgeH1\edge-http1.cmd`

```bat
start "" "...\msedge.exe" --disable-http2 --disable-quic %*
```

3. **桌面快捷方式**：`Edge (HTTP-1.1).lnk` → 指向上面那个 .cmd，
   最小化窗口（`WindowStyle=7`），图标借用 msedge.exe。
   创建方式：用 `cscript //nologo` 跑一段 VBScript 调 `WScript.Shell`，临时脚本用完已删。

### 把参数塞进系统自带的快捷方式（同日追加）

先纠正一个易错点：本机 `ProductName` 报的是「Windows 10 IoT Enterprise LTSC 2024」，
但 **build = 26100 ⇒ 这其实是 Windows 11 24H2**（微软在所有 Win11 上都沿用
「Windows 10」这个 ProductName 字符串）。判据看 `CurrentBuild`，不看 ProductName。

于是按 Win11 机制处理：开始菜单的固定项**引用**这些 .lnk，启动时读它 —— 所以直接改 .lnk 的
Arguments 即可，不需要换 AUMID、也不需要改那坨 CloudStore 二进制。

| 快捷方式 | 原始 Arguments | 改后 |
|---|---|---|
| `<C盘>:\ProgramData\Microsoft\Windows\Start Menu\Programs\Microsoft Edge.lnk`（开始菜单「所有应用」与固定项） | `--source-shortcut-location=start-menu` | 追加 `--disable-http2 --disable-quic` |
| `...\User Pinned\TaskBar\Microsoft Edge.lnk`（任务栏固定） | `--profile-directory=Default` | 追加同上 |

做法：用 VBScript 的 `WScript.Shell.CreateShortcut` 读改 `.lnk`（不需要第三方工具）。
脚本 `apply-h1-args.vbs` 是**幂等**的 —— 先把已有的两个参数剔掉再追加，所以重复跑不会叠加：

```
ARGS=[--source-shortcut-location=start-menu --disable-http2 --disable-quic]
ARGS=[--profile-directory=Default      --disable-http2 --disable-quic]
```

配套产物（都在 `<C盘>:\Users\Administrator\AppData\Local\Programs\EdgeH1\`）：

- `apply-h1-args.vbs` —— 注入/修复参数
- `reapply-edge-h1.cmd` —— 双击版（Edge 更新后重跑一次）
- `readlnk.vbs` —— 只读：打印三个快捷方式的 target/args，用于回读核对
- `edge-http1.cmd` + 桌面 `Edge (HTTP-1.1).lnk` —— **兜底通道**，不依赖系统快捷方式

改完重启了 `StartMenuExperienceHost.exe` 强制重读（自动拉起，未影响 explorer）。
原 `.lnk` 已备份为 `*.bak-20261024`。

**三个必须知道的限制**：

1. **Edge 自动更新可能重建 `ProgramData` 下那个 .lnk**，我们的参数会丢 —— 到时候跑一次
   `reapply-edge-h1.cmd` 即可（这就是它存在的理由）。
2. **参数是按进程的**：Edge 已有进程在跑时，点任何入口都只在旧进程里开新窗口，参数不生效。
3. 若某个固定项是「从旧快捷方式复制出来的独立副本」，改 `.lnk` 不一定反映到它 ——
   那种情况只能取消固定后重新固定（**本机未出现此情况，重启开始菜单宿主后已重读**）。

### URL 协议处理器：已改（机器级 4 处 + 用户级 1 处）

先记一个**必须先说清的事实**：这台机器的默认浏览器是 **Firefox**，不是 Edge。

```
HKCU\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice
    ProgId = FirefoxURL-308046B0AF4A39CB
```

所以"点链接"默认根本不经过 Edge —— 改 Edge 的处理器**不会改变日常点链接的行为**。
它的作用是：一旦 Edge 被显式调用（`microsoft-edge:` 协议、Office/Teams 里的"在浏览器中打开"、
或哪天 Edge 变成默认浏览器），也照样带参数。

已改（全部用 `reg add ... /reg:64`，值已回读）：

| 键 | 值 |
|---|---|
| `HKLM\SOFTWARE\Classes\MSEdgeHTM\shell\open\command` | `"...msedge.exe" --disable-http2 --disable-quic --single-argument %1` |
| `HKLM\SOFTWARE\Classes\microsoft-edge\shell\open\command` | 同上 |
| `HKLM\SOFTWARE\Classes\http\shell\open\command` | `"...msedge.exe" --disable-http2 --disable-quic "%1"` |
| `HKLM\SOFTWARE\Classes\https\shell\open\command` | 同上 |
| `HKCU\SOFTWARE\Classes\MSEdgeHTM\shell\open\command` | 同第一行（**用户级覆盖**：Edge 更新重写 HKLM 时，用户这份压过它） |

参数位置有讲究：**必须插在 `--single-argument` 之前**（该参数语义是「其后整体视为 URL」）。

`HKU\.DEFAULT` 里本来就没有 `MSEdgeHTM`（只有 S-1-5-18、两个服务账户和本机 SID），
所以"默认用户的配置"那一份**不存在**，正确做法就是在自己的 hive 下建覆盖。

### ⚠️ 记一个假成功的坑：`WScript.Shell.RegWrite` 的最后一段是**值名**

第一版脚本用 VBS 的 `sh.RegWrite "HKLM\...\shell\open\command", value` 写注册表，
**报了 5 个 OK，实际一个都没生效**。原因：

> `RegWrite(strName, ...)` 里路径**最后一段被当作"值名"**，除非路径以反斜杠结尾
> （结尾带 `\` 才是写该键的**(默认)** 值）。

于是它创建了 5 个叫 `command` 的**值**挂在 `shell\open` 下，真正的 `shell\open\command`
**子键**纹丝不动。而 `reg query ... /ve`（查默认值）自然读不到，看起来像"没写成"；
`reg query HKCR\...\command` 又显示旧值 —— 两者都不报错，**只有全库搜 `disable-http2`
才暴露真相**：

```
HKLM\SOFTWARE\Classes\MSEdgeHTM\shell\open
    command    REG_SZ    ...--disable-http2...     ← 这是值名，不是子键
```

**教训**：脚本报"成功"不等于写对了对象。这类误建要靠「搜值内容定位键」反查，
不能只看返回值。最终改法：**注册表一律走 `reg.exe /reg:64`**，VBS 只负责 `.lnk`。

> 另有一处踩空：想用桩程序验证"点链接→处理器收到参数"，两次都没触发
> （`start "" "microsoft-edge:https://..."` 在非交互 shell 里不落地，疑似需要真实外壳手势）。
> ⇒ **这一环未闭环**，注册值已核实，行为未实测。

### 维护脚本（一份，幂等，建议记住这一个）

`<C盘>:\Users\Administrator\AppData\Local\Programs\EdgeH1\reapply-edge-h1.cmd`

- 自带提权检查（`fltmc` 探针 → 不满足则用 `elevate.vbs` 走 UAC 重启自己）
- 写上面 5 处注册表（`reg.exe /reg:64`）
- 调 `apply-h1-shortcuts.vbs` 修两个 `.lnk`
- 结束提示"Edge 在跑就先全退"

原注册表项已导出备份到同目录 `backups\20261024-*.reg`（UTF-16，`reg import` 可回滚）。
另附 `readlnk.vbs`（只读，打印三个快捷方式的 target/args）。

点别处的链接（微信/邮件/文档里的 http(s)）走的是这条命令，不是快捷方式：

```
HKCR\MSEdgeHTM\shell\open\command
  = "<C盘>:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --single-argument %1
```

要塞参数，**必须插在 `--single-argument` 之前**（该参数的含义是「其后整体视为 URL」）：

```
"...msedge.exe" --disable-http2 --disable-quic --single-argument %1
```

效果：任何程序打开的链接都强制 1.1。代价：这是改系统命令（属"劫持"式做法），
Edge 更新或修复安装可能重置；出问题时比快捷方式更难回滚。**故未擅自修改。**

### ⚠️ 使用这个快捷方式的唯一注意事项

**启动参数是"每进程"的。** 如果 Edge 已经在后台跑着（本机常态：12 个 msedge 进程），
点任何入口（包括已带参数的系统快捷方式）都只会**在既有进程里开个新窗口，参数不生效**。

⇒ 想用 HTTP/1.1 时：先**完全退出 Edge**（含"启动加速"/后台驻留），再用这个快捷方式启动。

按这个规矩以外的入口（任务栏固定、开始菜单里的原版 Edge、文件关联）都**不带参数**。

## 四、验证方法（自己以后复核用）

```
1. 地址栏进 edge://policy  → 确认 QuicAllowed = false
2. F12 → Network → 右键列头 → 勾 Protocol  → 看是 h2 还是 http/1.1
3. Firefox 侧用 about:networking#http2 / #http3 看活连接
```

本次用过的自动化手段（CDP 探针）已随临时目录删除；需要时重写约 40 行 Node 即可：
起 Edge 带 `--remote-debugging-port`，连页面 WebSocket，`Network.enable` 后
`Page.navigate`，读 `Network.responseReceived` 的 `protocol`。

## 五、本次踩到的两个坑

1. **无效 A/B**：拿一个本身不走 h2 的站点做对照，两组都得到 http/1.1，
   看起来"开关无效"，其实是实验设计错了。**先验证对照组能出现 h2。**
2. **`start` + `cmd /c` 从 WSL 调用会挂住**：直接调 `msedge.exe` 正常，
   经 `cmd.exe /c "...\launcher.cmd"` 时进程不返回（已 kill）。
   最终改用「桩程序验证参数转发」来闭合这条链路 —— 桩把目标 exe 换成
   `cmd /c echo %* > args.txt`，实测收到 `ARGS=--headless=new --foo "bar baz"`，引号完好。
   **验证链路时，能分段验证就不要硬跑端到端。**

## 六、遗留

- Edge 的 H2 开关**无法做成全局策略**，这是 Chromium 的策略面缺失，不是配置没写对。
  若哪天想要"无感生效"，只能改所有启动入口（任务栏固定、文件关联、开机项），
  而 Edge 自动更新会重建部分快捷方式 ⇒ 不划算，未做。
- Firefox 的两个 pref 由用户手工配置，本文只做记录与名字核对。
