# 基线状态记录 — P1/P2/P3 验证起点

> 2026-06-28 · 对照 MIDTERM_REVIEW_2026-06-27 做的落地验证

## 1. 当前基线

| 项目 | 值 |
|---|---|
| 主基线 | `traces_blind_300.json` (n=300, blind, robust e2e=81%) |
| P1 trace | `traces_relfam_100.json` (n=100, blind, raw=81%) |
| P1+P2 trace | `traces_relfam_p2_100.json` (n=100, blind, raw=82%) |
| P3 generic (负结果) | `traces_reflect_100.json` (n=100, blind+reflect, raw=73%) |
| P3 targeted | `traces_reflect2_100.json` (n=100, blind+reflect, raw=77%) |
| 所有 5 个文件共享同一组 100 个 quid → 可直接配对 McNemar |

## 2. P1/P2/P3 实现状态 vs 实际使用

| 特性 | 代码存在? | Agent 实际使用? |
|---|---|---|
| `_relation_families.tsv` | ✅ build.py L67-231 | ✅ 100/100 题 (relfam_100) |
| `INDEX.md` + `by_year/` 时序切片 | ✅ build.py L352-403 | ✅ INDEX: 60/100, by_year: 22/100 (relfam_p2) |
| Targeted reflection | ✅ exp_runner.py L46-88 | 仅 6/100 触发 (reflect2) |
| NAVIGATION.md 关系查表流程 | ✅ NAVIGATION.md L45-75 | ✅ agent 会用 grep _relation_families |
| NAVIGATION.md 第 0 步分层导航 | ✅ NAVIGATION.md L23-43 | ⚠️ agent 用 INDEX 但**忽略了 "first/last 别用 by_year" 规则** |

## 3. 配对 McNemar 核心结论

### P1 (relation family) vs baseline (blind_300[0:100])

- **Overall**: 85%→81%, 改对6/改错10/净-4, p=0.454 (不显著)
- **visit 子集**: 100%→91%, 改对0/改错2/净-2, p=0.500 (不显著)
- **关键发现**: P1 没有提升——relation binding 的改善被 "Agent 更容易放弃(返回无相关事实)" 抵消

### P2 (temporal slice) vs P1

- **Overall**: 81%→82%, 改对12/改错11/净+1, p=1.000 (不显著)
- **multi_answer**: 71%→84%, 改对6/改错2/净+4, p=0.289 (趋势向好但不显著)
- **first_last**: 100%→88%, 改对0/改错3/净-3, p=0.250 — **P2 破坏了 3 个 first_last 题!**
- **before_last**: 83%→58%, 改对1/改错4/净-3, p=0.375 — **P2 破坏了 4 个 before_last 题!**
- **time answers**: 98%→90%, 改对1/改错4/净-3, p=0.375 — 时间题也受损
- **根因确认**: Agent 使用 INDEX.md/by_year 后，对 first/last/before_last 这类需要**跨年全量扫描**的查询错误地使用了年切片，导致漏答

### P3 (targeted reflection) vs P1+P2

- **Overall**: 82%→77%, 改对9/改错14/净-5, p=0.405 (不显著，方向负)
- **entity**: 77%→63%, 改对5/改错13/净-8, p=0.096 (趋势变差!)
- **negotiate**: 95%→65%, 改对1/改错7/净-6, p=0.070 (趋势变差!)
- **multi_answer**: 84%→65%, 改对1/改错7/净-6, p=0.070
- **first_last**: 88%→100% — P3 **修复了 P2 破坏的 3 个 first_last 题!**
- **visit**: 83%→87%, 改对4/改错3/净+1
- **根因**: P3 的 "空结果" 反射探针让 Agent 二次尝试后更倾向于放弃(14 个回归中大部分变为 "知识库中无相关事实")；但 "不完整" 探针修复了几个 P2 破坏的题

## 4. 需要修复的明确缺口

### 4.1 P2: by_year 对 first/last/before_last 有毒

NAVIGATION.md 已写 "first/last 用全量 data.txt" 但 Agent **不遵守**。需要更强有力的约束。

### 4.2 P3: 空结果反射探针有害

"给'无相关事实'前再核一次" 的探针导致 Agent 彻底放弃而非修正。需要重新设计或移除该信号。

### 4.3 P1: 关系族查表流程需要优化

`_relation_families.tsv` 100% 使用但仍出现 relation binding 错误（visit 100%→91%），说明查表流程本身有 friction。

### 4.4 多答案完整性: 核心 awk 配方未改

before_after SKILL.md 的 awk 配方本身没变，只是外围补丁。

## 5. 可做同题配对的子集清单

- visit: 23 题 (quid 重叠)
- before_after: 20 题
- multi_answer: 31 题
- negotiate: 20 题
- first_last: 26 题
- before_last: 12 题
- has_pivot: 40 题
