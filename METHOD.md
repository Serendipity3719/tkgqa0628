# TKG2Skill — Navigating a Temporal Knowledge Graph as a Skill Library

> 把时序知识图谱（TKG）**离线投影**成一个双层 Agent Skill 库（数据层 + 过程层），
> serve 时让 LLM Agent 用通用 shell 工具**导航**它，从而把传统 KGQA 的
> 「实体链接 → 关系预测 → 图搜索」流水线，整体替换为
> **一次技能路由 + 文件系统内的自主导航**。
>
> 它是 Corpus2Skill「Don't Retrieve, Navigate」范式在
> **同质表格型语料（该论文 §5.3 自陈的失败域）**上的结构化实例化。

---

## 1. 核心问题的形式化回答

### 1.1 Skill 是什么？(两类)

- **数据技能 $S^K$ (knowledge skill)**：KG 的一个**结构化分区**被物化成可导航文件。
  分区键 = **实体**：每个实体一个 `data.txt`，存其全部 1-hop 事件，经
  **视角归一化**（方向标记 `>`/`<`）+ **双向冗余**（每条四元组在 head、tail 各存一份）
  + **按日期升序**。接口 $R$ = 文件系统（`grep`/`awk`/`cat`）。
  它不含策略，是被导航的**底座**。

- **过程技能 $S^P=(C,\pi,T,R)$ (procedural skill)**：借 Jiang et al. (2026) 的 skill 形式。
  - $C$ = 适用条件（一个**问题模式** qtype）
  - $\pi$ = 参数化**导航策略**（一段以"槽位"为参数的 `awk`/`grep` 序列）
  - $T$ = 终止条件（抽到答案 / 回溯预算耗尽）
  - $R$ = `SKILL.md` 指令 + 共享原语接口

### 1.2 Skill 如何生成？

一个**确定性、无 LLM、无嵌入、无聚类**的编译映射 $\Phi: G \to (\mathcal{S}^K, \text{Index})$：

1. **投影**：$\forall (h,r,t,\tau)\in G$，向 $h$ 写 $(\tau,\texttt{>},r,t)$、向 $t$ 写 $(\tau,\texttt{<},r,h)$；
   每个实体文件按 $\tau$ 排序 → 得 $\mathcal{S}^K$。
2. **索引综合**：
   - `_catalog.tsv`（实体 → 安全路径 + 计数 + 时间跨度，= **实体索引 / 路由键**）
   - `_relations.txt`（关系词表 + 频次）
   - 大实体 `INDEX.md`（逐年计数 / 高频关系 / 高频邻居，= **结构化摘要卡**）
3. **过程技能 $\mathcal{S}^P$ 不逐语料生成**，而是**对四元组 schema 一次性手写**
   （6 个 qtype 配方 + 共享原语），跨 KG 复用。

> **关键对照**：Corpus2Skill 用 `embed → cluster → LLM-summarize` 生成技能；
> 本方法把这一整套换成**结构投影**（用 KG 自带的确定性键：实体、时间、关系、方向）。
> 原因正是该论文 §5.3 的结论——**同质表格语料上语义聚类摘要会坍缩成近似重复标签**。
> 同时，推理逻辑被**显式物化为 skill**，而非隐含在 LLM 摘要里。

### 1.3 Agent 如何选择 Skill？(两级路由 + 渐进披露)

- **过程路由**：问句 → 问题模式 → 选 $S^P$。Agent 仅先看 `SKILLS.md` 里各 skill 的
  一行 `description`（~200 tokens），据此装载对应 `SKILL.md`。
  （当前系统 qtype 作元数据给出，路由退化为确定性；一般情形由 Agent 读 description 分类。）
- **数据路由（= 把"实体链接"降格为 grep）**：在 $\pi$ 内部，
  `grep _catalog.tsv` 把锚实体短语解析到某个 $S^K$ 的路径；
  `grep _relations.txt` 把谓词解析到关系编码。

### 1.4 Agent 如何调用 Skill？

$\pi$ 被实现为 Agent 经**单个只读 code-execution 工具**发出的一串 shell 操作：

```
cat SKILL.md          # 载策略 π
  → grep 索引          # 绑定槽位: 锚实体 / 关系 / 方向 / 枢轴 / 粒度
  → awk data.txt       # 按 方向+关系 选事件, 按日期做位置选择
  → 抽答案
  → (空则) 回溯         # 翻方向 / 换关系族 / 重链实体
```

- **Grounding 硬规则**：答案必须来自某条被打印出的数据行，否则报"无相关事实"。
- **终止**：抽取成功或预算耗尽（~10 条命令）。

