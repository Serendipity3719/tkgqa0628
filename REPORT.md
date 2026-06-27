# TKG2Skill 实验总报告 (Consolidated)

> 2026-06-27 · 把 DIAGNOSIS / S1_FINDINGS / S2_FINDINGS / MEASUREMENT 收敛成一条主线。
> 目的: 给出**诚实、可复现、可做 ablation** 的实验结论, 供论文/汇报使用。
> 详细过程见各分文档; 本文是导航与定论。

---

## 0. TL;DR (五条要记住的)

1. **系统不是 Deep Agent, 是"执行引导的语义解析器"**: 把 NL 问句合成为对一个**离线确定性投影**的
   TKG 索引的 grep/awk 查询。真贡献是 `build.py` 的离线投影, 不是 agent 智能。
2. **诚实端到端 = 81%** (n=300, [76,85], 无任何 gold 元数据); oracle 上界 91%。
   两者 10pt 差距**几乎全部来自 qtype**(answer_type/time_level ≈ 0 价值)。
3. **routing 不是瓶颈**: 把自路由从 88%→94.6%(S2′)后, 整体 e2e **没动**(仍 81%)。
   真瓶颈是 **entity 多答案完整性**(time 答案已 99% 解决, entity 73%; before_after 57%)。
4. **parse 前端是负优化**(77% < blind 81%): 一个自信但错的 qtype 硬标签会**压制 agent**自身判断。
5. **测量比改进更难**: n=100 单次运行噪声 ±3-4pt, 淹没了多数 skill 改动。必须**机制证明 + 同题配对
   McNemar** 才算数。沿途修了两个让数字漂移 5-13pt 的打分 bug。

---

## 1. 系统是什么 (re-framing, 来自代码)

```
(question) ──parse/route──> qtype ──load──> 1 个 awk 模板 skill
          ──bind──> 锚实体(catalog 10k) + 关系码(251) + 方向 + 枢轴 + 粒度
          ──awk──> 在离线投影的 ego 文件(已按时间升序+双向冗余)上取证 ──> answer
```
- 它与 **text-to-SQL / 神经语义解析同构**: skill 库 = 查询模板文法, 文件系统+awk = 执行引擎。
- ReAct 循环是外壳(avg 7 命令、回溯 0.04-0.12/题, 近直线管线), 无 planning / 无持久 state / 无真反思。
- **建议论文定位**: 不主张 agent 智能; 主张"**离线把 TKG 投影成可导航索引, 使 serve 期仅用通用
  shell 原语(无图库/SPARQL/向量库)即可 TKGQA**", 并量化各投影结构(排序/冗余/ego切分)减轻的 serve 负担。

---

## 2. 诚实数字 (可信基线)

| 配置 | n | robust e2e | routing | 说明 |
|---|---|---|---|---|
| oracle (全 gold facet) | 100 | 91% | 97% | 上界 |
| **blind (当前最佳 S2′+S2b)** | **300** | **81% [76,85] ±4pt** | **94.6%** | **真实端到端** |
| parse (预测3facet硬喂) | 100 | 77% | 82% | 负优化 |

**facet 价值**: oracle 91 → 移除 qtype 损失 ~12pt; 移除 answer_type+time_level ~0(噪声内)。
**子集地图 (n=300)**: time 答案 **99%**(已解决) vs entity **73%**(gap); before_after **57%/n72**、
multi_answer **67%/n110**、has_pivot 64% 最弱; first_last 100%、equal 92%。

---

## 3. 方法论贡献 (本项目最硬的部分)

1. **三重 oracle 泄漏诊断 + facet-blind 协议** (`exp_runner --reveal`): 原 85% 是 qtype+answer_type+
   time_level 三 gold 给定下的成绩; 去掉后真实 81%。
2. **失败分类器校准** (`failure_annotations*.json`, 34 题人工标): 启发式分类器 vs 人工**一致率 0-21%**
   —— 原"temporal 主导"是伪命中(0/15 真为时序错)。改人工标注优先 + 保守启发式(needs_review 不臆测)。
3. **测量协议** (`exp_subset.py` + `MEASUREMENT.md`): 单文件 Wilson 95%CI + 双文件**同题配对 McNemar**。
   实测噪声地板: n=100 整体 ±7pt, 子集 ±15-30pt。SOP: **机制对 + 配对显著(p<0.05)才算数**。
