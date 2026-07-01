# 共享导航原语 (所有 qtype skill 都依赖)

你在导航一个时序知识图谱的文件系统知识库。Phase 3 后, 默认入口是
`tkgqa/semantic_clusters/` 语义路由层; `database/` 是最终 grounding 事实层。
**每一步必须产出可观测的输出; 空结果、回溯、fallback 都必须记录 reason, 不要静默跳过。**

## 数据源布局

```
tkgqa/
  root/index.md
  semantic_clusters/index.md
  semantic_clusters/clusters.tsv
  semantic_clusters/<cluster_id>_<name>/
    index.md                 该语义簇的 routing_policy / hints / coverage
    catalog.tsv              本簇候选实体。列: canonical_name \t database_path \t count \t min_date \t max_date
    relation_families.tsv    本簇候选关系族。列: family \t canonical_direction \t member_codes
    <entity>/index.md
    <entity>/temporal_slices/index.md
    <entity>/temporal_slices/<slice_id>/index.md
    <entity>/temporal/<年>/index.md
  temporal_slices/index.md
  temporal_slices/<slice_id>/index.md
  temporal_slices/<slice_id>/entities.tsv
  temporal_schema/index.md
  indexes/semantic_cluster_index.tsv
  indexes/temporal_index.tsv
  indexes/entity_temporal_slices.tsv

database/
  _catalog.tsv            实体规范名 -> 安全目录路径。列: name \t dir_path \t count \t min_date \t max_date
  _relations.txt          全部 251 个关系编码 + 频次 (按频次降序)。列: code \t freq
  _relation_families.tsv  关系族投影 (28 族): 谓词 -> 族 -> 规范码 + 标准方向 (见第 1 步)
  entities/<桶>/<安全名>/
    data.txt              该实体全部事件, 已按日期升序 (全量, 永远可用)
    INDEX.md              仅大实体(>2000 条): 导航地图 (逐年地图/高频关系/高频邻居 + 钻取指引)
    by_year/<年>.txt      仅大实体: 按年切片 (INDEX.md 的钻取目标)
```

---

## 第 0 步: Phase 3 语义簇导航 (必须先做)

默认流程是:

```
Query -> Semantic Cluster (Top-K) -> Candidate Entity/Relation/Time -> Drill Down -> database fact
```

### 标准动作流

1. 读根入口:
```bash
cat tkgqa/root/index.md
```

2. 读语义簇总索引:
```bash
cat tkgqa/semantic_clusters/index.md
```

3. 根据问题语义选择 Top-2 簇, 优先打开 Top-1:
```bash
cat "tkgqa/semantic_clusters/cluster_004_military_security_actors/index.md"
```

4. 在该簇内点杀实体和关系族:
```bash
grep -i "Military" "tkgqa/semantic_clusters/cluster_004_military_security_actors/catalog.tsv"
grep -i "military_force" "tkgqa/semantic_clusters/cluster_004_military_security_actors/relation_families.tsv"
```

5. 若问题含明确年份/区间, 优先进入 entity temporal slice:
```bash
cat "tkgqa/semantic_clusters/cluster_004_military_security_actors/<entity>/temporal_slices/2021_2024/index.md"
```

6. 兼容旧 year leaf 的调用才使用:
```bash
cat "tkgqa/semantic_clusters/cluster_004_military_security_actors/<entity>/temporal/2024/index.md"
```

7. leaf 中的 `fact_doc` 指向最终 `database/.../data.txt`; 结合 `filter_hint` 做时间过滤。

### Phase 4 Temporal Slice 规则

- 有明确年份: 先选包含该年份的 `temporal_slices/<slice_id>/index.md`。例如 2014 通常落在 `2013_2016`。
- 有 `between 2010 and 2012` / `from 2010 to 2012`: 先选覆盖起止范围的 slice, 不够再查相邻 slice。
- 有 `after 2014` / `before 2016`: 先找 pivot 年份所在 slice, 若无证据再向后/向前相邻 slice backtrack。
- `first_last` / `before_last` / `after_first`: 禁止只读 slice, 必须用 parent entity 的全量 `data.txt`。
- 长实体: 先读 `<entity>/temporal_slices/index.md`, 不要直接读全量 entity index 或 data.txt。

