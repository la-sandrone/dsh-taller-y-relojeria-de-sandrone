# System Prompt 四副本漂移 · 审计报告

审计时间：2026-10-07 ｜ 触发原因：`tools/patch-system-prompt-sections.py --check` 在注入两个新章节后仍报「四副本不一致」

> **一句话结论**：`--check` 的红**不是本次注入造成的**，而是既有漂移——**C（活配置）已领先 A/B/D**，且 A/B/D 与 C 是**双向差异**（不是单向落后），所以**不能无脑覆盖**，需要逐节人工合并。

---

## 一、现象

```
preset     agent-presets  patches        cordis内嵌       一致
coding     402525a3406d   402525a3406d   c572a6e2abe5   False
general    c56dd52f6544   c56dd52f6544   160875863b8a   False
scifi      72a1cbf63bce   72a1cbf63bce   75162916dc2b   False
fantasy    89c3c90ae7c6   89c3c90ae7c6   f705f0f549f1   False
academic   add08431fa55   add08431fa55   08a2fee7eabd   False
```

比对口径（脚本 `do_check()`）：`D(.agent-presets)` vs `B(patches)` vs `C(cordis 内嵌块)`，取 `prefix: |-` 到 `complete:` 之间、去公共缩进后逐字比较。
**注意：该检查从不包含 A（人类源 txt）。**

---

## 二、证据 1：漂移早于本次改动

用 `compute` 注入**之前**的备份（时间戳 `20261007-124640`）跑同一口径：

| preset | D(legacy) | B(patch) | C(cordis) | D==B | B==C |
|---|---|---|---|---|---|
| coding | 1319990cebbe | 1319990cebbe | a79072e87415 | ✅ | ❌ |
| general | f6c21a63fdcb | f6c21a63fdcb | 7fd8695ce4c2 | ✅ | ❌ |
| scifi | 4c4478d7ec5e | 4c4478d7ec5e | 40d74ac278da | ✅ | ❌ |
| fantasy | edd26ea28347 | edd26ea28347 | 8fed4edfc384 | ✅ | ❌ |
| academic | 4e3b30c9f507 | 4e3b30c9f507 | aecb24d1d827 | ✅ | ❌ |

→ **注入前就已经红**。本次注入对 A/B/D 三者保持一致（块级已验，见第四节）。

备份位置（⚠️ 路径已于 2026-10-07 失效，见下方说明）：
- `dsh-domus-0.1.7-rc.2/profiles/web/cordis.patch.yml.bak-compute-20261007-124640`
- `dsh-domus-0.1.7-rc.2/patches/0.1.7-agent-presets/<id>.patch.yml.bak-compute-20261007-124640`
- `dsh-domus-0.1.7-rc.2/.agent-presets/<id>/agent.cordis.yml.bak-compute-20261007-124640`

> **⚠ 2026-10-07 更新：上述 `.bak-compute-20261007-124640` 快照已按「备份统一交 git 管理」清退。**
> 当日共清退 163 个残件；这一族（`bak-compute-20261007-1246*` / `1247*`）共 22 个：
> **21 个的内容仍躺在 git 对象库里**（判据：把残件字节 `git hash-object` 成 blob 后
> `git cat-file -e` 认得——不是「活文件有没有提交历史」），可用
> `git -C <home> log --all -- <对应活文件路径>` 找回改前版本；
> **1 个（`profiles/web/cordis.patch.yml.bak-compute-20261007-124640`）git 里没有**，
> 已收进 `backups/residue-git-unrecoverable-20261007-230429.tar.zst`。
> 取用方法与完整说明见 `DSH停机卡.md` 的「残件清退」小节。

---

## 三、证据 2：差异是**双向**的，不是单向落后

把三个载体按同一口径归一化后逐行 diff（非空行）：

| preset | A 行数 | C 行数 | 仅在 A | 仅在 C |
|---|---|---|---|---|
| coding | 506 | 518 | 13 | 25 |
| general | 353 | 363 | 8 | 18 |
| scifi | 389 | 396 | 15 | 22 |
| fantasy | 398 | 408 | 12 | 22 |
| academic | 373 | 380 | 12 | 19 |

（B/D 相对 C 同量级：仅在 B/D 8–15 行，仅在 C 17–24 行）

**仅在 B/D/A 出现的行（33 条去重）性质：**
- 旧一代 MCP 工具名：`search_arxiv` / `search_iacr` / `search_zenodo` / `Paper-search-MCP` / `download_scihub` / `download_with_fallback`
  → C 已换成新一代（`search_papers` 等，来源 mcp-pergaminos）