### 1.5 KG 如何被导航？

KG **从不**被当作图加载或用嵌入检索，而是被当**文件系统导航**：

- 实体文件 = 该实体的 **1-hop ego-graph**（双向），所以"图搜索"= `awk` 扫一个文件。
- 日期升序使**时序算子退化为字典序操作**：
  `first/last` = `head/tail`、`before/after` = `$1<t0`/`$1>t0`、`equal` = 按粒度截前缀。
- **带枢轴的"多跳"问题留在单文件内**：因视角归一化 + 双向冗余，枢轴事件与答案事件
  共享锚实体，故无需真正跨文件。跨实体跳转（偶尔需要）= 重 `grep` catalog
  —— 实体索引充当跨链接（对应 Corpus2Skill 的 `entity_index.json`）。

---

## 2. Method Overview

TKG2Skill 分**编译**与**服务**两相。

**编译相**把 KG $G=(E,\mathcal{R},\mathcal{T})$ 的 $N$ 条四元组确定性投影为：
(i) $|E|$ 个实体数据技能（视角归一化、双向冗余、时间排序），
(ii) 三个路由索引（实体索引、关系词表、大实体摘要卡）。
过程技能库（按问题模式组织的 awk 配方 + 共享原语 + 路由清单）随 schema 一次性给定。

**服务相**中，一个 LLM Agent 持**单一只读 shell 工具**，经渐进披露选过程技能、
grep 索引绑定结构化槽位、awk 在实体文件内做"方向 × 关系 × 时序位置"的选择、
并在空结果时自主回溯，输出**可溯源**答案。
全程 serve 端**无向量库、无三元组库、无 SPARQL**。

---

## 3. Architecture Diagram（文字）

```
                    OFFLINE  COMPILE  (Φ: 确定性, 无 LLM/嵌入/聚类)
 ┌────────────────────────────────────────────────────────────────────┐
 │  TKG  G = {(h, r, t, τ)}  (461k 四元组, 1万实体, 11年, 按天)          │
 │            │ 视角归一化 + 双向冗余 + 按 τ 排序                        │
 │            ▼                                                          │
 │  数据技能层 S^K           索引层 Index                               │
 │  entities/<e>/data.txt    _catalog.tsv  (实体索引 = 路由键)           │
 │    τ \t dir \t r \t other _relations.txt(关系词表)                   │
 │    (1-hop ego, 双向)      <e>/INDEX.md  (大实体摘要卡)               │
 └────────────────────────────────────────────────────────────────────┘
              ▲ 被导航                          ▲ 被 grep 路由
 ┌────────────────────────────────────────────────────────────────────┐
 │  过程技能层 S^P (手写, 跨 KG 复用)                                    │
 │  SKILLS.md(路由清单) ─ _shared/NAVIGATION.md(原语)                   │
 │  {equal, first_last, after_first, before_last, before_after}/SKILL.md │
 │     每个 = (C 适用条件, π awk 策略, T 终止, R 接口)                   │
 └────────────────────────────────────────────────────────────────────┘
        │                          ONLINE  SERVE
        ▼
   Question + qtype
        │  ① 渐进披露: 读 SKILLS.md 描述
        ▼
 ┌──────────────┐  ② 过程路由: 选 S^P, cat 其 SKILL.md + 共享原语
 │  LLM  Agent  │  ③ 数据路由: grep catalog/relations 绑定槽位
 │  (单一只读   │  ④ 导航: awk data.txt → 方向×关系×时序位置选择
 │  bash 工具)  │  ⑤ 回溯: 翻方向 / 换关系族 / 重链实体  (预算 ~10)
 └──────────────┘  ⑥ Grounding: 答案必来自打印行
        │
        ▼
   FINAL: 可溯源答案
```

---

## 4. Algorithm 流程

### 4.1 编译（Compile，离线一次）

```
Φ(G):
  for (h, r, t, τ) in G:                       # 投影 + 视角归一化 + 双向冗余
      append (τ, '>', r, t) to file[h]
      append (τ, '<', r, h) to file[t]
  for e in E:
      sort file[e] by τ ascending              # 时序 ⇒ 字典序
      write entities/safe(e)/data.txt
      catalog[e] = (path, |file[e]|, min τ, max τ)
      if |file[e]| > θ: write INDEX.md(年计数, 高频关系, 高频邻居)
  write _catalog.tsv, _relations.txt           # 索引层
  return  (S^P 过程技能库为 schema 固定, 不在此生成)
```

