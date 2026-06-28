---
name: tkgqa-after-first
description: 在枢轴 Y 之后, 第一个对 X 做某关系的对方; 枢轴日期 t0 之后取首个
applies_to: [after_first]
---

# after_first 配方

> ⛔ **铁律: 永远只用 `database/$D/data.txt` 全量。禁止使用 `by_year/<年>.txt` 或 `INDEX.md`。**
> "After Y, first …" 可能跨多年, 切到单年会取成"该年第一个"而非"全局第一个", 答案必然错。

"After Y, who was the first to <REL> X?" → 锚=X, 方向由 `_relation_families.tsv` canonical_direction 判定, 枢轴=Y。

```bash
# 1) 查 _relation_families.tsv 取规范码 REL + 方向
# 2) 取该方向+关系的全量序列 (已按日期升序)
awk -F'\t' '$2=="<" && $3=="REL" {print}' database/$D/data.txt > /tmp/seq.txt
# 3) 枢轴 Y 的日期 t0 (精确匹配 $4=="Y_NAME")
t0=$(awk -F'\t' '$4=="Y_NAME" {print $1; exit}' /tmp/seq.txt)
# 4) t0 之后第一行的对方
awk -F'\t' -v t="$t0" '$1>t {print $4; exit}' /tmp/seq.txt
```

## 终止
取到即 `FINAL:`。
枢轴找不到 (t0 空) → 翻方向重取 seq → 把 Y 当锚实体反查其日期 → 换同族关系码。
仍空 → `FINAL: 知识库中无相关事实`。
