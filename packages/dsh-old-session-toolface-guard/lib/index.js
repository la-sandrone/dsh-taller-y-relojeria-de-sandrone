// 文件名: lib/index.js
// 摘要: 拦住「工具面翻转 ⇒ 全部 defer_loading ⇒ DeepSeek 400」。**派发前**把一条真实工具
//       补回会话基线，使 projectToolUpdates() 至少留下一个非延期声明。
// 依赖: @deepseek-ai/schemastery（配置校验与默认值）
//
// ── 铁律：next() 只能调一次 ──────────────────────────────────────────
//  Cordis 的 llm/stream 是 waterfall，监听者拿到的 next 是「往下走一跳」，
//  调第二次会直接抛 next() called multiple times（2026-11-05 实测，把整轮打成失败）。
//  ⇒ 本插件只在派发**之前**就地改请求，之后原样调一次 next()；不做重派发兜底。
//
// ── 配置在哪改 ──────────────────────────────────────────────────────
//  唯一入口：<home>/profiles/web/cordis.patch.yml 的「工具面守门」段。
//  改完下一次启动生效（本 profile 是 patchReload: live）。默认值同时写在 Config 里，
//  但改默认请改配置文件，别改代码。
//
// ── 修法取舍 ────────────────────────────────────────────────────────
//  不补假占位工具（pi-ai 的 DeferredToolPlaceholder 只让请求合法，模型拿不到真工具），
//  而是把当前活跃的那一个（默认 run_code）写回历史基线：基线 ∩ 活跃 ≠ ∅ ⇒ 投影自然合法。

import z from '@deepseek-ai/schemastery'

export const name = 'old-session-toolface-guard'

export const Config = z.object({
  cutoff: z.string().default('2026-11-05T00:00:00+08:00')
    .description('会话创建时刻早于此刻 ⇒ 视为「老会话」，无条件补一次基线（判据①）。ISO 8601，必须带时区偏移。'),
  residentTool: z.string().default('run_code')
    .description('补回基线的常驻工具名（须是当前活跃工具之一）；找不到时回落到第一个活跃工具。'),
  predicted: z.boolean().default(true)
    .description('预测式（判据②）：复算投影集合运算，结果「全延期或为空」就先修再发。与日期无关。'),
  oldSessionProactive: z.boolean().default(true)
    .description('判据①是否生效：老会话即使预测没命中，也无条件补一次基线。补的是真实活跃工具，代价是一条声明。'),
  dryRun: z.boolean().default(false)
    .description('只判定不修（排查用）。'),
  repairMode: z.union(['restore', 'reset', 'append']).default('restore')
    .description('restore = 还原翻面前那张面（旧基线 ∪ 当前活跃）并关掉 tool update 机制（老人老办法，默认）；reset = 基线重设为当前活跃工具（新人新办法）；append = 只补一条进旧基线。'),
})

/** 截止时刻必须带显式时区，否则时区歧义会让判据悄悄偏移。 */
const OFFSET_SUFFIX = /(?:Z|[+-]\d{2}:?\d{2})$/i

/**
 * 解析 cutoff；非法值 fail-loud（配置错不该退化成「静默不设防」）。
 * @param raw - 配置里的 ISO 8601 字符串
 * @returns 毫秒时间戳
 */
function parseCutoff(raw) {
  const text = typeof raw === 'string' ? raw.trim() : ''
  if (text === '' || !OFFSET_SUFFIX.test(text)) {
    throw new Error('old-session-toolface-guard: config.cutoff 必须带显式时区（Z 或 ±HH:MM），否则时区歧义会让判据悄悄偏移。例如 2026-11-05T00:00:00+08:00，收到: ' + JSON.stringify(raw))
  }
  const ms = Date.parse(text)
  if (Number.isNaN(ms)) {
    throw new Error('old-session-toolface-guard: config.cutoff 无法解析为 ISO 8601 时刻，收到: ' + JSON.stringify(raw))
  }
  return ms
}

