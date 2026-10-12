# 相关研究与实践

> **检索日期**：2026-10-07
> **检索源**：arXiv API（按 ID 精确核对 + 字段前缀检索）、Crossref REST、公开网页（厂商官方文档）
> **引用约定**：文末参考文献按编号 `[n]` 引用。每条论断后标注引用；**没有引用支撑的内容一律显式标注为「经验之谈」或「未找到研究支撑」**，不混入研究结论里。
> **可获取性**：本综述优先选取有 arXiv 预印本的工作；用户无机构订阅（ACM DL / IEEE Xplore / Springer 不可用）。文中个别 IEEE / USENIX 收录论文**同时有 arXiv 预印本**，已在参考文献中给出 arXiv 链接。未发现「仅有付费版且无预印本」的关键论文（若后续发现会在对应处标注 `⚠️[付费墙]`）。
> **检索受限说明**：`platform.claude.com`（Anthropic 平台文档）在本网络返回区域不可用，`developers.openai.com` / `platform.openai.com` 返回 403，`raw.githubusercontent.com` 连接被重置。因此第 6 节的厂商侧材料只覆盖到 Anthropic 工程博客、Google Cloud 官方文档、OpenAI agents 指南 PDF 三处可访问来源。

---

## 1. System Prompt 到底有多大作用？——量化证据

**结论：作用真实且可测量，但「大」的方式与直觉不同——它对格式/风格的影响远大于对客观任务正确率的影响，而且极易被无关变量淹没。**

1. **加 persona（「你是一位…」）对客观任务没有增益，甚至可能有害。** Zheng 等（EMNLP 2024 Findings）系统评测了 162 个角色（覆盖 6 类人际关系 × 8 个专业领域），结论是 system prompt 中的人设**并不提升** LLM 在客观任务上的表现 [1]。这与厂商文档的推荐形成直接张力——Google Cloud 官方文档把「定义 persona 或角色」列为 system instructions 的第一条用例，并用一个「大学写作助教 vs 小学写作助教」的对照示例来证明其有效 [95]（该示例是**单例演示，不是对照实验**，属经验之谈）。

2. **prompt 格式的「表面差异」能造成灾难级波动。** Sclar 等（ICLR 2024）在 few-shot 设置下只改动**语义等价**的格式，用 LLaMA-2-13B 测出**最多 76 个准确率点**的差距；增大模型、增加 few-shot 样例数、做指令微调都不能消除这种敏感性 [2]。更关键的是，**格式优劣在不同模型之间只有弱相关**，这直接质疑了「在单一格式上比较不同模型」的方法学效度 [2]。同理，Lu 等（ACL 2022）发现 few-shot 样例的**排列顺序**可以决定性能落在「接近 SOTA」还是「接近随机猜」[3]。
   → 对实践的含义：**A/B 一个 prompt 的收益，必须与「同一 prompt 换一种等价写法」的噪声幅度对比才有意义。**

3. **system prompt 是可以被「优化」的，且优化结果可迁移。** SPRIG（ICLR 2026）用基于编辑的遗传算法构造 system prompt，在 47 类任务上评测，发现**单个优化后的 system prompt 能达到与逐任务优化 prompt 相当的水平**；system 级与 task 级优化可叠加；优化后的 system prompt 还能跨模型家族、参数规模、语言迁移 [6]。Choi 等（NeurIPS 2025）进一步用元学习让 system prompt 一次优化、跨任务复用 [7]。
   → 这是「system prompt 值得被当作一个可优化对象来投入」的最强量化依据。

4. **真实世界的 system prompt 遵循度并不稳。** Mu 等（2025）用从 OpenAI GPT Store 与 HuggingFace HuggingChat 采集的真实 prompt 构建评测集，发现模型**经常忘记相关 guardrail，或无法在 system 与 user 的要求冲突时做出取舍**；用贴近真实的微调数据 + 推理时干预（classifier-free guidance）可显著改善 [8]。

5. **工业界的 system prompt 长什么样：以运维内容为主。** Patsakis 等（ICTAI 2026）分析 62 家厂商的 407 份泄露/重建/公开 system prompt，发现 **29 组近重复（共 66 个文件）**，且语料由**操作性内容而非伦理宣示**主导 [9]。
   → 推论（非文献结论）：这个领域的 prompt 设计正在快速同质化，「抄一份改改」是常态，差异化价值不在体量而在约束的准确性与可测性。

6. **机制层面的理解刚刚开始。** Usama 与 Chang（2026）在 17 个指令微调模型、8 个架构家族、1.5B–72B 参数量、5 类共 20 条 system prompt 上，用 CKA 比较逐层表征差异 [10]。同期还有工作探索**能否用单个学习到的 token 承载长 system prompt 的行为效应**（Behavior-Equivalent Token）[11]，这本身就是「长 system prompt 的效果有多少是冗余的」这一问题被正式提出的信号；而长 system prompt 的重复处理本身是真实的推理成本（RelayAttention，ACL 2024）[12]。

---

## 2. 约束机制的类型学：各自的能力边界

把「约束 LLM 行为」的手段排成一条**从软到硬**的谱系，各段的边界如下。

| 层级 | 手段 | 机制 | 已知边界 |
|---|---|---|---|
| 最软 | **System prompt / 自然语言规则** | 上下文条件化，无参数变化 | 遵循度不稳、易被冲突指令覆盖 [8][15]；可优化但收益易被格式噪声掩盖 [2][6] |
| ↓ | **Few-shot 示例** | 上下文学习 | 顺序敏感（近 SOTA ↔ 随机猜）[3]；**标签正确性几乎不重要**，重要的是标签空间与输入分布 [4]；几百到上千例的 many-shot 仍持续带来增益 [5] |
| ↓ | **结构化输出（提示层）** | 要求模型自己吐 JSON/XML | **显著降低推理能力，且格式越严退化越大** [30] |
| ↓ | **Constrained decoding（解码层硬约束）** | 在 token 采样时屏蔽非法 token | 能**保证**语法合法（Outlines 的 FSM 索引 [57]；语法约束解码 [58]），但**若词表对齐不当会实质损害准确率** [59]；逐 token 贪婪约束会使输出分布偏离目标分布（grammar-aligned decoding 的动机）[60] |
| ↓ | **工具调用约束** | 用 schema 把模型行为限制在可执行动作上 | 见第 5 节；副作用是**工具过用**（不需要也调）[71][72][73] |
| ↓ | **Guardrails / 内容过滤** | 模型之外的前后置检查器 | NeMo Guardrails 的「可编程护栏」[49]、Llama Guard 的输入输出分类 [50]；**代价明确**：安全与可用性存在此消彼长，且存在误报/漏报权衡 [51]；体系化评测见 SoK [52]，代码生成场景见 CS-Guard [53] |
| ↓ | **对齐训练（RLHF / DPO / Constitutional AI）** | 改权重 | 这是**唯一能改「默认倾向」**的层级：InstructGPT 证明可用人类反馈对齐意图 [61]；DPO 提供无需显式奖励模型的等价目标 [62]；Constitutional AI 用一份「原则清单」替代逐条人类标注 [63]；指令微调（FLAN）本身就能提升零样本泛化 [64]；对齐所需数据量可以极小（LIMA：1000 条精选样本、不做 RLHF）[65] |
| 最硬 | **架构 / 表征层** | 给不同来源的指令打上结构性标记 | Instructional Segment Embedding 把指令层级写进表示 [21]；更强执行的中间表征增强 [见第 4 节] |

**这张表最重要的一条信息**：**「提示层的约束」和「训练层/解码层的约束」不是程度差别，而是种类差别。** 提示层约束是**概率性的、可被覆盖的**；解码层约束是**保证性的、但只保证形式不保证质量**；训练层约束改的是**默认倾向**。把三者混为一谈（例如指望一句 system prompt 达到 schema 强制的效果）是设计上最常见的范畴错误。

---

## 3. 负面结果的证据：哪些约束被证明无效甚至有害

### 3.1 无外部反馈的自我纠错：无效

- **核心负面结果**：Huang 等（ICLR 2024）的标题即结论——**LLM 目前还不能自我纠正推理**；在没有外部反馈的「内在自我纠错」（intrinsic self-correction）设定下，模型不仅无法改善推理，性能反而经常**下降** [23]。
- **系统性综述**：Kamoi 等（TACL 2024）对自我纠错文献做了批判性综述，指出**分歧主要来自实验设计的缺陷**——许多报告成功的框架实际上依赖了**不可靠的自评**或**引入了 oracle 标签/答案信息**；在排除这些信息后，「无外部反馈但有效」的证据站不住 [24]。
- **独立复核**：Liu 等（2024）进一步论证自我纠错**不是语言模型的先天能力**，并专门考察内在知识与外部反馈的交互 [25]。
- **现象刻画**：Tsui（COLM 2026）提出 **self-correction blind spot**：模型在「能否发现错误」与「能否改正错误」之间存在系统性缺口（即失败未必是能力不足，也可能是**不会去检查**），并给出缓解方法 [26]。Li（2025）报告类似的「准确率—纠错悖论」，并提出错误深度假设 [93]。
- **对照组（说明边界在哪）**：
  - **有外部反馈的反思是有效的**：Reflexion 依靠环境给出的任务反馈信号（如单元测试结果）做语言化反思，在多个任务上取得实质提升 [28]。
  - **把「验证」结构化成可核查条件也有效**：Wu 等（EMNLP 2024）用关键条件验证显著改善了内在自纠的效果 [29]。
  - **Self-Refine 报告的正面结果** [27] 与 [23][24] 不矛盾：它的收益主要出现在**没有明确正确答案**的任务（风格、可读性）上；在**有客观判据的推理任务**上，无外部反馈的自我精炼正是 [23][24] 的打击面。
  → **可操作判据**：自我纠错只在两种情形下值得开启——(a) 存在**外部可判定的反馈信号**（测试、编译、verifier）；(b) 目标函数是**主观质量标准**而非客观正确性。

### 3.2 过度约束：格式约束与指令密度

- **格式约束伤推理**：Tam 等（2024）在多种常见任务上对比「自由生成」与「受结构化格式约束（JSON/XML）」，观察到 **推理能力显著下降**，并且**格式约束越严格，推理任务上的退化越大** [30]。
- **指令密度伤遵循率**：Jaroslawicz 等（2025）发布 IFScale（500 条关键词包含指令的商务报告写作基准），评测 7 家厂商的 20 个 SOTA 模型，发现**即使在最强的前沿模型上，500 条指令密度下的准确率也只有 68%**；并识别出三种退化模式（与模型规模和推理能力相关）以及**对靠前指令的系统性偏置** [31]。
- **约束组合的代价**：ComplexBench（NeurIPS 2024 D&B）专门评测「多个约束组合」的指令遵循 [32]；FollowBench（ACL 2024）做多级细粒度约束评测 [33]；Multi-IF 覆盖多轮 + 多语言 [34]；IFEval 提供可验证指令的自动化评测口径 [35]；Han 等（EMNLP 2025 Findings）专门研究**多轮中相互纠缠甚至冲突**的指令 [36]。
  → 叠加起来：**约束不是免费的，且成本随约束数量非线性上升，并偏向最先出现的约束。**

### 3.3 长 prompt 的注意力稀释与位置效应

