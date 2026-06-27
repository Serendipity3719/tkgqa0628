# 🩺 TKG2Skill 中期审查与演进报告（Mid-term Review）

> 2026-06-27 · 审查人视角：TKGQA/Agent 首席架构师 + 顶会审稿人
> 对照基准：《Don't Retrieve, Navigate: Distilling Enterprise Knowledge into Navigable Agent Skills》(CORPUS2SKILL)
> 一句话结论：**工程很干净、诚实评估做到了顶尖水平，但"导航(Navigate)"这个论文的灵魂目前没做出来——
> 现在的系统是一个"扁平实体索引 + 按问题类型套 awk 模板"的语义解析器，不是论文那种"分层拓扑导航"的 Deep Agent。**

---

## 0. 先把两个东西摆在一起看（这是全篇的锚点）

| 维度 | 论文 CORPUS2SKILL 做的 | 你现在 TKG2Skill 做的 | 对齐？ |
|---|---|---|---|
| 离线编译产物 | **拓扑层级森林**（embed→KMeans 聚类→LLM 摘要→递归，<K 个顶层簇） | **扁平实体目录** + 首字母分桶（34 桶，纯整洁用，不参与路由） | ❌ 核心机制缺失 |
| Skill 是什么 | **信息型 skill**（"语料里有什么"，SKILL.md/INDEX.md 逐级变细） | **过程型 skill**（"怎么用 awk 查"，按 qtype 套配方） | ⚠️ 走了论文明确放弃的老路 |
| 路由 | 顺着**目录树**鸟瞰→钻取（拓扑路由） | grep 一张 10489 行的扁平 `_catalog.tsv`（查表） + qtype 选模板 | ❌ 不是分层路由 |
| 渐进披露 | 描述→SKILL.md→INDEX.md→文档（拓扑越钻越细） | SKILLS.md→SKILL.md→NAVIGATION.md（**文档**渐进，非**数据**渐进） | ⚠️ 半对 |
| 回溯 | 分支不产出就回退换分支 | NAVIGATION.md 写了回溯预算，但实测 0.04–0.12 次/题，几乎不触发 | ⚠️ 写了没用上 |
| Serve 期基础设施 | 只用 code_execution，无向量库/SPARQL | 只用只读 shell（grep/awk），无图库/向量库 ✅ | ✅ **这一条是真对齐** |

> **核心判断**：论文的"navigate"= 顺着一棵**语义拓扑树**自上而下钻取并回溯。你把它替换成了
> "一次扁平查表 + 一次 ego 文件 awk"。这不是 navigate，是 **lookup**。论文恰恰是要反对 retrieve/lookup 的。
> 这就是你担心的"跑偏"——**确实偏了，偏在最核心的那根轴上。**

---

## 1. 🔍 目前已经实现了什么（Status Quo）

### 1.1 论文在做什么任务、怎么设计的（大白话）
- **任务**：企业客服知识库 QA/RAG（WixQA、RAGBench）。一堆杂乱文档，问一个问题要找到证据回答。
- **论文的反叛**：别再做"嵌入→取 top-k 段落"的 RAG 了（模型看不到语料全貌、不知道还有什么没看）。
- **论文的做法**：
  1. **离线一次性编译**：把整个语料 `embed → KMeans 聚类 → LLM 给每簇写摘要 → 再聚类`递归，直到顶层 <K 个簇，
     落成一棵**文件目录树**（每个节点一个 `SKILL.md` 概览 + `INDEX.md` 明细），边界文档交叉挂到次优簇（跨枝导航）。
  2. **Serve 期**：Agent 像浏览文件夹一样，从鸟瞰视角往下钻（描述→SKILL.md→INDEX.md→文档），
     钻错了**回溯**换枝，**全程只用 code_execution，不碰向量库**。
- **论文最硬的一句洞察**：把 skill 从"**过程型**（怎么做一件事）"改造成"**信息型**（语料里有什么）"——
  *"This shift from procedural to informational skills is the central design insight."*

