# S1 评估诚实化 — 结果与结论

> 2026-06-26 · 目标: 解决 P0(三重 oracle 泄漏) / P1(routing 是 oracle) / P2(分类器有偏)。
> 不加能力, 只让量具诚实。所有结论基于 `agent_nav_100.json` 真实轨迹, 离线可复现。

---

## ① facet-blind 模式 (解决 P0/P1 的**测量手段**)

`exp_runner.py` 的 `--routing-mode` 升级为 `--reveal`, 控制喂给 Agent 的 gold 元数据子集:

| 命令 | 喂入 | 含义 |
|---|---|---|
| `--reveal all` | qtype+answer_type+time_level | = 旧 oracle (现状) |
| `--reveal none` | 无 | **全盲**: Agent 须自行从问句推断类型/答案类型/粒度 |
| `--reveal answer_type,time_level` | 盲 qtype | 单独测路由 |

trace.meta 记录 `revealed_facets` 与 `routing_mode`, eval 报告自动标注。

### 实测结果 (2026-06-27, n=100, 两臂同一份修好的 plumbing)

| | **oracle** (reveal all) | **blind** (reveal none) | 落差 |
|---|---|---|---|
| **e2e (robust)** | **91%** | **81%** | **-10pt** = 三重 facet 泄漏的真实价值 (P0) |
| **routing acc** | 97% (上界) | **88% (真实!)** | routing_loss 3%→12% (P1) |
| nav_loss \| routing对 | 9.3% | 18.2% | — |

> **结论 P0**: 去掉 qtype+answer_type+time_level 三个 gold 信号, e2e 从 91% 掉到 **81%**。
> 即真实端到端(无任何 gold 元数据)是 **81%**, 而非之前报告的 89%。10 个点就是脚手架价值。
>
> **结论 P1**: 真实路由能力 = **88%**, 不是 oracle 的 97%。路由错集中在**相邻时序类型**:
> `first_last→before_last` (6 次)、`before_after→after_first` (4 次) —— 即 "first/last" 与
> "枢轴前后" 的混淆。`equal`/`first_last` 路由稳。

### 隐藏 bug 修复 (本轮副产品, 影响所有历史数字)
`agent_nav.run_bash` 的 `subprocess.run(text=True)` 在 Windows 默认按 GBK 解码 bash 输出,
遇到变音字符实体(Abdullah Gül / Aïchatou… KG 里大量)直接抛 UnicodeDecodeError → 证据行损坏。
已加 `encoding='utf-8', errors='replace'`。**影响量化: oracle robust 从旧 86%(buggy) → 91%(fixed), +5pt。**
故旧 `agent_nav_100.json` 的 85/86% 是被该 bug 压低的脏数; 新 `traces_oracle_100.json` 才是干净基线。

### facet 泄漏对各 qtype 的价值 (oracle→blind robust 落差)
| qtype | oracle | blind | Δ |
|---|---|---|---|
| after_first | 100% | 75% | -25% |
| equal_multi | 100% | 67% | -33% (n=3, 噪声大) |
| before_after | 75% | 55% | -20% |
| before_last | 83% | 75% | -8% |
| first_last | 100% | 96% | -4% |
| equal | 94% | 90% | -3% |
→ facet 主要在**枢轴/位置类**(after_first/before_after)上撑分; equal/first_last 对盲态稳健。

---

## ② 分类器人工校准 (解决 P2)

逐条人工读了**全部 15 个失败**的轨迹 (`failure_annotations.json`), 得到 ground truth, 并据此重写分类器。

### 颠覆性结论
1. **原 `temporal_reasoning_error` 桶 100% 是伪命中**: 人工核验 **0/15** 真为时序推理错。
   旧分类器把"时序 qtype 上答错"一律记 temporal → 系统性误导。
   旧/新启发式 vs 人工 **一致率 = 0%** (n=14) —— 启发式不可信, 故改**人工标注优先**。
2. **真实失败分布** (robust 重判后 10 个真模型失败 + 4 个非模型):
   | 类别 | 数 | 性质 |
   |---|---|---|
   | relation_direction_error | 6 | **模型错(主因)**: 关系码/方向, 尤其 Host vs Make、`>`/`<` |
   | entity_resolution_error | 3 | **模型错**: 锚/枢轴解析、路径漏 `database/` 前缀 |
   | answer_selection_error | 1 | **模型错**: 取到正确证据却输出别的 |
   | gold_or_question_issue | 4 | **非模型**: 问 "country" 但 gold 含人/组织, agent 合理过滤 |
   → **上游绑定 (relation/direction + entity) = 9/15 = 60%**, 印证 P4「瓶颈在绑定, 非执行」。
   → **temporal reasoning 真实占比 = 0**。
