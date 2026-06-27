# TKG2Skill 系统诊断与迭代路线

> 日期 2026-06-26 · 研究型系统审计 · 基于代码与真实运行行为, 不依赖先验假设
> 配套: `AUDIT_2026-06-26.md`(状态审计)。本文聚焦诊断 + 渐进改进 + 实验重设计 + 重定位。

---

## 1. 系统理解(基于代码重新建模)

### 1.1 真实架构
喂给系统的不是「一个问题」,而是「问题 + 3 个 gold 元数据」(`agent_nav.py:92`):
```python
user = f"问题: {question}\nqtype: {qtype}\nanswer_type: {answer_type}\ntime_level: {time_level}\n..."
```
于是真实数据流是:
```
(question, gold_qtype, gold_answer_type, gold_time_level)
   │  gold_qtype  →  确定性选中 5 个 recipe 之一 (LLM 只是 cat 文件)
   │  gold_answer_type → 已告知抽实体列还是时间列
   │  gold_time_level  → 已告知时间粒度前缀 P(day/month/year)
   ▼
LLM 的真实工作 = 槽位绑定(slot-filling):
   anchor 实体短语 → catalog 目录(10,488 实体里选 1)
   谓词短语 → 关系编码(251 个里选 1)
   方向 >/< · pivot/other 实体
   ▼
拼出一条 awk → 单只读 bash 执行(run_bash :60-78)
   数据已离线投影(按时间升序 + 双向冗余 + per-entity ego file)→ awk 近乎平凡
   ▼
FINAL 抽答案
```

### 1.2 各层真实作用
- **routing**: 真实作用 ≈ **空**。qtype 是 gold 直接给的,路由退化为「按已知类名 cat 对应文件」。它不解析问题,不做决策。
- **skill**: 真实作用 = **一张参数化 awk 模板 + 槽位绑定说明**(一种受约束解码脚手架)。它不是「能力」,而是「qtype 标签的 1:1 配方」——5 个 skill 恰好等于 5 类 qtype。
- **execution(bash/awk)**: 真实作用 = **确定性抽取器/验证器**,在预建索引上跑。它不推理,几乎不出错(失败分类里 execution_error=0)。数据预投影把它的难度抽干了。

### 1.3 它本质是哪类 AI system
**不是 agent,也不是 Deep Agent。** 它是一个
**「执行引导的结构化查询合成管线(execution-guided structured-query synthesis)」**——
本质上与 **text-to-SQL / 神经语义解析** 同构:
- 「skill 库」= 手写的查询模板文法(grammar of query templates);
- 「文件系统 + awk」= 执行引擎;
- ReAct 循环只是外壳(实测 avg 7 命令、回溯 0.07/题,分支极低,接近一条直线管线)。