- **经典结论**：Liu 等（TACL 2023）发现性能随关键信息位置变化剧烈，呈 **U 形**——放在开头或结尾最好，**放在中间显著变差**（lost in the middle）[43]。
- **机制与修复**：Hsieh 等（ACL Findings 2024）把该现象归因于 LLM 内在的 **U 形注意力偏置**（首尾 token 获得更高注意力），并提出校准方法 [44]。
- **长上下文被高估**：NoLiMa（ICML 2025）指出传统 needle-in-a-haystack 测试可被字面匹配「作弊」，在避免字面匹配的设定下，模型的有效上下文**远短于标称长度** [45]。
- **多轮同样会丢**：Laban 等（2025）证明 LLM 在多轮对话中会「迷路」，**即使信息全程可见**，性能也显著下降 [46]。
- **顺序即信息**：Chen 等（ICML 2024）发现前提（premise）顺序改变会让推理性能剧烈波动，最佳顺序是**与中间推理步骤所需的上下文顺序一致**的顺序 [47]；多跳 QA 中多个关键信息分散时，「中间遗失」的效应会放大 [48]。
  → 对**长 system prompt** 的直接含义（推论，非单篇文献结论）：把关键约束放在 prompt **首尾**、避免让真正的硬约束落在中段、不要指望「都在上下文里」等于「都用得上」。

### 3.4 安全对齐的副作用：over-refusal 与 alignment tax

- **过度拒答**：OR-Bench（ICML 2025）用自动生成的大规模数据集量化「安全对齐的副作用——拒绝无害请求」[37]；XSTest（NAACL 2024）用「与不安全提示措辞相似但本身安全」的用例揭示同一问题，并指出 helpfulness 与 harmlessness 的张力 [38]。
- **对齐很「浅」**：Qi 等（2024）指出当前安全对齐主要作用在**最初几个输出 token 的分布**上（shallow safety alignment），因此简单攻击甚至有监督微调就能越狱 [39]。
- **对齐税**：Lin 等（EMNLP 2024）在 OpenLLaMA-3B 上实测到**明显的 alignment tax**——RLHF 对齐会导致预训练能力的遗忘 [40]。
- **多样性与泛化**：Kirk 等（2024）分解 SFT / 奖励建模 / RLHF 各阶段，结论是 **RLHF 改善了分布外泛化，但降低了输出多样性** [41]；Gao 等（2022）给出奖励过优化的 scaling law（Goodhart 的定量版本）[42]。
- **对创作类场景的直接影响**：多篇创意写作工作把「后训练（尤其 RL）降低输出多样性」当成首要待解问题 [89][90]，并有公开的评估基准 [91][92]。这解释了为什么「硬科幻 / 奇幻设定」这种需要**受约束但高多样性**的场景，难以靠对齐手段解决，只能靠**上下文层的约束设计**。

---

## 4. 指令冲突与优先级：有研究，且结论对实践很不友好

1. **问题被正式提出并形式化**：Wallace 等（2024）提出 **instruction hierarchy**——明确定义不同优先级指令冲突时模型应如何行为（system > user > third-party/tool 输出），并给出训练方法 [13]。这是本方向被引用最多的框架性工作，动机是 prompt injection 与 jailbreak。

2. **领域已有成套评测**：IHEval（NAACL 2025）建立了 system → user → 对话历史 → tool 输出四级优先序的评测 [14]；后续出现更细的 IH-Benchmark [18]、PRIME（不可兼容指令下的 prompt 消解）[19]、以及面向 agent 的 **many-tier 层级**（system / user / tool 输出 / **其他 agent**）[20]。
   → 值得注意的是：**「多 agent 互发指令」已经被纳入层级模型**，这正是 DSH 这类框架的现实形态。

3. **最重要的负面结果：system/user 的分离本身建立不起可靠的层级。** Geng 等（AAAI-26）评测 6 个 SOTA 模型，结论有三条 [15]：
   - 模型**无法一致地按优先级取舍**，**连简单的格式冲突都做不到**；
   - 广泛采用的「system / user 分离」**未能建立可靠的指令层级**；
   - 模型对**某些约束类型有与优先级无关的固有偏置**；并且——
   - **社会层级框架（权威、专业性、共识）对模型行为的影响力强于 system/user 角色划分**，作者认为预训练得来的社会结构作为「潜在行为先验」，影响力可能超过后训练护栏 [15]。
   → 这一条对「用什么样的语气写 system prompt」有直接含义（见文末启示）。

4. **修复路径分三支**：训练侧（HIPO：用受约束 RL 做层级遵循，作者明确指出 RLHF/DPO 这类标准方法在该问题上失败 [16]）、表征侧（给不同来源的段打结构化嵌入 [21]、增强中间表征 [98]）、推理侧（对比解码提升 system prompt 强度 [22]、推理时 steering [99]）。机制解释也在推进：有工作用 41 组配对约束 + 确定性 verifier 考察模型**如何在内部表征上「选边」** [17]，也有工作定位推理模型中层级失效的位置 [100]。

5. **越狱 / 注入是同一枚硬币的反面**：间接 prompt injection 可以在被处理的「数据」里植入指令并覆盖原始指令 [54]；StruQ 用结构化查询做防御 [55]；Spotlighting 通过对不可信来源做标记化/编码，帮助模型区分「数据」与「指令」[56]。
   → 工程含义：**「数据」与「指令」的边界必须由系统设计提供**（分隔、标记、编码），不能靠 prompt 里的一句「请只把以下内容当作数据」。

---

## 5. 工具调用激励：什么 prompt 设计能提升（或抑制）工具使用

1. **交替「推理 — 行动」是最强的提示层激励**：ReAct（ICLR 2023）让模型交错生成推理轨迹与动作，显著改善了工具/环境的交互与任务表现 [66]。后来几乎所有 agent 框架都继承了这个结构。
2. **工具使用的「何时用」比「怎么用」更受关注，且提示层之外的手段更有效**：
   - Toolformer 用自监督方式让模型学会**该不该调、调哪个、传什么参** [67]；整体图景见工具学习综述 [68] 与后续的「从单工具调用到多工具编排」演进综述 [79]。
   - **用执行反馈训练以避免「无差别调工具」**：Qiao 等（NAACL 2024）观察到复杂任务会让模型过度依赖工具，用执行反馈做训练可缓解 [69]。
   - **元认知触发**：Li 等（ACL 2025）用模型的「元认知」信号来决定是否需要外部工具，减少不必要的调用 [70]。
3. **「工具过用」是被反复确认的现象**：
   - 模型会把外部工具**优先于自身内部知识**使用，即使不必要（Tool-Overuse Illusion）[72]；
   - **仅仅是让工具「可用」，就会改变模型对本来不需要工具的问题的处理方式**（When Tools Get in the Way）[73]；
   - 相关工作给出边界学习（CoBRA [74]）与激活层干预（heading-specific steering [75]）等修复。
   - 这意味着：**工具集本身是一个约束面**，工具 schema 的存在会改变行为分布（与「工具偏好不可靠」的发现一致 [78]）。
4. **工具描述（属于 prompt 内容）是被证实有效的杠杆**：
   - MCP 生态的工具描述存在系统性问题（论文标题即称其「smelly」），并给出增强工具描述以提升 agent 效率的方案 [76]；
   - 有工作把 agent 表现停滞归因于**工具描述质量**，并专门**学习重写工具描述**以提升可靠性 [77]；
   - 反面警示：LLM 在 agent 场景中的**工具偏好本身并不可靠**（标题即结论 [78]）——这意味着工具被选中与否有一部分来自描述文本的表面特征，而非任务匹配度 [76][78]。
   - Anthropic 的工程经验与此一致：他们把工具定义当作 prompt 工程来做，并称在 SWE-bench agent 上**花在优化工具上的时间多于优化整体 prompt** [94]。
5. **「把计算外置」有直接且强的文献支撑**：
   - **PAL**（Program-aided Language Models）把求解步骤交给程序执行、只让模型负责理解与分解，在算术/符号推理上优于纯 CoT [81]；
   - **PoT**（Program of Thoughts，TMLR 2023）明确主张**把计算从推理中剥离**，模型输出程序、由解释器计算 [82]；
   - **Faith and Fate** 从组合性上限角度解释了纯 CoT 在多步计算上的固有弱点 [83]。
   - 对 code-capable 模型，还有「用脚本替代刚性 JSON 调用」的 programmatic tool calling 趋势 [80]。
   → **「LLM 不擅长多步算术、应把计算外置给确定性工具」是本综述中证据最扎实的实践主张之一。**（唯一需要注意的边界见 [71][72]：外置要配合「何时该外置」的判据，否则会退化成工具过用。）

---

## 6. 工业界的公开经验：哪些被研究验证过，哪些只是经验之谈

> **本节覆盖范围（本轮已补齐 OpenAI 官方指南）**：OpenAI prompt engineering 官方指南 [101]、OpenAI GPT-5 / 5.1 / 5.2 prompting guide [102][103][104]、OpenAI *A practical guide to building agents* [96]、Google Cloud prompt 设计文档六页 [95][105][106]、Anthropic 工程博客 [94]。
>
> **一条必须写在前面的来源诚信声明**：OpenAI 的 *平台文档站点*（`platform.openai.com`、`developers.openai.com`）在本网络**仍然不可达**——挂代理后返回 **HTTP 403**（59 字节边缘拦截页，形如 `Forbidden / hkg1::sbsgh-…`，说明是**出口 IP 被地理/机房级拦截**，不是资源不存在；代理出口 IP 为香港 `188.253.112.120`）。因此 [101] 的内容取自 **OpenAI 官方仓库 `openai/openai-cookbook` 内的文档快照** `examples/data/oai_docs/prompt-engineering.txt`，该文件的**最后一次提交日期是 2024-07-25**，且正文自述面向 GPT-4o。**这是一份冻结在 2024 年中的快照，可能滞后于当前线上页面**——引用时请带这个日期。[102][103][104] 则是刻意补上的**更新世代**官方指南，正是用来检验 [101] 是否过期的。`platform.claude.com`（Anthropic 平台文档）按你的要求本轮**未尝试**。
>
> **证据分级图例**：✅ 有研究支撑（附文献编号）｜⚠️ 经验之谈（厂商实践总结，本文未找到受控实验）｜❌ 与研究冲突（附冲突文献）。
>
> **本节的判定标准是「这条建议我该不该听」，不是「厂商说了什么」。** 第三列给出等级，第四列给出处置。

### 6.1 OpenAI 官方指南逐条判定

来源：prompt engineering 官方指南 [101]（2024-07-25 快照），六条策略逐条拆解。