### 4.2 服务（Serve，每问一次；ReAct 式自主导航）

```
Answer(q, qtype):
  show SKILLS.md descriptions                  # 渐进披露 (~200 tok)
  S ← select procedural skill by qtype         # ① 过程路由
  read NAVIGATION.md, S.SKILL.md               # 载策略 π
  bind slots from q:                           # ② 数据路由 (grep, 非模型推断)
      D   ← grep _catalog.tsv  (锚实体 → 路径)
      REL ← grep _relations.txt(谓词 → 关系编码)
      dir, pivot, granularity ← parse(q) + 原语规则(demonym/role/被动语态)
  repeat until answer or budget exhausted:      # ③④⑤ 导航 + 回溯
      seq ← awk over D/data.txt  filter (dir, REL)        # 1-hop ego, 已排序
      ans ← position-select(seq, op(qtype), pivot, granularity)
            # first/last=head/tail; after/before=τ≷t0; equal=按粒度截前缀
      if ans = ∅: backtrack(flip dir / relation family / re-link D)
  assert ans 来自打印行 else "无相关事实"        # ⑥ grounding
  return normalize(ans)                          # 下划线→空格, 时间按粒度截
```

---

## 5. 与传统 KGQA 的区别

| 维度 | 传统 KGQA | TKG2Skill（本方法） |
|---|---|---|
| 流水线 | Question → Entity Linking → Relation Prediction → Graph Search → Answer，各为学习/服务组件 | Question → 选过程技能 → grep 绑槽 → Agent 自导航 → Answer，**单一 Agent + 通用工具** |
| KG 形态 | 三元组库 / 图数据库，藏在查询引擎后 | **静态文件系统**，Agent 直接可见可遍历 |
| 实体链接 | 专门的 EL 模型 | **`grep _catalog.tsv`**（实体索引即路由键） |
| 关系预测 | 专门的关系分类/排序 | **`grep _relations.txt` + skill 提示** |
| 图搜索 | SPARQL / 子图匹配 / 多跳遍历 | **`awk` 扫单个实体 ego-file**（多跳因双向冗余坍缩为单文件） |
| 时序推理 | 时间约束求解 / 区间逻辑 | **字典序算子**（`head`/`tail`/`<`/`>`/前缀截断） |
| serve 期基础设施 | 向量库 / 三元组库 / 图引擎 | **无**（仅 shell 工具读文件） |
| LLM 角色 | 被动消费检索回来的子图 | **主动导航者**：先有"鸟瞰"（catalog 知有哪些实体、INDEX 知实体画像）再决策，可回溯 |
| 推理逻辑所在 | 隐含在模型权重 / 检索器 | **显式物化为可读 skill 文件**（可审计、可复用、可 grounding） |
| 可溯源性 | 依赖检索召回 | **硬 grounding**：每个答案绑定一条被打印的事实行 |

### 与父方法 Corpus2Skill 的区别

共享"导航代替检索 + 文件系统技能 + 渐进披露 + 回溯"四大支柱；但本方法：

1. 技能生成是**确定性结构投影**而非嵌入聚类 + LLM 摘要（针对其自陈的同质表格失败域）；
2. 显式区分**过程技能 vs 数据技能**两类，而非单一信息技能树；
3. 导航接口是对**类型化记录**的关系/时序 `awk` 算子，而非对散文档的 `cat` + `get_document`；
4. 路由键是**结构键**（实体 / 时间 / 关系 / 方向）而非主题标签。

---

## 6. 系统映射（方法 ↔ 当前代码）

| 方法组件 | 实现 |
|---|---|
| 编译映射 $\Phi$ | `build.py` |
| 数据技能层 $\mathcal{S}^K$ + 索引 | `database/entities/**/data.txt`、`_catalog.tsv`、`_relations.txt`、`INDEX.md` |
| 过程技能层 $\mathcal{S}^P$ | `skills/SKILLS.md`、`skills/_shared/NAVIGATION.md`、`skills/<qtype>/SKILL.md` |
| 服务 Agent loop | `agent_nav.py`（单一只读 bash 工具，ReAct 自主导航） |
| Oracle 上界参照 | `eval_fs.py`（LLM 解析 facets + Python 死写 recipe，非导航） |

> **实验佐证**（100 题，不追 SOTA）：真 Agent 端到端 **85%**，平均 **7.1 条命令/题**，
> 距 oracle 上界（92%）的"导航损耗"约 **7pp**，验证了 KG → Skill → Agent Navigation 链路可行。