> 一句话定性: **它穿着 agent 外衣的语义解析器(semantic parser in agent's clothing)**,
> 且当前连解析的前半段(qtype/answer_type/time_level)都是 gold 喂的。

---

## 2. 问题诊断(按"对结果影响"排序)

### P0 — 评估被「三重 oracle 泄漏」抬高(最致命,决定一切数字的含义)
qtype + answer_type + time_level **三个 gold 信号全部喂入**。后果:
- 路由(选哪类)未被测;
- 答案类型选择(抽实体还是时间)未被测;
- 时间粒度(P)未被测——对占比最大的 `equal`(17,311 题)尤其关键,P 直接决定 substr 前缀。

所以 **85% e2e 是「在已知问题类型、答案类型、时间粒度三个条件下」的成绩**,系统性高估了独立能力。
这是**影响结果最大的问题**:它让"验证了 skill-based KGQA"这一主张失真——实际只验证了
"给定查询类型/答案类型/粒度后,槽位绑定 + 抽取能否做对"。

### P1 — routing 是 oracle 不是 router(P0 的子项,用户单独问)
routing_acc 97% = `cat 由 gold qtype 命名的文件`。无任何证据表明系统能从问句**自行**路由。
真实路由能力 = **未知**。

### P2 — 失败分类器本身有偏(评估工具尚不可信,实测已证)
抽样两条被判 `temporal_reasoning_error` 的题,真实错因并非时间推理:
- *"China threaten last before Taiwan military"*: gold=Angela Merkel, pred=Iran —— 更像 **pivot/关系绑定错**;
- *"which month UAE received visit from China"*: gold=2010-03, pred=2012-08;2015-01 —— 更像 **Host_a_visit vs Make_a_visit 关系错 / 数据分区错**。

`exp_eval.classify_failure` 把「temporal qtype 上答错」一律归 temporal,**高估了 temporal、低估了 relation/entity**。
→ 在该分类器经人工校验前,"11–12/15 是 temporal"这个结论**不可信**。

### P3 — skill 设计: 抽象度低、不可组合、与 qtype 冗余
- **抽象度**: 停在 awk 层,不是能力层。skill 名 = qtype 名,是「贴着标签的配方」。
- **覆盖性**: 闭世界,只覆盖这 6 类 qtype;任何超出的问句无 skill 可走。
- **可组合性**: 执行层**零组合**。多跳("same month as X")被硬写进 `equal` 配方 B 段,而非 skill 组合。
→ 当前"skill library"≈ "对 gold qtype 的 switch 语句"。

### P4 — execution 不是瓶颈(反直觉的反证)
0 execution_error;数据预排序 + 双向冗余使 awk 一旦槽位填对就近乎必中。
**瓶颈在上游绑定**: 10,488 实体的模糊 NL→规范名解析、251 关系的谓词→编码映射。
→ **不要优化 execution**;优化点在 entity/relation resolution。

---

## 3. 渐进式改进路线(每步最小改动、每步可验证)

> 原则: 在"评估诚实"之前,任何能力提升都不可信。故 Stage 1 是强制前置。

### Stage 1 — 让评估变诚实(不加能力,只去泄漏 + 校准量具)
**最小改动**:
1. `exp_runner` 增 `--blind-facets`: 不仅抹 qtype,**同时抹 answer_type、time_level**(当前 blind 只抹了 qtype,不够)。
2. 人工标注 ~30 个失败,测 `classify_failure` 与人工的一致率,修掉 temporal 过归因(在判 temporal 前先查"关系/pivot 是否绑定正确")。
- **解决**: P0/P1/P2。 **能力提升**: 故意为零。 **价值**: 让后续每个数字可信。
- **验证**: 报告 oracle vs facet-blind 的 e2e 落差(预期明显下降);报告分类器对人工标注的精度(目标 >0.8)。

### Stage 2 — 补上真正的解析/路由前端(把泄漏用"组件"补回,而非靠喂)
**最小改动**: 新增**一个** `parse` skill —— 仅凭问句预测 (qtype, answer_type, time_level)。
5 个执行 skill **完全不动**。
- **解决**: 把 oracle→real;路由与答案类型选择从此**可独立测量**。
- **能力提升**: 系统在推理期**不再依赖任何 gold 元数据**,变成自洽端到端。
- **验证**: 独立报告 parse 准确率(预测 facet vs gold);报告 "parse→execute" 的 blind e2e 与 oracle 上界的落差 = 前端代价。

### Stage 3 — 让 skill 脱离 qtype: 引入最小可组合能力层
**最小改动**: 把 5 个 qtype-skill 归约为 2 个原语 +组合(按 `SCHEMA_v3_capability`):
`locate(anchor, rel, dir, time-op)` 与 `select_position(seq, op, pivot)`,
用组合表达 6 类 qtype。**先只对多跳子集("same X as Y")落地组合**,其余维持原状。
- **解决**: P3(抽象/组合);检验 skill 到底是"真能力分解"还是"qtype 改名"。
- **能力提升**: 多跳/新组合问句变得可达;错误可归因到"组合阶段"。
- **验证**: 在多跳子集上比 组合式 vs 单体配方 的准确率 + 分阶段错误归因。

---

## 4. 更可信的实验结构

### 4.1 oracle vs blind 仍然必要——但要升级
- 当前 blind 只抹 qtype,**不够**。改为 **facet-blind**(抹 qtype+answer_type+time_level)。
- **两者都跑、都报**:
  - oracle = 给定完美解析时, 执行段能力的**上界**;
  - facet-blind = 真实端到端;
  - 二者落差 = 解析/路由段损耗。这把总损耗干净拆成 [解析段] + [执行段]。

### 4.2 routing error vs execution error 的拆分
需要 Stage-2 的 parse 组件存在,才有"路由预测"可比。然后用 **2×2 归因**:
| | 执行正确 | 执行错 |
|---|---|---|
| **解析正确** | 真命中 | **execution error**(槽位绑定/位置选择错) |
| **解析错** | 偶中(应记为 routing error) | **routing/parse error**(下游不再追究) |
定义: parse error = 预测 facet ≠ gold facet(**独立于最终答案**,可单独测);
execution error = facet 全对但答案错。两者从此互斥可加。

### 4.3 衡量 skill 本身的贡献(消融)
建议一个 **2×2×2 网格**,干净隔离三段贡献:
- 维度 A `facets ∈ {oracle, blind}` —— 解析段贡献;
- 维度 B `skill ∈ {on, off}` —— off = 只给 catalog/_relations + 问句、无配方,测"配方"增益;
- 维度 C `slots ∈ {oracle, predicted}` —— oracle = 直接喂 gold 实体目录 + 关系编码,把**绑定**从**执行**里剥离,上界化"更好的 binding 能买到多少"。
关键对照: `skill-off` 基线量化模板贡献;`slots-oracle` 上界量化绑定瓶颈(对应 P4)。
另设 `wrong-skill` 控制(强制错配方)测配方的约束强度。

---

## 5. 自由重定义(研究定位)

### 5.1 当前隐含定位 vs 代码现实
- **隐含定位**(METHOD.md/叙事): "导航 TKG 的 Deep Agent / skill-based KGQA"。
- **代码现实**: **执行引导的、模板文法约束的、对离线预投影 KG 索引的查询合成**;路由是 oracle,agency 极弱。
两者不一致——继续用"Deep Agent"会被审稿一击即破(无 planning/持久 state/真实 reflection;且三重 gold 泄漏)。

### 5.2 更合理的 research framing(建议)
把卖点从"agent 导航"换成**"离线投影把 serve 期推理负担抽干"**——这正是论文
"Don't Retrieve, Navigate"的真精神,且是代码**真正做到**的事:

> **研究问题**: 当把一个 TKG 离线投影成「按时序排好 + 双向冗余 + per-entity ego 文件」的
> 可导航索引后,serve 期是否能**仅用通用 shell 原语(grep/awk)、无图数据库/无 SPARQL/无向量库**
> 完成 TKGQA?各项投影结构(排序 / 冗余 / ego 切分)各自减轻了多少 serve 期负担?

这个 framing 的好处:
- **可证、可消融**: 贡献是"把工作从推理期搬到离线结构化",用 4.3 的 `slots-oracle` / `skill-off` 网格直接量化每个投影属性的增益。
- **诚实**: 不主张 agent 智能;主张"结构化预处理 + 轻量查询合成"。
- **对齐数据**: 真正难的是 10k 实体绑定 + 251 关系映射(P4),framing 自然把研究重心引到这里,而非伪 agent 回溯。

### 5.3 这个系统更适合研究的问题
1. **离线 KG→可导航语料投影** 对 serve 期查询复杂度的影响(核心,build.py 是真贡献)。
2. **NL→典型化查询模板** 的可组合性(Stage 3 检验)。
3. **无专用图引擎的 KGQA** 可行性边界(哪些 qtype 能被 grep/awk 坍缩,哪些不能)。

> 一句话重定位: 这不是"会导航的 Deep Agent",而是
> **"用离线结构投影 + 模板化查询合成替代图引擎检索的 TKGQA 方法"**;
> agent 循环是实现细节,不是研究主张。把论文重心放到投影与查询合成的可验证增益上,
> 它就能从"看起来很强但泄漏严重"变成"主张克制但每步可证"的 research prototype。

---

## 附: 本轮新增的硬证据
- gold 三泄漏: `agent_nav.py:92`(qtype+answer_type+time_level)。
- 数据集: test.json 54,584 题; qtype 分布 equal 17311 / before_after 11073 / first_last 10480 / after_first 6266 / before_last 6247 / equal_multi 3207。
- KG 规模: 10,488 实体, 251 关系, 72 个大实体(>2000 条, 带 INDEX.md)。
- execution 非瓶颈: 失败分类 execution_error=0; 数据预投影使 awk 平凡。
- 分类器偏差: 抽样 2 条 temporal 误判实为 relation/pivot 错(见 §2 P2)。