| 厂商说法 | 来源 | 判定 | 依据与处置建议 |
|---|---|---|---|
| **「让模型扮演某个 persona」**（Write clear instructions 下的 tactic） | [101] §Ask the model to adopt a persona | ❌ **与研究冲突** | [1] 的系统评测：**162 个角色**（覆盖 6 类人际关系 × 8 个专业领域）、**4 个模型家族**、**2,410 个事实性问题**，结论是「与不加 persona 的对照组相比，加 persona **不提升**性能」。注意 [101] 原始示例本身就是风格导向的（「每段至少一个玩笑」），而 [1] 测的是**客观正确率**。（[1] 另发现「为每道题挑选最佳 persona」能提升——但那是**逐题查表的事后 oracle**，不是可部署策略。）→ **仅当你要调风格时可用；不要指望 persona 提升正确率。** 这是本节最强的一条 ❌，因为 OpenAI 与 Google 两家都把它列为正式 tactic |
| 在 query 里**给足细节与上下文**（否则模型靠猜） | [101] §Include details in your query | ⚠️ **经验之谈**（方向有间接支持） | 与「避免歧义、显式化」（Google [105] 的健康检查清单）同向，但「细节多寡 ↔ 正确率」没有受控实验被本文找到。反向证据是 [31]：**指令越多，遵循率越低**。→ **要听，但前提是「细节」用于消歧，不是用于堆量**；两者混为一谈会让你把 prompt 越写越长而变差 |
| **用分隔符标记输入的不同部分** | [101] §Use delimiters | ✅ **有支撑** | 格式化/分隔方式强烈影响行为 [2]；机制性的支撑来自 spotlighting [56] 与结构化查询 [55]。→ **听。** 且这不是风格偏好，是**抵御间接注入的机制** [54] |
| **显式写出完成任务的步骤** | [101] §Specify the steps required | ⚠️ **经验之谈** | 与「拆解任务」同族（见 6.2 的 break-down）；受控层面只查到「约束组合有代价」[32] 与「多任务单轮处理会变差」[31]。→ **听，但要按 [31] 的代价模型控制条数**，不要无限展开步骤 |
| **给示例（few-shot）** | [101] §Provide examples | ✅ **有支撑** | [4] 是本条最精准的支撑：**演示的标签往往不重要，重要的是输入分布与格式**——即示例真正在传递的是格式与任务分布。另有 [5]（many-shot 的收益与边界）与 [3]（**示例顺序敏感**，同类示例的排列会显著改变结果）。→ **听，但必须固定并记录示例顺序**，否则你的评测波动会被误读为 prompt 改动效果 |
| **指定输出长度**（并自承「指定词数不精确，段落/条目数更可靠」） | [101] §Specify the desired length | ⚠️ **经验之谈**（但自承的局限是诚实的） | 长度类硬约束的遵循度已被 IFEval [35] 量化，属「可测但有限」。→ **听它的后半句**：用段落数/条目数，别用词数。厂商在此**主动标注了不确定性**，这条反而可以照用 |
| **提供参考文本以减少编造** | [101] §Provide reference text | ⚠️ **经验之谈** | 方向上与「外置证据」一致，但论文级最相关的是引用而非「编造率下降幅度」（见下一行）。→ **听，但把它当工程手段而非已验证的降编造率手段** |
| **要求模型给出引用，且引用可用字符串匹配程序化校验** | [101] §Answer with citations | ✅ **部分支撑** | ALCE [109] 正是为「生成带引用的文本并校验其可验证性」建立的基准与方法，证明该路线可行且可自动评估。→ **强烈建议听**：这是把「幻觉」变成「可自动检测的失败」的少数可操作手段，对你这种需要溯源的项目尤其对口 |
| **拆解复杂任务**（意图分类、状态机、长对话摘要） | [101] §Split complex tasks | ✅ **有支撑** | 多轮与长上下文退化 [46]、纠缠多轮指令 [36]、约束组合代价 [32] 共同支持「拆小」。其中「长对话要摘要」一条与 [46] 直接同向。→ **听。** 这是 [101] 里证据最扎实的一条策略 |
| 「当状态变化时让模型输出特殊字符串，把系统做成状态机」 | [101] §intent classification | ⚠️ **经验之谈**（但工程价值高） | 无对应的受控实验；不过与结构化输出可校验的整体方向一致（[55][56] 的机制同族）。→ **听**——它的收益来自**可解析性**，不来自模型能力提升 |
| **给模型时间「思考」**（先自己解题再评判、inner monologue） | [101] §Give the model time to "think" | ✅ **有支撑**（但有**版本边界**，见 6.4） | CoT 提升复杂推理是经典结论 [107]；[101] 那个「学生解题」示例（模型漏看 10x vs 100x）正是 CoT 的教科书案例。→ **听，但先看 6.4 的版本冲突**：对 reasoning 模型，这条已被厂商自己部分撤回 |
| **inner monologue：把要隐藏的推理包进结构化标记再由外层解析掉** | [101] §inner monologue | ⚠️ **经验之谈** | 无受控实验。注意其隐含前提是「模型展示的推理 = 模型实际的推理」，而该前提在研究中并不总是成立（[24] 对自校正与推理可靠性的综述给出的是**谨慎**结论）。→ **可用作工程手段，但不要基于「展示的推理」去做安全或审计判断** |
| **「问模型是否漏掉了什么」**（followup 追一轮） | [101] §Ask the model if it missed anything | ❌ **与研究冲突** | 这是**无外部反馈的内在自校正**。[23] 证明 LLM 在推理任务上「还不能自我纠错」（无外部信号时自校正常常**降低**准确率）；[24] 的批判性综述划定了自校正仅有在**有可靠外部反馈**时才成立的边界；[26] 进一步指出系统性的**自校正盲区**。→ **不要把这条当成「让模型自查」的授权**。若真要用，只用于**穷尽性/召回**（「还有没有漏掉的片段」），**不要**用于正确性（「我算得对吗」）——那正是 [23] 说会变差的地方 |
| **用外部工具**：embeddings 检索、**代码执行做精确计算**、函数调用 | [101] §Use external tools | ✅ **强支撑** | 这三条整条命中本综述证据最扎实的实践主张。指南原文「**语言模型不可被依赖来独立完成算术或长计算**」与 PAL [81]、PoT [82]、Faith and Fate [83] 完全同向；函数调用侧另有工具描述质量的实证 [76][77]。→ **照单全收。** 这是 OpenAI 官方文档里**与你「计算外置铁律」逐字同向**的一条 |
| 「**执行模型生成的代码本身不安全**，必须沙箱化」 | [101] §Use code execution 的 WARNING | ✅ **有支撑** | 代码生成的安全面已被基准化评测（CS-Guard [53]）；该警告属工程常识且有评测支撑。→ **听**，且这条**与「鼓励用代码外置计算」不矛盾**——外置 + 沙箱才是完整方案 |
| **系统性测试改动**（eval / 金标准对照） | [101] §Test changes systematically | ✅ **有支撑** | system prompt 可被优化且可迁移 [6][7]；但评估本身必须抗格式噪声 [2][3]，否则你测的是措辞噪声。→ **听，并且把「评估集要多样」当成硬要求**——厂商原文「在小样本上变好、在代表性集合上变差」正是 [2][3] 的实证结论 |
| eval 样本量对照表（检测 30%/10%/3%/1% 差异分别约需 10/100/1000/10000 例） | [101] §Test changes systematically 表 | ✅ **可核查的定量声明** | 这是官方文档里罕见的**可验证数字**，其量级与标准统计功效计算一致。→ **直接拿来用**：它给你一个「我的 A/B 对比到底有没有统计意义」的门槛，正是本综述反复强调的「别把噪声读成改进」 |

### 6.2 Google Cloud 官方指南逐条判定

来源：`Use system instructions` [95]、`Introduction to system instructions` [106]、`Prompt design strategies` + Prompt health checklist [105]，以及 `clear-instructions` / `few-shot-examples` / `explain-reasoning` / `break-down-prompts` / `structure-prompts` 五个子页（均属 [105] 所在文档集，本轮全部重新抓取并复核）。