/** @param tools - 活跃工具数组 @returns 工具名集合 */
function activeNames(tools) {
  const names = new Set()
  if (Array.isArray(tools)) for (const tool of tools) if (tool && typeof tool.name === 'string') names.add(tool.name)
  return names
}

/**
 * 复算 packages/llm/llm/src/content.ts 的 toolDeclarations()：该模式下是否全延期 / 为空。
 * 两种模式都要算：'addition-only' 会把不在活跃集里的基线工具删光，那才是元凶；
 * 只看 'in-history' 会漏判。路由实际模式在适配器内部、瀑布层读不到 ⇒ 任一命中即风险。
 * @param history - GenerateOptions.toolHistory
 * @param tools - GenerateOptions.tools（addition-only 用它做活跃集）
 * @param mode - 'in-history' | 'addition-only'
 * @returns 该模式下是否没有一个是可加载声明
 */
function allDeferred(history, tools, mode) {
  if (history === undefined || history === null) return false
  const declarations = new Map()
  const base = Array.isArray(history.tools) ? history.tools : []
  for (const tool of base) if (tool && typeof tool.name === 'string') declarations.set(tool.name, tool)
  const updates = Array.isArray(history.updates) ? history.updates : []
  for (const update of updates) {
    const additions = Array.isArray(update && update.additions) ? update.additions : []
    for (const tool of additions) {
      if (!tool || typeof tool.name !== 'string') continue
      if (!declarations.has(tool.name)) declarations.set(tool.name, { ...tool, deferLoading: true })
    }
  }
  if (mode === 'addition-only') {
    const active = activeNames(tools)
    for (const key of [...declarations.keys()]) if (!active.has(key)) declarations.delete(key)
  }
  if (declarations.size === 0) return true
  for (const decl of declarations.values()) if (decl.deferLoading !== true) return false
  return true
}

/**
 * 把一条真实工具写回基线；原地改 options。已存在同名基线声明则不动。
 * @param options - GenerateOptions
 * @param residentTool - 期望的常驻工具名
 * @returns 是否真的改了
 */
function armResident(options, residentTool) {
  try {
    const history = options.toolHistory
    if (history === undefined || history === null) return false
    const tools = Array.isArray(options.tools) ? options.tools : []
    const resident = tools.find(tool => tool && tool.name === residentTool) ?? tools[0]
    if (resident === undefined || resident === null || typeof resident.name !== 'string') return false
    const clean = {
      name: resident.name,
      description: resident.description ?? '',
      parameters: resident.parameters ?? { type: 'object', properties: {} },
    }
    const base = Array.isArray(history.tools) ? history.tools : []
    if (base.some(tool => tool && tool.name === clean.name)) return false
    options.toolHistory = { ...history, tools: [...base, clean] }
    options.tools = tools.map(tool => (tool && tool.name === clean.name ? clean : tool))
    return true
  } catch {
    return false
  }
}

/**
 * 还原「上一次正常发送时的那张面」：旧基线 ∪ 当前活跃，并**关掉 tool update 机制**。
 * GenerateOptions.toolHistory 的契约是「省略 ⇒ 发送完整声明、不带 tool update」，
 * 于是请求里不存在中途新增、也不存在 defer_loading，服务端不可能以「全延期」拒绝。
 * 这就是「老人老办法」：把翻面之前那张面原样发出去，再多给一个当前执行器的新工具。
 * @param options - GenerateOptions
 * @returns { changed, faceSize }
 */
