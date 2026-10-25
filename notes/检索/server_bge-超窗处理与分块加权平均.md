# server_bge 超窗处理：拒绝 / 分块加权平均 / 截断

文件名: 用户笔记/检索/server_bge-超窗处理与分块加权平均.md
摘要: 给 `server_bge.py` 加装超窗检测与三档策略。此前它对超长文本**静默截断**——
      调用方以为向量覆盖了全文，其实尾部被丢了，且无任何报错。
依赖: `<挂载d>:/DataServices/MCP/memoria-del-hielo/server_bge.py`（与公开发布版同源）

---

## 一、起因：原本没有任何检查

2026-10-25 用 Everything 找齐 **5 个 `server_bge` 源文件**（主文件、`<发布项目目录>`
副本、3 个 `.bak`），逐个搜 `truncat` / `clip` / `chunk` —— **一处都没有**。
所有版本都只声明 `max_length: 8192`，实际由模型在编码时静默截断。

这意味着：

> 你送一段 3 万 token 的文本，拿到一个 1024 维向量，它只代表**前 8192 token**。
> 没有报错、没有警告、没有标记。

这是"静默降级"的一种——比崩溃恶劣，因为调用方会拿它当全文的代表去检索。

## 二、三档策略

全局置顶配置（`server_bge.py` 顶部，环境变量可覆盖）：

```python
EMBED_OVERFLOW_MODE   = os.getenv("EMBED_OVERFLOW_MODE", "reject")   # reject|average|truncate
EMBED_WINDOW_RATIO    = float(os.getenv("EMBED_WINDOW_RATIO", "0.85"))
EMBED_OVERFLOW_STATUS = 413   # HTTP 413 Content Too Large（RFC 9110 §15.5.14）
```

| 档 | 行为 | 何时用 |
|---|---|---|
| **`reject`（默认）** | 超窗直接返回 **413**，`detail` 里写清 token 数 vs 窗口 | 让**调用方**决定怎么切——服务端替它猜是最坏的一种"帮你" |
| **`average`** | 按窗口的 85% 切块 → 各块分别嵌入 → **按每块字符数加权平均**并重新 L2 归一化 | 确实想要"整段文本一个向量"，且接受 token 消耗上涨 |
| **`truncate`** | 只留前 `max_length` token（旧的静默行为） | 仅为兼容保留 |

**`average` 会增加 token 消耗**：原文被切成多块各自编码。一段 3 万 token 的文本
在 average 下要付 4 块的钱。这是明码标价的交换，不是免费的。

## 三、为什么是「分块 + 加权平均」——文献依据

**分块 + 池化是长文本嵌入的标准做法**，不是自创：

- **Late Chunking**（Jina AI, arXiv:2409.04701）摘要原文：
  > "practitioners often split text documents into smaller chunks and encode them
  > separately... chunking applied after the transformer model and just before
  > **mean pooling**"

  它明确把 "split → encode → mean pooling" 当作**既有实践**来对比，自己的
  贡献是把 chunk 提到 transformer 之后（late）以保留上下文。

- **SBERT 生态**：`SentenceTransformer.encode` 默认对超长输入截断；长文档的
  通行做法就是 chunk + pool。

**为什么按长度加权而非等权**：长块承载的信息多。等权平均时，一个 100 字的碎片
和一个 5000 字的章节各占 1/2 权重，语义会被短块拉偏。按字符数加权是
mean pooling 的自然变体。

**为什么合并后要重新归一化**：余弦距离要求单位向量，而加权和不是单位长度。
不归一化会让相似度计算失真（内积偏大）。

## 四、切点必须吸附字素簇（UAX #29）

直接按字符下标切会把这些东西切成两半：

```
👨‍👩‍👧‍👦   emoji ZWJ 序列（7 个码点，1 个字素簇）
a̐        字母 + 组合重音符
क्षि       天城文连字
```

实现用 `regex` 模块的 `\X`（遵循 UAX #29），实测切分正确：

```python
regex.findall(r'\X', '👨‍👩‍👧‍👦a̐天城文क्षि')
# ['👨‍👩‍👧‍👦', 'a̐', '天', '城', '文', 'क्षि']
```

切块流程：tokenizer 的 `offset_mapping` 给出 token→字符区间，
把区间端点用 `_snap_forward()` 吸附到**不小于它的最近字素簇边界**。

## 五、实测

| 输入 | 结果 |
|---|---|
| 48000 字符 / **30001 tokens** | `average` → 切 5 块，各 6963/6964/6964/6964/2150 tokens（= 8192 × 0.85） |
| 同上 | `reject` → **413**，detail: `输入 #0 超出模型窗口：30001 tokens > 8192` |
| 同上 | `truncate` → 截到 13106 字符（8192 tokens） |
| 短文本 | 三者都不展开（`prepared=1, mapping=[None]`） |
| 加权平均自测 | `[1,0]×3 + [0,1]×1` → `[0.949, 0.316]`，模 **1.000** ✓ |

## 六、一个意外发现：中文约 4 字 / token

`XLMRobertaTokenizer` 对中文的压缩率比预想高得多：

```
"这是一个用于测试超窗处理的句子。" × 3000 = 48000 字符 → 30001 tokens
⇒ 约 1.6 字符/token（含重复句的高频词优势）
```

单独测短句时见过 4 字/token。所以：

> **按「字符数 ≤ 8192」做的估算，对中文偏保守**（真实 token 数通常远小于字符数），
> 不会误判超窗，但会高估 TPM 消耗。

这也解释了 `server_bge` 的 limiter 为什么用 `sum(len(t))` 估 token —— 保守方向。

## 七、对现有调用方的影响

| 调用方 | 影响 |
|---|---|
| `melquiades` 的 draftpad 嵌入 | 文本短（笔记均长 1.4 KB），不受影响 |
| `memoria` 的 chunk 嵌入 | chunk 本身 ≤2500 字符（chunker 的 `max_chars`），不受影响 |
| `tools/lane-a-embed-messages.py` | cap 8192 **字符** → 约 2048–5000 tokens，安全 |

**默认 `reject` 是行为变更**：任何送超长文本且依赖静默截断的调用方会开始收到 413。
这是有意的——静默截断的问题正是没人知道自己被截了。

## 八、生效方式

`server_bge` 是独立常驻服务（`python ~/ai-services/server_bge.py`），
**改完要重启它**。改配置可只设环境变量：

```bash
EMBED_OVERFLOW_MODE=average EMBED_OVERFLOW_RATIO_OVERRIDE=... python server_bge.py
```

（当前 `EMBED_WINDOW_RATIO=0.85` 也可用同名环境变量覆盖。）
