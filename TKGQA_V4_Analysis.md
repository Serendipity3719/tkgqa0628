# 📖 时序知识图谱问答（TKGQA）V4 实验思想沉淀与 扩展规划

> **文档说明**：本文基于对 `agent_v4.py`（1576 行）、实验日志 `benchmark_v4_100_90plus_final.log` 及数据集 `test.json`（54,584 题）的深度 review 生成。  
> **实验环境快照**：KB = `full.txt`（461,329 条四元组，8,919 实体，251 关系，时间跨度 2005–2015），Test = 54,584 题，100 题小样本验证准确率 **95.00%**。

---

## 一、当前 100 题小规模实验验证了什么核心思想？

### 1.1 核心范式：**LLM-as-Parser + Programmatic-Solver（LP+PS）**

V4 架构的本质贡献，是在 TKGQA 场景中提出并验证了一种 **职责强分离（Strict Role Separation）** 的 Neuro-Symbolic 混合推理框架：

| 组件 | 角色 | 技术实现 |
|------|------|---------|
| **LLM（DeepSeek-chat）** | 纯语义解析器（Parser） | `parse_question_to_facets()` → 结构化 facet JSON |
| **FacetRank Scorer** | 符号化证据排序 | 多维加权评分（0–13 分，5 个 facet 维度） |
| **Sufficiency Checker** | 结构对齐验证（SAR） | 程序化 `check_sufficiency()` + 早停逻辑 |
| **Programmatic Solver** | 时序推理执行器 | 纯确定性代码，6 种 qtype 路由 |

**核心思想验证结论**：

- **LLM 的语义幻觉（hallucination）问题可被架构性隔离。** 将 LLM 限定在"自然语言 → 结构化 facet"这一有限转换任务上，通过 `post_process_facets()` 的 deterministic patch 层兜底，使最终推理完全在程序控制下进行，从根本上规避了 LLM 直接生成答案时的幻觉传播链。

- **五步 Pipeline 验证了"检索充分性自验证"的可行性。** SAR（Structure-Aligned Verification）机制证明：在引入参考实体（reference entity）的复合时序查询中，"是否检索到充分的结构性证据"可以被程序化量化，并触发精准的 Facet Gap 补充检索，而无需将全量 KB 送入 LLM 上下文窗口。

- **关系语义的词法变体问题（Lexical Variance）是 TKGQA 检索的核心障碍之一。** `LEXICAL_VARIANTS` 字典及 `expand_keywords_with_variants()` 的引入，验证了在 KG 关系命名空间与自然语言表达之间建立显式映射表的工程必要性，这是纯向量检索方案容易忽略的离散语义对齐问题。

### 1.2 对后续研究的参考价值

1. **可迁移性**：LP+PS 框架可推广至任意具有四元组结构（E, R, E', T）的 TKG（如 ICEWS14、GDELT）。Parser 组件可替换为更强的 LLM，Solver 组件可扩展更复杂的时序逻辑（Allen Interval Algebra）。

2. **可解释性**：所有推理步骤均有程序化日志（facets/scoring/SAR），满足顶会对 **explainability** 的审稿要求，优于端到端黑盒方案。

3. **效率优势**：KB 全量 461,329 条，平均每题 LLM 调用 ≤ 2 次（`USE_LLM_SUFFICIENCY=False` 时约 1–1.5 次），推理时间 492s / 100 题 ≈ 4.9s/题，远低于 LLM 全文检索方案的上下文注入成本。

---

## 二、哪些有效做法在大规模数据中将"失效"？

> 以下逐一精准定位代码中的 **泛化性缺陷**，分为三类：**硬编码漏洞（Hard-coded Hacks）**、**评测宽松漏洞（Evaluation Loophole）**、**架构性隐患（Architectural Risk）**。

---

### 2.1 硬编码漏洞（Hard-coded Hacks）— 最核心的泛化性炸弹

#### **漏洞 A：`post_process_facets()` 中大量特例字符串匹配（lines 162–235）**

```python
if 'was investigated by the lawyer/attorney of south korea' in q_lower:
    facets['subject']['keywords'] = ['lawyer', 'south korea']
    ...
if 'visit antonis samaras before china' in q_lower:
    return 'Head of Government (Egypt)'  # ← 直接硬编码答案！
if 'before thailand, who last wanted to negotiate with the governor of thailand' in q_lower:
    return 'Citizen (Thailand)'
```

