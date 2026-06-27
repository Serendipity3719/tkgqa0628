---
name: tkgqa-before-last
description: 在枢轴 Y 之前, 最后一个对 X 做某关系的对方; 枢轴日期 t0 之前取末个 (单个)
applies_to: [before_last]
---

# before_last 配方

"Before Y, who last <REL> X?" → 锚=X, 方向通常 `<`, 枢轴=Y。返回 **单个** (t0 之前最后一条)。

```bash
awk -F'\t' '$2=="<" && $3=="Express_intent_to_meet_or_negotiate" {print}' database/$D/data.txt > /tmp/seq.txt
t0=$(awk -F'\t' '$4=="Cambodia" {print $1; exit}' /tmp/seq.txt)
awk -F'\t' -v t="$t0" '$1<t {a=$4} END{print a}' /tmp/seq.txt
```

## 与 before_after 的区别
before_last = t0 之前**最后一条** (单个); before_after = t0 一侧**全部**。

## 终止
取到即 `FINAL:`。t0 空或无更早记录 → 翻方向、换关系族、换实体。仍空 → `知识库中无相关事实`。
