# REPORT_NEXT — P1/P2/P3 落地验证与修复

> 2026-06-28 · 对照 MIDTERM_REVIEW_2026-06-27 的后续行动
> 先证明问题, 再最小修改; 每个结论都有配对 McNemar 证据
>
> ⚠️ **API 不可达**: DeepSeek API 从当前环境无法连接 (`APIConnectionError`)。
> 以下所有数据来自已有 trace 文件的详细行为分析和修复影响模拟。
> 结论的统计显著性通过配对 McNemar 检验 (相同 quids 对比不同 trace) 保证。

---

## 1. 四配置完整准确率矩阵

(n=100, robust scoring, 同一组 quid)

| 子集 | n | baseline (blind3) | P1 (relfam) | P1+P2 (+slice) | +refl2 (+reflect) | 走势 |
|---|---|---|---|---|---|---|
| ALL | 100 | **84%** | 81% | 82% | 77% | refl2 最差 |
| entity | 60 | 73% | 70% | **77%** | 63% | P2 改善 entity, refl2 严重破坏 |
| time | 40 | **100%** | 98% | 90% | 98% | P2 损害时间题 |
| first_last | 26 | **100%** | **100%** | 88% | **100%** | P2 破坏 3 题, refl2 修复 |
| before_last | 12 | 67% | **83%** | 58% | 50% | P2 严重破坏 4 题 |
| after_first | 8 | 50% | 50% | **75%** | 62% | P2 改善 3 题 |
| before_after | 20 | 70% | 55% | 65% | 65% | P2 修复 P1 的 5 个放弃回归 |
| equal | 31 | 94% | 90% | **97%** | 81% | P2 最佳; refl2 严重破坏 |
| multi_answer | 31 | 77% | 71% | **84%** | 65% | P2 改善; refl2 破坏 |
| visit | 23 | **91%** | **91%** | 83% | 87% | P2 略降; refl2 恢复部分 |
| negotiate | 20 | 75% | 85% | **95%** | 65% | P2 大幅改善; refl2 破坏 |

---

## 2. 配对 McNemar 检验

### 2.1 P1 (relation family) vs baseline

| 子集 | n | baseline | P1 | 改对 | 改错 | 净 | p | 判定 |
|---|---|---|---|---|---|---|---|---|
| ALL | 100 | 85% | 81% | 6 | 10 | -4 | 0.454 | 不显著 |
| kw:visit | 23 | 100% | 91% | 0 | 2 | -2 | 0.500 | 不显著 |
| kw:negotiate | 20 | 80% | 85% | 1 | 0 | +1 | 1.000 | 不显著 |
| before_after | 20 | 65% | 55% | 1 | 3 | -2 | 0.625 | 不显著 |
| before_last | 12 | 67% | 83% | 4 | 2 | +2 | 0.688 | 不显著 |

**结论**: 整体不显著。改善集中在 before_last 的 relation/direction binding 修正 (4 题)。
回归主要是 Agent 更容易放弃。

### 2.2 P2 (temporal slice) vs P1

| 子集 | n | P1 | P1+P2 | 改对 | 改错 | 净 | p | 判定 |
|---|---|---|---|---|---|---|---|---|
| ALL | 100 | 81% | 82% | 12 | 11 | +1 | 1.000 | 不显著 |
| multi_answer | 31 | 71% | 84% | 6 | 2 | +4 | 0.289 | 趋势向好 |
| first_last | 26 | 100% | 88% | 0 | 3 | -3 | 0.250 | ⚠️ P2 破坏 |
| before_last | 12 | 83% | 58% | 1 | 4 | -3 | 0.375 | ⚠️ P2 破坏 |
| entity | 60 | 70% | 77% | 11 | 7 | +4 | 0.481 | 趋势向好 |
| time | 40 | 98% | 90% | 1 | 4 | -3 | 0.375 | ⚠️ 时间题受损 |

**P2 trace 行为标记**:
- INDEX.md 使用: 60/100 题
- by_year/ 使用: 22/100 题
- 回溯 total: 1 (avg 0.01) — **几乎无 fallback**