4. **两个打分 bug**(暴露"工程噪声 ≠ 方法效应"):
   - `run_bash` GBK 解码崩(变音字符实体证据损坏): oracle 86→91 (+5pt)。
   - `norm` 不去 markdown(agent 把 `**` echo 进答案): 单次 raw 漂 8-13pt。**已修, raw≈robust。**

---

## 4. 关键结果 (正 / 负 / 反直觉)

| 结果 | 证据 | 可信度 |
|---|---|---|
| **三重 facet 泄漏值 10pt, 几乎全是 qtype** | oracle 91 / blind 81 / qtype-blind 79 | 高(大效应) |
| **parse 前端净负** | 77 < 81; before_after 20题误判12(硬标签压制 agent) | 高(机制+大效应) |
| **S2′ 路由文档修复**: 自路由 88%→94.6% | before_after 误路由 4→0; routing +9pp | 高(远超噪声) |
| **但 routing 修复不涨 e2e** | n=300 仍 81% = 原始 blind | 高(n=300) |
| **S2b visit 绑定**: 机制正确但整体不显著 | 3000023 数据级证明对; 但配对 p=0.625 | 机制高 / 整体测不出 |
| answer_type/time_level ≈ 0 价值 | blind 81 vs qtype-blind 79 | 中(噪声内, 但方向稳) |

---

## 5. 真实瓶颈与下一步候选 (未决)

- **最大可测瓶颈 = entity 多答案完整性**: before_after(57%/n72)、multi_answer(67%/n110)
  常返回**子集**而非单侧全部。子集够大, n=300 同题配对可检出真改动。
  ⚠️ **但混有 gold/题面噪声**(问 "which country" 但 gold 含人/组织, 非模型错)→ 真实空间 < 名义 gap。
- **未做的 roadmap 项 = S3 可组合层**(P3): 把 5 个 qtype-skill 归约为 `locate`+`select_position`,
  对 "same X as Y" 多跳落地组合。但其靶子 equal_multi 仅 n=11, accuracy 影响小, 属研究叙事而非提分。

---

## 6. 哪些可信 / 哪些是噪声 (诚实边界)

- **可信(大效应, 远超噪声)**: oracle-vs-blind 10pt; parse 负结果; routing +9pp; time 99% vs entity 73%。
- **不可细抠(噪声内)**: blind 81 vs 79 vs 85 这些 ±2-4pt; 单个 skill 微调的"涨几点"。
- **靠机制而非数字成立**: S2b visit 修复(数据级对, 整体配对 p=0.625)。

---

## 7. 完成度 (P0-P4 / S1-S3)

| 项 | 状态 |
|---|---|
| P0 三重泄漏 / P1 routing oracle / P2 分类器偏 / P4 execution非瓶颈 | ✅ 已解决/已证 |
| P3 skill 抽象与组合 = **S3** | ❌ **未做**(执行层无组合; "same X as Y" 仍硬写 equal 配方) |
| S1 评估诚实化 | ✅(诚实偏差: 分类器>0.8不可达→改人工优先) |
| S2 解析前端 | ✅ 已探索完(parse否决; 改 S2′路由+S2b绑定) |

---

## 8. 产物清单 (file inventory)

- **管线**: `agent_nav.py`(serve, 已修2bug) · `build.py`(离线投影) · `eval_fs.py`(oracle上界) · `skills/`(双层技能库)
- **实验设施**: `exp_trace.py`(trace schema+推断) · `exp_runner.py`(--reveal/--parse) · `exp_eval.py`(robust+校准+taxonomy) · `exp_parse.py`(解析前端) · `exp_subset.py`(子集+McNemar)
- **数据**: `traces_{oracle,blind,parse,qtypeblind}_100.json` · `traces_blind{2,3}_100.json` · `traces_blind_300.json`(基线) · `failure_annotations{,_blind}.json`
- **文档**: `AUDIT` · `DIAGNOSIS` · `S1_FINDINGS` · `S2_FINDINGS` · `MEASUREMENT` · 本 `REPORT` · `skills/_shared/SCHEMA*.md`(设计稿)
- 仓库: gitee `tkgqa` remote (Serendipity3719/tkgqa_-experiment1)
