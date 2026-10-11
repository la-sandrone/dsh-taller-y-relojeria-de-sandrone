# dsh-user-markdown 补丁存档（方案 A · 0.1.5 版）

> 让用户消息气泡（user / steering）按 Markdown 渲染的本地补丁。
> 性质：**改官方源码**（`ui-chat/src/client/chat/MessageItem.tsx`），非插件。
> 官方立场：2026-07-23 决策文档把"用户输入是否格式化"定义为**产品选择**、默认按字面渲染
> ——本补丁即本地做出的那次选择。

## 状态

- **当前版本**：v0.1.5-rc.2（2026-09-13 实施并构建通过）
- **目标文件**：`packages/client/ui-chat/src/client/chat/MessageItem.tsx`
- **改动量**：+46 / −3 行（单文件）
- **补丁文件**：`patches/dsh-user-markdown-0.1.5.patch`（基于该版本文本的 `git apply` 可重放）
- **验证**：tsc 类型检查 ✅ ／ tsdown bundle ✅ ／ cloudflared 指纹未变 ✅
- **浏览器实测**：✅ 2026-09-13 渲染通过（用户确认；actions 行未被触碰，按设计保留）

## 改了什么

`UserStyleBubble` 的内容行（`projectUserText` → `projectUserContent`）
＋ 新增该函数 ＋ import 三处 ＋ 文件头注释块。

核心函数：

```tsx
function projectUserContent(text, referenceLabels, skillNames, labels) {
  const projected = projectUserText(text, referenceLabels, skillNames)
  const undecorated = isValidElement(projected)
    && (projected.props as { children?: unknown }).children === text
  return undecorated ? <MarkdownText text={text} labels={labels} /> : projected
}
```

## 判定逻辑（关键设计）

**不复刻官方正则**，而是问官方自己的返回值：

- 官方 `projectUserText` 无装饰时返回 `<span className={css.plainRun}>{text}</span>`（单元素，children 即原文）
- 有装饰时返回 Fragment（多片段）

→ 所以 `isValidElement(x) && x.props.children === text` 即"无引用装饰"。

**安全失败方向**：官方若改实现（例如无装饰时改返回 Fragment），判定失效 → 退回纯文本，
不会渲染坏。这是刻意选择的保守姿态。

## 覆盖范围

改 `UserStyleBubble` = 4 条调用路径全部生效（**有意为之**，2026-09-13 用户确认）：

| 路径 | 效果 |
|---|---|
| `UserMessageNodeView`（落库的 user / steering） | ✅ 主线 |
| `PendingSteeringBubble`（引导排队中） | ✅ 顺带（观感一致，无跳变） |
| `PendingSubmissionBubble`（本地回声） | ✅ 顺带 |

## 明确不受影响

- **actions 行**（复制 / 分支 / 插件 `extraActions`）——零接触
- **queue 排队预览**（`QueueDock`，`nowrap` 单行）——不走 `UserStyleBubble`
- **assistant 消息**——另一条渲染链

## 边界（有意为之，勿当 bug）

1. 消息含任何引用 token（`@文件`、会话引用、已加载技能名）→ **整条退回纯文本**。
   原因：引用扫描是纯文本层的、不理解 Markdown 结构，强行走 Markdown 会把代码块与表格里的
   `@`、`/` 误抠成 chip 导致语法腰斩。宁可整条不渲染，也不渲染坏。
2. 换行语义变化：纯文本是 `pre-wrap`（单换行保留显示）；Markdown 折叠段内单换行为空格，
   **空行才分段**。
3. `$E=mc^2$` 会渲染成 KaTeX 公式。
4. 纯文本里的裸 markdown 字符（`2*3*4`、`#话题`）会被解释——用户已知并接受（2026-09-13）。

## 构建（0.1.5）

`ui-chat` 是**动态 client 插件**，不进 vite graph → **不需要 `pnpm build:web`**：

```bash
cd ~/deepseek-harness/原始代码研究/$DSH_VERSION
pnpm exec tsc -b tsconfig.client.json                       # 增量类型构建（~2s）
pnpm --filter @deepseek-ai/dsh-client-ui-chat run bundle    # 只重打包 ui-chat（~0.6s）
# 然后浏览器刷新（client module system 的 HMR 可能自动重载）
```

开发循环：`cd packages/client/ui-chat && pnpm run watch`（`tsdown --watch`）。

## ⚠️ cloudflared 护栏（重要）

本补丁的构建发生在**基座检出**，与 `dsh-domus/profiles/web/node_modules` 相互隔离，
**不会碰** cloudflared 的手工二进制。仍建议构建前后各校验一次指纹：

