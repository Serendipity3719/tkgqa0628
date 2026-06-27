---
name: tkgqa-equal
description: 在某时间粒度(day/month/year)恰好发生的事件; 返回全部满足的对方; 含 "same month/year as X" 和时间型答案
applies_to: [equal, equal_multi]
---

# equal / equal_multi 配方

锚实体 $D, 关系 REL, 方向通常 `<` (问"谁与 X 做了某事" → 锚=X)。
**时间按粒度截前缀匹配, 不是按天**。粒度前缀长度 P: day=10, month=7, year=4。

## A. 答案是实体, 且问句给定时间 T

把 T 截到粒度前缀 (如 month → "2005-04"), 返回该粒度内全部对方:
```bash
awk -F'\t' -v p=7 -v t="2005-04" \
  '$2=="<" && $3=="Sign_formal_agreement" && substr($1,1,p)==t {print $4}' \
  database/$D/data.txt | sort -u
```
若问句含 "first/last" (该粒度内第一个/最后一个): 去掉 sort -u, 改 `| sort | head -1` 或 `| tail -1` 取对方。

## B. "same month/year as X" 型 (先用枢轴 X 求时间)

```bash
# 1) 取枢轴 X 那条事件的日期前缀 (X 用 catalog 规范名精确匹配)
t=$(awk -F'\t' '$2=="<" && $3=="Make_a_visit" && $4=="Oleg_Ostapenko" {print substr($1,1,7); exit}' database/$D/data.txt)
# 2) 同粒度全部对方, 排除枢轴 X 自己
awk -F'\t' -v p=7 -v t="$t" '$2=="<" && $3=="Make_a_visit" && substr($1,1,p)==t && $4!="Oleg_Ostapenko" {print $4}' database/$D/data.txt | sort -u
```

## C. 答案是时间 (answer_type=time, "When/which month did X … with Y")

此时 subject 和 object 都已知 (锚=X, 固定对方=Y, 方向 `>`)。取事件日期, 按粒度截:
```bash
awk -F'\t' '$3=="Make_a_visit" && $4=="China" {print $1}' database/$D/data.txt
# month → substr 1,7 ; year → 1,4 ; day → 原样
```

## 终止
取到对方/时间即 `FINAL:`。空 → 翻方向 (`>`↔`<`)、换关系族、检查粒度; 仍空 → `知识库中无相关事实`。
