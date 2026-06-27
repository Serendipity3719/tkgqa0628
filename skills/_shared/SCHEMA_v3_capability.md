# TKG2Skill — Capability Schema (v3)

v2 (`SCHEMA.md`) 从 **bash/awk 实现**角度定义 skill (原子命令、/tmp、awk 模板)。
v3 上移一层: 从 **Agent 能力**角度定义 skill —— 让 skill 成为
**「可组合的 KG 导航策略 (composable KG navigation policy)」**。

> 关键区分: **navigation policy 是 bash 无关的**。它描述「在 KG 上怎么走」(选关系边→
> 定向→按时间排→选位置→投影)，是一段**抽象算子序列**。awk 只是它在文件系统后端的一种
> *realization*。换 SPARQL/向量库后端, policy 不变, 只换 realization。这层解耦是做
> ablation 的前提 (可单独替换 router / policy / backend / fallback 任一段)。

v3 不替换 v2; v2 退化为 v3 `navigation_policy` 字段的「filesystem realization」附录。

---

## 0. 一个 skill = 7 个字段

```yaml
capability:          # 这个 skill 给 Agent 的一项 KG 导航「能力」(声明式, 实现无关)
trigger:             # 何时路由到我 (问句形态 + qtype + 可判别条件)
io:                  # 类型化的输入/输出契约 (使 skill 可组合)
  input:  {...}
  output: {...}
navigation_policy:   # 抽象算子序列 (bash 无关); 末尾挂 realization 指针
dependency:          # 依赖的共享原语 / KG 结构不变量
composition:         # 怎样与别的 skill 串联/嵌套 (输出→输入)
fallback_strategy:   # 策略层的备选走法 (re-orient / re-type / re-anchor / relax-temporal)
```

---

## 1. `capability` — 声明式能力

一句**实现无关**的能力陈述: 这个 skill 让 Agent 能在 TKG 上完成的一类导航。
区别于 v2 的 `description` (描述配方), capability 描述**能力**。

> 例 (after_first):
> *"沿某关系类型的时序边序列, 定位某枢轴事件之后的第一个邻居。"*
> ——不提 awk、不提 data.txt, 只讲「在图上做什么」。

capability 是 **Router 的真正匹配目标**: 问句被理解为「需要哪项导航能力」, 再路由到提供该能力的 skill。这把 routing 从「qtype 查表」抽象成「能力匹配」(可做 blind-routing ablation)。

---

## 2. `trigger` — 路由条件

```yaml
trigger:
  question_shape: '"After <PIVOT>, who was the first to <REL> <ANCHOR>?"'
  qtype: [after_first]               # 训练集里的对应 qtype (oracle 路由用)
  discriminators:                    # blind 路由时的可判别线索
    - "含 after/following + first/earliest"
    - "存在一个枢轴实体 (非锚、非答案)"
  not_me: "若要的是枢轴之前 → before_last/before_after; 若要全部而非第一个 → before_after"
```

`discriminators` 与 `not_me` 是 v2 `GUARD` 的升级: 不仅说自己, 还显式划清与近邻 skill 的边界——降低 routing 混淆 (exp_eval 的 routing_confusion 直接量化这点)。

---

## 3. `io` — 类型化契约 (组合的基石)

skill 之间能不能拼, 取决于**类型对得上**。定义一套 KG 导航类型:

| 类型 | 含义 |
|---|---|
| `Entity` | 单个实体 (catalog 规范名) |
| `EntitySet` | 实体集合 |
| `Time(P)` | 带粒度 P 的时间点 (day/month/year) |
| `Edge` | 一条 (anchor, rel, dir, other, time) 五元 |
| `Sequence<Edge>` | 按时间升序的边序列 (= 过滤后的 ego 视图) |

```yaml
io:
  input:
    anchor: Entity          # 锚实体 X
    relation: RelCode       # 关系类型
    pivot: Entity           # 枢轴 Y
  output:
    type: Entity            # 单个后继实体
    cardinality: one        # one | set
```

输出有类型, 才能当下一个 skill 的输入 (见 §5)。`cardinality` 区分 `after_first/before_last`(one) 与 `before_after/equal_multi`(set)——这正是 exp_eval 里 before_last vs before_after 易混的根因, 现在写进契约。

---

## 4. `navigation_policy` — 抽象算子序列 (bash 无关)

policy 是 5 个**导航原语算子**的组合。所有 6 类 qtype 都是这 5 个算子的不同编排:

| 算子 | 签名 | 语义 |
|---|---|---|
| `SELECT_RELATION(rel)` | `Anchor → Sequence<Edge>` | 取锚实体上该关系类型的边 |
| `ORIENT(dir)` | `Sequence → Sequence` | 按方向 `>`/`<` 过滤 (定向: 答案在 head 还是 tail) |
| `ORDER_TIME()` | `Sequence → Sequence` | 按时间升序 (数据已预排, 恒等算子) |
| `SELECT_POSITION(op, pivot?)` | `Sequence → Sequence` | 位置选择: first / last / after(t) / before(t) / at(t,P) |
| `PROJECT(field)` | `Sequence → Entity\|Time\|Set` | 投影出答案列 (对方 / 时间) |