```bash
md5sum dsh-domus/profiles/web/node_modules/cloudflared/bin/cloudflared
# 期望：1d0ea8cd29387b0050075c5aca1485ae
md5sum tools/cloudflared-linux-amd64.staged   # 同源暂存件，兜底来源
```

**绝不在 `dsh-domus/profiles/web/` 里跑 `pnpm install` / `pnpm add`**——那会把整个
`cloudflared/` 目录从 store 重新解压，而 `bin/` 是 postinstall 产物、不在 tarball 里，
手工塞进去的二进制会消失。真丢了就用暂存件补回：

```bash
mkdir -p <profile>/node_modules/cloudflared/bin
install -m 755 tools/cloudflared-linux-amd64.staged <profile>/node_modules/cloudflared/bin/cloudflared
```

## 版本升级立即排查清单

升级基座后 `lib/` 被重建覆盖，补丁丢失（**改的是 `src/`——这是本版与 0.1.1 版最大的不同**）。
重打步骤：

1. 打开 `packages/client/ui-chat/src/client/chat/MessageItem.tsx`
2. 检查四项：
   ① `UserStyleBubble` 是否仍存在、内容行是否仍调 `projectUserText`
   ② `@deepseek-ai/dsh-client-ui-primitives` 是否仍导出 `MarkdownText` / `MarkdownLabels` / `projectUserText`
   ③ `projectUserText` 的"无装饰"分支是否仍返回单个 `span`（判定逻辑的依据）
   ④ `../markdown-labels.ts` 的 `markdownLabels(t)` 是否仍存在
3. 应用 `patches/dsh-user-markdown-0.1.5.patch`（`git apply`）或手改那 4 处
4. 构建（见上）+ 浏览器刷新

## 回滚

- 基座 git：`git checkout -- packages/client/ui-chat/src/client/chat/MessageItem.tsx`
- 重新 bundle 即还原官方产物

## 历史沿革

| 版本 | 方案 | 目标 | 关键差异 |
|---|---|---|---|
| v0.1.1-rc.2（2026-09-02） | 改**构建产物** `ui-conversation/lib/client.js`（`MessageText` → `MarkdownText`） | 3 行 | `lib/` 被基座 .gitignore 忽略，只能文档存档 |
| v0.1.5-rc.2（2026-09-13） | 改**源码** `ui-chat/src/.../MessageItem.tsx` | +46 / −3 | `MessageText` 已被官方删除；`projectUserText` 迁到 ui-primitives；判定改为"复用官方返回值" |

**0.1.5 相比 0.1.1 的三处结构变化**（升级时必须知道）：

1. `MessageText` 原语**已被官方删除**，`ui-primitives` 现在只导出 `MarkdownText`
2. `projectUserText` 从 `ui-conversation` 迁到 `ui-primitives/src/user-text.tsx`
3. 目标从构建产物 `lib/client.js` 变成源码 `src/.../MessageItem.tsx`

## 附加记录：0.1.1 版的一处实测偏差（保留备查）

0.1.1 版实测发现：含引用 token 的消息 `@<R盘>:\123.txt $E=mc^2$` 的公式**仍然渲染了**，
与"含引用则退回纯文本"的代码预期不符。推断原因是 composer 在发送时已把 `@<R盘>:\123.txt`
折叠成引用对象，落库文本里不再有裸 token，气泡层扫描不到 → 走了 Markdown 分支。
0.1.5 版沿用同一判定思路，若日后复现"引用 chip 丢失/渲染错乱"，优先排查 composer 折叠路径。

## 讨论记录（为什么不做成插件）

2026-09-13 曾评估"独立插件 shadow `conversation.chat.node` 的 `user` key"
（0.1.5 的 slot 支持 `priority` 遮蔽：`entriesOfSlot` 按 priority 取首个 live entry，
不同 priority 不抛错而是遮蔽，`lowest renders`）。**否决**，理由：

- 会连带丢失 `MessageIconActions`（复制 / 分支按钮，**未导出**），而用户有多个插件通过
  `MessageIconActionsProps.extraActions` 挂在这一栏（官方注释：placed between the built-in
  copy and branch controls）——shadow 整个组件会让这些挂载点一起消失
- 需自绘气泡 + 复刻 CSS，外观漂移
- 源码方案改动更小（单文件 4 处）、外观 100% 官方、且天然覆盖 pending 态

（`conversation.chat.node` 的遮蔽机制本身是可行的，记录在此以备将来复用。）
