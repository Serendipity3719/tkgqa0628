---
name: tkgqa-after-first
description: 在枢轴 Y 之后, 第一个对 X 做某关系的对方; 枢轴日期 t0 之后取首个
applies_to: [after_first]
---

# after_first 配方

"After Y, who was the first to <REL> X?" → 锚=X, 方向通常 `<`, 枢轴=Y。

```bash
# 1) 取该方向+关系的序列 (已按日期升序)
awk -F'\t' '$2=="<" && $3=="Make_a_visit" {print}' database/$D/data.txt > /tmp/seq.txt
# 2) 枢轴 Y 的日期 t0 (Y 用 catalog 规范名精确匹配 $4=="...")
t0=$(awk -F'\t' '$4=="Defense_/_Security_Ministry_(Denmark)" {print $1; exit}' /tmp/seq.txt)
# 3) t0 之后第一行的对方
awk -F'\t' -v t="$t0" '$1>t {print $4; exit}' /tmp/seq.txt
```

## 终止
取到即 `FINAL:`。
枢轴找不到 (t0 空) → 翻方向重取 seq, 或把 Y 当锚实体反查其日期; 换关系族。
仍空 → `知识库中无相关事实`。