> after_first 的 policy:
> ```
> SELECT_RELATION(REL) ▷ ORIENT('<') ▷ ORDER_TIME()
>   ▷ SELECT_POSITION(after, t0=time_of(PIVOT)) ▷ PROJECT(other) : Entity
> ```
> 这段**没有一个 bash 字符**。它是 Agent 在脑子里走的图路径。

```yaml
navigation_policy:
  ops:
    - SELECT_RELATION({{relation}})
    - ORIENT({{dir|default '<'}})
    - ORDER_TIME
    - SELECT_POSITION: {op: after, pivot: {{pivot}}}
    - PROJECT: other
  realization: skills/after_first/SKILL.md   # ← v2 的原子 awk 实现挂在这里
```

`realization` 是唯一指向后端的指针。**做后端 ablation 时只换它**。

---

## 5. `composition` — 可组合性 (本次重点)

skill 不是孤岛。三种组合算子让简单 skill 拼出复杂查询:

| 算子 | 形式 | 例 |
|---|---|---|
| **PIPE** `▷` | `A.output → B.input` (类型须匹配) | `first_last:Time ▷ equal@Time` |
| **NEST** | 子 skill 求出某个槽 (如 pivot 的时间) | after_first 内部 NEST 一个 `time_of(pivot)` |
| **JOIN** | 两个枢轴求区间 | `before_after` 的「A 之后 B 之前」= `after(tA) ∩ before(tB)` |

> **"same month as X" 的去糖** (现在 equal 配方 B 段手写, v3 让它显式可组合):
> ```
> resolve_time:  first_last/equal 求出 X 那条事件的 Time(month)   ── 输出 Time
>        ▷
> equal_at_time: equal@(Time, P=month) 取同粒度全部对方            ── 输入 Time, 输出 EntitySet
> ```
> 两个独立 skill PIPE 成一个 2-hop 查询。**ablation**: 可单测每段, 定位是 resolve_time
> 错还是 equal_at_time 错——而不是把 2-hop 当黑箱算一个 acc。

```yaml
composition:
  exposes_as_subskill: true          # 我的 output 可被别的 skill 当输入
  composable_with:
    - {skill: equal, via: PIPE, on: output.time -> input.time}
  internal_nest:                      # 我内部嵌套调用的子能力
    - {capability: resolve_pivot_time, binds: t0}
```

> **范式含义**: KG → Skill Library → Router → **Navigation (可组合)** → Answer。
> 组合算子让「Skill Navigation」从单步变成可拼接的**策略图**, multi-hop 不再坍缩进单条 awk,
> 而是显式的 skill DAG——这才让 multi-hop ablation 成为可能。

---

## 6. `dependency` — 依赖

```yaml
dependency:
  shared_primitives: [BIND-ENT, BIND-REL, BIND-DIR, MATCH-EXACT, GROUND]  # 见 NAVIGATION.md
  kg_invariants:                     # policy 正确性所依赖的 KG 结构不变量
    - ego_file_time_sorted           # data.txt 已按时间升序 → ORDER_TIME 是恒等
    - bidirectional_redundancy       # 双向冗余 → ORIENT 翻转不丢边, 多跳坍缩为单文件
    - canonical_naming               # catalog 规范名 → MATCH-EXACT 可精确比
```

把 policy 正确性所依赖的**不变量显式写出**: 一旦换后端 (如未排序的图库), 哪些算子 (ORDER_TIME) 需要重新 realize 一目了然。这是 ablation 的安全网。

---

## 7. `fallback_strategy` — 策略层备选

v2 的 bash 阶梯 (swap-rel/flip-dir/...) 上移成**策略层动作** (对 policy 算子的扰动):

| 策略动作 | 扰动的算子 | = v2 rung |
|---|---|---|
| `re-type-relation` | `SELECT_RELATION` 换同族 rel | R1 |
| `re-orient` | `ORIENT` 翻方向 | R2 |
| `re-anchor` | 把 pivot 当 anchor 重绑 (靠 bidirectional_redundancy) | R3 |
| `relax-temporal` | `SELECT_POSITION` 放宽粒度 P | R4 |
| `re-resolve-entity` | 重绑 anchor (catalog 换候选) | R5 |
| `abstain` | 输出「知识库中无相关事实」 | R6 |

```yaml
fallback_strategy:
  order: [re-anchor, re-orient, re-type-relation, abstain]   # 各 skill 自定优先级
  budget: 8
```

每个 fallback 动作对应 exp_eval 失败分类的一个**可恢复维度**: 失败归类里若 relation_error 多 → 说明 `re-type-relation` 该更早触发。fallback 顺序本身就是一个可 ablate 的超参。

---

## 8. 与实验基础设施的接线

| v3 字段 | exp_eval 里被它驱动的指标 |
|---|---|
| `capability` / `trigger` | Skill Routing Accuracy + routing_confusion |
| `io` (cardinality) | before_last↔before_after 混淆诊断 |
| `navigation_policy` (算子) | Navigation Efficiency; 算子级失败定位 |
| `composition` | multi-hop ablation (分段 acc) |
| `fallback_strategy` | Failure Taxonomy 的可恢复性分析 |
| `dependency.kg_invariants` | 后端替换 ablation 的边界 |

> 一句话: v3 让每个 skill 都**自带它在实验里要被怎么度量**, 实验系统因此从「黑箱 acc」
> 变成「沿 KG→Skill→Router→Nav→Answer 逐段可归因」。