| 厂商说法 | 来源 | 判定 | 依据与处置建议 |
|---|---|---|---|
| **用 system instructions 定义 persona / 角色** | [95][105][106] | ❌ **与研究冲突** | 同 6.1 首行 [1]。→ **且注意 Google 的举证方式是「单次生成对比」**（大学 vs 小学两个角色的输出并排展示），**不是对照实验**——这是把演示当证据的典型样本。[105] 的健康检查清单更进一步要求「若要模型扮演角色，**必须**在 system instructions 里定义该角色」，把一个未被证实的做法升级成了**规范**。→ **不予采信为正确率手段** |
| **用 system instructions 定义输出格式 / 风格 / 语气 / 目标规则** | [95][105][106] | ✅ **部分支撑** | 格式与风格约束确实强烈影响行为 [2]；但要附带 [30] 的警告：**过度格式约束会损害推理质量**。→ **听格式，警惕过度**：格式用来服务下游解析，不要用来「让答案更好」 |
| system instructions **作用于整个请求、跨多轮持续生效** | [95][106] | ⚠️ **名义成立，实效会衰减** | 作用域机制属实，但多轮中遵从会退化 [46]，且系统提示的持久性有专门的鲁棒性研究 [8]。GPT-5 指南更直接承认「Markdown 类指令在长对话中会被逐渐忽略」（见 6.3）。→ **不要依赖「一次写进 system prompt 就永久生效」**，需要周期性重申（有厂商实操依据，见 6.3） |
| **「system instructions 不能完全阻止越狱或泄漏」**（官方明确警告） | [95][106] | ✅ **有支撑** | instruction hierarchy 在实际模型上会失败（Control Illusion [15]）；越狱与注入的防御需体系化而非靠措辞 [52]。→ **听，且这条是厂商难得的诚实**：它等于承认 system prompt 不是安全边界 |
| system instructions **适合放「终端用户看不到也改不了」的信息** | [106] | ⚠️ **经验之谈** | 无受控实验。且与上一条并列时**逻辑上紧张**：既然它不能防注入，那把它当「用户看不到的受信通道」就有前提风险（间接注入 [54] 正是从数据面打进来的）。→ **听一半**：可以放配置，**不要放密钥或权限凭据** |
| 用 system instructions **定义输出语言**（非英语 prompt 时尤其） | [95] | ⚠️ **经验之谈** | 交叉语言下的指令层级遵从刚有研究起步 [97]，但「强制指定输出语言能稳定生效」没有受控实验被本文找到。→ **可听**，本综述的「中文 prompt 约束效应」缺口（见检索缺口声明第 2 条）与此直接相关，建议自测 |
| **给清晰具体的指令**（说做什么、给约束与格式） | [105] `clear-instructions` | ⚠️ **经验之谈**（方向合理） | 同上，与 [31] 的密度代价并列考虑。→ **听，但用 [31] 约束条数** |
| **用 few-shot 示例**；**「示例必须配清晰指令，否则模型会学到非预期的模式」** | [105] `few-shot-examples` | ✅ **有支撑** | 后半句是**教科书级的准确**：[4] 的核心发现正是「模型从演示中学到的常常是**输入分布与格式**，而非示范的标签」——这既是 few-shot 有效的机制，也正是「不配指令就会学歪」的原因。→ **听，且把「配清晰指令」当成必要条件** |
| **few-shot 要「具体且多样」**；**示例个数要实验，太多会过拟合** | [105] `few-shot-examples` | ✅ **有支撑** | 「多样」由 [4] 支持（决定作用的是输入分布）；「个数存在最优而非越多越好」由 [5] many-shot 的边界刻画支持；「顺序敏感」另见 [3]。→ **听**，并把「示例个数」列为你的**必测变量**——这里研究给的是「有最优值」，不是「越多越好」 |
| **示例格式要一致**；用 XML 类标记包裹示例 | [105] `few-shot-examples` | ✅ **有支撑** | 格式一致性 [2]；标记化同时服务注入防御 [55][56]。→ **听** |
| **「指令要解释推理步骤」/ think step-by-step 提升准确率** | [105] `explain-reasoning` | ✅ **有支撑**（有**版本边界**） | CoT [107]。→ **听，但对 reasoning 模型先看 6.4** |
| **「推理步骤要能解析出来，用 XML 或分隔符隔开」** | [105] `explain-reasoning` | ⚠️ **经验之谈**（有反向张力） | 解析需求真实，但把推理塞进严格结构化格式有代价 [30]。→ **用它做工程解析，但要自测 [30] 是否在你场景里吃掉推理质量** |
| **拆解复杂 prompt**（链式串行 / 并行聚合）：「更小的 prompt 提升可控性、可调试性与准确率」 | [105] `break-down-prompts` | ✅ **部分支撑** | 「拆小更好」由 [32][36][46] 支持；但「准确率提升」的幅度与条件没有直接受控实验。→ **听，主要图可控性与可调试性**，别把准确率提升当既定收益 |
| **结构上：顺序、标注、分隔符都会影响响应质量** | [105] `prompt-design-strategies` | ✅ **强支撑** | [2] 直接证明了**无关的表面特征（格式、顺序）会造成巨大性能波动**；[3] 证明少样本示例**顺序敏感**。→ **听，且这条在本综述里是被反复验证过的「格式即变量」** |
| 提供**情境/背景上下文** | [105] | ⚠️ **经验之谈** | 同 6.1 的「给足细节」。→ **听，按消歧目的使用** |
| **实验参数值**（temperature 等） | [105] | ✅ **有支撑**（本文未在 §6 展开） | 采样参数影响输出多样性与稳定性是同族结论 [41]。→ **听** |
| **prompt 迭代策略 / 测试驱动** | [105] `prompt-design-strategies`、`prompt-iteration` | ✅ **有支撑** | [6][7] 支持「prompt 可被系统化优化」。→ **听** |
| 健康检查清单：拼写、语法、标点、未定义术语、歧义、缺失关键信息 | [105] 清单 | ⚠️ **经验之谈**（低风险） | 无受控实验，但属零成本检查项，且「避免无度量定义的相对修饰语」与显式化方向一致。→ **可听**，不会有害 |
| **「避免冗余指令」**（同一指令换说法重复讲而不增信息） | [105] 清单 | ⚠️ **经验之谈**（**但与同页另一条自相矛盾**，见 6.4） | 与 [31] 的密度代价同向，故方向可信。→ **方向可听**，但请看 6.4 的内部矛盾——同一份官方文档把「末尾重申」列为推荐做法 |
| **「避免无关指令」**（删掉不影响核心任务的指令） | [105] 清单 | ✅ **有支撑** | 与 [31] 同向：指令越多遵循率越低。→ **听**，这是最省成本的一条 |
| **「一轮里塞太多任务会失败，要拆成多个 prompt」** | [105] 清单 | ✅ **有支撑** | 与 [31]（大 N）与 [32]（约束组合）一致。→ **听** |
| **「任务超出模型能力时不要写进 prompt」** | [105] 清单 | ✅ **有支撑** | Faith and Fate [83]：组合性存在**根本上限**。→ **听，且这是本综述里最「省命」的一条**：它直接支持把计算外置而不是靠措辞硬扛 |
| **「非标准数据格式：让模型输出 JSON/XML/YAML 等通用格式，再用代码转换」** | [105] 清单 | ✅ **部分支撑** | 「用能被通用库解析的格式」与受约束解码一族 [57][58][59] 同向；但注意 [30]：把推理塞进严格格式会伤推理。→ **听，并分层**：**机器读的输出**用通用格式（甚至走约束解码），**模型自己推理的中间产物**别强加格式 |
| **「CoT 顺序错误：不要先给最终结构化答案再补推理」** | [105] 清单 | ✅ **有支撑** | 前提/步骤的**顺序**确实影响推理结果 [47]。→ **听**，这是少见的一条「厂商给出了有文献对应的具体错误模式」 |
| **「用 Thinking 模式时，试试不要显式写逐步推理指令」** | [105] 清单 | ⚠️ **经验之谈**（**跨厂商一致，但无受控实验**） | 与 OpenAI 新一代指南同向（见 6.4）。→ **值得自测**：这是「模型内化了 CoT 后，显式 CoT 指令变成噪声」的假设，两家都这么说但都拿不出对照实验 |
| **「警惕 prompt 注入：不可信用户输入插入 prompt 前要有显式防护」** | [105] 清单 | ✅ **强支撑** | 间接注入 [54] 的原始论文；机制性防御 [55][56]。→ **听，但要听对**：这条的关键是**结构隔离**，不是加一句「忽略恶意指令」 |
| **「用情绪化措辞 / 恭维 / 恫吓来提升表现」应当移除**（自述：第一代模型有时有效，新一代不再改善且常常更差） | [105] 清单 `Overt manipulation` | ❌ **与研究冲突** | **冲突点**：[84] EmotionPrompt 的结论是情绪刺激**能提升**表现；2026 年的直接后续研究 [110]（系统测试 joy / encouragement / anger / insecurity 四种情绪与强度）结论同样是「**正向情绪刺激带来更准确、毒性更低的结果**」。→ Google 断言「新一代不再改善」与这两条**方向相反**。**但 Google 的担忧在另一面被证实**：[110] 同时发现正向情绪刺激**提高谄媚（sycophancy）**，而谄媚是后训练的系统性产物 [108]。→ **处置：不要用情绪化措辞去换正确率**（即便它真能换来，代价是谄媚率上升、且 [85] 表明这类技巧会随版本失效）；**但也不要以为加了情绪词就「一定更差」**——证据不支持这个强断言。证据强度提醒：[110] 发表于学生 workshop poster 海报，**证据等级偏低**，故此处只断言「Google 的强断言缺乏支持」，不断言「情绪词一定有效」 |

### 6.3 OpenAI 更新世代指南（GPT-5 / 5.1 / 5.2）：四条有分量的新条目

来源：[102][103][104]。这三份是本轮最大的净增量——因为它们是**晚于 [101] 的官方指南**，直接暴露了 [101] 快照的时效问题。

| 厂商说法 | 来源 | 判定 | 依据与处置建议 |
|---|---|---|---|
| **「自相矛盾或含糊的指令对 GPT-5 的伤害比其他模型更大——它会消耗推理 token 去调和矛盾，而不是随机挑一条执行」**，并建议逐条审查 prompt 库里的冲突 | [102] §Instruction following | ✅ **有支撑** | 这与本综述 §4 的结论**完全同向**：指令层级在真实模型上会失败 [15]，冲突解决是独立难点 [18][19]，多层指令层级另有专门研究 [20]。→ **这是本节最该听的一条**。它把「审查你的 prompt 库里是否有互相矛盾的条目」从「风格建议」升格为**有机制、有文献的功能性要求**——对你的 prompt 设计体系，这等于一条**必做的静态检查** |
| **「长对话里 Markdown 类格式指令的遵从会衰减，实测每 3–5 轮用户消息追加一次格式指令可恢复稳定遵从」** | [102] §Markdown formatting | ✅ **有支撑** | [46] 正是「LLM 在多轮中会「迷路」」的系统证据——长会话中的指令与约束遵从会显著退化。→ **听，而且这条可直接落地**：它给出了一个**定量的再注入节奏（3–5 轮）**。注意厂商自述这是「实测观察」而非对照实验，但方向有 [46] 背书，**是本综述里少见的「厂商操作细节 + 学术机制」对得上的例子** |
| **metaprompting：把 system prompt 与失败样例交给模型，让它诊断并提出最小修改**（含可照抄的模板；5.1 更给出完整的三步流程） | [102] §Metaprompting、[103] §How to metaprompt effectively | ✅ **有支撑** | system prompt 可被自动优化且有可迁移收益 [6][7]。→ **听。** 对维护一套 prompt 体系的人，这条的性价比最高：它把「猜哪一行导致行为漂移」变成「让模型指出哪一行」 |
| **工具使用的双向边界**：一边「凡涉及具体价格/场地/供应商，优先用工具而非内部知识」，一边「简单概念性问题不要调工具，免得又慢又僵」 | [103] §GreenGather 反例分析 | ✅ **有支撑** | 这正是工具**过用**与**欠用**的两侧：[72] 剖析「偏好外部工具而非内部知识」的过用机制，[73] 证明**不必要的工具可用性本身就会损害回答**，[70][74] 给出元认知触发与工具边界的学习方法。→ **听，且把它当成分界问题而非取舍问题**：厂商的实操与文献都指向同一件事——**要给「何时不用工具」写判据**，这正是本综述 §5 与 [71][72] 的结论 |
| **显式长度/冗长度约束**（`<output_verbosity_spec>` 之类的显式规格块） | [104] §3.1 | ⚠️ **经验之谈** | 长度约束可测但有限 [35]；且严格格式有代价 [30]。→ **可用**，但别指望它替代真正的输出裁剪 |
| **「迁移到新模型时要显式钉住 reasoning_effort，避免 provider 默认值带来的成本/冗长漂移」**；「新旧 prompt 迁移后要先用 eval 验证再改」 | [104] §8 | ✅ **有支撑**（间接但有力） | 直接对应 [85]：**prompt 工程技术的有效性会随模型版本迭代而变化**，一项局部复现研究已实证。→ **听，而且这条是你整个体系最该制度化的一条**：把「模型版本」当成 prompt 的**一等依赖**记录（[85] 的直接含义） |

### 6.4 厂商文档的三处「自相矛盾」与一处「跨版本撤回」

这几条不放进表格，因为它们本身就是结论：**厂商文档内部并不自洽，且会随模型换代推翻自己**，这恰好是 [85] 的现场例证。

**（1）同一份 Google 文档里，「末尾重申」与「避免冗余」互相打架。**
[105] 的 Prompt 组件表把 **Recap** 列为推荐组件——「在 prompt 末尾简洁重复关键点，**尤其是约束与输出格式**」；而同一份文档的健康检查清单又要求审查 **Redundant instructions**——「同一条指令换着说法重复多次、不增加新信息」。
→ **这不是「抄错」，而是两种机制的真实张力**：位置效应研究 [43][44] 表明长上下文中**首尾位置**更受注意（U 形），故「末尾重申约束」有机制支持；而 [31] 表明**指令条数密度**上升会压低遵循率。**处置**：把「重申」限定为**极少数关键约束的末尾锚定**（位置收益），而不是把整份约束表复制一遍（密度代价）。**两条都别全信，也别全不信。**

**（2）「情绪化措辞」上的正面冲突（已在 6.2 表格展开）。**
Google 说「不再改善甚至更差」，[84] 与 [110] 说「正向情绪刺激更准确」。**处置**：见 6.2 对应行——**不为正确率使用，但也不必因厂商断言而认为它必然有害**。

**（3）OpenAI 对自己 2024 年指南的部分撤回——「让模型思考」这条的版本边界。**
[101]（2024-07，面向 GPT-4o）把 **Give the model time to "think"** 列为**六大策略之一**，教你在 prompt 里显式要求先展开推理。
但到 GPT-5 世代，[102][103][104] 的叙事已转为 **reasoning effort / reasoning tokens 由模型内化**，官方建议的是「学会控制 reasoning effort 与冗长度」「resolved 冲突以让推理 trace 更高效」，而不再把「显式要求一步一步想」当作首要手段；Google 也在其清单里并列给出同向提示：「**用 Thinking 模式时，试试不要显式写逐步推理指令**」（[105]）。
→ **这是本节的第二个头条结论**：**同一家厂商、相隔约一年，对同一条核心策略的建议方向发生了实质变化**。这正是 [85] 所实证的「prompt 技术有效性随模型版本漂移」的一手案例。
→ **处置**：凡是写着「要求模型 step-by-step」的条目，都要按**目标模型世代**分叉——对非推理模型（GPT-4o 一类）保留 [107] 的 CoT 收益；对 reasoning 模型，把「显式 CoT 指令」降级为**待自测项**，而不是默认动作。**不要把一个世代的经验当普适规律固化进你的体系。**

