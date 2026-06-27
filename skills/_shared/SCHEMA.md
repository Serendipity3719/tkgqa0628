# TKG2Skill — Procedural Skill Schema (v2)

规范化的过程技能 (Procedural Skill, $S^P$) 定义标准。本文件**只描述 schema 本身**
(给作者/审稿读)，不在运行时装载给 Agent。每个 `skills/<qtype>/SKILL.md` 必须符合本规范。

---

## 0. 设计第一性原理

一个过程技能是一个**参数化函数**：

```
S^P : (slots) ──bind──► (atomic shell command) ──run──► (evidence rows) ──ground──► answer
```

它**不是**一段散文，而是一张「槽位绑定表 + 单条自洽 shell 模板 + 回溯阶梯」。三条铁律，
直接对应 v1 的三个崩溃点：

| 铁律 | 解决的崩溃点 |
|---|---|
| **R1 原子性 (Atomicity)**：每个导航步骤必须是**一条自洽的 bash 命令**，不得跨命令依赖 shell 变量。 | serve 端每条命令是全新 `bash -lc`，shell 变量**不跨轮存活**；且并发 worker 共享 `/tmp` 会串台。 |
| **R2 引用性 (Citation)**：所有绑定 (实体/关系/方向…) 必须**引用 `NAVIGATION.md` 的具名原语 ID** (`BIND-ENT` 等)，不得就地另造逻辑。 | v1 共享文件是散文，无法被「调用」，Agent 每题重新发明绑定。 |
| **R3 状态外显 (Externalized State)**：当前已绑定的槽位 + 回溯阶梯档位，必须以一行 `STATE:` 显式维护在 Agent 推理里。 | shell 无状态 → 状态只能活在 Agent 的上下文里，必须强制其写下来。 |

> **原子优先于 /tmp**：能用一条 `awk` 单趟完成的，绝不拆成「写 /tmp/seq → 读 t0 → 再 awk」三步。
> 单趟 awk 用内部数组扫一遍即可同时定位枢轴日期并做位置选择 (见 §8 SEQ-PIVOT)。
> 只有当一条命令确实无法表达 (极少) 才允许写 `/tmp/<唯一名>` 且必须用 `mktemp`。

---

## 1. 渐进披露 (Progressive Disclosure) — 三层

| 层 | 内容 | 何时进入 Agent 上下文 | 字数预算 |
|---|---|---|---|
| **Tier-0 CARD** | YAML frontmatter：`trigger` / `applies_to` / `answer_types` / `cost` | **永远在路由清单里** (`SKILLS.md` 汇总所有 CARD) | ≤ 5 行 |
| **Tier-1 BODY** | `SIGNATURE` / `GUARD` / `PLAN` / `FALLBACK` / `TERMINATE` | Agent 决定装载后 `cat skills/<qtype>/SKILL.md` | ≤ 60 行 |
| **Tier-2 PRIMITIVES** | `NAVIGATION.md` 的具名原语库 | 每会话开头 `cat` 一次，被 BODY 以 ID 引用 | 共享 |

CARD 是 Agent 选 skill 的**唯一依据**——它读不到 BODY 就要能判断「走不走我」。
因此 `trigger` 必须是**可判别的问句骨架**，不是泛泛描述。

---

## 2. Tier-0 CARD (frontmatter) 字段规范

```yaml
---
id: tkg.after_first              # 全局唯一，命名空间 tkg.*
applies_to: [after_first]        # 命中的 qtype 列表 (路由键)
trigger: '"After <PIVOT>, who was the first to <REL> <ANCHOR>?" — 枢轴之后的首个后继'
answer_types: [entity]           # entity | time  (决定抽哪一列 / 是否截粒度)
consumes: [ANCHOR, REL, DIR, PIVOT]   # 本技能消费的槽位 (= 它的「函数签名」)
cost: 1                          # 典型「取证」命令条数 (绑定命令不计)；用于预算与路由偏好
loads: [_shared/NAVIGATION.md]   # 装载前置依赖
---
```

字段语义：
- `trigger`：**一行问句模板**，占位符用 `<SLOT>`。路由清单逐字展示它。
- `consumes`：声明式函数签名。列出的每个槽必须在 BODY 的 `SIGNATURE` 给出绑定方法。
- `cost`：取证命令的典型条数 (原子化后多为 1)。路由遇到多 skill 可选时优先低 `cost`。

