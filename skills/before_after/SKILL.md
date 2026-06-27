---
name: tkgqa-before-after
description: 在枢轴(实体 Y 或某日期)之前/之后, 满足关系的**全部**对方; 方向由问句 before/after 决定
applies_to: [before_after]
---

# before_after 配方

"Before/After Y, which countries <REL> X?" → 锚=X, 枢轴=Y (实体) 或一个**显式日期**。
返回枢轴**单侧的全部**对方 (不是单个)。问句含 before → t0 之前; 含 after → t0 之后。

## 枢轴是实体 Y
```bash
awk -F'\t' '$2==">" && $3=="Express_intent_to_meet_or_negotiate" {print}' database/$D/data.txt > /tmp/seq.txt
t0=$(awk -F'\t' '$4=="Ethiopia" {print $1; exit}' /tmp/seq.txt)
awk -F'\t' -v t="$t0" '$1<t {print $4}' /tmp/seq.txt | sort -u   # before; after 用 $1>t
```

## 枢轴是显式日期 ("Before 25 April 2005, who <REL> X")
直接用该日期当 t0, 无需找枢轴实体:
```bash
awk -F'\t' -v t="2005-04-25" '$2=="<" && $3=="Use_conventional_military_force" && $1<t {print $4}' database/$D/data.txt | sort -u
```
注意 "after 2012" 这类年份枢轴: t0="2012", 字典序 `$1>"2012"` 即 2012 年起的全部。

## 终止
有结果即 `FINAL:` (多值 `; ` 连接)。空 → 翻方向、换关系族; 注意被动语态会翻转方向。
仍空 → `知识库中无相关事实`。