**（4）「厂商都在推荐 persona，而唯一的系统研究说没用」。**
OpenAI [101] 把它列为正式 tactic，Google [95][105][106] 把它列为 use case 且升格为清单要求，Anthropic [94] 的「把模型当团队里的初级工程师」也含角色设定意味——**三家一致**，而 [1] 用 162 个角色得到的结论是**客观任务无增益**。
→ **处置**：厂商的「三家一致」在这里**不构成证据**（它们共享同一套实践者直觉，而非共享对照实验）。**persona 用于风格与语气，不用于正确率。**

### 6.5 复核 Anthropic 条目（原版条目，本轮维持判定）

来源：[94]。本轮复核后维持原判，仅补充一句：Anthropic 平台侧的 prompt 文档（`platform.claude.com`）按你的要求未尝试，因此 **Anthropic 的条目覆盖度仍是三家里最薄的一家**——不要把它当作已穷尽。

| 厂商说法 | 来源 | 判定 | 依据与处置建议 |
|---|---|---|---|
| 「保持简单」；只在**可证明**改善结果时才增加复杂度 | [94] | ✅ **间接支撑** | 指令密度越高遵循率越低 [31]，约束组合有代价 [32]。→ **听**，且这是与 [31] 最直接对应的一条厂商建议 |
| 「先用简单 prompt，再用全面评估去优化」 | [94] | ✅ **支撑** | [6][7]；但评估必须能抵御格式噪声 [2][3]。→ **听** |
| 精心设计工具文档与 ACI；「把模型当团队里的初级工程师」 | [94] | ✅ **支撑** | 工具描述质量显著影响 agent 表现 [76][77]；但工具偏好可被描述操纵 [78]。→ **听设计，但不要用它去「诱导」工具选择**（[78]） |
| 「给模型足够的 token 先思考」「格式贴近互联网自然文本」「避免格式开销」 | [94] | ⚠️ **经验之谈** | 前半与 [30] 同向但无该具体建议的受控实验；「贴近自然文本」可视为格式敏感性 [2] 的推论。→ **"避免格式开销"可听**（有 [30] 背书），其余待自测 |
| Guardrails 是**分层防御**，「单一 guardrail 不太可能提供足够保护」 | [96] | ✅ **支撑** | 体系化评测显示各类手段各有盲区 [51][52][53]；厂商原文「把 guardrail 想成分层防御」与 [52] 的 SoK 结论一致。→ **听** |
| Guardrails 要**同时优化安全与用户体验** | [96] | ✅ **支撑** | 安全与可用性的权衡已被量化：过度拒绝 [37][38]、guardrail 代价 [51]。→ **听**，且这是罕见的「厂商主动承认代价」 |
| 用「已有文档」生成指令、让模型拆细步骤、定义明确动作、覆盖边界情况；并可用强模型**自动把帮助文档转成 agent 指令** | [96] | ✅ **部分支撑** | 「拆细步骤/显式动作」与 [31][32] 同向；「自动生成指令」有 prompt 优化的文献家族 [6][7] 支持（metaprompting 亦见 [103]）。→ **听，且「用强模型把你的文档转成指令」值得直接采用** |
| 把「数据里夹带的指令」当作系统边界问题，而不是 prompt 措辞问题 | 本节综合判断（非厂商原文） | ✅ **支撑** | 有效防御来自结构化查询与前缀标记等机制，而非自然语言叮嘱 [54][55][56]。→ **听，这是全节最重要的一条「别写措辞、去改架构」** |

### 6.6 「工业经验会过时」的硬证据（原版保留，本轮获得更多一手案例）

Rudyk 等（ICSME 2026）对一项 prompt 工程技术研究做了局部复现（原作者为 Khojah 等 2025），结论是**prompt 工程技术的有效性会随 LLM 版本迭代而变化** [85]。
→ **因此「某条厂商建议有效」这句话必须带模型版本与评测日期，否则不可复现。** 本轮为这条结论补上了**两份一手案例**：OpenAI 在 GPT-5 世代事实上收回/弱化了 2024 年指南的「显式要求 CoT」策略（6.4 第 3 条），Google 则断言情绪化措辞的效果「已随世代消失」（6.2，且有 2026 年研究直接反驳）。

**与你的项目同类型工件已有专门研究**：`AGENTS.md` / `CLAUDE.md` 这类**编码 agent 配置文件**的常见错误已被系统研究（Configuration Smells，SCAM 2026）[86]；system prompt 的**干扰检测**也已有工具化框架（Arbiter，面向编码 agent 的 system prompt 测试基础设施）[87]。这两篇与「维护一套可公开的 prompt 设计体系」直接同题，建议优先精读。

**本节给 prompt 设计者的三句话结论**：
1. **可以照单全收的**：把计算外置给代码执行并与沙箱配套 [101]→[81][82][83]；指令冲突要做静态审查 [102]→[15][18][19][20]；格式/顺序/分隔符是真实变量而非风格问题 [105]→[2][3]；引用要可程序化校验 [101]→[109]；工具使用要写「何时不用」的判据 [103]→[72][73]。
2. **只用于风格、不用于正确率的**：persona / 角色设定（三家都在推荐，[1] 不支持），情绪化措辞（[84][110] 与厂商冲突，且代价是谄媚 [108]）。
3. **必须按模型世代分叉、并自测的**：显式 CoT 指令（6.4 第 3 条）、情绪刺激（6.2）、以及一切「某条技巧有效」的断言——因为它们会随版本失效 [85]。

### 6.7 本节新增文献（编号 101–110，已并入文末参考文献表）

> 说明：§6 原文的 [94]–[97] 编号保持不变，本节续接编号。**其中 [101][102][103][104] 为厂商官方文档，证据等级本身不高（实践者经验），列此处是为了让上表的「厂商说法」可被溯源**；[107]–[110] 才是用来做判定的研究文献。

101. OpenAI. *Prompt engineering*（官方指南；本节引用的文本取自官方仓库 `openai/openai-cookbook` 内文档快照 `examples/data/oai_docs/prompt-engineering.txt`，**该文件最后提交日期 2024-07-25**，正文面向 GPT-4o；线上页面 `platform.openai.com/docs/guides/prompt-engineering` 在本网络返回 **HTTP 403** 不可达）— https://raw.githubusercontent.com/openai/openai-cookbook/main/examples/data/oai_docs/prompt-engineering.txt
102. OpenAI. *GPT-5 prompting guide*（官方 cookbook）— https://cookbook.openai.com/examples/gpt-5/gpt-5_prompting_guide
103. OpenAI. *GPT-5.1 prompting guide*（官方 cookbook）— https://cookbook.openai.com/examples/gpt-5/gpt-5-1_prompting_guide
104. OpenAI. *GPT-5.2 Prompting Guide*（官方 cookbook）— https://cookbook.openai.com/examples/gpt-5/gpt-5-2_prompting_guide
105. Google Cloud. *Prompt design strategies* / *Prompt health checklist*（Gemini Enterprise Agent Platform 官方文档；本轮另抓取同文档集子页 `clear-instructions`、`few-shot-examples`、`explain-reasoning`、`break-down-prompts`、`structure-prompts`、`prompt-iteration`）— https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/prompts/prompt-design-strategies
106. Google Cloud. *Introduction to system instructions*（官方文档）— https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/prompts/system-instruction-introduction
107. ★ Wei, J., Wang, X., Schuurmans, D., et al. *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models*. NeurIPS 2022. arXiv:2201.11903 — https://arxiv.org/abs/2201.11903
108. Sharma, M., Tong, M., Korbak, T., et al. *Towards Understanding Sycophancy in Language Models*. 2023. arXiv:2310.13548 — https://arxiv.org/abs/2310.13548
109. Gao, T., Yen, H., Yu, J., Chen, D. *Enabling Large Language Models to Generate Text with Citations*（ALCE）. EMNLP 2023. arXiv:2305.14627 — https://arxiv.org/abs/2305.14627
110. Patel, A., Lee, F., Liang, K., et al. *The Role of Emotional Stimuli and Intensity in Shaping Large Language Model Behavior*. Poster, AACL Student Research Workshop 2025. arXiv:2604.07369 — https://arxiv.org/abs/2604.07369

> **证据强度提醒**：[110] 为学生 workshop 海报，证据等级偏低，本节仅用它反驳 Google「情绪化措辞已不再有效」的**强断言**，未用它确立「情绪词有效」的正面结论。[101][102][103][104] 同为厂商自述，其中 [101] 是**冻结于 2024-07-25 的快照**，可能已滞后于线上版本。
## 检索缺口声明

以下方向**我没有找到可靠研究**，或找到的证据不足以支撑结论。列出原因，不用泛泛而谈凑数。

1. **「system prompt 总长度（token 数）↔ 指令遵守率」的受控实验：未找到。** 现有最接近的是**指令条数密度**（IFScale，500 条指令 → 68%）[31] 与**长上下文位置效应**（U 形）[43][44]。但「同样 N 条指令，写成 500 token vs 3000 token，遵循率差多少」这个问题，我没有找到直接回答它的论文。这恰恰是你的设计体系最需要自测的变量（见启示第 4 条）。
2. **「中文 prompt 的约束效应」：覆盖极薄。** 指令层级的跨语言研究刚起步（Language Shapes Instruction Hierarchy Compliance in Multilingual LLMs，EMNLP 2026 [97]）；我**没有**找到「中文 system prompt 与英文相比遵循率如何变化」的系统研究，也没有找到针对中文长 system prompt 的位置效应研究。你的体系是中文的，这是个真实的证据空白。
3. **「什么措辞能提高工具调用意愿」的直接因果实验：未找到。** 相邻证据是（a）交替推理—行动的结构性收益 [66]，（b）工具描述质量的影响 [76][77]，（c）元认知/边界训练 [70][74]，（d）工具过用的机制分析 [72][73]。但**「把『必须用工具计算』写成祈使句 vs 写成禁令，调用率差多少」这类措辞级对照**，我没有找到。你的「计算外置铁律」在**理由**上证据充分 [81][82][83]，在**措辞有效性**上属于自测结论。
4. **创意写作场景（硬科幻 / 奇幻）中「system prompt 约束 ↔ 文学质量」的系统研究：未找到。** 找到的是：后训练降低多样性 [41][89][90]、创意写作评估基准 [91][92]、最接近的一条是**增量投递指令对创意写作的影响**（2026）[88]。**「设定类约束（世界观一致性、术语表）如何影响生成质量」我没有找到受控研究。**
5. **学术讨论场景：未找到专门研究。** 无论是「system prompt 如何影响辩论/论证质量」还是「学术讨论助手的约束设计」，本次检索都未命中可靠文献。
6. **厂商文档的可核查性受限（环境问题，非文献问题）**：
   - **OpenAI** —— 平台站点（`platform.openai.com` / `developers.openai.com`）**仍为 403**
     （59 字节拦截页，出口 IP 级，非资源不存在）。本轮改由**官方仓库快照**覆盖
     （`openai/openai-cookbook`），已补齐 prompt engineering 指南 + GPT-5 / 5.1 / 5.2 三份指南。
     ⚠️ **该快照冻结于 2024-07-25**，不是线上文档 —— 引用时须带着这个日期走。
   - **Anthropic** —— 平台文档区域不可用，本轮**按要求未尝试**，是三家中覆盖最薄的一家。
     （可达通路留档：`anthropics/prompt-eng-interactive-tutorial` 在 GitHub 上可访问。）