---

## 3. 槽位 (Slots) —— 过程技能的「参数」

所有过程技能共享同一套槽位词汇表 (the navigation key)。技能通过 `consumes` 声明子集。

| 槽 | 含义 | 绑定原语 | shell 占位符 |
|---|---|---|---|
| `ANCHOR` | 锚实体的 catalog `dir_path` | `BIND-ENT` | `{{D}}` |
| `REL` | 关系编码 | `BIND-REL` | `{{REL}}` |
| `DIR` | 方向 `>`/`<` | `BIND-DIR` | `{{DIR}}` |
| `PIVOT` | 枢轴对方实体 (规范名，精确匹配) | `BIND-ENT`+`MATCH-EXACT` | `{{PIV}}` |
| `OTHER` | 固定对方 (time 型答案里已知的另一端) | `BIND-ENT`+`MATCH-EXACT` | `{{OTH}}` |
| `P` | 时间粒度前缀长度 day=10 / month=7 / year=4 | 由 `time_level` 直接给定 | `{{P}}` |
| `T` | 时间字面量 (已按 P 截好前缀) | 问句解析 | `{{T}}` |

> 槽是**值**，不是 shell 变量。绑定后把值**内联**进命令模板 (R1)，不要 `export D=...`。

---

## 4. Tier-1 BODY —— 五个必需小节

BODY 必须且只能含以下五节，顺序固定：

### 4.1 `## SIGNATURE` — 怎么把问句绑成槽
对 `consumes` 里每个槽给一行：`槽 ← 原语ID(问句要素)`。这是「参数化」的落点。
```
ANCHOR ← BIND-ENT(被指向的已知实体 X)
REL    ← BIND-REL(谓词短语)
DIR    ← BIND-DIR(默认 '<'：问"谁对X")
PIVOT  ← BIND-ENT(枢轴短语) + MATCH-EXACT
```

### 4.2 `## GUARD` — 何时确属本技能 / 与近邻的区分
一句话边界条件，防止与相邻 qtype 混 (如 before_last vs before_after：单个 vs 全部)。

### 4.3 `## PLAN` — 取证 (PLAN step 语法见 §6)
编号步骤。每步 = `intent` + 一条 `shell:` 模板 (含 `{{slot}}`) + `extract:` (抽哪列/怎么截)。
**目标：原子化到 1 步**。

### 4.4 `## FALLBACK` — 回溯阶梯 (语法见 §7)
有序阶梯。每档 = `on`(触发条件) + `do`(槽变换) + `Δshell`(命令改动) + `cost`。

### 4.5 `## TERMINATE` — 成功/放弃/输出
- 成功：拿到证据行即 `FINAL:`。
- 放弃：阶梯走完仍空 → `FINAL: 知识库中无相关事实` (硬 grounding)。
- 后处理：引用 `GROUND` 原语 (下划线→空格、按 P 截时间、多值 `; `)。

---

## 5. STATE 账本契约 (解决「丢状态」)

Agent **每次发命令前**，必须在推理里先写一行当前账本：

```
STATE: D=entities/i/Iraq REL=Make_a_visit DIR=< PIV=Denmark P=10 rung=R0 budget=3/10
```

- `rung`：当前回溯档位 (R0=主路径)。每次回溯 `+1` 并改写对应槽。
- `budget`：已用/上限取证命令数。
- 因为 shell 无跨轮记忆，这行 `STATE` **就是** Agent 唯一的工作内存；丢了它就要重新绑定。
- serve 端不解析它，但它让 Agent 自己不迷路——这是 R3 的执行形态。

---

## 6. PLAN step 语法 (模板 → shell)

```
- step: <intent 一句话>
  shell: |
    awk -F'\t' -v rel="{{REL}}" -v piv="{{PIV}}" '
      $2=="{{DIR}}" && $3==rel { n++; d[n]=$1; w[n]=$4; if($4==piv && t0=="") t0=$1 }
      END{ for(i=1;i<=n;i++) if(d[i]>t0){ print w[i]; exit } }' database/{{D}}/data.txt
  extract: 对方列 $4 的首个后继 (entity)
```

