---
name: tkgqa-first-last
description: X 第一次/最后一次做某关系是何时(time)或对谁(entity); 取按日期排好的序列的首/尾
applies_to: [first_last]
---

# first_last 配方

锚实体 $D, 关系 REL。data.txt 已按日期升序, 所以 `head -1`=first, `tail -1`=last。
判 first/last: 问句含 "first" → head -1; 含 "last" → tail -1。

## 答案是时间 (answer_type=time, "In which year did X last … Y")

subject=X(锚), object=Y(固定对方, 方向 `>`)。**Y 用 catalog 规范名精确匹配**:
```bash
awk -F'\t' '$3=="Make_an_appeal_or_request" && $4=="China" {print $1}' database/$D/data.txt | tail -1
# year → 再 cut -c1-4 ; month → cut -c1-7
```

## 答案是实体 ("Who was the first country X expressed optimism about")

锚=X, 方向 `>`, 答案是对方列:
```bash
awk -F'\t' '$2==">" && $3=="Make_optimistic_comment" {print $4}' database/$D/data.txt | head -1
```

## 终止
取到即 `FINAL:`。空 → 翻方向、换关系族 (尤其 appeal↔request↔demand); 仍空 → `知识库中无相关事实`。
注意: 固定对方若是国家, 必须精确匹配 (`$4=="Thailand"`), 别用子串误中 `Government_(Thailand)`。
