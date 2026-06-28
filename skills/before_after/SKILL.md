---
name: tkgqa-before-after
description: 在枢轴(实体 Y 或某日期)之前/之后, 满足关系的**全部**对方; 方向由问句 before/after 决定
applies_to: [before_after]
---

# before_after 配方

"Before/After Y, which countries <REL> X?" → 锚=X, 枢轴=Y (实体) 或一个**显式日期**。
返回枢轴**单侧的全部**对方 (**不是单个**)。

> ⚠️ **多答案铁律**: before_after 的答案是一批。**必须 `sort -u` 去重后输出全部, 禁止只取前几个。**
> 如果结果只有 1 个 → 确认是否漏了同侧其他行, 翻方向或换关系码再查一次。

## 文件选择

- 问题锚定明确年份 → 可先用 `by_year/<年>.txt` 缩小范围
- 问题跨多年或年份不明确 → 用全量 `data.txt`
- **切片结果为空或不完整 → 必须回退全量 `data.txt` 重查** (记 `fallback: by_year_to_full`)

## 枢轴是实体 Y

先查 `_relation_families.tsv` 取规范码 REL + 方向:
```bash
# 1) 取该方向+关系的全量序列
awk -F'\t' '$2==">" && $3=="REL" {print}' database/$D/data.txt > /tmp/seq.txt
# 2) 找枢轴 Y 的日期 t0 (精确匹配 $4=="Y_NAME")
t0=$(awk -F'\t' '$4=="Y_NAME" {print $1; exit}' /tmp/seq.txt)
# 3) t0 之前/之后的**全部**对方 (before=$1<t, after=$1>t)
awk -F'\t' -v t="$t0" '$1<t {print $4}' /tmp/seq.txt | sort -u   # before
awk -F'\t' -v t="$t0" '$1>t {print $4}' /tmp/seq.txt | sort -u   # after
```

## 枢轴是显式日期 ("Before 25 April 2005, who <REL> X")

直接用该日期当 t0, 无需找枢轴实体:
```bash
awk -F'\t' -v t="2005-04-25" '$2=="<" && $3=="REL" && $1<t {print $4}' database/$D/data.txt | sort -u
```
注意 "after 2012" 这类年份枢轴: t0="2012", 字典序 `$1>"2012"` 即 2012 年起的全部。

## 终止

- 拿到结果 → `sort -u` 去重 → `FINAL: <全部答案>`, 多值 `; ` 连接。
- 空结果 → 翻方向 → 换同族关系码 → 把 Y 当锚反查 → 回退全量 data.txt(如果之前用了切片)。
- 仍空 → `FINAL: 知识库中无相关事实`。