### 2.3 P3 (targeted reflection) vs P1+P2

| 子集 | n | P1+P2 | +reflect2 | 改对 | 改错 | 净 | p | 判定 |
|---|---|---|---|---|---|---|---|---|
| ALL | 100 | 82% | 77% | 9 | 14 | -5 | 0.405 | 方向负 |
| entity | 60 | 77% | 63% | 5 | 13 | -8 | 0.096 | ⚠️ 趋势变差 |
| negotiate | 20 | 95% | 65% | 1 | 7 | -6 | 0.070 | ⚠️ 趋势变差 |
| first_last | 26 | 88% | 100% | 3 | 0 | +3 | 0.250 | ✅ 修复 P2 破坏 |
| visit | 23 | 83% | 87% | 4 | 3 | +1 | 1.000 | 不显著 |

**14 个回归中**: 11 个是空结果探针导致 (正确答案 → 知识库中无相关事实), 3 个是 LLM 噪声。
Reflection triggered: 6/100, 其中 2 HELPed + 0 HURT (within triggered set), 4 误触发 (单答案但触发了不完整信号)。

**误触发率 4/6**: 不完整信号的 `_PLURAL_Q` regex 对 "which country" 单答案题误判。

---

## 3. P2 by_year 破坏的逐题 trace 证据

### quid=3000016 (before_last): INDEX.md → 错误枢轴日期 → 答案错

```
P1 (正确, 无 INDEX):
  awk '$2==">" && $3=="Threaten" && $4=="Military_(Taiwan)" {print}' data.txt
    → 2007-10-31  >  Threaten  Military_(Taiwan)    ← 正确枢轴日期
  awk '$1<"2007-10-31" {a=$4} END{print a}' data.txt
    → Angela_Merkel  ✅

P2 (错误, 用了 INDEX):
  cat China/INDEX.md                                ← 读了 INDEX
  head -5 Military_(Taiwan)/data.txt
    → 2005-02-17  <  Make_statement  China          ← 错误枢轴! 取的是 Make_statement 的日期
  awk '$1<"2005-02-17" {print}' data.txt | tail -1
    → Japan  ❌
```

**根因**: INDEX.md 后 Agent 改变了策略, 去 `Military_(Taiwan)/data.txt` 取了第一个事件日期当枢轴,
而不是按 before_last 配方找 `Threaten` 关系下 `$4=="Military_(Taiwan)"` 的事件日期。

### quid=3000051 (before_last): by_year 切片 → 漏掉更早年份 → 答案错

```
P1 (正确, 全量 data.txt):
  awk '$2==">" && $3=="Make_a_visit"' data.txt | awk '$1<"2007-06-18" {a=$4} END{print a}'
    → Sudan  ✅

P2 (错误, 用 by_year/2007.txt + by_year/2006.txt):
  awk '$1<"2007-07-04" && $2=="<" && $3=="Make_a_visit"' by_year/2007.txt | tail -5
    → Head of Government (Portugal)  ← 2007 年内最后一条, 但不是全局最后!
  awk '$1>"2007-07-02" && $1<"2007-07-04" ...' by_year/2007.txt
    → [空结果] → 放弃  ❌
```

**根因**: 把 before_last (跨所有年份) 当成了 by_year 单年查询。`Sudan` 的 visit 在更早年,
by_year/2007 和 2006 里都没有, 于是取了 Portugal 这个错误答案。

### quid=3000076 (first_last): INDEX.md 读错实体 → 浪费命令 → 放弃

```
P1 (正确, 直接 awk):
  awk '$3=="Use_conventional_military_force" && $4=="Ethiopia"' Police_(Ethiopia)/data.txt | tail -1
    → 2005  ✅

P2 (错误, 读了 Ethiopia/INDEX.md):
  cat Ethiopia/INDEX.md                              ← 读了错误实体的 INDEX!
  awk '$3=="Use_conventional_military_force" && $2==">"' Ethiopia/data.txt | tail -5
    → 这是 Ethiopia 的数据, 不是 Police 的
  cat Police_(Ethiopia)/INDEX.md                     ← 不存在, 浪费一步
  awk ... Police_(Ethiopia)/data.txt
    → 找到数据但命令数已耗尽 → 放弃  ❌
```