全局时间先行时, 先读:
```bash
cat tkgqa/temporal_slices/index.md
cat tkgqa/temporal_slices/2013_2016/index.md
```

再从 `entities.tsv` 跳到对应 semantic entity skill。

### ⛔ 禁止的默认动作

不要一上来就全局:
```bash
grep -i "..." database/_catalog.tsv
```

只有在以下条件满足时才允许 fallback 到 `_catalog.tsv`:
- Top-2 semantic clusters 的 `catalog.tsv` 都没有候选;
- Top-2 semantic clusters 的 relation_families 都无法绑定关系;
- temporal leaf 不存在且无法从 entity index 回退;
- trace 中明确记录 `fallback_reason: semantic_top2_exhausted`。

### 必须记录 routing_path

每个问题至少在心智 trace 中维护:

```json
{
  "semantic_cluster": "cluster_004_military_security_actors",
  "entity_candidate": "...",
  "relation_cluster": "...",
  "temporal_leaf": "...",
  "temporal_slice": "2013_2016",
  "temporal_reason": "query year 2014 falls inside slice"
}
```

`data.txt` 每行 (以本实体为视角): `日期 \t 方向 \t 关系 \t 对方`
- 方向 `>` = 本实体是 head (本实体 → 对方)
- 方向 `<` = 本实体是 tail (对方 → 本实体)
- 日期 `YYYY-MM-DD`, **字典序即时间序**。双向冗余: 每条事实在 head 与 tail 两个目录各存一份。

---

## 第 -1 步: 文件选择 (最先做, 选错文件 = 答案错)

**定位到实体目录后, 先 `ls` 检查目录里有什么:**
```bash
ls "database/$D/"
```
这会列出 `data.txt`、可能的 `INDEX.md`、可能的 `by_year/`。

### ⛔ 铁律: first_last / before_last / after_first **绝对禁止**使用 by_year/

这些 qtype 的答案**跨所有年份**, 切到任何单年都会取错范围:
- `first_last`: "第一次/最后一次 X" → 必须扫描**全量** `data.txt` 用 `head -1` / `tail -1`
- `before_last`: "在 Y 之前最后一个 X" → 枢轴日期 t0 之前的**全部年份**都要看, 不能只查一年
- `after_first`: "在 Y 之后第一个 X" → 同理, t0 之后可能跨多年, 不能只查一年

> ⛔ 你如果对 first_last / before_last / after_first 用了 `by_year/<年>.txt`,
> **答案一定是错的** (会把跨年首尾取成单年首尾)。

### 文件选择决策树 (必须按序判断, 不可跳过)

| 步骤 | 条件 | 行动 | 否则 |
|---|---|---|---|
| 1 | qtype ∈ {first_last, before_last, after_first} | → **只用 `data.txt`**(全量)。**禁止**看 INDEX.md / by_year/。跳到第 1 步。 | → 步骤 2 |
| 2 | qtype ∈ {before_after, equal, equal_multi} | → **可以先** `cat INDEX.md`(若存在)了解年份分布 | → 直接 awk `data.txt` |
| 3 | 步骤 2 后, 问题**锚定明确年份/月份** (如 "in 2010", "July 2006") | → 可用 `by_year/<年>.txt` 缩小范围 | → 用全量 `data.txt` |
| 4 | 步骤 3 用了切片但结果为空或不全 | → **回退到全量** `data.txt` 重查。在 trace 里记 `fallback_reason: by_year_empty` | — |

```bash
# 步骤 1 (first_last / before_last / after_first):
awk -F'\t' '...' "database/$D/data.txt"    # ← 永远 data.txt, 绝不用 by_year/

# 步骤 2-3 (before_after / equal / equal_multi, 且锚定年份):
cat "database/$D/INDEX.md"                  # 先看地图
awk -F'\t' '...' "database/$D/by_year/2010.txt"  # 锚定年才钻切片

# 步骤 4 (回退):
awk -F'\t' '...' "database/$D/data.txt"     # 切片空 → 回退全量
```

- **没 `INDEX.md`** (小实体): 直接 awk `data.txt`, 它本就很小。
- INDEX.md 辅助**绑定确认**: 目标关系不在"高频关系"里 → 回 `_relation_families.tsv` 换同族码;
  目标年份事件数为 0 → 方向或关系码可能错。