### 1.2 你的系统做到了什么程度
- **离线投影 `build.py`（这是你真正的贡献，且很扎实）**：
  四元组 `(head, rel, tail, date)` → **每个实体一个目录**，`data.txt` 按日期升序。
  - ✅ **双向冗余**：每条事实在 head 和 tail 目录各存一份，带方向标记 `>`(本体是 head) / `<`(本体是 tail)。
    → "谁访问了 X" 只读 X 一个文件，不用全库扫描。**这一步设计非常对，是论文精神在 TKG 上的合理变体。**
  - ✅ `_catalog.tsv`（10489 实体，唯一入口）+ `_relations.txt`（251 关系，按频次降序）。
  - ⚠️ 大实体（>2000 条）才生成 `INDEX.md`（逐年计数/高频关系/高频邻居）——**只对大实体，且没人真正"钻"它**。
  - ❌ **明确不切年、不建时间索引**（代码注释原话）；首字母分桶只是"文件系统整洁"，**不参与路由**。
- **Skill 库**：5 个 qtype 过程技能（`before_after / after_first / before_last / first_last / equal`）
  + `SKILLS.md`（路由清单）+ `_shared/NAVIGATION.md`（关系/实体/方向/回溯/grounding 原语）。
- **Serve `agent_nav.py`**：单层 ReAct 循环（`for _turn in range(max_cmds+4)`），无 plan/无持久 state/无反思。
- **诚实数字（n=300 盲态）**：robust e2e **81%**，oracle 上界 91%，routing 94.6%。

### 1.3 头实体聚类 / 实体节点 / 时序细分 / skill —— 具体怎么做的（带例子走一遍）

**头实体"聚类"**：⚠️ **名不副实**。只有 `bucket_of()` 按安全名**首字符**分 34 个桶（a–z、数字、`_other`）。
这是字母排序，不是语义聚类；而且 Agent 路由时**根本不看桶**，直接 `grep _catalog.tsv`。
→ **论文那种"<100 个语义类别的拓扑路由"在你这里等于 0。**

**实体节点 / 时序细分**：每个实体 = 一个目录 + 一个按日期升序的 `data.txt`。
**时序细分=无**（不切年）。时序"导航"完全靠 awk 比较字典序日期（`$1<t0` / `$1>t0` / `head -1` / `tail -1`）。

**skill 设计**：过程型 awk 配方。例如 `before_after/SKILL.md` 里直接写：
```bash
awk -F'\t' '$2==">" && $3=="Express_intent_to_meet_or_negotiate" {print}' database/$D/data.txt > /tmp/seq.txt
```

**完整走一遍**（问："After Ethiopia, which countries did Eritrea express intent to negotiate with?"）：
1. **qtype 路由**：SKILLS.md 决策树 → 有枢轴(Ethiopia) + 无 first/last → 选 `before_after`。`cat` 它的 SKILL.md + NAVIGATION.md。
2. **绑定**：`grep -i Eritrea _catalog.tsv` 取目录 `$D`；`grep -iE "negotiat" _relations.txt` → `Express_intent_to_meet_or_negotiate`；方向 `>`。
3. **取证**：awk 过滤出该关系全序列 → 找 Ethiopia 行的日期当 `t0` → `awk '$1>t {print $4}' | sort -u`。
4. **作答**：`FINAL: <下划线还原空格的国家列表>`。

→ 看清楚了吗：**全程没有"钻目录树"**。第 1 步是查表，第 3 步是单文件 awk。这是 **text-to-query**，不是 navigate。

### 1.4 多大程度符合"用 Unix 原生能力分层导航"的初衷？

| 子目标 | 评分 | 说明 |
|---|---|---|
| 用 grep/awk 当执行引擎、不 cat 整文件 | ✅ **9/10** | 真的只用 shell 原语，靠 build.py 投影把暴力 grep 降成"查表+ego 文件 awk"。**这部分没走老路。** |
| **分层**导航（多级目录逐级钻取） | ❌ **2/10** | 只有"catalog→ego 文件"两跳扁平结构，没有任何层级下钻。 |
| 摆脱硬编码规则 | ⚠️ **4/10** | 关系映射是 NAVIGATION.md 里**手写的散文**（251 个关系只手映了 ~10 个）；visit 还专门打了补丁。换数据集就废。 |

> 结论：**没走"全文暴力 grep"的老路（好），但也没走到"分层导航"（论文核心），停在了"扁平查表"——
> 而且关系映射这一块是实打实的硬编码散文，泛化性差。**

---

## 2. 🚨 核心方向对齐检查（Alignment Check）

