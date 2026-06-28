---
name: tkgqa-before-last
description: 在枢轴 Y 之前, 最后一个对 X 做某关系的对方; 枢轴日期 t0 之前取末个 (单个)
applies_to: [before_last]
---

# before_last 配方

> ⛔ **铁律: 永远只用 `database/$D/data.txt` 全量。禁止使用 `by_year/<年>.txt` 或 `INDEX.md`。**
> 枢轴 t0 之前的答案可能跨多年, 切到单年会漏掉更早年份的记录, 取到错误的"最后一个"。

"Before Y, who last <REL> X?" → 锚=X, 方向由 `_relation_families.tsv` canonical_direction 判定, 枢轴=Y。
返回 **单个** (t0 之前最后一条)。

```bash
# 1) 查 _relation_families.tsv 取规范码 REL + 方向
# 2) 取该方向+关系的全量序列, 找枢轴 Y 的日期 t0
awk -F'\t' '$2=="<" && $3=="REL" {print}' database/$D/data.txt > /tmp/seq.txt
t0=$(awk -F'\t' '$4=="Y_NAME" {print $1; exit}' /tmp/seq.txt)
# 3) t0 之前最后一条 (遍历取最后一个)
awk -F'\t' -v t="$t0" '$1<t {a=$4} END{print a}' /tmp/seq.txt
```
> ⚠️ 枢轴匹配用精确 `$4=="Y_NAME"`, 不用子串。

## 与 before_after 的区别
before_last = t0 之前**最后一条** (单个); before_after = t0 一侧**全部** (多个)。

## 终止
取到即 `FINAL:`。t0 空或无更早记录 → 翻方向 → 换同族关系码 → 把 Y 当锚实体反查。仍空 → `知识库中无相关事实`。