7. **本综述的检索方法局限**：arXiv 的全文检索（`all:`）噪声极大（实测一条查询返回了 LIGO 论文），因此我主要采用**按 ID 精确核对 + 字段前缀（`ti:` / `abs:`）检索**。这偏向英文、偏向量化方法学的工作；向量库检索类、纯工程博客类材料覆盖不全。

---

## 参考文献

**★ 标记为「若只读 10 篇」的核心文献。**

1. ★ Zheng, M., Pei, J., Logeswaran, L., et al. *When "A Helpful Assistant" Is Not Really Helpful: Personas in System Prompts Do Not Improve Performances of Large Language Models*. Findings of EMNLP 2024. arXiv:2311.10054 — https://arxiv.org/abs/2311.10054
2. ★ Sclar, M., Choi, Y., Tsvetkov, Y., Suhr, A. *Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design or: How I learned to start worrying about prompt formatting*. ICLR 2024. arXiv:2310.11324 — https://arxiv.org/abs/2310.11324
6. ★ Zhang, L., Ergen, T., Logeswaran, L., et al. *SPRIG: Improving Large Language Model Performance by System Prompt Optimization*. ICLR 2026. arXiv:2410.14826 — https://arxiv.org/abs/2410.14826
8. ★ Mu, N., Lu, J., Lavery, M., et al. *A Closer Look at System Prompt Robustness*. 2025. arXiv:2502.12197 — https://arxiv.org/abs/2502.12197
13. ★ Wallace, E., Xiao, K., Leike, R., Weng, L., Heidecke, J., Beutel, A. *The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions*. 2024. arXiv:2404.13208 — https://arxiv.org/abs/2404.13208
15. ★ Geng, Y., Li, H., Mu, H., et al. *Control Illusion: The Failure of Instruction Hierarchies in Large Language Models*. AAAI-26. arXiv:2502.15851 — https://arxiv.org/abs/2502.15851
23. ★ Huang, J., Chen, X., Mishra, S., et al. *Large Language Models Cannot Self-Correct Reasoning Yet*. ICLR 2024. arXiv:2310.01798 — https://arxiv.org/abs/2310.01798
24. ★ Kamoi, R., Zhang, Y., Zhang, N., et al. *When Can LLMs Actually Correct Their Own Mistakes? A Critical Survey of Self-Correction of LLMs*. TACL 2024, 12:1417–1440. arXiv:2406.01297 — https://arxiv.org/abs/2406.01297
30. ★ Tam, Z. R., Wu, C.-K., Tsai, Y.-L., et al. *Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of Large Language Models*. 2024. arXiv:2408.02442 — https://arxiv.org/abs/2408.02442
31. ★ Jaroslawicz, D., Whiting, B., Shah, P., et al. *How Many Instructions Can LLMs Follow at Once?* 2025. arXiv:2507.11538 — https://arxiv.org/abs/2507.11538
37. ★ Cui, J., Chiang, W.-L., Stoica, I., Hsieh, C.-J. *OR-Bench: An Over-Refusal Benchmark for Large Language Models*. ICML 2025. arXiv:2405.20947 — https://arxiv.org/abs/2405.20947
43. ★ Liu, N. F., Lin, K., Hewitt, J., et al. *Lost in the Middle: How Language Models Use Long Contexts*. TACL 2023. arXiv:2307.03172 — https://arxiv.org/abs/2307.03172
66. ★ Yao, S., Zhao, J., Yu, D., et al. *ReAct: Synergizing Reasoning and Acting in Language Models*. ICLR 2023. arXiv:2210.03629 — https://arxiv.org/abs/2210.03629
81. ★ Gao, L., Madaan, A., Zhou, S., et al. *PAL: Program-aided Language Models*. ICML 2023. arXiv:2211.10435 — https://arxiv.org/abs/2211.10435
82. ★ Chen, W., Ma, X., Wang, X., et al. *Program of Thoughts Prompting: Disentangling Computation from Reasoning for Numerical Reasoning Tasks*. TMLR 2023. arXiv:2211.12588 — https://arxiv.org/abs/2211.12588
86. ★ dos Santos, H. V. F., Costa, V., Montandon, J. E., et al. *Configuration Smells in AGENTS.md Files: Common Mistakes in Configuring Coding Agents*. SCAM 2026. arXiv:2606.15828 — https://arxiv.org/abs/2606.15828
87. ★ Mason, T. *Arbiter: Detecting Interference in LLM Agent System Prompts*. 2026. arXiv:2603.08993 — https://arxiv.org/abs/2603.08993

<details>
<summary>其余 83 条（正文以 [n] 引用，编号保持原样）</summary>

