// 文件名: index.js
// 摘要: dsh-sandrone-ui-patches 的 host 半区 —— 把随包的可变字体用一条 HTTP 前缀路由发出去，
//       供 client 半区的 @font-face 引用；缓存头由本半区掌握（immutable + 内容哈希 ETag）。
// 依赖: node:crypto, node:fs
//
// ── 为什么需要这条路由（三条路都试过）────────────────────────────────────
//  ① 内嵌进 client bundle：全量 woff2 426,716 B → base64 568,956 B，把 bundle 从 16 KB 撑到 570 KB。
//  ② 放皮肤 assets：那是皮肤的资产（谁的孩子谁抱走），且响应头 cache-control: no-store，
//     417 KB 每次页面加载都要重传。
//  ③ /plugins 路由：只服务 client bundle 与 source map —— 官方文档原话是「绝不提供其他字节」。
//  ⟹ 走官方给的通用机制：插件自己注册前缀路由（ctx.webServer.register）。
//
// ── 命名纪律（重要）────────────────────────────────────────────────────
//  路由前缀刻意**含完整包名** dsh-sandrone-ui-patches：公开导出脚本
//  tools/export-to-sandrone.py 做的是「字面替换完整包名 → dsh-sandrone-ui-patches」，
//  于是导出后这里自动变成 /api/dsh-sandrone-ui-patches/fonts/...，脚本一行都不用改。
//  （反例：缩写 sgt- 不在替换表里会被漏掉；单独出现的 sandrone 同样不在表里。）
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'

/** 路由前缀；含完整包名，便于导出脚本字面替换。 */
const ROUTE_PREFIX = '/api/dsh-sandrone-ui-patches/fonts'

/** 对外暴露的字体：URL 末段 -> 包内相对路径（相对本文件所在的 lib/）。 */
const FONTS = {
  'source-serif-4-var-roman.woff2': '../font/SourceSerif4Variable-Roman.woff2',
}

/** 启动时读一次并缓存：426 KB 常驻，换每请求零 IO 与稳定 ETag。 */
const LOADED = new Map()
for (const [urlName, rel] of Object.entries(FONTS)) {
  const body = readFileSync(new URL(rel, import.meta.url))
  LOADED.set(urlName, {
    body,
    etag: '"' + createHash('sha256').update(body).digest('hex').slice(0, 32) + '"',
  })
}

export const name = 'dsh-sandrone-ui-patches'

/**
 * 注册字体前缀路由。
 *
 * 依赖走 `ctx.inject(['webServer'], cb)` 回调而**不写进顶层 inject**：没有 web server 的组合
 * （headless）里本半区本该无事可做，但写进顶层 inject 会让服务缺席时**整个插件**加载失败，
 * 连带干掉 client 半区的 UI 补丁 —— 那是拿可选能力去赌必需能力
 * （2026-10-07 模型身份注入那场的教训）。写法与 packages/host/open-in-app 同源。
 * @param ctx - cordis 上下文。
 */
export function apply(ctx) {
  ctx.inject(['webServer'], (webCtx) => {
    webCtx.effect(() => webCtx.webServer.register({
      kind: 'prefix',
      path: ROUTE_PREFIX,
      handler: (req, res) => {
        if (req.method !== 'GET' && req.method !== 'HEAD') {
          res.writeHead(405, { allow: 'GET, HEAD' })
          res.end()
          return
        }
        const pathname = new URL(req.url ?? '/', 'http://localhost').pathname
        const urlName = decodeURIComponent(pathname.slice(ROUTE_PREFIX.length + 1))
        const font = LOADED.get(urlName)
        if (font === undefined) {
          res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' })
          res.end('unknown font')
          return
        }
        const headers = {
          'content-type': 'font/woff2',
          'cache-control': 'public, max-age=31536000, immutable',
          etag: font.etag,
        }
        if (req.headers['if-none-match'] === font.etag) {
          res.writeHead(304, headers)
          res.end()
          return
        }
        res.writeHead(200, { ...headers, 'content-length': String(font.body.byteLength) })
        if (req.method === 'HEAD') { res.end(); return }
        res.end(font.body)
      },
    }), 'dsh-sandrone-ui-patches: variable font route')
  })
}