| # | 论文学术卖点 | 现状评分 | 判定 |
|---|---|---|---|
| 1 | **文件系统多级目录做头实体聚类路由（<100 类）** | 🔴 **1/10** | 只有 34 个字母桶且不参与路由；Agent 走扁平 catalog 查表。**论文的招牌机制基本没实现。** |
| 2 | **过程技能：渐进披露 + 参数化** | 🟡 **5/10** | 渐进披露：**文档层**做到了（SKILLS→SKILL→NAVIGATION）；**数据层**没有（不钻 INDEX→年→事实）。参数化：awk 用 `$D/REL/t0` 变量，但配方里嵌死了具体关系码当例子，关系映射靠手写散文，**v3 capability schema 是草稿没 rollout**。 |
| 3 | **Shell 序列具备回溯 + 时间窗口松弛兜底** | 🟡 **4/10** | 回溯：NAVIGATION.md 写了 4 档预算（换关系族/翻方向/换实体/放宽粒度），但实测 0.04–0.12 次/题，**形同虚设**；时间窗口松弛**只有一句口号，没有真配方**（无"精确日期查不到就 ±N 天/月扩窗"的实现）。 |
| 4 | **留出自我反思接口（非 ReAct 一条道）** | 🔴 **2/10** | 纯 ReAct 单循环，无 plan、无持久 state、无反思节点。REPORT.md 自己也承认"无 planning/无持久 state/无真反思"。 |

**对齐总评**：4 项学术卖点里，**3 项基本没落地（1/3/4），1 项半落地（2）**。
你做到顶尖的是**评估诚实性**（三重 oracle 泄漏诊断、facet-blind 协议、配对 McNemar、失败分类器校准）——
**但那是"方法论严谨度"的贡献，不是论文主张的"navigation 范式"贡献。** 两者别混为一谈。

---

## 3. ⚠️ 致命缺陷与未竟工作（Gaps & Shortcomings）

### 3.1 已写出来但"不对/硬编码/泛化差"的

| 问题 | 位置 | 为什么是坑 |
|---|---|---|
| **关系映射是手写散文** | `NAVIGATION.md` 第 1 步 | 251 个关系只手映 ~10 个，靠 prose 启发 Agent。换数据集/换关系体系直接失效。**这是当前 #1 失败源（relation/direction 绑定占失败 53–60%）的根因。** |
| **visit 专项补丁** | `NAVIGATION.md` visit 规则 | 用一大段散文 hack 单个关系（Make vs Host + 方向），是"缺系统性关系族/方向投影"的症状，不是解法。 |
| **首字母分桶冒充聚类** | `build.py: bucket_of()` | 34 个字母桶既非语义、又不参与路由，是死代码级别的"伪层级"。 |
| **qtype 路由 = 语义解析器** | `SKILLS.md` + 5 skill | 按"问题类型"套模板，本质 text-to-query，不是按"实体在图中的位置"导航。论文明确要从过程型转信息型，你反向走了。 |
| **parse 前端**（已否决，留着会误导） | `exp_parse.py` | 你自己已证它净负（77%<81%），硬标签会压制 Agent。**应在报告里明确标注为死路，避免后人重蹈。** |

### 3.2 TKGQA 任务该有、但**完全没做/被遗漏**的核心逻辑

| 缺失项 | 状态 | 影响 |
|---|---|---|
| **时序切片（temporal slicing）** | ❌ 完全没做（build.py 明确"不切年"） | 这本是 TKG 上**最自然的分层导航轴**（实体→年→月→事实），正好对应论文的"逐级钻取"。不做=放弃了把论文落到 TKG 的最佳着力点。 |
| **关系族映射（relation-family）作为离线产物** | ❌ 没有（只有手写散文） | 应离线把 251 关系聚成族 + 标准方向语义，生成 `_relation_families.tsv`，让绑定步骤查表而非靠 prose。**直接对应论文的"离线 cluster-summarize"，且直击你测出的真瓶颈。** |
| **双向冗余** | ✅ **已做且做得好** | 唯一一个真正对齐论文精神的 TKG 适配。 |
| **多答案完整性**（before_after/multi_answer 返回全部而非子集） | ❌ 未治（你 n=300 测出的最大可测瓶颈：entity 73% vs time 99%；before_after 57%） | 真正影响 accuracy 的洞，但混有 gold/题面噪声，真实空间 < 名义 gap。 |
| **自反思/规划接口** | ❌ 没有 | 论文卖点之一，架构上完全没留口子。 |

---