function restoreFace(options) {
  try {
    const history = options.toolHistory
    if (history === undefined || history === null) return { changed: false, faceSize: 0 }
    const base = Array.isArray(history.tools) ? history.tools : []
    const active = Array.isArray(options.tools) ? options.tools : []
    const seen = new Set()
    const face = []
    for (const tool of [...base, ...active]) {
      if (!tool || typeof tool.name !== 'string' || seen.has(tool.name)) continue
      seen.add(tool.name)
      const { deferLoading, ...rest } = tool
      face.push(rest)
    }
    if (face.length === 0) return { changed: false, faceSize: 0 }
    options.tools = face
    options.toolHistory = undefined
    return { changed: true, faceSize: face.length }
  } catch {
    return { changed: false, faceSize: 0 }
  }
}

/**
 * 把会话基线整体重设为「当前活跃工具、无中途新增」。
 * 这是最稳的一招：投影随后无论走 addition-only 还是 in-history，都会得到
 * 「= 当前活跃集、全部非延期」，不存在删空或全延期的可能。代价是那些"中途新增"
 * 的 developer 声明不再进入请求（附带的延迟加载优化也随之失效）—— 对已经废掉的
 * 老会话，这是拿优化换可用。
 * @param options - GenerateOptions
 * @returns 是否真的改了
 */
function resetBaseline(options) {
  try {
    const history = options.toolHistory
    if (history === undefined || history === null) return false
    const tools = Array.isArray(options.tools) ? options.tools : []
    if (tools.length === 0) return false
    const clean = tools.map(tool => {
      const { deferLoading, ...rest } = tool
      return rest
    })
    options.toolHistory = { ...history, tools: clean, updates: [] }
    options.tools = clean
    return true
  } catch {
    return false
  }
}

/**
 * 会话创建时刻（毫秒）；取不到返回 undefined（不影响预测式判据）。
 * @param ctx - 插件上下文
 * @param sessionId - GenerateOptions.sessionId
 */
function sessionCreatedAt(ctx, sessionId) {
  try {
    if (sessionId === undefined) return undefined
    const sessions = ctx.get('sessions')
    if (sessions === undefined || typeof sessions.get !== 'function') return undefined
    const session = sessions.get(sessionId)
    if (session === undefined || session === null) return undefined
    const header = session.header ?? (session.which && session.which.header) ?? session.meta
    const at = header && header.createdAt
    return typeof at === 'number' ? at : undefined
  } catch {
    return undefined
  }
}

export const inject = []

/**
 * 挂 llm/stream 网守（只改请求，next() 只调一次）。
 * @param ctx - 插件上下文（用 ctx.get('sessions') 做可选读取，不声明强注入）
 * @param config - 见 Config
 */
export function apply(ctx, config) {
  const cutoffMs = parseCutoff(config?.cutoff ?? '2026-11-05T00:00:00+08:00')
  const residentTool = typeof config?.residentTool === 'string' && config.residentTool !== '' ? config.residentTool : 'run_code'
  const predictedEnabled = config?.predicted !== false
  const proactiveEnabled = config?.oldSessionProactive !== false
  const dryRun = config?.dryRun === true
  const repairMode = config?.repairMode === 'reset' || config?.repairMode === 'append' ? config.repairMode : 'restore'

  ctx.on('llm/stream', (options, next) => {
    try {
      if (options === undefined || options === null || options.toolHistory === undefined) return next()
      const flipped = predictedEnabled
        && (allDeferred(options.toolHistory, options.tools, 'addition-only')
          || allDeferred(options.toolHistory, options.tools, 'in-history'))
      const createdAt = sessionCreatedAt(ctx, options.sessionId)
      const oldSession = proactiveEnabled && createdAt !== undefined && createdAt < cutoffMs
      if (!flipped && !oldSession) return next()
      if (dryRun) return next()
      if (repairMode === 'restore') {
        const { changed } = restoreFace(options)
        if (!changed) armResident(options, residentTool)
      } else if (repairMode === 'reset') {
        if (!resetBaseline(options)) armResident(options, residentTool)
      } else {
        armResident(options, residentTool)
      }
      return next()
    } catch {
      return next()
    }
  }, { global: true, prepend: true })
}