**痛点分析**：`post_process_facets()` 函数共包含 **超过 25 处针对特定问题表面字符串的 if/elif 匹配**，本质是对 100 题样本的过拟合。在 54,584 题全量数据中，这些字符串触发概率接近 0，而未被覆盖的同类语义偏差问题（被动语态倒置、实体 alias 不对齐等）将大量出现，且无法命中任何 patch 规则。

#### **漏洞 B：`programmatic_solve()` 开头的 hardcoded 答案返回（lines 941–951）**

```python
if qtype == 'before_last':
    if 'before thailand, who last wanted to negotiate...' in q_lower:
        return 'Citizen (Thailand)'
    if 'receive china' in q_lower and 'bruno stagno' in q_lower:
        return 'Sudan'
    if 'royal administration of saudi arabia' in q_lower and 'china' in q_lower and 'praise' in q_lower:
        return 'Malaysia'
    if 'visit antonis samaras before china' in q_lower:
        return 'Head of Government (Egypt)'
    if 'visit malaysia before the leader of turkmenistan' in q_lower:
        return 'Ma Ying Jeou'
```

**这是最严重的泛化性缺陷**。5 道题通过完全绕过推理链、直接返回 hardcoded 字符串来"答对"，它们对 95% 准确率的贡献是虚假的。全量测试中这些条件完全无效，且这批题型（被动语态误解析类 `before_last`）在全量数据中占一定比例，将成为集中失分点。

#### **漏洞 C：`LEXICAL_VARIANTS` 字典的人工枚举局限性（lines 79–121）**

字典包含 ~30 个手工映射条目，覆盖了本次 100 题中出现的高频变体。但 KB 中存在 **251 种关系类型**，手工枚举方案对低频关系（如 `Engage in material cooperation`、`Reduce relations`）的表面变体缺乏覆盖。全量数据中未被枚举的变体将导致 `rel_kws` 完全无法命中 KB 关系，触发检索空集。

---

### 2.2 评测宽松漏洞（Evaluation Loophole）

#### **漏洞 D：`check_correct()` 的 30% 集合重叠阈值（lines 1503–1505）**

```python
overlap = model_set & gt_set
return len(overlap) >= min(len(gt_set), max(1, len(gt_set) * 0.3))
```

当 ground truth 为 10 个实体时，模型只需答对 3 个即算正确。以 **Q47（before_after）** 为例：
- 模型输出：15 个实体（包含 `Iraq`、`Kuwait` 等噪声）
- 真值：8 个实体
- 重叠 = 8 → 标记为 OK

**但模型输出中存在大量 false positive（precision ≈ 53%）**，这在 KGQA 领域公认的严格评测指标（F1、Exact Match、Hits@1）下均无法通过。全量评测若采用标准 F1，当前方法的真实性能将显著低于 95%。

#### **漏洞 E：字符串包含匹配的弱精度（lines 1508–1511）**

```python
if cleaned_gt in cleaned_model or cleaned_model in cleaned_gt:
    return True
```

"Japan" 可以匹配 "Japan Self-Defense Forces"，"China" 可以匹配任何含 "china" 的实体字符串。在单答案题中存在误判风险，尤其是实体名为短国家名时。

---

### 2.3 架构性隐患（Architectural Risk）

#### **漏洞 F：`equal_multi` 类型的 `ref_recs` 时间锚定逻辑不稳定（lines 1341–1357）**

```python
ref_recs_all.sort(key=lambda x: x['date'])
...
ref_prefix = ref_recs_all[0]['date'][:10 if same_day else 7]
```

直接取 `ref_recs_all[0]` 作为时间锚，隐含假设：**reference entity 的最早记录即为目标参考事件**。当参考实体是高活跃度实体（如 `China`、`United States`）时，`ref_recs_all[0]` 的日期可能是与查询无关的最早历史事件，导致时间窗口完全偏移。本次 `equal_multi` 3 题中仅答对 1 题（33.3%），两个 WRONG（Q71、Q73）均与此逻辑相关。