3. Lu, Y., Bartolo, M., Moore, A., et al. *Fantastically Ordered Prompts and Where to Find Them: Overcoming Few-Shot Prompt Order Sensitivity*. ACL 2022. arXiv:2104.08786 — https://arxiv.org/abs/2104.08786
4. Min, S., Lyu, X., Holtzman, A., et al. *Rethinking the Role of Demonstrations: What Makes In-Context Learning Work?* EMNLP 2022. arXiv:2202.12837 — https://arxiv.org/abs/2202.12837
5. Agarwal, R., Singh, A., Zhang, L. M., et al. *Many-Shot In-Context Learning*. NeurIPS 2024 (Spotlight). arXiv:2404.11018 — https://arxiv.org/abs/2404.11018
7. Choi, Y., Baek, J., Hwang, S. J. *System Prompt Optimization with Meta-Learning*. NeurIPS 2025. arXiv:2505.09666 — https://arxiv.org/abs/2505.09666
9. Patsakis, C., Argyropoulos, V., Alepis, E. *Configuration, Not Conscience: A Large-Scale Empirical Study of LLM System Prompts*. ICTAI 2026. arXiv:2609.31575 — https://arxiv.org/abs/2609.31575
10. Usama, M., Chang, D. E. *The System Prompt Illusion: How Instruction Preambles Modify Computation in Language Models*. 2026. arXiv:2609.38205 — https://arxiv.org/abs/2609.38205
11. Dong, J., Jia, P., Peng, J., et al. *Learning a Single Token to Replace Long System Prompts in LLMs*. 2025. arXiv:2511.23271 — https://arxiv.org/abs/2511.23271
12. Zhu, L., Wang, X., Zhang, W., et al. *RelayAttention for Efficient Large Language Model Serving with Long System Prompts*. ACL 2024. arXiv:2402.14808 — https://arxiv.org/abs/2402.14808
14. Zhang, Z., Li, S., Zhang, Z., et al. *IHEval: Evaluating Language Models on Following the Instruction Hierarchy*. NAACL 2025 (oral). arXiv:2502.08745 — https://arxiv.org/abs/2502.08745
16. Chen, K., Luo, J., Lin, S., et al. *HIPO: Instruction Hierarchy via Constrained Reinforcement Learning*. 2026. arXiv:2603.16152 — https://arxiv.org/abs/2603.16152
17. Balp-Straffon, E., Hsu, C.-H., Gadhvi, R., et al. *How Language Models Choose Sides: Internal Representations of Instruction Hierarchy*. ICML 2026 Mechanistic Interpretability Workshop. arXiv:2608.28648 — https://arxiv.org/abs/2608.28648
18. McCauley, C., Kan, Z., Martin, J. *IH-Benchmark: A Conflict-Centered Benchmark for Instruction-Hierarchy Robustness in LLM Applications*. 2026. arXiv:2607.25987 — https://arxiv.org/abs/2607.25987
19. Javed, T., Fatimah, S., Bakhtiari, M., et al. *PRIME: Evaluating Prompt Resolution Under Incompatible Instructions in LLMs*. 2026. arXiv:2606.22470 — https://arxiv.org/abs/2606.22470
20. Zhang, J., Li, T., Jurayj, W., et al. *Many-Tier Instruction Hierarchy in LLM Agents*. EMNLP 2026 Findings. arXiv:2604.09443 — https://arxiv.org/abs/2604.09443
21. Wu, T., Zhang, S., Song, K., et al. *Instructional Segment Embedding: Improving LLM Safety with Instruction Hierarchy*. ICLR 2025. arXiv:2410.09102 — https://arxiv.org/abs/2410.09102
22. Dong, Y. R., Hu, T., Hui, Z., et al. *Steer Model beyond Assistant: Controlling System Prompt Strength via Contrastive Decoding*. 2026. arXiv:2601.06403 — https://arxiv.org/abs/2601.06403
25. Liu, G., Qi, Z., Zhang, X., et al. *Self-correction is Not An Innate Capability in Language Models*. 2024. arXiv:2410.20513 — https://arxiv.org/abs/2410.20513
26. Tsui, K. *Self-Correction Bench: Uncovering and Addressing the Self-Correction Blind Spot in Large Language Models*. COLM 2026. arXiv:2507.02778 — https://arxiv.org/abs/2507.02778
27. Madaan, A., Tandon, N., Gupta, P., et al. *Self-Refine: Iterative Refinement with Self-Feedback*. NeurIPS 2023. arXiv:2303.17651 — https://arxiv.org/abs/2303.17651
28. Shinn, N., Cassano, F., Berman, E., et al. *Reflexion: Language Agents with Verbal Reinforcement Learning*. NeurIPS 2023. arXiv:2303.11366 — https://arxiv.org/abs/2303.11366
29. Wu, Z., Zeng, Q., Zhang, Z., et al. *Large Language Models Can Self-Correct with Key Condition Verification*. EMNLP 2024. arXiv:2405.14092 — https://arxiv.org/abs/2405.14092
32. Wen, B., Ke, P., Gu, X., et al. *Benchmarking Complex Instruction-Following with Multiple Constraints Composition (ComplexBench)*. NeurIPS 2024 Datasets & Benchmarks. arXiv:2407.03978 — https://arxiv.org/abs/2407.03978
33. Jiang, Y., Wang, Y., Zeng, X., et al. *FollowBench: A Multi-level Fine-grained Constraints Following Benchmark for Large Language Models*. ACL 2024. arXiv:2310.20410 — https://arxiv.org/abs/2310.20410
34. He, Y., Jin, D., Wang, C., et al. *Multi-IF: Benchmarking LLMs on Multi-Turn and Multilingual Instructions Following*. 2024. arXiv:2410.15553 — https://arxiv.org/abs/2410.15553
35. Zhou, J., Lu, T., Mishra, S., et al. *Instruction-Following Evaluation for Large Language Models (IFEval)*. 2023. arXiv:2311.07911 — https://arxiv.org/abs/2311.07911
36. Han, C., Liu, X., Wang, H., et al. *Can Language Models Follow Multiple Turns of Entangled Instructions?* EMNLP 2025 Findings. arXiv:2503.13222 — https://arxiv.org/abs/2503.13222
38. Röttger, P., Kirk, H. R., Vidgen, B., et al. *XSTest: A Test Suite for Identifying Exaggerated Safety Behaviours in Large Language Models*. NAACL 2024. arXiv:2308.01263 — https://arxiv.org/abs/2308.01263
39. Qi, X., Panda, A., Lyu, K., et al. *Safety Alignment Should Be Made More Than Just a Few Tokens Deep*. 2024. arXiv:2406.05946 — https://arxiv.org/abs/2406.05946
40. Lin, Y., Lin, H., Xiong, W., et al. *Mitigating the Alignment Tax of RLHF*. EMNLP 2024 Main. arXiv:2309.06256 — https://arxiv.org/abs/2309.06256
41. Kirk, R., Mediratta, I., Nalmpantis, C., et al. *Understanding the Effects of RLHF on LLM Generalisation and Diversity*. 2024. arXiv:2310.06452 — https://arxiv.org/abs/2310.06452
42. Gao, L., Schulman, J., Hilton, J. *Scaling Laws for Reward Model Overoptimization*. 2022. arXiv:2210.10760 — https://arxiv.org/abs/2210.10760
44. Hsieh, C.-Y., Chuang, Y.-S., Li, C.-L., et al. *Found in the Middle: Calibrating Positional Attention Bias Improves Long Context Utilization*. ACL Findings 2024. arXiv:2406.16008 — https://arxiv.org/abs/2406.16008
45. Modarressi, A., Deilamsalehy, H., Dernoncourt, F., et al. *NoLiMa: Long-Context Evaluation Beyond Literal Matching*. ICML 2025. arXiv:2502.05167 — https://arxiv.org/abs/2502.05167
46. Laban, P., Hayashi, H., Zhou, Y., et al. *LLMs Get Lost In Multi-Turn Conversation*. 2025. arXiv:2505.06120 — https://arxiv.org/abs/2505.06120
47. Chen, X., Chi, R. A., Wang, X., et al. *Premise Order Matters in Reasoning with Large Language Models*. ICML 2024. arXiv:2402.08939 — https://arxiv.org/abs/2402.08939
48. Baker, G. A., Raut, A., Shaier, S., et al. *Lost in the Middle, and In-Between: Enhancing Language Models' Ability to Reason Over Long Contexts in Multi-Hop QA*. 2024. arXiv:2412.10079 — https://arxiv.org/abs/2412.10079
49. Rebedea, T., Dinu, R., Sreedhar, M., et al. *NeMo Guardrails: A Toolkit for Controllable and Safe LLM Applications with Programmable Rails*. EMNLP 2023 Demo. arXiv:2310.10501 — https://arxiv.org/abs/2310.10501
50. Inan, H., Upasani, K., Chi, J., et al. *Llama Guard: LLM-based Input-Output Safeguard for Human-AI Conversations*. 2023. arXiv:2312.06674 — https://arxiv.org/abs/2312.06674
51. Kumar, D., Birur, N. A., Baswa, T., et al. *No Free Lunch with Guardrails*. 2025. arXiv:2504.00441 — https://arxiv.org/abs/2504.00441
52. Wang, X., Ji, Z., Wang, W., et al. *SoK: Evaluating Jailbreak Guardrails for Large Language Models*. IEEE S&P 2026. arXiv:2506.10597 — https://arxiv.org/abs/2506.10597
53. Li, J., Guo, M., Nguyen, H. X. *CS-Guard: Benchmarking LLM Guardrails for Code Generation Security*. 2026. arXiv:2609.09798 — https://arxiv.org/abs/2609.09798
54. Greshake, K., Abdelnabi, S., Mishra, S., et al. *Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection*. 2023. arXiv:2302.12173 — https://arxiv.org/abs/2302.12173
55. Chen, S., Piet, J., Sitawarin, C., et al. *StruQ: Defending Against Prompt Injection with Structured Queries*. USENIX Security 2025. arXiv:2402.06363 — https://arxiv.org/abs/2402.06363
56. Hines, K., Lopez, G., Hall, M., et al. *Defending Against Indirect Prompt Injection Attacks With Spotlighting*. 2024. arXiv:2403.14720 — https://arxiv.org/abs/2403.14720
57. Willard, B. T., Louf, R. *Efficient Guided Generation for Large Language Models*. 2023. arXiv:2307.09702 — https://arxiv.org/abs/2307.09702
58. Geng, S., Josifoski, M., Peyrard, M., et al. *Grammar-Constrained Decoding for Structured NLP Tasks without Finetuning*. EMNLP 2023 Main. arXiv:2305.13971 — https://arxiv.org/abs/2305.13971
59. Beurer-Kellner, L., Fischer, M., Vechev, M. *Guiding LLMs The Right Way: Fast, Non-Invasive Constrained Generation*. 2024. arXiv:2403.06988 — https://arxiv.org/abs/2403.06988
60. Park, K., Wang, J., Berg-Kirkpatrick, T., et al. *Grammar-Aligned Decoding*. NeurIPS 2024. arXiv:2405.21047 — https://arxiv.org/abs/2405.21047
61. Ouyang, L., Wu, J., Jiang, X., et al. *Training language models to follow instructions with human feedback*. 2022. arXiv:2203.02155 — https://arxiv.org/abs/2203.02155
62. Rafailov, R., Sharma, A., Mitchell, E., et al. *Direct Preference Optimization: Your Language Model is Secretly a Reward Model*. 2023. arXiv:2305.18290 — https://arxiv.org/abs/2305.18290
63. Bai, Y., Kadavath, S., Kundu, S., et al. *Constitutional AI: Harmlessness from AI Feedback*. 2022. arXiv:2212.08073 — https://arxiv.org/abs/2212.08073
64. Wei, J., Bosma, M., Zhao, V. Y., et al. *Finetuned Language Models Are Zero-Shot Learners (FLAN)*. ICLR 2022. arXiv:2109.01652 — https://arxiv.org/abs/2109.01652
65. Zhou, C., Liu, P., Xu, P., et al. *LIMA: Less Is More for Alignment*. 2023. arXiv:2305.11206 — https://arxiv.org/abs/2305.11206
67. Schick, T., Dwivedi-Yu, J., Dessì, R., et al. *Toolformer: Language Models Can Teach Themselves to Use Tools*. 2023. arXiv:2302.04761 — https://arxiv.org/abs/2302.04761
68. Qin, Y., Hu, S., Lin, Y., et al. *Tool Learning with Foundation Models*. 2023. arXiv:2304.08354 — https://arxiv.org/abs/2304.08354
69. Qiao, S., Gui, H., Lv, C., et al. *Making Language Models Better Tool Learners with Execution Feedback*. NAACL 2024. arXiv:2305.13068 — https://arxiv.org/abs/2305.13068
70. Li, W., Li, D., Dong, K., et al. *Adaptive Tool Use in Large Language Models with Meta-Cognition Trigger*. ACL 2025. arXiv:2502.12961 — https://arxiv.org/abs/2502.12961
71. Xu, H., Wang, Z., Zhu, Z., et al. *Alignment for Efficient Tool Calling of Large Language Models*. 2025. arXiv:2503.06708 — https://arxiv.org/abs/2503.06708
72. Zeng, Y., You, S., Liu, Y., et al. *The Tool-Overuse Illusion: Why Does LLM Prefer External Tools over Internal Knowledge?* 2026. arXiv:2604.19749 — https://arxiv.org/abs/2604.19749
73. Paturi, S., Kenzhebayev, A., Sethi, A., et al. *When Tools Get in the Way: The Effect of Unnecessary Tool Availability on LLM Answering*. 2026. arXiv:2609.14157 — https://arxiv.org/abs/2609.14157
74. Zou, W., Liu, X., Bi, W., et al. *CoBRA: Learning Tool-Use Boundaries via Counterfactual Margins*. EMNLP 2026. arXiv:2609.00967 — https://arxiv.org/abs/2609.00967
75. Chen, Y., Siu, V., Liu, Y., et al. *Controlling Tool Use with Heading-Specific Activation Steering*. 2026. arXiv:2607.05790 — https://arxiv.org/abs/2607.05790
76. Hasan, M. M., Li, H., Rajbahadur, G. K., et al. *Model Context Protocol (MCP) Tool Descriptions Are Smelly! Towards Improving AI Agent Efficiency with Augmented MCP Tool Descriptions*. 2026. arXiv:2602.14878 — https://arxiv.org/abs/2602.14878
77. Guo, R., Dong, K., Gao, X., et al. *Learning to Rewrite Tool Descriptions for Reliable LLM-Agent Tool Use*. 2026. arXiv:2602.20426 — https://arxiv.org/abs/2602.20426
78. Faghih, K., Wang, W., Cheng, Y., et al. *Tool Preferences in Agentic LLMs are Unreliable*. EMNLP 2025 Main. arXiv:2505.18135 — https://arxiv.org/abs/2505.18135
79. Xu, H., Li, C., Ma, X., et al. *The Evolution of Tool Use in LLM Agents: From Single-Tool Call to Multi-Tool Orchestration*. 2026. arXiv:2603.22862 — https://arxiv.org/abs/2603.22862
80. Patel, I., Sen, S., Lumer, E., et al. *The Bitter Lesson of Tool Calling*. 2026. arXiv:2608.06370 — https://arxiv.org/abs/2608.06370
83. Dziri, N., Lu, X., Sclar, M., et al. *Faith and Fate: Limits of Transformers on Compositionality*. NeurIPS 2023. arXiv:2305.18654 — https://arxiv.org/abs/2305.18654
84. Li, C., Wang, J., Zhang, Y., et al. *Large Language Models Understand and Can be Enhanced by Emotional Stimuli*. 2023. arXiv:2307.11760 — https://arxiv.org/abs/2307.11760
85. Rudyk, A., Oertel, J., Hebig, R. *Aging of Prompt Engineering Techniques Across LLM Versions*. ICSME 2026. arXiv:2608.24641 — https://arxiv.org/abs/2608.24641
88. Singh, A., Eyasir, A., Yaqoob, H., et al. *The Effects of Incremental Instruction Delivery on Language-Model Creative Writing*. 2026. arXiv:2609.33738 — https://arxiv.org/abs/2609.33738
89. Chung, J. J. Y., Padmakumar, V., Roemmele, M., et al. *Modifying Large Language Model Post-Training for Diverse Creative Writing*. 2025. arXiv:2503.17126 — https://arxiv.org/abs/2503.17126
90. Cao, Q., Liu, Y., Bi, W., et al. *DPWriter: Reinforcement Learning with Diverse Planning Branching for Creative Writing*. 2026. arXiv:2601.09609 — https://arxiv.org/abs/2601.09609
91. Fein, D., Russo, S., Xiang, V., et al. *LitBench: A Benchmark and Dataset for Reliable Evaluation of Creative Writing*. 2025. arXiv:2507.00769 — https://arxiv.org/abs/2507.00769
92. Wang, T., Chen, J., Jia, Q., et al. *Weaver: Foundation Models for Creative Writing*. 2024. arXiv:2401.17268 — https://arxiv.org/abs/2401.17268
93. Li, Y. *Decomposing LLM Self-Correction: The Accuracy-Correction Paradox and Error Depth Hypothesis*. 2025. arXiv:2601.00828 — https://arxiv.org/abs/2601.00828
94. Anthropic. *Building Effective AI Agents*（工程博客，2024-12-19 发布，2026-08-10 更新）— https://www.anthropic.com/engineering/building-effective-agents
95. Google Cloud. *Use system instructions* / *Introduction to system instructions*（Gemini Enterprise Agent Platform 官方文档）— https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/prompts/system-instructions
96. OpenAI. *A practical guide to building agents*（官方 PDF）— https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf
97. Moon, J., Hwang, Y., Jung, K. *Language Shapes Instruction Hierarchy Compliance in Multilingual LLMs*. EMNLP 2026 Main. arXiv:2607.23545 — https://arxiv.org/abs/2607.23545
98. Kariyappa, S., Suh, G. E. *Stronger Enforcement of Instruction Hierarchy via Augmented Intermediate Representations*. 2025. arXiv:2505.18907 — https://arxiv.org/abs/2505.18907
99. Zeng, S., Lee, S., Zhao, H., et al. *Steering Instruction Hierarchies at Inference Time*. COLM 2026. arXiv:2607.26228 — https://arxiv.org/abs/2607.26228
100. Kariyappa, S., Suh, G. E. *Where Instruction Hierarchy Breaks: Diagnosing and Repairing Failures in Reasoning Language Models*. 2026. arXiv:2606.07808 — https://arxiv.org/abs/2606.07808
101. OpenAI. *Prompt engineering*（官方指南；本节引用的文本取自官方仓库 `openai/openai-cookbook` 内文档快照 `examples/data/oai_docs/prompt-engineering.txt`，**该文件最后提交日期 2024-07-25**，正文面向 GPT-4o；线上页面 `platform.openai.com/docs/guides/prompt-engineering` 在本网络返回 **HTTP 403** 不可达）— https://raw.githubusercontent.com/openai/openai-cookbook/main/examples/data/oai_docs/prompt-engineering.txt
102. OpenAI. *GPT-5 prompting guide*（官方 cookbook）— https://cookbook.openai.com/examples/gpt-5/gpt-5_prompting_guide
103. OpenAI. *GPT-5.1 prompting guide*（官方 cookbook）— https://cookbook.openai.com/examples/gpt-5/gpt-5-1_prompting_guide
104. OpenAI. *GPT-5.2 Prompting Guide*（官方 cookbook）— https://cookbook.openai.com/examples/gpt-5/gpt-5-2_prompting_guide
105. Google Cloud. *Prompt design strategies* / *Prompt health checklist*（Gemini Enterprise Agent Platform 官方文档；本轮另抓取同文档集子页 `clear-instructions`、`few-shot-examples`、`explain-reasoning`、`break-down-prompts`、`structure-prompts`、`prompt-iteration`）— https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/prompts/prompt-design-strategies
106. Google Cloud. *Introduction to system instructions*（官方文档）— https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/prompts/system-instruction-introduction
107. ★ Wei, J., Wang, X., Schuurmans, D., et al. *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models*. NeurIPS 2022. arXiv:2201.11903 — https://arxiv.org/abs/2201.11903
108. Sharma, M., Tong, M., Korbak, T., et al. *Towards Understanding Sycophancy in Language Models*. 2023. arXiv:2310.13548 — https://arxiv.org/abs/2310.13548
109. Gao, T., Yen, H., Yu, J., Chen, D. *Enabling Large Language Models to Generate Text with Citations*（ALCE）. EMNLP 2023. arXiv:2305.14627 — https://arxiv.org/abs/2305.14627
110. Patel, A., Lee, F., Liang, K., et al. *The Role of Emotional Stimuli and Intensity in Shaping Large Language Model Behavior*. Poster, AACL Student Research Workshop 2025. arXiv:2604.07369 — https://arxiv.org/abs/2604.07369
---