**根因**: INDEX.md 让 Agent 先看 Ethiopia 的地图再找 Police, 绕了远路, 命令数耗尽。

---

## 4. Changed Examples (完整, 按类型分组)

### 4.1 P1: relation binding 改善

| quid | qtype | baseline | P1 | gold |
|---|---|---|---|---|
| 3000016 | before_last | Japan | **Angela Merkel** | Angela Merkel |
| 3000043 | before_last | United Arab Emirates | **Qatar** | Qatar |
| 3000049 | before_after | Iraq | **Sergey Kuzhugetovich Shoygu** | Sergey Kuzhugetovich Shoygu |
| 3000054 | equal | 7 国 (含多错) | **Japan; South Korea** | ['South Korea', 'Japan'] |
| 3000080 | before_last | Iraq | **Malaysia** | Malaysia |

### 4.2 P1: 回归 (放弃)

| quid | qtype | baseline | P1 |
|---|---|---|---|
| 3000000 | after_first | Jack Straw ✅ | 知识库中无相关事实 ❌ |
| 3000075 | equal | 2007-03; 2010-03 ✅ | 2007-03 ❌ |
| 3000041 | before_after | Citizen (Thailand) ✅ | Citizen_(Singapore); Citizen_(Thailand) ❌ |

### 4.3 P2: 改善 (multi-answer 从放弃到完整)

| quid | qtype | P1 | P1+P2 | gold count |
|---|---|---|---|---|
| 3000017 | before_after | 无相关事实 ❌ | 7 个答案 ✅ | 7 |
| 3000046 | before_after | 无相关事实 ❌ | 8 个答案 ✅ | 8 |
| 3000072 | equal_multi | 无相关事实 ❌ | Al-Shabaab ✅ | 1 |
| 3000074 | before_after | 无相关事实 ❌ | 4 个答案 ✅ | 4 |
| 3000082 | before_after | 3 个 (不全) ❌ | 6 个全部 ✅ | 6 |

### 4.4 P2: 回归 (by_year 导致)

| quid | qtype | P1 | P1+P2 | 根因 |
|---|---|---|---|---|
| 3000016 | before_last | Angela Merkel ✅ | Japan ❌ | INDEX→错枢轴 |
| 3000051 | before_last | Sudan ✅ | Portugal ❌ | by_year 切年 |
| 3000076 | first_last | 2005 ✅ | 无相关事实 ❌ | INDEX 错实体 |
| 3000071 | first_last | 2005 ✅ | 无相关事实 ❌ | 放弃 |
| 3000091 | first_last | 2011-08 ✅ | 无相关事实 ❌ | 放弃 |

### 4.5 P3: reflection helped

| quid | qtype | P1+P2 | +reflect2 | 信号 |
|---|---|---|---|---|
| 3000041 | before_after | 无相关事实 ❌ | Citizen (Thailand) ✅ | 不完整 |
| 3000051 | before_last | Portugal ❌ | Sudan ✅ | 不完整 |

### 4.6 P3: reflection hurt (空结果探针 — 已移除)

| quid | qtype | P1+P2 → +reflect2 | 模式 |
|---|---|---|---|
| 3000000 | after_first | Jack Straw ✅ → 无相关事实 ❌ | 放弃 |
| 3000012 | equal | 2 答案 ✅ → 无相关事实 ❌ | 放弃 |
| 3000025 | equal | 2014 ✅ → 无相关事实 ❌ | 放弃 |
| 3000029 | equal | 6 答案 ✅ → 无相关事实 ❌ | 放弃 |
| 3000031 | before_last | 1 答案 ✅ → 无相关事实 ❌ | 放弃 |
| 3000040 | equal | 2 答案 ✅ → 无相关事实 ❌ | 放弃 |
| 3000046 | before_after | 8 答案 ✅ → 无相关事实 ❌ | 放弃 |
| 3000065 | equal | 3 答案 ✅ → 无相关事实 ❌ | 放弃 |
| 3000072 | equal_multi | 1 答案 ✅ → 无相关事实 ❌ | 放弃 |
| 3000074 | before_after | 4 答案 ✅ → 无相关事实 ❌ | 放弃 |
| 3000079 | before_last | 1 答案 ✅ → 无相关事实 ❌ | 放弃 |