## 4. 🗺️ 紧迫的下一步行动指南（Next Steps）

### 4.0 先做一个方向决策（这决定 Top 3 的排序）

你现在站在岔路口，两条路的学术故事不同，**别两头都抓**：

- **路线 A（提分 + 部分对齐，务实）**：承认"离线投影让 TKGQA 只用 shell 原语即可"的故事（你 REPORT 已论证扎实），
  下一步攻**关系族投影**（治真瓶颈 + 去硬编码 + 对应论文离线 summarize）。**风险低、有数字、能写。**
- **路线 B（真正复刻 navigation 范式，对齐满分但更重）**：把 build.py 升级成**实体→关系族→时序切片**的多级目录树，
  让 Agent 真的"钻取+回溯"。**这是论文的灵魂，novelty 最高，但 6 类 qtype 的 benchmark 上 accuracy 收益不确定（实体路由本就不是瓶颈）。**

> **我的推荐：先 A 后 B。** 用 A 的关系族投影立刻止血（既提分又去硬编码又沾论文边），
> 同一个产物又能当 B 的第二级目录。**A 是 B 的地基，不浪费。**

### Top 3 优先级

| 优先级 | 行动 | 为什么是它 | 对齐/提分 |
|---|---|---|---|
| **P1（本周）** | **离线生成关系族投影 `_relation_families.tsv`**：把 251 关系聚成族（visit/sign/negotiate/appeal/criticize…）+ 每族标准方向语义，改 `build.py` 产出；`NAVIGATION.md` 的手写散文改成"查这张表"。 | 直击 #1 失败源（relation/direction 绑定）；消灭最大硬编码；对应论文离线 cluster-summarize。**唯一一个同时治 accuracy + 治对齐 + 治泛化的动作。** | 提分🟢 对齐🟡 |
| **P2** | **给 build.py 加时序切片层**：大实体生成 `INDEX.md → 年目录/年内 data`，让 Agent 真正逐级钻取（实体→年→事实）+ 实现"时间窗口松弛"真配方。 | 这是 TKG 上论文 navigation 的正统落地；把"扁平两跳"变"真分层导航"。 | 提分🟡 对齐🟢 |
| **P3** | **加一个反思/回溯触发节点**：serve 循环里，空结果或多候选时插入一次"自检"轮（不是 plan-everything，是轻量 reflect-on-empty）。 | 补论文卖点 4；把"写了不触发的回溯"变成"真会回溯"。 | 提分🟡 对齐🟢 |

### 第一步：具体改哪个文件 + 给 Claude Code 的明确指令

**改 `E:\TKGQA_Experiment1\build.py`**（而不是先重构 SKILL.md——SKILL.md 的散文是症状，投影缺失才是病根）。

> **给 Claude Code 的指令（可直接粘）**：
> "在 `build.py` 里新增一个离线阶段，读 `_relations.txt` 的 251 个关系码，按词法/前缀+可选 embedding
> 聚成 ≤30 个**关系族**，每族给一个规范族名、成员关系码列表、以及该族的**标准方向语义**
> （谁是施动者=head）。产出 `database/_relation_families.tsv`（列：family \t canonical_direction \t member_codes）。
> 保持纯确定性优先（先做词法聚类版本，embedding 作为可选开关），幂等，不破坏现有 data.txt/catalog 产出。
> 然后把 `skills/_shared/NAVIGATION.md` 第 1 步的手写关系映射散文，替换成'grep `_relation_families.tsv`
> 取族 + 方向'的查表流程。改完用现有 `exp_subset.py` 在 visit / before_after 子集上跑同题配对 McNemar，
> 证明绑定准确率提升（而非靠整体涨点这种噪声）。"

**先别动的**：`agent_nav.py` 的 qtype 路由（你已证 routing 不是瓶颈）、`exp_parse.py`（已否决的死路）、
v2/v3 schema rollout（你明确暂缓）。

---

## 5. 一句话总结给项目负责人

> **你把"评估诚实性"做到了审稿人会点赞的水平，但论文的招牌——"分层拓扑导航 Deep Agent"——目前没做出来，
> 现在是个干净的扁平查表式语义解析器。想对齐论文 + 提分，第一刀砍向 `build.py` 的关系族投影：
> 它一箭三雕（去硬编码、治真瓶颈、沾上论文的离线 summarize 思想），且是后续时序分层导航的地基。**