3. **eval 自身有假阴性**: robust 归一化(去 markdown `**`/标点)后, e2e **85% → 86%**
   (`equal` 90%→94%)。至少 1 题模型答对却被尾部 `**` 判错。
4. **约 1/3 "失败" 不是模型问题** (gold/题面冲突 4 + 打分假阴性 1 = 5/15)。
   说明真实 ceiling 比 86% 更高, 且部分错来自数据集"which country"措辞与 gold 集不一致。

### 工具改动 (exp_eval.py)
- 新 `FAILURE_CATS`: 增 scoring_artifact / gold_or_question_issue / answer_incompleteness /
  relation_direction_error / answer_selection_error / **needs_review**; 删 temporal 默认。
- `classify_failure` 改**保守版**: 只在高置信信号(robust 重判正确 / 路径错 / pivot-not-found /
  PRED⊊GOLD)下给标签, 否则 `needs_review`(诚实留白, **不再臆测 temporal**)。
- 新增 `recheck_correct` (robust 归一化重判) + 假阴性计数。
- 新增 `[6] Classifier Calibration`: 报告启发式 vs 人工一致率。
- `--annotations failure_annotations.json` 人工标注优先。

---

## ③ blind 81% 失败归因 (全部 19 个真失败逐条人工标, `failure_annotations_blind.json`)

| 类别 | 数 | 性质 | 是否盲态新增 |
|---|---|---|---|
| relation_direction_error | 5 | 模型错: Host vs Make、方向 `>`/`<` | 否(两臂都有) |
| gold_or_question_issue | 4 | **非模型**: "which country" 但 gold 含人/组织 | 否(数据噪声) |
| routing_error | 3 | 模型错: **before_after 误装 after_first**, 只回"第一个"而非全部 | **是(盲态独有)** |
| temporal_position_error | 3 | 模型错: 枢轴日期 t0 选错(过早/过晚) | 否 |
| entity_resolution_error | 2 | 模型错: 锚/枢轴解析、路径漏 `entities/` 前缀 | 否 |
| answer_selection_error | 1 | 模型错: 已取到正确证据却输出"无相关事实" | 否 |
| answer_incompleteness | 1 | 模型错: 方向对但过度收窄丢实体 | 否 |

**归因结论**:
- **上游绑定仍是主因**: relation/direction 5 + entity 2 + temporal-pivot 3 = **10/19 (53%)**, 两臂共有, 再次印证 P4。其中 **Host_a_visit vs Make_a_visit** 与方向 `>`/`<` 反复出现 (≥5/run)。
- **routing 是盲态唯一新增的失败模式 (3/19)**, 全是 `before_after→after_first` —— 装错 skill 导致返回**基数错**(回 1 个而非全部)。这正是 91%→81% 落差里**路由段那一份**(~3pt)。
- **约 21% (4/19) 不是模型问题** (gold/题面冲突), 两臂都有, **不解释 oracle→blind 落差**。
- 启发式 vs 人工一致率 blind **21%** (oracle 0%): 保守分类器能靠"路径错/子集/打分"高置信命中一部分, 仍需人工兜底。

### 对 S2 的直接含义 (用证据决定下一步投入)
oracle→blind 的 10pt 落差里:
- `parse` skill (预测 qtype/answer_type/time_level) **只能收回 routing 那 ~3pt** (修 3 个 routing_error), 让系统不再依赖 gold、路由变真。**必要, 但不是 accuracy 大头。**
- 真正的 accuracy 漏点是 **relation/direction 绑定** (Host/Make + 方向), 它在 oracle 和 blind **都**是最大单一模型失败 (~5-6/run), `parse` 碰不到它。

> 即: **S2(parse) 解决"诚实/自洽"(P1 收尾), 但要提 accuracy 得单独治 relation/direction 绑定。** 两者目标不同, 别混。

## 对之前数字的修正 (诚实化后)
| 指标 | 旧说法 | S1 修正后 |
|---|---|---|
| e2e | 85% | **86% (robust)**; 真实 ceiling 更高 (含 gold 噪声) |
| 失败主因 | temporal 11–12/15 | **relation/direction 6 + entity 3** (绑定 60%); temporal **0** |
| routing | 97% | 仍是 **oracle 上界**; 真值待 `--reveal none` 跑出 |
| 分类器 | 当真 | **不可信 (一致率 0%)**, 已改人工标注优先 |

## 下一步 (S1 收尾 → S2)
- 跑 `--reveal none` 与 `--reveal answer_type,time_level`, 填上 P0/P1 的真实数字。
- 失败样本扩到 ~30 (跑更大 n 或并集多次运行), 复核 relation/direction 是否仍主导。
- 然后进 S2: 加 `parse` skill 把三个 facet 从"喂"变成"模型自推"。