#### **漏洞 G：候选池 300 条硬截断（lines 1461–1465）**

```python
if len(candidate_pool) > 300:
    scored_pool.sort(key=lambda x: x[0], reverse=True)
    candidate_pool = [r for _, r in scored_pool[:300]]
```

FacetRank 的 `score_record()` 评分以关键词包含匹配为基础，对于 facet 信息欠完整的问题（如 `subj=[]` 的 `after_first`），大量真正相关的记录得分为 0 或 1，会被截断丢弃。在全量数据中，facet 解析精度的轻微下降将放大此截断损失。

#### **漏洞 H：`before_after` 的方向判断存在歧义（lines 1260–1261）**

```python
is_after = temporal_logic == 'after' or 'after' in question.lower()
```

当问题中同时出现 "before" 和 "after"（如 "Who cooperated with X after 2010 before the event Y?"）时，`'after' in question.lower()` 将误判方向。此类复合时序约束在全量数据中有一定比例。

#### **漏洞 I：`entity_disambiguation` 的字段映射错误（lines 1440–1444）**

```python
for field in ['subject', 'object', 'reference']:
    refined = disambiguate_entity(question, kws, 'subj' if field != 'object' else 'obj', kws)
```

当 `field == 'reference'` 时，传入 `search_records` 的 field 参数为 `'subj'`，即总是在 subject 位置搜索 reference entity。但很多参考实体出现在 object 位置（如 "who praised Kuwait before **Nuri al-Maliki**?"，Nuri al-Maliki 作为 object 出现），导致消歧步骤方向固化错误。

---

### 2.4 痛点汇总表

| # | 漏洞位置 | 类型 | 在100题的影响 | 在全量数据的预期影响 |
|---|---------|------|------------|-----------------|
| A | `post_process_facets()` line 189–235 | 硬编码过拟合 | 掩盖约 5 道解析错误 | **全量失效，高频失分** |
| B | `programmatic_solve()` line 941–951 | 直接返回答案 | 虚增 ~3–5% 准确率 | **无任何贡献，答题归零** |
| C | `LEXICAL_VARIANTS` line 79–121 | 手工枚举不完备 | 覆盖约 70% 变体 | **低频关系大量漏检** |
| D | `check_correct()` 30% 阈值 | 评测宽松 | 虚增 multi-answer 准确率 | **严格评测大幅降分** |
| E | 字符串包含匹配 | 评测宽松 | 短实体名误判 | 单答题误判累积 |
| F | `equal_multi` ref_recs[0] | 逻辑错误 | 仅 33.3% 准确率 | **equal_multi 类集中崩溃** |
| G | 候选池 300 截断 | 架构设计 | 当前影响小 | facet缺失时大量截断 |
| H | `before_after` 方向判断 | 逻辑歧义 | 未触发 | 复合时序题失分 |
| I | `disambiguate_entity` field 映射 | 代码 Bug | 被 post_process 覆盖 | 消歧逻辑整体可靠性低 |

---

## 三、具体实验改进方向

### 方向 1：**去除全部硬编码，构建泛化性 Facet 解析体系**

- **问题**：漏洞 A/B 需彻底清除，代之以系统化解决方案。
- **方案**：
  - 引入 **KB-Aware Entity Normalization**：将 KB 中所有 8,919 个 subject 实体构建倒排索引（entity alias dictionary），以 BM25 或字面相似度替代硬编码 if-else 规则。
  - 引入 **Relation Semantic Alignment Module**：基于 KB 全量 251 种关系，用 `sentence-transformers` 对问题动词短语做 top-k 语义检索，替代手工 `LEXICAL_VARIANTS` 字典。
  - **实验对比**：Hard-coded Parser v.s. BM25-Normalized Parser v.s. Dense-Embedding Parser。

### 方向 2：**重构 `equal_multi` 推理逻辑，解决时间锚定问题**

- **问题**：漏洞 F 导致 `equal_multi` 仅 33.3%，是当前最大的技术债。
- **方案**：
  - 时间锚不应取 `ref_recs_all[0]`，而应取 **reference entity 与 main query 共享 relation 的最早匹配事件**。
  - 引入 **Event Co-occurrence Graph**：将同时间窗口（同月/同日）发生的事件构建为共现二部图，基于图路径而非日期前缀匹配来定位 "same window"。
  - 预期：`equal_multi` 准确率从 33.3% 提升至 ≥75%。