---

## 第 1 步: 关系映射 — **查表, 严禁凭记忆猜码**

关系映射的唯一入口是 `database/_relation_families.tsv` (28 个关系族, 离线生成)。
**不要凭记忆、不要凭经验、不要自己拼关系码。每一步都 grep 这张表。**

表的列: `family \t canonical_direction \t member_codes`
- `member_codes` **空格分隔**; 频次降序; **第一个 = 规范码**;
  `!` 前缀 = 镜像/冗余码, **勿用作初次绑定** (如 `!Host_a_visit`), 仅在规范码查不到结果时作 fallback 尝试。
- `canonical_direction` = 该族施动者(=head)是谁, 如 `head=visitor` / `head=accuser` / `head=actor`。

> ⚠️ **选码规则**: 族内挑**与谓词词面最匹配**的成员码。谓词指名具体成员时用具体码:
> "optimistic comment" → `Make_optimistic_comment`; "military force" → `Use_conventional_military_force`。
> 谓词只是泛指 ("visit"/"sign"/"praise") 才用第一个(规范码)。

### 查表流程 (必须按序)

```bash
# 1) 按 NL 谓词关键词 grep (一两个词即可)
grep -i "visit" database/_relation_families.tsv
#   -> visit  head=visitor  Make_a_visit !Host_a_visit

# 2) 取规范码: 第 3 列空格切分的第一个 (不含 ! 前缀的)
awk -F'\t' '/visit/{split($3,a," "); print a[1]}' database/_relation_families.tsv

# 3) 取标准方向: 第 2 列
awk -F'\t' '/visit/{print $2}' database/_relation_families.tsv
```

> ⚠️ grep 命中**多行**时: **选第 1 列 family 名与谓词最匹配的那行**。
> 例: "appeal" 命中 `appeal_request` 和 `meet_negotiate`(成员含 Appeal_to_others_to_meet_or_negotiate)
> → 选 `appeal_request`(family 名直接匹配), 不是 `meet_negotiate`。

### 查不到时的 fallback (按序尝试, 记 reason)

| 优先级 | 动作 | trace 标记 |
|---|---|---|
| 1 | 换更短的 grep 关键词 (如 "cooperat" 替代 "cooperation") | `fallback: broader_keyword` |
| 2 | 在**同族**换下一个非 `!` 成员码 | `fallback: same_family_alt_code` |
| 3 | 尝试该族的 `!` 降级码 (镜像码, 方向语义相反) | `fallback: demoted_mirror_code` |
| 4 | grep 其他族的成员码名 (跨族搜索) | `fallback: cross_family_search` |

**严禁跳过的步骤**: 必须先查 `_relation_families.tsv` → 再模糊 grep → 最后才允许人工推断。
如果最终仍用人工推断的关系码, trace 必须标记 `binding_source: manual_guess`。

---

## 第 2 步: 实体映射 (锚实体 / 枢轴 / 固定对方)

优先在已选 semantic cluster 的 `catalog.tsv` 中找实体候选:
```bash
grep -i "Seyoum" "tkgqa/semantic_clusters/<cluster>/catalog.tsv" | grep -i "Mesfin"
```

只有 semantic Top-2 都失败, 才允许回退全局 catalog。绝不自己拼 database 路径。fallback 用 2 个区分性 token grep catalog 取 dir_path:
```bash
grep -i "Seyoum" database/_catalog.tsv | grep -i "Mesfin"   # 取第 2 列 = $D
```
精确取某实体行 (避免 grep 子串误中): `awk -F'\t' '$1=="China"' database/_catalog.tsv`。
**路径含括号必须加引号**: `cat "database/entities/d/Defense___Security_Ministry_(Taiwan)/data.txt"`。

归一化规则 (catalog 里实体名用下划线, 角色写成 `Role_(Country)`):
- 国民形容词 → 国家: `Danish` Ministry → `Denmark`; `Somali` criminal → `Criminal_(Somalia)`
- `X of Y` / `Y's X` / `leader of Y` → `Role_(Y)`: "leader of Mongolia" → `Head_of_Government_(Mongolia)`
- 英式拼写 → 美式: `defence`→`defense`, `centre`→`center`
- "citizens of Belgium" → `Citizen_(Belgium)`

---