</details>
## 给这份 prompt 设计体系的启示

以下逐条对照你的设计做法。**凡我找不到公开文献支撑的，一律标注为「自测结论 / 未验证经验」——这不是贬低，而是把它放进正确的证据等级里**，这样才能知道哪些部分可以写进 README 当「有研究支撑的做法」，哪些只能写成「我的实测」。

### 一、有文献支撑的做法

**1. 「计算外置铁律」是本体系里证据最扎实的一条。**
PAL [81] 与 PoT [82] 从方法层面证明：把计算从「推理」中剥离、交给确定性执行器，在数值/符号任务上优于纯 CoT；Faith and Fate [83] 从组合性上限的角度解释了为什么纯语言推理在多步计算上必然不可靠。你 prompt 里那些「多位数乘除也算」「不要手算」的判据，方向与文献完全一致。
补充边界：外置要配「何时该外置」的判据，否则会滑向工具过用 [71][72][73]。你已经写了「已调过工具、返回值一致 → 不得重复调用」——这条恰好对应工具过用研究的修复方向。

**2. 「无外部反馈的重推不是验证，只是烧 token」——被一整条研究线支持。**
[23] 证明无外部反馈的自我纠错在推理任务上无效甚至有害；[24] 用批判性综述排除了实验设计噪声后得到同一结论；[26][93] 进一步刻画了「知道错」与「能改」之间的缺口。你把它写成一个**禁令**（中断语：写到这里就停）而不是一个建议，这在证据上是站得住的。
同时注意你要保留的另一半：**有外部反馈的反思是有效的** [28]，**有外部可判定信号的验证是有效的** [29]。所以这条铁律的正确表述不是「禁止反思」，而是「禁止没有新证据的反思」。

**3. 「分场景各写一套 prompt」与文献一致，但理由要换。**
SPRIG [6] 发现 system 级与 task 级优化**互补**——通用 system prompt 与任务专用指令叠加能进一步提升，且优化后的通用 system prompt 可跨模型、跨语言迁移 [6]。这支持你「一套通用底盘 + 5 个场景分支」的结构。
**但不要用 persona 来论证场景分支的价值**：[1] 用 162 个角色的系统评测表明，人设本身不提升客观任务表现。场景分支的价值应落在**流程约束、格式约束、术语约定、可信来源**这些可测的维度上，而不是「你是一位硬科幻作家」。

**4. 「不要一套 prompt 打所有模型」（你的 Flash/Pro 分治）方向正确，但强度需要降级表述。**
- 支持：prompt 有效性**随模型版本变化**（ICSME 2026 的复现研究直接给出这一结论）[85]；格式等价改写的性能波动可达 76 个点 [2]；指令层级的遵从行为在不同模型家族间差异显著 [15]。
- 未支持：**「Flash 需要某组锚、Pro 不需要某组锚」这个具体结论，我没有找到任何公开文献**。这是你的 P11/P24 实测结论。建议在 README 里如实写成「笔者实测」，并附上可复现的评测协议——这反而是你相对公开文献的**真实增量**。

**5. 「八荣八耻 / 以…为荣、以…为耻」的权威语式，有间接证据，但机制与你想的可能不同。**
Geng 等（AAAI-26）最重要的发现之一是：**社会层级框架（权威、专业性、共识）对模型行为的实际影响力强于 system/user 的角色划分**，作者推测预训练得到的社会结构作为潜在先验，其作用可能超过后训练护栏 [15]。你的「铁律」「不容商量」这类语式，属于「权威框架」。EmotionPrompt [84] 也从另一个角度报告了情感/权威性措辞可以改变输出。
**但请注意这条证据的读法**：它说明「权威语式能施加影响」，**不能**说明「权威语式能稳定地被遵守」——[15] 的同一篇论文的结论恰恰是**层级遵从整体不可靠**。所以：权威语式可以用来**提高注意力权重**，不能用来**替代可验证的机制**（这与你已经写的「以跳过验证为耻」是一致的）。

**6. 「精确状态外置到确定性存储」（草稿纸）与长上下文证据一致。**
lost in the middle 的 U 形效应 [43][44]、NoLiMa 揭示的有效上下文远短于标称长度 [45]、多轮对话中「信息可见但仍丢失」[46]——三者共同支持一个结论：**不要指望「写进上下文」等于「会被用到」**。把计数、checkpoint、状态外置到 DB，是应对这一点的正确方向。
（严格说，这三篇研究的是「检索/利用」，不是「memory offloading」本身；因此这条属于**方向一致的间接支撑**，不是直接实验验证。）

**7. 模块化自文档与小节结构，与工业界的「显式化」建议一致。**
OpenAI 的 agent 指南给出四条指令最佳实践：复用已有文档、**把任务拆细**、**定义明确动作**、**覆盖边界情况** [96]；Anthropic 强调 simplicity 与 transparency（显式展示规划步骤）[94]。
**但要诚实标注**：这四条是厂商从客户部署中总结的**经验之谈**，我没有找到对应的受控实验；而「格式变化会引起巨大性能波动」[2] 意味着**分节本身也可能带来不可预期的副作用**，结构化是「大概率有帮助但必须自测」的类别。

### 二、属于「未经验证的经验」的做法

| 做法 | 证据状态 |
|---|---|
| Flash 专用锚 / Pro 专用锚的具体分配 | **自测结论**（P11/P24）。公开文献只支持「prompt 效果随模型版本变化」[85]，不支持具体分配方案 |
| 「回顾锚」「反跑题锚」的具体措辞 | **未找到研究支撑**。相关的是指令密度退化 [31] 与自纠盲区 [26]，但都不是针对这两条锚 |
| 「以位置索引为耻/列名映射」等编程规范 | **属于工程规范，不是 LLM 约束研究**。它靠的是「让模型在推理时少做隐式状态追踪」，与组合性弱点 [83] 方向一致，但没有针对 prompt 设计的对照实验 |
| 「多位数乘除也算」的**具体阈值** | 阈值本身是**经验取值**。文献只支持「应外置」[81][82][83]，不支持「几位数以上才该外置」 |
| 停止信号 / 断点恢复的贯穿链路 | **系统工程实践，无 LLM 行为研究支撑**（也没有必要有——这是确定性控制流问题） |
| 「隐藏的连贯性」一节里「中文引号一律用「」」这条 | **纯工程约束**（解析安全性），与研究无关；这类规则的正当性来自语法风险本身，不需要文献支撑 |

### 三、建议在 README 里补的三项自测（对应本综述识别出的证据空白）

1. **「长度 vs 条数」对照实验**：固定指令条数，只改 system prompt 的总 token 数（例如把每条规则从一句扩写成一段），测遵守率变化。缺口声明第 1 条指出这正是公开文献没回答的问题，而你的 prompt 长度远超常见量级。
2. **「措辞强度」对照实验**：同一约束分别写成祈使句（「必须 X」）、禁令句（「禁止 Y」）、权威句（「铁律：X」），测触发率。缺口声明第 3 条指出措辞级因果实验缺失，而你的体系大量使用权威语式（第 5 条发现与之相关但不到位）。
3. **「中文 vs 英文」对照实验**：把同一条约束分别用中文和英文表述，测遵守率。缺口声明第 2 条指出中文覆盖极薄，而你的体系全中文。

这三项都属于**成本低、公开文献空白、且直接决定你体系可信度**的实验——做完之后，你的 README 就不只是「一篇综述的复述」，而是补上了三个文献缺口。

### 四、一条结构性提醒

本综述里最锋利的负面结果不是「某条 prompt 写法没用」，而是：**约束存在层级之分，提示层约束是概率性的、可被覆盖的** [13][15]。因此你的五套 prompt 无论多完善，都**不能承担「保证」的职责**——保证只能来自解码层约束（如 schema 强制 [57][58]）或系统层机制（数据/指令分离 [55][56]、可验证的检查点）。

这与你已经写下的「以跳过验证为耻」「以静默降级为耻」是同一条思路：**把保证放在确定性机制里，把倾向放在 prompt 里。** 文献支持这个分工。
