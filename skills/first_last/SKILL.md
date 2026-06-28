---
name: tkgqa-first-last
description: X 第一次/最后一次做某关系是何时(time)或对谁(entity); 取按日期排好的序列的首/尾
applies_to: [first_last]
---

# first_last 配方

> ⛔ **铁律: 永远只用 `database/$D/data.txt` 全量。禁止使用 `by_year/<年>.txt` 或 `INDEX.md`。**
> first/last 是跨所有年份的全局极值, 切到任何单年会变成"该年的首尾", 答案必然错。

锚实体 $D, 关系 REL (先查 `_relation_families.tsv` 拿到规范码)。data.txt 已按日期升序, `head -1`=first, `tail -1`=last。
判 first/last: 问句含 "first/earliest" → `head -1`; 含 "last/latest" → `tail -1`。

## 答案是时间 (answer_type=time, "In which year did X last … Y")

subject=X(锚), object=Y(固定对方, 方向 `>`)。**Y 用 catalog 规范名精确匹配**:
```bash
# 1) 查 _relation_families.tsv 取规范码 REL
# 2) 过滤 + 取首/尾日期
awk -F'\t' '$3=="REL" && $4=="Y_NAME" {print $1}' database/$D/data.txt | tail -1
# year → cut -c1-4 ; month → cut -c1-7 ; day → 原样
```

## 答案是实体 ("Who was the first country X expressed optimism about")

锚=X, 方向由 `_relation_families.tsv` canonical_direction 判定, 答案是对方列:
```bash
awk -F'\t' '$2==">" && $3=="REL" {print $4}' database/$D/data.txt | head -1
```
> ⚠️ 精确匹配对方: `$4=="Thailand"`, 不用 regex `/Thailand/` 防误中 `Government_(Thailand)`。

## 终止

取到即 `FINAL:`。空结果 → 按 NAVIGATION.md 回溯预算: 翻方向 → 换同族关系码 → 换锚实体视角。
仍空 → `FINAL: 知识库中无相关事实`。