## 第 3 步: 方向判定 (答案在哪一列)

先查 `_relation_families.tsv` 拿到的 `canonical_direction`:
- `head=visitor` → 访客(主动去的人)是 head, 方向 `>`。问 "谁访问了X" = X 是目的地 → 在 X 文件用 `<`。
- `head=accuser` → 谴责者是 head, 方向 `>`。问 "谁被X谴责" = X 是施动者 → 在 X 文件用 `>`。
- `head=actor` → 施动者=actor=head。按问句语义判定谁主动。

通用规则:
- 问 "谁/which country **对 X 做了**某事" → 锚=X, 方向 `<`, 答案在 $4。
- 问 "**X 对谁做了**某事 / X 最后…谁" → 锚=X, 方向 `>`, 答案在 $4。
- **被动语态**: "who was accused **by** Ethiopia" → Ethiopia 是施动者=head, 在 Ethiopia 文件方向 `>`。
- 拿不准就两个方向都试, 哪个有结果用哪个。

### visit 方向规则 (参照 `_relation_families.tsv`)

`_relation_families.tsv` visit 行: `visit \t head=visitor \t Make_a_visit !Host_a_visit`
含义: 访客(主动去的人)=head。**只用 `Make_a_visit`, 绝不用 `Host_a_visit`。**

在锚实体 X 的文件里:
- **"谁访问了 X" / "X received/hosted a visit from Y"** → X=目的地, `$2=="<" && $3=="Make_a_visit"`, 访客在 $4。
- **"X 访问了谁" / "X paid a visit to Y"** → X=访客, `$2==">" && $3=="Make_a_visit"`, 目的地在 $4。

> `Host_a_visit` 带 `!` 前缀 = 降级镜像码, 仅在 `Make_a_visit` 查不到结果时作 fallback 尝试。

---

## 固定对方 / 枢轴的精确匹配

匹配"对方"列时精确比较, 不用子串 regex——否则 "Thailand" 误中 `Government_(Thailand)`:
```bash
# 错: $4 ~ /Thailand/      对: $4=="Thailand"
```

---

## 回溯预算 (可观测, 每次 fallback 记 reason)

**空结果 / 答案不全时必须回溯, 不要直接给 FINAL: 知识库中无相关事实。**

| 优先级 | 触发条件 | 动作 | trace 标记 |
|---|---|---|---|
| 1 | awk 过滤结果为空 | 翻转方向 `>` ↔ `<` 重试 | `backtrack: flip_direction` |
| 2 | 方向翻转仍空 | 换同族下一个关系码 (跳过 `!` 码, 仍空才试 `!` 码) | `backtrack: alt_relation_code` |
| 3 | 换码仍空 | 把枢轴实体当锚实体, 换视角反查 | `backtrack: swap_anchor` |
| 4 | 换锚仍空 | 检查时间粒度: 日→月→年 逐步放宽 t0 前缀 | `backtrack: coarsen_time` |
| 5 | 全部试完仍空 | → `FINAL: 知识库中无相关事实` | `gave_up: exhausted` |

- 每次回溯**输出一条注释**说明原因 (如 `# backtrack: flip_direction — no rows with <, trying >`)。
- 回溯总数上限 ≈ 10 条命令。超过上限 → 基于已有证据给 FINAL。
- **关键: 回到全量 `data.txt` 也是 backtrack**——如果你之前在 by_year/ 里查但无结果,
  回退到 `data.txt` 全量重查, 标记 `backtrack: by_year_to_full`。

---

## Grounding 硬规则

- 答案只能来自命令输出的行。查不到就回答 `知识库中无相关事实`, **绝不编造**。
- 永远 awk/grep 过滤, 绝不 cat 整个 data.txt (大实体 5 万行)。
- **第一次给出 FINAL 前, 确认**: ①是否用了全量 data.txt(非仅切片)? ②多答案题是否 `sort -u` 去重后逐行核对过?

## 输出格式

- 库内下划线 → 输出空格: `Jack_Straw` → `Jack Straw`。括号/逗号/变音字符原样保留。
- 多值答案: `sort -u` 去重, 列表返回。多值用 `; ` 分隔。
- 时间答案按粒度截取: year=前4位, month=前7位, day=完整。
- 最终答案用一行 `FINAL: <答案>` 给出。
