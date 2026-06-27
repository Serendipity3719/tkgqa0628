# 自反思协议 (Self-Reflection Protocol) — P3

> 给 Agent 一个**提交前的自检关口**, 而不是 ReAct 一条道走到黑 (生成 FINAL 就交)。
> 由 serve 循环 (`exp_runner.solve_traced`, `--reflect`) 实现, 不是 prompt 里的一句话。

## ⚠️ 关键教训: 通用版被数据否决, 现用 targeted 版

**通用版 (每个 FINAL 都注入一张五项通用清单) = 净负** (n=100 配对):
- ALL 82%→73% (净 −9); **qtype:equal 97%→77%, p=0.031 显著**; multi_answer 84%→61%。
- backtracks 0.01→0.20: 无条件"再想想"让 agent 二次检索, **把已对的答案改错**。
- 与 parse 前端同类的**过度干预失效**: 自信但多余的 nudge 会压制已 grounded 的正确检索。

**现行 targeted 版**: 仅在命中**具体风险信号**时才反思; 信心十足的单答案**不碰**。

## 触发 (targeted, 仅两类风险, 各注入一次)

| 风险信号 | 检测 (只看问句+候选答案, 无 gold, 盲态无泄漏) | 注入的聚焦提示 |
|---|---|---|
| **不完整** | 复数问句 (`which countries/哪些/who are/list…`) 却只给 **1 个**答案 | 提示在正确方向重跑 + `sort -u` 核对行数; 确实只有一个就原样重发, 别编 |
| **空/放弃** | 候选 = `知识库中无相关事实` | 提示翻镜像方向 / 换同族关系码再试一次; 仍空才确认 |

- 其余情况 (单答案问句给了答案 / 多答案问句已给多个 / API 错误) **一律不反思**。
- 每题最多反思一次; 反思后给 +3 命令预算核实; 仍受总命令上限约束。
- trace.meta 记 `reflect`(是否开启) 与 `reflected`(本题是否真触发), 可在 exp_subset 切片。

## 设计原则

- **只治可治的瓶颈**: 当前最大可治失败源 = 多答案完整性 (before_after/multi_answer 返回子集)。
  targeted 反思精准打这个, 不去骚扰 equal / first_last 这类已近满分的单答案题。
- **绝不无端改动**: 提示语都带"确实如此就原样重发, 别编造"——防止把对的改错。
- **可 ablation**: `--reflect` 开关 + meta 标记, 支持 reflect-off vs reflect-on 同题配对。