- 旧措辞：`## 一、一切网络连接默认 HTTP/1.1`（C：`… 且慎用长连接`）
- 旧表述：`本机在中国移动网络上、经代理访问境外`（C：`中国移动提供的互联网服务网上，网络连接质量很差…`）
- 旧条目：`以盲写代码为耻，以庙算为先为荣`（C：`在先`）
- 疑似**只存在于旧版**的条目：`- 灭世级：地球引力结合能 ≈ 2×10³² J。低于这个数字，别说"毁灭世界"。`（硬科幻版；C 中未见）
- 各预设「搜索工具」开场的不同写法（5 个版本各一）

**仅在 C 出现的行性质：**
- `# 环境信息和环境相关特殊说明` 整章（沙盒 /tmp 一次性、GitHub 走代理、WSL Arch 勿自行装包、Firefox 惯例）
- `# 模型身份` 整章（`{{model}}` 插值 + Flash/Pro 分治说明）
- `## 零、访问有可能被锁的境外网站一定询问用户是否需要挂代理。`
- 新一代 MCP 工具名与措辞更新

→ **C 是「新版本」，A/B/D 是「旧版本」+ 缺两章**。但旧版本里含 C 没有的条目（如「灭世级」那条），所以**合并需要逐节确认，不能整体覆盖**。

---

## 四、本次两个新章节不受影响

块级比对（去缩进后逐字）——四副本完全一致：

| 章节 | coding | general | scifi | fantasy | academic |
|---|---|---|---|---|---|
| `# 计算外置铁律（禁止手算）` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `# 文本引号规范（中文一律用「」）` | ✅ | ✅ | ✅ | ✅ | ✅ |

- compute 块 md5 前缀 `0d00e92f`（1185 字符 × 5 预设 × 4 副本全同）
- quotes 块 md5 前缀 `681f816b`（470 字符 × 5 预设 × 4 副本全同）
- 验收脚本：`_scratch/up020/verify-v2.py`
- 幂等复跑：80 处全 SKIP（= 4 章节 × 5 预设 × 4 副本）

---

## 五、风险

1. **重建即丢失**：若将来从 A（人类源）或 B（补丁源）重新生成 profile 配置，
   `# 环境信息和环境相关特殊说明` 与 `# 模型身份` **两章会丢**——而这两章当前正在影响模型行为。
2. **陈旧指导回流**：A/B/D 中的文献章节仍指向**已退役的 paper-search MCP 工具名**；
   若发生重建，模型会被提示去调用不存在的工具。
3. **A 不在护栏内**：`--check` 从不比对 A，所以 A 的漂移**永远不会被自动发现**。
4. **正式源与活配置脱节**：`tools/literature-policy/*.md` 已是新一代工具名（与 C 一致），
   但 A/B 的对应章节仍是旧版 → 说明 C 曾被**直接编辑**，绕过了「改正文源 → 分发四副本」的通道。

---

## 六、处置建议（三选一或组合）

**方案 A｜以 C 为准逐节回写 A/B/D（推荐）**
1. 先把 C 的 persona 导出为「当前权威文本」快照，落 `tools/` 下作为可比基线；
2. 逐节 diff（不整篇覆盖），确认 C 独有的 17–24 行**全部是更新而非误删**，
   A/B 独有的 8–15 行**逐条判定**（更新 / 保留 / 删除）；
3. 判定结果通过 `patch-system-prompt-sections.py` 的 SECTIONS 机制落地（正文源 → 四副本），
   而不是直接手改 A/B/D —— 否则漂移会再次发生；
4. 完成后 `--check` 应转绿。

**方案 B｜把 A 纳入护栏**
`do_check()` 增加 A（txt）与 B/D/C 的块级比对，或在脚本里加一个 `--check-all`
供定期巡检。否则 A 的漂移仍不可见。

**方案 C｜接受漂移，但冻结 C**
在脚本 docstring 与本文件里登记「C 为唯一权威，A/B/D 仅历史对照」，
并在 `tools/DSH-升级铁律.md` 级别的文档里禁止「从 A 重建」。

> ⚠️ 无论选哪个：**A/B/D 里旧一代 MCP 工具名（`search_arxiv` / `Paper-search-MCP` / `download_scihub`）
> 应尽快清理或确认已退役**，避免重建后误导模型。

---

## 附录 · 复现命令

```bash
cd $HARNESS
python3 tools/patch-system-prompt-sections.py --check          # 复现红
python3 _scratch/up020/verify-v2.py                            # 复现两个新章节的四副本一致
```

漂移量化脚本（本报告第三、四节）：`_scratch/up020/verify-v2.py` 与本节内联的 difflib 口径。