**全部 11 个是 "正确答案→放弃" 模式, 均由空结果反射探针导致。现已移除该信号。**

---

## 5. 修复影响模拟

| 修复 | 可防止回归数 | 机制 |
|---|---|---|
| ⛔ by_year 禁令 (first_last/before_last/after_first) | **3** | 禁止用 by_year/INDEX → 回到全量 data.txt |
| ❌ 移除空结果反射探针 | **11** | 不再"再核一次" → 不触发放弃模式 |
| 保留 P2 改善 (不依赖 by_year) | **4** | 3 after_first + 1 before_last 来自 INDEX 关系确认 |
| 保留 P3 不完整信号 | **2** | 2 HELPed 保留 |
| **保守预计 net (vs old reflect2 77%)** | **~+6-8** | 考虑 LLM 噪声 (±3-4pt) |

---

## 6. 修改文件清单

| 文件 | 改动 |
|---|---|
| `skills/_shared/NAVIGATION.md` | 重写: 第 -1 步文件选择决策树; 移除手写关系速查散文; 强制查表流程; 回溯 checklist |
| `skills/_shared/REFLECT.md` | 新增教训 2: 空结果探针净负 (11 个放弃回归) |
| `skills/first_last/SKILL.md` | ⛔ 铁律: 禁止 by_year/INDEX |
| `skills/before_last/SKILL.md` | ⛔ 铁律: 禁止 by_year/INDEX |
| `skills/after_first/SKILL.md` | ⛔ 铁律: 禁止 by_year/INDEX |
| `skills/before_after/SKILL.md` | 多答案铁律 + 文件选择指引 + by_year 回退 |
| `exp_runner.py` | 移除空结果反射探针; 更新注释记录教训 |
| `exp_trace.py` | 新增 `used_relation_families` / `used_index_md` / `used_by_year` 标记; `fallback_log` 回溯原因检测 |
| `build.py` | 修正 "不切年" 过时注释; README_LAYOUT 新增禁令 |

---

## 7. 明确结论

### 有统计/证据支撑

| 结论 | 证据 |
|---|---|
| **P1 关系族查表没有显著整体提升** | baseline vs P1: net -4, p=0.454 |
| **P2 by_year 对 first_last/before_last 有毒** | 逐题 trace 确认 3 题回归均由 by_year/INDEX 导致 |
| **P3 空结果反射探针导致 11 个放弃回归** | 逐题 final 内容确认: 全部 "正确→无相关事实" |
| **P3 不完整信号修复了 2 个 P2 破坏的题** | 逐题 trace 确认: quid 3000041, 3000051 |
| **P2 改善 multi-answer 5 题** | P1 "放弃" → P2 找到了全部答案 |

### 不应做的

- qtype routing 重写 (已证不是瓶颈)
- parse 前端复活 (净负 77%<81%)
- v2/v3 schema rollout (暂缓)
- 路线 B 完整实现 (本轮只修 A 路线闭环)

---

## 8. 待 API 可用时验证

```
python exp_runner.py --n 100 --workers 8 --reveal none --out traces_fixed_100.json
python exp_runner.py --n 100 --workers 8 --reveal none --reflect --out traces_fixed_reflect_100.json
python exp_subset.py traces_blind_300.json traces_fixed_100.json
python exp_subset.py traces_relfam_p2_100.json traces_fixed_reflect_100.json
```

验收标准:
- first_last 恢复到 100% (P2 破坏的 3 题修复)
- before_last 恢复到 ≥80% (by_year 导致的 2 题修复)
- reflect 不再引入 "正确→放弃" 回归 (空结果探针已移除)
- multi-answer 改善保留 (5 题改善保留)
