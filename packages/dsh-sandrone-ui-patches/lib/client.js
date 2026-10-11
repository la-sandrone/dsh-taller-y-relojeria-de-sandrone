// dsh-sandrone-ui-patches（桑多涅的 UI 补丁，client 半区）：factory 期注入全局 CSS。
// 覆盖五件事：① 衬线字体方案（:root 基线 + 皮肤 body 克隆免疫）；② 字号倍率（基准交还 ui-theme，各档按倍率跟随）；
// ③ 超长 markdown 表格强制压缩；④ 暗色皮肤表格分割线对比度；⑤ crumb 限宽放开（标题集群居中已于 2026-09-27 撤销）。
// Pattern copied from dsh-client-ui-skin-center/lib/client.js (factory-time CSS injection).
// NOTE: the client module loader applies every entry as a cordis plugin, so the
// bundle exports MUST carry an `apply` function (isApplicable check), otherwise
// the entry fails to load with "invalid plugin ... received object".

window.__ModuleLoader__.load({
	id: "dsh-sandrone-ui-patches",
	factory: (require) => {
		var module = { exports: {} };
		var exports = module.exports;

		// 字体栈单一权威源：:root 基线与 html body 克隆免疫块共用——改字体只动这两行常量。
		var SERIF_FAMILY = "'Source Serif 4 VF', 'Source Serif 4 Display', 'Source Serif 4', 'Times New Roman', '仿宋', 'FangSong','思源宋体', 'Noto Serif CJK SC', serif";
		//var CODE_FAMILY = "'Fira Code', '仿宋', 'FangSong', serif";
		//var SERIF_FAMILY = "'Source Serif 4 Display','Source Serif 4','仿宋', 'FangSong','思源宋体', 'Noto Serif CJK SC', serif";
		var CODE_FAMILY = "'Fira Code', '仿宋', 'FangSong','思源宋体', 'Noto Serif CJK SC',monospace";
		var SIDEBAR_FAMILY = "'思源宋体', 'Source Han Serif SC', 'Noto Serif CJK SC', 'Source Serif 4 Display', 'Times New Roman', serif";
		// ── 侧栏字体简写 token 重算（2026-10-09 v2：修 font: 简写漏网）────────────
		// ui-theme 把字族**烘进**了 --dsw-font-* 简写 token，例如
		//   --dsw-font-xxs-12: 12px/18px var(--dsw-font-family);
		// 而 CSS 自定义属性的 Computed value 是「specified value with variables
		// substituted」（css-variables-1 的 --* propdef）⇒ 嵌套 var() 在**声明处**
		// （:root / html body）就解析完了，之后按计算值继承。
		// ⇒ 只重定义 --dsw-font-family 没用；必须把这些简写 token 本身在侧栏根上重算。
		// 子变量 -font-style/-font-weight/-font-size/-line-height 只是数值与长度、
		// 不含嵌套 var() ⇒ 继承干净，拿来重建简写就不必硬编码任何尺寸。
		// 刻意只列这 27 个字族简写：代码族（--ds-font-family-code / --dsw-font-mono /
		// --dsw-font-markdown-code*）一概不碰 —— 终端、代码块、git diff 的等宽必须原样。
		var SIDEBAR_FONT_TOKENS = ["xl-24", "l-20", "m-18", "base-16", "base-strong-16", "s-14", "s-strong-14", "xs-13", "xs-strong-13", "xxs-12", "xxs-strong-12", "xxxs-11", "xxxs-strong-11", "markdown-h1", "markdown-h2", "markdown-h3", "markdown-h4", "markdown-base", "markdown-base-strong", "markdown-base-italic", "markdown-base-strong-italic", "markdown-table", "markdown-table-head", "markdown-small", "markdown-small-strong", "markdown-small-italic", "markdown-small-strong-italic"];
		var REBAKE_SIDEBAR_FONTS = SIDEBAR_FONT_TOKENS.map(function (t) {
			return "  --dsw-font-" + t + ": var(--dsw-font-" + t + "-font-style, normal) var(--dsw-font-" + t + "-font-weight, 400) var(--dsw-font-" + t + "-font-size)/var(--dsw-font-" + t + "-line-height) var(--dsw-font-family);";
		}).join("\n");

		// ── 字号倍率（2026-10-08 改为比例式，与 VSCode 对齐）────────────────────────
		// 唯一绝对数字交还 ui-theme 的 --dsh-content-font-size（设置面板「字号大小」）：
		// 由 boot script 与 ui-layout 的 theme-presenter 写在 body 内联样式上。本包只留倍率。
		// 倍率 = 2026-10-07 在 18px 基准下定稿的绝对 px ÷ 18 ⇒ 基准设 18 时与当时逐像素一致，
		// 其它基准按「DPI 缩放」式等比跟随（乘法）。不用加法：复用官方 delta 时锚点在 14px，
		// 22px 基准下代码块会算成 16 + 8 = 24px，比正文还大 —— 层级翻转。
		// DSH 的 delta 链（h1/h2/h3/h4/base/table）是 calc(<原字号> + delta)，官方自管，本包不碰；
		// code / code-block 是硬编码绝对值（12px / 11px），压根不跟随，故这几档由本包接管。
		var CODE_RATIO = 0.8888888888888889;              // 16/18 —— 代码块与行内代码
		var CODE_LINE_RATIO = 1.4444444444444444;        // 26/18
		var CODE_LINE_SMALL_RATIO = 1.3333333333333333;  // 24/18
		var BANNER_RATIO = 0.8333333333333333;           // 15/18 —— 代码块头部语言标签
		var BANNER_LINE_RATIO = 1.2222222222222222;      // 22/18

		var FONT_CSS = [
			"/* ── 随包可变字体（Source Serif 4 Variable / Roman / woff2 全量 426,716 B）────────────",
			"   由 host 半区 lib/index.js 的前缀路由提供。URL 前缀刻意含完整包名，便于公开导出脚本",
			"   字面替换（/api/dsh-sandrone-ui-patches/fonts/ -> …/dsh-sandrone-ui-patches/fonts/）。",
			"   为什么不走别的路：内嵌进 bundle 会让它 +570 KB；借皮肤 assets 是 no-store，417 KB",
			"   每次页面加载重传；/plugins 只服务 client bundle。这条路由带 immutable 缓存与内容哈希",
			"   ETag，是三害相权取其轻。",
			"   ★ 全量、不子集化：本机场景是科幻 + 人类学讨论，数学符号 / 希腊字母 / IPA / 转写",
			"     变音符都是高发字符。",
			"   ★ 可变轴（wght 200-900、opsz 8-60）保留 ⇒ font-optical-sizing: auto 能按实际",
			"     font-size 自动选光学尺寸。这正是「字号可调」这个设计成立的前提：手工分档是静态",
			"     映射，字号一调就失配；opsz 轴是动态的。",
			"   许可 SIL OFL 1.1（Adobe）；随包附 font/LICENSE-SourceSerif4.md。 */",
			"@font-face {",
			"  font-family: 'Source Serif 4 VF';",
			"  src: url('/api/dsh-sandrone-ui-patches/fonts/source-serif-4-var-roman.woff2') format('woff2');",
			"  font-weight: 200 900;",
			"  font-style: normal;",
			"  font-display: swap;",
			"}",
			":root {",
			"  /* 正文族：西文 Source Serif 4（人文衬线/手写味）打头 -> Times New Roman（印刷感兜底） -> 中文仿宋（手写感） -> 思源宋体（印刷感兜底） */",
			"  --dsw-font-family: " + SERIF_FAMILY + " !important;",
			"  /* 代码族（2026-10-07 与 VSCode 对齐）：Fira Code -> 中文仿宋 -> serif 兜底。",
			"     不再以 monospace 收尾：Windows 下裸 monospace 的 CJK 会落宋体，与仿宋正文打架。 */",
			"  --ds-font-family-code: " + CODE_FAMILY + " !important;",
			"}",
			"/* 皮肤字体变量 body 克隆免疫（2026-09-20 定案，取代逐皮肤特判）：",
			"   skin-center 的 CSS 管线（core/css-safety/transform.ts）把皮肤裸 :root/html 块里的自定义属性",
			"   逐行 clone 到 html[data-dsh-skin=\"<id>\"] body 上——token 类（--dsw-alias-* / --dsw-specific-*）",
			"   的 !important 会被剥掉，以让 body 上的暗色变体生效；其余自定义属性原样保留。CSS 变量继承",
			"   在最近祖先定义处停止，于是 body 上的克隆劫持整个正文子树，上面 :root 的 !important 穿不过去。",
			"   已知中招者（都在裸 :root 里重定义 --dsw-font-family）：matrix/skin.css（Menlo 等宽栈）、",
			"   xp/skin.css（Tahoma sans 栈）、deep-current/skin.css（-apple-system sans 栈）；其余皮肤",
			"   （furina/navia/harbor/mint/summer-liquid-glass/war-thunder）不定义字体变量，天然免疫。",
			"   修法收敛成 body 锚点、不再逐皮肤枚举：克隆的落点就是 body，且克隆出的字体声明至今无一使用",
			"   !important——同一元素（body）上先比重要性再比特异性，本块 !important 必胜，一份规则覆盖所有",
			"   现存与将来的皮肤。若日后某皮肤故意以 !important 写字体变量（今天没有），在此补回显式",
			"   html[data-dsh-skin=\"…\"] / html[data-dsh-skin=\"…\"] body 锚点即可（即旧版 matrix/xp 的写法）。",
			"   code/pre 于 2026-10-07 改为**全局压制**（见下方两层通用规则）；deep-current 会话标题仍保留",
			"   皮肤自己的 display 字体（组件级直接声明，变量覆盖动不了，2026-09-20 决策）。 */",
			"html body {",
			"  --dsw-font-family: " + SERIF_FAMILY + " !important;",
			"  --ds-font-family-code: " + CODE_FAMILY + " !important;",
			"}",
			"/* ── 侧边栏字族：思源宋体一体（2026-10-09；v2 补 font: 简写漏网）──────────",
			"   只管左右两栏的「铬件」，会话内容与正文一律不动。",
			"   ① 属性层：font-family 从 body 继承 ⇒ 在侧栏根上写一条就覆盖整棵子树；刻意",
			"      不写通配选择器（直系声明永远赢过继承，写 `*` 会反过来压过本包上面那条",
			"      code,pre 的 CODE_FAMILY）。左栏（ui-sidebar / ui-workspace）的 CSS 里一个",
			"      font-family / font: 简写都没有，纯靠继承 ⇒ 这一条就够。",
			"   ② 变量层（v2 新增，漏网的根因）：右栏插件 dsh-better-sidebar 大量使用",
			"      `font: var(--dsw-font-xxs-12)` 这类**简写 token**。font: 简写会把 token 里",
			"      烘着的字族展开成**元素上的直系 font-family 声明** —— 继承压不过它，而那个",
			"      变量又是在 :root 解析完的（见上面 SIDEBAR_FONT_TOKENS 注释）⇒ 文件浏览器",
			"      目录树、编辑器 chrome、标签条统统落回仿宋。修法：用各 token 自己的子变量在",
			"      侧栏根上重建简写。",
			"   ③ 为什么必须换思源宋体：侧栏字号是上游写死的字面 px（Rows.module.css .title",
			"      14 / .meta 12 / .time 10），不吃 --dsh-content-font-size。14px 下仿宋竖画",
			"      = 0.035em x 14 x 1.5 ≈ 0.74 设备像素，永远画不出一个纯黑像素（实测墨像素",
			"      均值 129/255、纯黑占比 0%），而同一行的西文有 1.9 设备像素 ⇒「西文显胖」。",
			"      思源宋体 CJK 竖画 0.0675em → 1.42 设备像素，稳过线；且思源宋体的拉丁本来就是",
			"      Frank Griesshammer 手笔的 Source Serif（name 表第 9 项自述），与正文同源，",
			"      失配比 1.22x（仿宋 是 2.60x）。",
			"   ④ 例外：右栏编辑器正文（dsh-better-sidebar 的 .editorBody，构建后类名形如",
			"      <hash>_editorBody）是大字号细读区，保留原衬线栈；类名子串抗哈希漂移。它同时",
			"      需要 token 重算（编辑器里 .editorMd 也是 font: 简写），所以它也在 ② 的选择器",
			"      名单里，只是 --dsw-font-family 被下面第三条规则改回原栈。",
			"   副作用：编辑器内可折叠的文件树 dock（.editorTreeDock，含在 editorBody 内）跟着",
			"   保留旧栈 —— 它其实是铬件，要一并换就把它也加进 ②③ 的选择器即可。 */",
			"[data-slot=\"sidebar\"],",
			"[data-slot=\"rightbar\"],",
			"[data-slot=\"rightbar\"] [class*=\"editorBody\"] {",
			REBAKE_SIDEBAR_FONTS,
			"}",
			"[data-slot=\"sidebar\"],",
			"[data-slot=\"rightbar\"] {",
			"  --dsw-font-family: " + SIDEBAR_FAMILY + " !important;",
			"  font-family: " + SIDEBAR_FAMILY + " !important;",
			"}",
			"[data-slot=\"rightbar\"] [class*=\"editorBody\"] {",
			"  --dsw-font-family: " + SERIF_FAMILY + " !important;",
			"  font-family: " + SERIF_FAMILY + " !important;",
			"}",
			"/* ── 会话「编辑日志」卡（ui-deliverables / ChangedFiles）：只抬字号（2026-10-09）──",
			"   锚点 data-changed-files=\"true\" 是插件自己写的**稳定属性**（非 CSS Module 哈希）；",
			"   卡内类名构建后是 <hash>_<local>（lightningcss），故用 [class*=\"_local\"] 子串匹配，",
			"   同时兼容 <local>_<hash>_<n>。属性选择器默认区分大小写 ⇒ [class*=\"_path\"] 不会误伤",
			"   _previewPath。",
			"   ★ 字族**刻意不动**（原本写过一版思源宋体兜底，已撤）：实测只要把字号拉上来，",
			"     仿宋 × Source Serif 4 混排毫不违和 —— 「违和」的根因自始至终是**字号低于渲染",
			"     地板、把仿宋压成灰**，不是两个字体不搭。上游字族原样保留：.path 读",
			"     --dsw-font-family、.title/.toggle 走 .header{font:inherit} 继承、",
			"     .row/.statCounts 走等宽 --ds-font-family-code（那是 +N/-N 对齐用的，别碰）。",
			"     （对比：左右两栏在更上面那两块里确实换了字族 —— 那是因为侧栏字号被布局锁死在",
			"       14px 且行高只有 32px，抬不动；这里抬得动，就不动字族。）",
			"   ★ 字号：上游把这五处写成字面 px（title 13 / stat 10 / row 11 / path 12 / toggle 12），",
			"     既不跟 --dsh-content-font-size，也不跟本包的倍率 ⇒ 正文设 20px 时它们仍只有",
			"     10~13px，远低于渲染地板（仿宋竖画仅 0.035em ⇒ 12px 下约 0.5 CSS px、必是灰的）。",
			"     改成「基准 x 倍率」，倍率按「基准 20px 时小字 >= 16px」反推，标题留在同一条乘法",
			"     链上以保住层级： title 0.90 / path 0.85 / toggle 0.85 / row 0.80 / stat 0.80",
			"     ⇒ 基准 20px 时 = 18 / 17 / 17 / 16 / 16px。是纯乘法式、无硬下限。",
			"   ★ .header 原本 height:60px 是照 13px 标题定的，字号上抬后会裁切 ⇒ 放开为 auto。 */",
			"[data-changed-files=\"true\"] [class*=\"_header\"] {",
			"  height: auto !important;",
			"  min-height: 60px;",
			"}",
			"[data-changed-files=\"true\"] [class*=\"_title\"] {",
			"  font-size: calc(var(--sgt-content-size, 14px) * 0.9) !important;",
			"  line-height: calc(var(--sgt-content-size, 14px) * 1.3) !important;",
			"}",
			"[data-changed-files=\"true\"] [class*=\"_path\"],",
			"[data-changed-files=\"true\"] [class*=\"_toggle\"] {",
			"  font-size: calc(var(--sgt-content-size, 14px) * 0.85) !important;",
			"  line-height: calc(var(--sgt-content-size, 14px) * 1.25) !important;",
			"}",
			"[data-changed-files=\"true\"] [class*=\"_row\"] {",
			"  font-size: calc(var(--sgt-content-size, 14px) * 0.8) !important;",
			"  line-height: calc(var(--sgt-content-size, 14px) * 1.25) !important;",
			"}",
			"[data-changed-files=\"true\"] [class*=\"_stat\"] {",
			"  font-size: calc(var(--sgt-content-size, 14px) * 0.8) !important;",
			"  line-height: calc(var(--sgt-content-size, 14px) * 1.2) !important;",
			"}",
			"/* ── 字号倍率（2026-10-08 改比例式；基准交还 ui-theme）────────────────────",
			"   ① 基准 --dsh-content-font-size 由 ui-theme 写在 body 内联（设置面板「字号大小」10..22），",
			"      本包不再覆盖 —— 覆盖会以 !important 压过内联，让整个设置面板失效。",
			"   ② 本包接管的档（官方 code 12px / code-block 11px / banner 11px 都是硬编码绝对值、",
			"      不跟随 delta 链）改为「基准 × 固定倍率」，倍率见上方常量。",
			"   ③ ★ 简写陷阱：--dsw-font-markdown-code-block 把字号**字面量内联**在值里，而 CodeCard /",
			"      DiffBlock / SearchBlock / TerminalBlock / CodeBlock 六处用 `font: var(...)` 简写取值；",
			"      CSS 变量是静态替换，只改 -font-size 子变量不会重算简写变量 —— 两者必须一起覆盖。",
			"   ④ ★ 只挂 html body，不并挂 :root：:root 在 <html> 上解析，取不到只写在 body 上的基准值",
			"      （会掉进 14px 兜底），且 :root 特异性 (0,1,0) 高于 html body (0,0,2)，挂错会反过来赢。",
			"      它同时兼任「皮肤克隆免疫」：皮肤管线把 :root 自定义属性 clone 到 body，本块 !important",
			"      压过无 !important 的克隆。 */",
			"html body {",
			"  /* 基准的本地别名（sgt 前缀避与官方/皮肤变量重名），供下面几条比例式复用。 */",
			"  --sgt-content-size: var(--dsh-content-font-size, 14px);",
			"  --dsw-font-markdown-code: calc(var(--sgt-content-size) * " + CODE_RATIO + ") / calc(var(--sgt-content-size) * " + CODE_LINE_RATIO + ") var(--ds-font-family-code) !important;",
			"  --dsw-font-markdown-code-font-size: calc(var(--sgt-content-size) * " + CODE_RATIO + ") !important;",
			"  --dsw-font-markdown-code-line-height: calc(var(--sgt-content-size) * " + CODE_LINE_RATIO + ") !important;",
			"  --dsw-font-markdown-code-block: calc(var(--sgt-content-size) * " + CODE_RATIO + ") / calc(var(--sgt-content-size) * " + CODE_LINE_RATIO + ") var(--ds-font-family-code) !important;",
			"  --dsw-font-markdown-code-block-font-size: calc(var(--sgt-content-size) * " + CODE_RATIO + ") !important;",
			"  --dsw-font-markdown-code-block-line-height: calc(var(--sgt-content-size) * " + CODE_LINE_RATIO + ") !important;",
			"  --dsw-font-markdown-code-block-small: calc(var(--sgt-content-size) * " + CODE_RATIO + ") / calc(var(--sgt-content-size) * " + CODE_LINE_SMALL_RATIO + ") var(--ds-font-family-code) !important;",
			"  --dsw-font-markdown-code-block-small-font-size: calc(var(--sgt-content-size) * " + CODE_RATIO + ") !important;",
			"  --dsw-font-markdown-code-block-small-line-height: calc(var(--sgt-content-size) * " + CODE_LINE_SMALL_RATIO + ") !important;",
			"}",
			"/* ── code/pre 字族的全局兜底与皮肤压制（2026-10-07）────────────────────────",
			"   背景：变量层的覆盖（--ds-font-family-code）只能管到「用变量取值」的地方；",
			"   只要有皮肤用**组件级直接声明** font-family，变量就穿不过去。",
			"   已知：matrix/patches.css:134 `code, pre { font-family: Menlo, Consolas, JetBrains Mono, monospace }`",
			"   （skin-center 管线 scope 成 html[data-dsh-skin=\"matrix\"] code ⇒ 特异性 0,1,2，无 !important）。",
			"   2026-09-07 的决策是「保留 Menlo」（终端美学）；2026-10-07 用户要求**全局覆盖**",
			"   （审美：练书法者偏好仿宋，认为无衬线观感差），故该决策作废。",
			"   ★ 不逐皮肤枚举：皮肤会陆续新增（9-07 记录 9 个 → 现 12 个，新增 blueprint /",
			"   crt-phosphor / remiel-starlit），逐皮肤特判必然漏。改为两层通用规则：",
			"     ① 裸元素层——无皮肤时也生效，!important 足以压过任何**非** !important 的皮肤声明；",
			"     ② 皮肤上下文层——借 [data-dsh-skin] 把特异性抬到 (0,1,2)+，",
			"        防将来某皮肤也用 !important 时被反压。",
			"   （变量层见上方 html body 锚点：crt-phosphor / deep-current / matrix / xp 四个皮肤",
			"     在 :root 重定义过 --dsw-font-family 或 --ds-font-family-code，同一锚点通用覆盖。） */",
			"code, kbd, samp, pre {",
			"  font-family: " + CODE_FAMILY + " !important;",
			"}",
			"html[data-dsh-skin] code,",
			"html[data-dsh-skin] kbd,",
			"html[data-dsh-skin] samp,",
			"html[data-dsh-skin] pre,",
			"html[data-dsh-skin] .md-code-block code,",
			"html[data-dsh-skin] .md-code-block pre,",
			"html[data-dsh-skin] [data-code-block-content] code,",
			"html[data-dsh-skin] [data-code-block-content] pre {",
			"  font-family: " + CODE_FAMILY + " !important;",
			"}",
			"/* ── 代码块头部文字（语言标签 .language / 标题 .title）字号（2026-10-07）──────────",
			"   病灶：CodeCard.module.css 的 .language / .title **不声明 font-size**，只给 color 与",
			"   font-family —— 字号靠继承自祖先那句 `font: var(--dsl-code-block-banner-font)`（11px）。",
			"   没有变量可改，只能上选择器。",
			"   锚点：data-code-block-banner 由 CodeBlock.tsx 写死，稳定；",
			"   类名形如 _language_<hash>_<n>，带 CSS Module 哈希，故用类名**子串**匹配抗哈希漂移。",
			"   取值：按基准比例（15/18），与代码正文同源 —— 页头文字不该与代码正文等重。 */",
			"[data-code-block-banner] [class*=\"_language_\"],",
			"[data-code-block-banner] [class*=\"_title_\"] {",
			"  font-size: calc(var(--sgt-content-size, 14px) * " + BANNER_RATIO + ") !important;",
			"  line-height: calc(var(--sgt-content-size, 14px) * " + BANNER_LINE_RATIO + ") !important;",
			"}",
			"html, body {",
			"  -webkit-font-smoothing: antialiased !important;",
			"  -moz-osx-font-smoothing: grayscale !important;",
			"  font-optical-sizing: auto !important;",
			"  /* 0.3px 伪加粗：补仿宋小字号笔画密度（Chatbox 同款） */",
			"  text-shadow: 0 0 0.3px currentColor !important;",
			"}",
			"/* 超长 markdown 表格（≥4列，全局类名 md-table-wide，挂在滚动容器上）：放弃横向滚动，强制压缩。",
			"   背景：官方 breakout 把容器撑到整个 transcript 宽度（100cqw, max-width:none），滚动条在 Firefox 下",
			"   走 scrollbar-width: thin + 暗色 thumb（#33406a），视觉隐形；实测无论 auto/scroll 都看不到条。",
			"   方案：容器宽度收进消息列并留 16px 呼吸（比 data-chat-flow 窄一点点），table width:100% 覆盖官方",
			"   max-content，table-layout:auto 让列宽按内容量比例分配，单元格 white-space:normal +",
			"   overflow-wrap:anywhere 强制断行——任何内容都物理上不溢出，也就不需要滚动条。 */",
			".md-table-wide {",
			"  box-sizing: border-box !important;",
			"  width: calc(100% - 16px) !important;",
			"  max-width: calc(100% - 16px) !important;",
			"  margin-left: 0 !important;",
			"  padding-left: 0 !important;",
			"  overflow-x: hidden !important;",
			"}",
			".md-table-wide table {",
			"  width: 100% !important;",
			"  max-width: 100% !important;",
			"  table-layout: auto !important;",
			"}",
			".md-table-wide th,",
			".md-table-wide td {",
			"  white-space: normal !important;",
			"  overflow-wrap: anywhere !important;",
			"}",
			"/* 暗色皮肤（furina/navia）下表格分割线对比度不足：",
			"   furina 皮肤重映射 --dsw-alias-border-l2: #2c3a7338 / --dsw-alias-border-l3: #2c3a7352",
			"   （深蓝+低透明度，暗底上几乎不可见）；navia 未重映射、官方默认值在暗底上同样偏暗。",
			"   官方表格边框：th 用 border-l3、td 用 border-l2（MarkdownText.module.css）。",
			"   这里按消息行范围（data-dsh-part=message-row，全局属性锚点，不受 CSS Module 哈希影响）",
			"   直接覆盖为半透明白：th 稍亮（表头层级）、td 稍暗；仅限这两个暗色皮肤，亮色皮肤不受影响。 */",
			"html[data-dsh-skin=\"furina\"] [data-dsh-part=\"message-row\"] table th,",
			"html[data-dsh-skin=\"navia\"] [data-dsh-part=\"message-row\"] table th {",
			"  border-bottom-color: rgb(255 255 255 / 0.35) !important;",
			"}",
			"html[data-dsh-skin=\"furina\"] [data-dsh-part=\"message-row\"] table td,",
			"html[data-dsh-skin=\"navia\"] [data-dsh-part=\"message-row\"] table td {",
			"  border-bottom-color: rgb(255 255 255 / 0.22) !important;",
			"}",
			"/* 会话标题集群居中（crumbs 居中 + headerActions 绝对左贴）—— 【2026-09-27 撤销】。",
			"   历史：本特性自 0.1.5 起存在；2026-09-26 随 0.1.7 从 data-dsh-responsive-part=session-title-cluster",
			"   换锚到 [data-slot=\"conversation.session.header\"] [class$=\"_titleCluster\"]（见 920523c）。",
			"   撤销原因：0.1.7 的 header 内新增「后台任务运行中」指示器后，居中的标题与绝对定位左贴的",
			"   headerActions（preset 标签 + 任务指示器）挤在同一行互相打架，观感反不如官方默认布局。",
			"   处理：两条规则整体删除，回归 ConversationRoot.module.css 默认 —— 官方 .titleCluster 本就",
			"   display:flex + align-items:center，补丁那两条声明冗余；position:relative 只为托住绝对子。",
			"   如需回滚：git show 920523c -- profiles/web/packages/dsh-sandrone-ui-patches/lib/client.js。 */",
			"/* crumb 限宽放开：官方 .crumb 有 max-width:220px + overflow:hidden + text-overflow:ellipsis",
			"   （ConversationRoot.module.css），超长标题（>220px）被截断成省略号。",
			"   放开限宽 + 允许换行，让标题完整显示；仍保留 padding/border-radius 观感。",
			"   crumbs 容器官方 overflow:hidden + nowrap——换行由 crumb 自身承担。",
			"   ⚠ 0.1.7 当前 crumb 由 <button disabled> 改成 <span>（darwin 拖拽行）：旧 nav button",
			"   结构选择器会漏掉当前 crumb；改用类名匹配并排除 Seg/Sep 包装。 */",
			"[data-slot=\"conversation.session.header\"] [class*=\"_crumb\"]:not([class*=\"_crumbSeg\"]):not([class*=\"_crumbSep\"]) {",
			"  max-width: none !important;",
			"  overflow: visible !important;",
			"  text-overflow: clip !important;",
			"  white-space: normal !important;",
			"  word-break: break-all !important;",
			"}"
		].join("\n");

		var tagId = "dsh-sandrone-ui-patches/ui.css";
		function injectFontCss() {
			if (typeof document === "undefined") return;
			if (document.querySelector("style[data-plugin-css=" + JSON.stringify(tagId) + "]") !== null) return;
			var tag = document.createElement("style");
			tag.dataset.plugin = "dsh-sandrone-ui-patches";
			tag.dataset.pluginCss = tagId;
			tag.textContent = FONT_CSS;
			document.head.appendChild(tag);
		}

		// cordis plugin shape: the loader calls apply() on the entry's exports.
		exports.apply = injectFontCss;
		// immediate injection (idempotent) — runs at materialization, before apply.
		injectFontCss();

		return module.exports;
	}
});
