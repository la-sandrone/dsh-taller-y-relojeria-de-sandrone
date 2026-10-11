// tools/dsh-force-h1.mjs —— 把 Node 内置 fetch 钉在 HTTP/1.1（DSH 的 H2 缓解补丁）。
//
// 为什么需要：undici v8 起 allowH2 默认 true（官方 v7→v8 迁移文档确认）。
//   H2 session 一旦因一次 TLS 抖动被销毁，undici 会【继续复用它】→ 之后每一发
//   都是毫秒级秒失败 → 只能重启。2026-09-25 的 A/B 对照证据见 tools/H1-AB-RESULTS.md。
//
// 依据（undici@8 lib/global.js 实读）：
//   setGlobalDispatcher(a) 写两个符号：
//     sym2 = a                                  ← Node 26 内置 fetch 读这个
//     sym1 = new Dispatcher1Wrapper(a)          ← 这个 wrapper 才强制 allowH2=false，但被绕过
//   所以必须显式改 sym2（换成 allowH2:false 的 Agent）。
//
// ★ 臂开关走【文件】不走环境变量：DSH 会清洗子进程环境（实测连 DEEPSEEK_API_KEY
//   都不给子进程），环境变量开关既不可靠、也无法从外部核对。
//   开关文件: <repo>/tools/h1-mode，内容 'on' | 'off'；缺省（缺文件/内容非法）= on。
//   无论哪一臂都写一条 event=force-h1 日志 —— "本进程属于哪个臂"永远是显式记录。
//
// ★ undici 解析【动态】：以前硬编码 `原始代码研究/v0.1.5-rc.2/...`，**换版本即静默失效**。
//   现在先读 DSH_VERSION 拼路径，再枚举 原始代码研究/* 兜底；并记录 resolvedFrom。
//   升级后核对：applied 必须为 true（见 tools/DSH-升级铁律.md 的铁律 2 ②）。
//
// 铁律：绝不写 stdout（bingcn 等 node MCP 用 stdio 传 JSON-RPC）。
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { existsSync, readFileSync, readdirSync, appendFileSync } from 'node:fs'

// 根目录：环境优先（启动器注入 DSH_HARNESS_DIR）→ 否则由本文件位置推导（tools/ 的上一级）
const REPO = (process.env.DSH_HARNESS_DIR ?? fileURLToPath(new URL('..', import.meta.url))).replace(/\/$/, '')
// 日志与臂开关都支持环境覆盖 —— 实现【每实例一份】。
// 起因（2026-09-26 实证）：两个实例同写一个取证文件，且 h1-mode 是全局文件开关，
// 一旦拉起第二个实例，HTTP/1.1 这个"臂"会对两个实例同时生效，实验设计就废了。
// 同上：回落只在没走启动器时生效 ⇒ 草稿区
const LOG = process.env.DSH_TRACE_LOG ?? `${REPO}/.dsh-scratch/fetch-trace.log`
const MODE_FILE = process.env.DSH_H1_MODE_FILE ?? `${REPO}/tools/h1-mode`
const CHECKOUT_ROOT = `${REPO}/原始代码研究`

function log(obj) {
  try {
    appendFileSync(LOG, JSON.stringify({ ts: new Date().toISOString(), pid: process.pid, ...obj }) + '\n')
  } catch {
    /* 取证失败绝不拖垮宿主 */
  }
}

// ── 当前生效版本：环境优先，配置文件的版本仅作回落 ─────────────────
// 与 bin/dsh 同一规则。旧版无条件读【全局选择器文件】DSH_VERSION → 第二个实例
// （DSH_VERSION 在 env 里）会去解析【第一个实例】的检出，把 undici 补丁打到错误的树上。
// 2026-10-08：那个全局文件随启动器移植退役，回落改读
// `启动器配置和日志/当前配置.toml` —— 元数据的唯一真相源。
function activeVersion() {
  const fromEnv = process.env.DSH_VERSION
  if (fromEnv && fromEnv.trim()) return fromEnv.trim()
  try {
    const toml = readFileSync(`${REPO}/启动器配置和日志/当前配置.toml`, 'utf8')
    const m = toml.match(/^\s*version\s*=\s*"([^"]+)"/m)
    return m ? m[1] : null
  } catch {
    return null
  }
}

// ── 候选 base（按优先级；去重）────────────────────────────────────
function candidateBases() {
  const out = []
  const ver = activeVersion()
  const P = (v) => [
    `${CHECKOUT_ROOT}/${v}/packages/util/http-proxy/package.json`,
    `${CHECKOUT_ROOT}/${v}/packages/web/web-fetch-http/package.json`,
  ]
  if (ver) out.push(...P(ver))
  try {
    for (const d of readdirSync(CHECKOUT_ROOT)) out.push(...P(d)) // 版本目录改名/升级后兜底
  } catch {
    /* 枚举失败就只靠 ver */
  }
  out.push(`${REPO}/node_modules/undici/package.json`)
  return [...new Set(out)]
}

function loadUndici() {
  for (const base of candidateBases()) {
    if (!existsSync(base)) continue
    try {
      const mod = createRequire(base)('undici')
      if (mod && typeof mod.Agent === 'function' && typeof mod.setGlobalDispatcher === 'function') {
        return { mod, from: base }
      }
    } catch {
      /* 试下一个 base */
    }
  }
  return undefined
}

function readMode() {
  try {
    const v = readFileSync(MODE_FILE, 'utf8').trim().toLowerCase()
    if (v === 'on' || v === 'off') return { mode: v, modeSource: 'file' }
  } catch {
    /* 缺省 */
  }
  return { mode: 'on', modeSource: 'default' }
}

const argv = process.argv.slice(0, 3)
const { mode, modeSource } = readMode()

// 给 tracer 读的臂标记（同进程内通过 globalThis 传递，跨模块可靠）
globalThis.__DSH_H1__ = { mode, modeSource, forced: false }

if (mode === 'off') {
  log({ event: 'force-h1', applied: false, reason: 'mode=off', mode, modeSource, argv })
} else {
  const found = loadUndici()
  if (!found) {
    globalThis.__DSH_H1__ = { mode, modeSource, forced: false, reason: 'undici-unresolved' }
    log({
      event: 'force-h1', applied: false, reason: 'undici-unresolved',
      mode, modeSource, argv, dshVersion: activeVersion(), tried: candidateBases().length,
    })
    console.error('[dsh-force-h1] 找不到可用的 undici —— H1 未生效！见 tools/DSH-升级铁律.md')
  } else {
    const agent = new found.mod.Agent({ allowH2: false })
    found.mod.setGlobalDispatcher(agent)
    globalThis.__DSH_H1__ = { mode, modeSource, forced: true, resolvedFrom: found.from }
    log({
      event: 'force-h1', applied: true, mode, modeSource, argv,
      dshVersion: activeVersion(), resolvedFrom: found.from,
    })
    console.error(`[dsh-force-h1] 已强制 HTTP/1.1 (allowH2=false) pid=${process.pid}`)
  }
}