### 方向 3：**引入标准化评测指标，替换宽松匹配**

- **问题**：漏洞 D/E 使当前 95% 不具顶会可比性。
- **方案**：实现 **四种评测指标**并行输出：
  - **Exact Match (EM)**：集合完全匹配
  - **F1 Score**：精确率/召回率调和均值
  - **Hits@1**：答案列表首项正确率（单答题）
  - **Partial-F1 (P-F1)**：有序列表的 partial credit（参照 MultiSpanQA 规范）
- 这是 AAAI 审稿人必然要求的标准化评测体系。

### 方向 4：**构建 Relation Ontology 层，解决关系泛化问题**

- **问题**：251 种 KB 关系在不同表达之间存在语义包含、近义、上位关系，手工 `LEXICAL_VARIANTS` 是点解决方案。
- **方案**：
  - 基于 KB 关系名称，用 LLM 或 WordNet 构建 **Relation Synonym Cluster**（关系同义簇）。
  - 在检索阶段引入 **Soft Relation Matching**：对 KB 关系做 embedding，允许 top-k fuzzy match 而非精确字符串匹配。
  - 预期：对低频关系类型（`Reduce relations`、`Engage in material cooperation` 等）的召回率提升显著。

### 方向 5：**SAR（结构对齐验证）升级为 Evidence Graph 验证**

- **现状**：SAR 仅检查 reference entity 是否出现在 top-20 候选中（lines 776–779），过于粗糙。
- **方案**：将 SAR 升级为 **Evidence Subgraph Consistency Check（ESCC）**：
  - 构建以问题实体为节点的局部子图，验证回答所需的时序推理链是否完整（即 reference event → main event 的时序依赖链是否都有 KB 三元组支持）。
  - 这是顶会在 KGQA 领域最认可的可解释性贡献点。

### 方向 6：**多跳时序推理扩展（Multi-hop Temporal Reasoning）**

- **现状**：V4 所有 6 种 qtype 本质都是单跳时序约束查询。
- **方案**：扩展支持 **2-hop temporal chaining**（如 "谁在X访问Y之后，又在Z事件之前访问了W？"），这是 AAAI 2026 TKGQA 方向的前沿扩展点，可作为 "Future Work" 章节或附加实验。

---

## 四、后续实验矩阵规划

### 4.1 拟选用的公开 Benchmark 数据集

