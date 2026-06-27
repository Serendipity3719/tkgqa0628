---
id: tkg.after_first
applies_to: [after_first]
trigger: '"After <PIVOT>, who was the first to <REL> <ANCHOR>?" — 枢轴日期之后的首个后继 (单个)'
answer_types: [entity]
consumes: [ANCHOR, REL, DIR, PIVOT]
cost: 1
loads: [_shared/NAVIGATION.md]
---

# after_first 配方 (v2)

## SIGNATURE
```
ANCHOR ← BIND-ENT(被指向的已知实体 X)          # 锚 = 被"对…做某事"的那个 X
REL    ← BIND-REL(谓词短语)
DIR    ← BIND-DIR(默认 '<'：问"谁对 X 做某事")
PIVOT  ← BIND-ENT(枢轴短语 Y) + MATCH-EXACT     # 精确名，单趟里用 $4==piv
```

## GUARD
返回**单个**对方 = 枢轴日期 `t0` 之后**第一条**。
对比：`before_last` 取 t0 之前最后一条；`before_after` 取一侧全部。三者只差位置算子。

## PLAN
一条原子 awk 单趟完成「过滤序列 → 定位枢轴日期 t0 → 取 t0 后首行对方」，**无 /tmp、无跨轮变量**：
```
- step: 取枢轴之后第一个对方
  shell: |
    awk -F'\t' -v rel="{{REL}}" -v piv="{{PIV}}" '
      $2=="{{DIR}}" && $3==rel { n++; d[n]=$1; w[n]=$4; if($4==piv && t0=="") t0=$1 }
      END{ if(t0==""){print "[pivot-not-found]"; exit}
           for(i=1;i<=n;i++) if(d[i]>t0){ print w[i]; exit } }' database/{{D}}/data.txt
  extract: 对方列 $4 的首个后继 (entity)
```
data.txt 已按日期升序，故数组天然时序；`d[i]>t0` 字典序即"之后"。

## FALLBACK
按 rung 升序；枢轴类先 repivot：
| rung | on | do | Δshell |
|---|---|---|---|
| R3 repivot | 输出 `[pivot-not-found]` | `PIVOT→ANCHOR` 重绑，反查 Y 文件里 X 的日期 | 换 `database/{{D}}`、`$4==旧ANCHOR` |
| R2 flip | 结果空 | `DIR ← flip` | `$2` 改 `>`/`<` |
| R1 swap | 结果空 | `REL ← FB-RELFAM(REL)` 同族兄弟 | 改 `-v rel=` |
| R6 give-up | 预算耗尽 | — | `FINAL: 知识库中无相关事实` |

每跳一档：改写 `STATE` 的 `rung=`，仅动一个槽。

## TERMINATE
拿到对方行 → `GROUND` 后处理 (下划线→空格，单值) → `FINAL:`。
阶梯走完仍空 → `FINAL: 知识库中无相关事实`。