约束：
- 模板里**只允许** `{{SLOT}}` 占位符，渲染时整串替换为绑定值。
- 一条 `shell` 必须**自洽可跑** (R1)：单趟 awk 内联完成「过滤→定位枢轴→位置选择」。
- 时间是字典序：`$1<t` / `$1>t` / 数组首尾即 first/last，**永不另调 `sort`**。
- 精确匹配对方：`$4==piv`，**禁止** `$4 ~ /piv/` (子串会误中 `Government_(...)`)。

---

## 7. FALLBACK 阶梯语法 (解决「无 SOP 回溯」)

回溯是一台**对槽位做有序变换的状态机**。每个过程技能从下表选取适用档位，按 `rung` 升序执行；
每档触发条件命中且仍空，则进入下一档。预算上限 ~8 条取证命令。

| rung | on (触发) | do (槽变换) | Δshell | cost |
|---|---|---|---|---|
| **R1 swap-relation** | 结果空 | `REL ← 同族兄弟` (`FB-RELFAM`) | 改 `-v rel=` | 1 |
| **R2 flip-direction** | 结果空 | `DIR ← flip(DIR)` | `>`↔`<` | 1 |
| **R3 repivot** | 枢轴日期 `t0` 空 | 把 `PIVOT` 当 `ANCHOR` 重绑 (`BIND-ENT`)，反查其日期 | 换 `database/{{D}}` 与匹配列 | 2 |
| **R4 relax-granularity** | time 型空/过严 | `P ← 更粗` (10→7→4) | 改 `-v p=` 与 `T` 截断 | 1 |
| **R5 rebind-entity** | 仍空 | 回 catalog 换候选行 (选错同名实体) | 换 `{{D}}` | 1 |
| **R6 give-up** | 预算耗尽 | — | — | 0 |

- 阶梯**顺序**由技能在 `## FALLBACK` 里显式列出 (不同 qtype 优先级不同：
  pivot 类先 R3，equal 类先 R4，普通类先 R1→R2)。
- 每跳一档，Agent 改写 `STATE` 的 `rung=` 并仅改动那一个槽——**单变量回溯**，便于归因。
- R6 = grounding 兜底，输出「知识库中无相关事实」，绝不编造。

---

## 8. Tier-2 共享原语库 (NAVIGATION.md 须暴露这些具名 ID)

技能 BODY 通过 ID 引用，不重复其内容。`NAVIGATION.md` 重构为「原语手册」，每个原语一个 `### <ID>`：

| ID | 作用 | 一行实现要点 |
|---|---|---|
| `BIND-REL` | 谓词→关系编码 | `grep -iE "<kw>" database/_relations.txt`，从输出挑 |
| `BIND-ENT` | 实体短语→`dir_path` | 2 个区分 token grep catalog 取 $2；`X of Y`→`Role_(Y)`；英式→美式拼写 |
| `BIND-DIR` | 定方向 | 问"谁对 X"→`<`；"X 对谁/X 何时"→`>`；被动 by→施动者为 head |
| `MATCH-EXACT` | 对方精确匹配 | 先解析成规范名再 `$4=="Name"`，禁子串 |
| `SEQ-PIVOT` | 单趟取枢轴日期+做位置选择 | §6 那段内联 awk 数组法 (无 /tmp) |
| `FB-RELFAM` | 关系同族表 | appeal↔request↔demand；visit make↔host；cooperate 族… |
| `GROUND` | 输出后处理 | 下划线→空格；按 P 截时间；`sort -u`；多值 `; ` |

> 重构原则：把现 `NAVIGATION.md` 的散文**切成上述 7 个带 `###` 锚点的小节**，内容基本不变，
> 但变成「可被 BODY 按 ID 引用」的库函数。这是 R2 的落点。

---

## 9. 参考实现 (after_first，已在真实数据上验证返回 `Jack_Straw`)

见同目录约定的 `skills/after_first/SKILL.md` (v2 形态)。其 PLAN 仅 1 条原子 awk，
FALLBACK 阶梯 `R3 repivot → R2 flip → R1 swap → R6`，全程零 `/tmp`、零跨轮 shell 变量。
```
```