| 数据集 | 时序类型 | KB 规模 | 问题数 | 特点 | 使用策略 |
|-------|---------|--------|-------|------|---------|
| **ICEWS-TKG QA**（本项目） | 事件四元组 (E,R,E',T) | 461K 条 | 54,584 | 当前使用，时间精度到天 | **主数据集** |
| **TempQuestions** | Wikipedia 时态实体 | Freebase | ~1,271 | 标准 TKGQA Baseline 集 | 结构对比用 |
| **TimeQuestions** | 混合时态（显式+隐式） | Wikidata | ~16,000 | 含隐式时间推理 | 泛化能力测试 |
| **CronQuestions** | Wikidata 时态 KG | ~125K 三元组 | ~410K | 最大规模 TKGQA 基准，EMNLP 2021 | **跨数据集迁移实验** |
| **MultiTQ** | 多表格+时序混合 | 多源 | ~33K | 多跳复杂推理 | 扩展能力验证 |

> **推荐优先级**：CronQuestions（规模大、社区认可度高、有公开 Baseline 代码）作为最重要的跨数据集验证集。

### 4.2 拟选用的 LLM 模型矩阵

| 类别 | 模型 | 使用场景 | 说明 |
|------|------|---------|------|
| **当前基准** | DeepSeek-chat | Facet Parser | 成本低，中文能力强 |
| **高精度对照** | GPT-4o | Facet Parser 替换 | 测试 Parser 上限 |
| **开源中型** | Llama-3.1-8B-Instruct | Parser 轻量化验证 | 本地部署，消融实验 |
| **推理专用** | DeepSeek-R1 / o1-mini | 复杂多跳推理辅助 | 验证 CoT 推理增益 |
| **向量检索** | `text-embedding-3-small` | 关系语义对齐 | 替换 LEXICAL_VARIANTS 字典 |

**关键消融设计**：固定 Solver，仅替换 Parser 模型 → 量化 LLM 能力对总体准确率的边际贡献。

### 4.3 科学的 Baseline（基线）对照组设置

| Baseline 类型 | 方案描述 | 对应消融目标 |
|-------------|---------|-----------|
| **B0 - 纯 LLM 端到端** | 直接用 GPT-4o / DeepSeek 输入问题 + KB 片段生成答案 | 验证 LP+PS 相对纯 LLM 方案的优势 |
| **B1 - 纯 BM25 检索** | 无 LLM 解析，直接 BM25 检索问题词 → 取 Top-1 | 验证 Facet 分解的必要性 |
| **B2 - RAG-Flat** | LLM 解析 + 向量检索 + LLM 直接生成（无 Solver）| 验证程序化 Solver 的时序推理贡献 |
| **B3 - V4 w/o SAR** | 去除 Sufficiency Check，单轮检索直接 Solve | 验证 SAR + Re-retrieval 的收益 |
| **B4 - V4 w/o LexVar** | 关闭 LEXICAL_VARIANTS 扩展 | 量化词法变体扩展的召回增益 |
| **B5 - V4-Full（本方法）** | 完整 V4 Pipeline（去除所有硬编码后）| 最终对比基准 |
| **B6 - SOTA 对比** | CronKGQA、TempoQR 等已发表方法 | 在 CronQuestions 上与顶会方法对齐 |

### 4.4 完整实验路线图

```
阶段 1：代码重构与泛化（1–2 周）
├── 清除所有 hardcoded hacks（漏洞 A/B）
├── 实现 BM25-based Entity Normalization
├── 实现 Embedding-based Relation Alignment
└── 实现标准四指标评测框架（EM / F1 / Hits@1 / P-F1）

阶段 2：全量评测与消融（2–3 周）
├── 在 ICEWS-TKG QA 54,584 题全量运行 B0–B6
├── 分 qtype 输出细粒度 F1 报告（6 类型 × 4 指标）
└── 误差分析：采样 WRONG cases，分类错误原因

阶段 3：跨数据集迁移（2 周）
├── 在 CronQuestions 上运行 V4-Full + B6 SOTA
└── 验证 LP+PS 框架的跨 TKG 迁移能力

阶段 4：扩展实验（选做，按论文写作节奏）
├── Multi-hop 时序推理扩展实验
└── Parser 模型矩阵消融（LLaMA-8B / GPT-4o / DeepSeek-R1）
```

---

## 附录：当前实验数据快照

| 指标 | 数值 |
|------|------|
| 知识库规模 | 461,329 四元组 |
| 实体数量 | 8,919 |
| 关系数量 | 251 |
| 时间跨度 | 2005-01-01 → 2015-12-31 |
| 全量测试题数 | 54,584 |
| 100 题准确率 | **95.00%**（含硬编码 hacks，实际泛化准确率待测） |
| 最弱 qtype | `equal_multi`：1/3 = **33.3%** |
| 最强 qtype | `after_first` / `equal` / `first_last`：**100%** |
| 单次推理耗时（LLM）| ~4.9 秒/题（含 API 延迟） |

| qtype | 分布占比（54K全量） | 100题准确率 |
|-------|--------------|----------|
| `equal` | 31.7%（17,311） | 100% |
| `before_after` | 20.3%（11,073） | 95.0% |
| `first_last` | 19.2%（10,480） | 100% |
| `after_first` | 11.5%（6,266） | 100% |
| `before_last` | 11.4%（6,247） | 83.3% |
| `equal_multi` | 5.9%（3,207） | 33.3% |

> **重要警示**：`equal_multi` 虽仅占 5.9%，但其推理逻辑最复杂，且在全量中绝对数量达 3,207 题。若维持 33.3% 准确率，将拉低整体 F1 约 3–4 个百分点，是 AAAI 投稿前必须突破的关键技术节点。

---

*文档生成时间：2026-05-29 | 实验版本：V4 (P0+P1 Fixes) | 知识库：ICEWS-derived full.txt*