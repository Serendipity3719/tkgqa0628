# 共享导航原语 (所有 qtype skill 都依赖)

你在导航一个时序知识图谱的文件系统知识库 `database/`。本文件是所有技能共用的底层操作手册。

## 数据源布局

```
database/
  _catalog.tsv            实体规范名 -> 安全目录路径。列: name \t dir_path \t count \t min_date \t max_date
  _relations.txt          全部 251 个关系编码 + 频次 (按频次降序)。列: code \t freq
  _relation_families.tsv  关系族投影 (28 族): 谓词 -> 族 -> 规范码 + 标准方向 (见第 1 步)
  entities/<桶>/<安全名>/
    data.txt              该实体全部事件, 已按日期升序 (全量, 永远可用)
    INDEX.md              仅大实体(>2000 条): 导航地图 (逐年地图/高频关系/高频邻居 + 钻取指引)
    by_year/<年>.txt      仅大实体: 按年切片 (INDEX.md 的钻取目标)
```

`data.txt` 每行 (以本实体为视角): `日期 \t 方向 \t 关系 \t 对方`
- 方向 `>` = 本实体是 head (本实体 → 对方)
- 方向 `<` = 本实体是 tail (对方 → 本实体)
- 日期 `YYYY-MM-DD`, **字典序即时间序**。双向冗余: 每条事实在 head 与 tail 两个目录各存一份。

## 第 0 步: 分层导航 (大实体先看地图再钻取)

定位到实体目录后, **先看它是不是大实体** (目录里有没有 `INDEX.md`)。**有就先 `cat INDEX.md`**
—— 这是鸟瞰地图 (哪些年有事件、各年最高频关系、Top 关系/邻居), 用它**规划再行动**, 大幅减少回溯。

**何时钻 `by_year/<年>.txt`, 何时用全量 `data.txt` (关键, 别钻错)**:
| 问题形态 | 用哪个文件 | 原因 |
|---|---|---|
| **锚定单年/单月** ("在 2010 年…"、`equal` 某年某月与 X) | `by_year/<年>.txt` | 答案只在那一年, 钻进去最省 |
| **全序列首尾** (`first_last`: 第一次/最后一次) | **全量 `data.txt`** (`head -1`/`tail -1`) | first/last 是**跨所有年**的, 切到单年会取成"该年的首尾"→错 |
| **枢轴单侧** (`before_after`/`after_first`/`before_last`, `$1<t0`/`$1>t0`) | **全量 `data.txt`** | 单侧通常跨多年, 切单年会漏 |

```bash
cat "database/$D/INDEX.md"                         # 1) 先看地图: 定位年份 + 确认关系/方向存在
awk -F'\t' '...' "database/$D/by_year/2010.txt"     # 2a) 只当问题锚定该年时才钻切片
awk -F'\t' '...' "database/$D/data.txt"             # 2b) first/last/枢轴单侧 -> 仍走全量
```
- **没 `INDEX.md`** (小实体): 直接 awk `data.txt`, 它本就很小。
- 切片与全量**结果完全一致** (by_year 是 data.txt 的按年子集), 钻错了无非多读, 回退到 data.txt 即可。
- INDEX.md 还辅助**绑定/回溯**: 关系不在"高频关系"里 → 多半关系码选错, 回 `_relation_families.tsv` 换同族码;
  目标年份事件数为 0 → 时间窗口或方向判断有误。

## 第 1 步: 关系映射 (先做, 最易错) —— **查表, 别凭记忆猜**

关系映射现在是**离线投影产物** `database/_relation_families.tsv` (28 个关系族)。
**不要再凭记忆写关系码**, 按 NL 谓词 grep 这张表, 拿到 ①规范码 ②标准方向。

表的列: `family \t canonical_direction \t member_codes`
- `member_codes` **空格分隔** (关系码内含逗号, 故不用逗号); 频次降序, **第一个 = 规范码**;
  `!` 前缀 = 镜像冗余码, **勿用** (如 `!Host_a_visit`)。
- `canonical_direction` = 该族施动者(=head)是谁, 如 `head=visitor` / `head=accuser` / `head=actor`。

> ⚠️ **选码规则 (重要)**: 在族内挑**与谓词词面最匹配**的成员码, **不是无脑用规范码**。
> 谓词指名具体成员时用具体码: "optimistic comment" → `Make_optimistic_comment` (**不是** `Praise_or_endorse`);
> "military force" → `Use_conventional_military_force`。谓词只是泛指(只说 "visit"/"sign"/"praise")才用第一个(规范码)。

```bash
# 1) 按谓词找族 (一两个判别词即可)
grep -i "visit" database/_relation_families.tsv
#   -> visit  head=visitor  Make_a_visit !Host_a_visit
# 2) 取规范码 = 第 3 列空格切分的第一个
awk -F'\t' '/visit/{split($3,a," "); print a[1]}' database/_relation_families.tsv
#   -> Make_a_visit
```
> ⚠️ grep 命中**多行**时 (谓词碰巧是别族某成员码的子串, 如 `appeal` 也出现在 `meet_negotiate` 的
> `Appeal_to_others_to_meet_or_negotiate` 里): **选第 1 列 family 名与谓词最匹配的那行**
> (`appeal` → `appeal_request`, 不是 `meet_negotiate`)。

取不到结果时, 在**同族**里换下一个成员码 (回溯第 1 档), 不要跳到别的族。
常用谓词 → 族关键词: visit→`visit` · negotiate/meet→`negotiat` · appeal/request→`appeal` ·
demand→`demand` · sign/agreement→`sign` · criticize/condemn→`criticiz` · accuse→`accuse` ·
cooperate→`cooperat` · praise/optimistic/endorse→`praise` · sanction/embargo→`sanction`。
visit 仍照下方"visit 专项规则"用方向区分访客/目的地。

## 第 2 步: 实体映射 (锚实体 / 枢轴 / 固定对方)

绝不自己拼路径。用 2 个区分性 token grep catalog 取 dir_path:
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

## 第 3 步: 方向判定 (答案在哪一列)

- 问 "谁/which country 对 X 做了某事" → 锚实体 = X (已知), 方向 `<`, **答案是对方列 $4**。
- 问 "X 对谁做了某事 / X 最后…谁" → 锚实体 = X, 方向 `>`, 答案是对方列 $4。
- **被动语态**: "who was accused **by** Ethiopia" → Ethiopia 是施动者=head, 方向 `>`。
- 拿不准就**两个方向都试**, 哪个有结果用哪个 (双向冗余保证不漏)。

### ⚠️ visit 专项规则 (两臂最高频的绑定错, 必须照做)

一次访问在库里有 4 份冗余: `Make_a_visit`/`Host_a_visit` × 两个 ego 文件。它们语义镜像、极易把方向搞反。
**铁律: visit 一律只用 `Make_a_visit`, 用方向区分谁是访客 (访客 = 主动"去"的一方 = head)。**

在锚实体 X 的文件里:
- **"谁访问了 X" / "X 接待/受访于谁" / "X hosted / received a visit from" / "visited X"**
  → X 是**目的地**, 用 `$2=="<" && $3=="Make_a_visit"`, **访客在 $4**。
- **"X 访问了谁" / "whom did X visit" / "X 出访"**
  → X 是**访客**, 用 `$2==">" && $3=="Make_a_visit"`, **目的地在 $4**。

> 例: "UAE received the visit from China" = China 访问 UAE → 在 UAE 文件 `$2=="<" && $3=="Make_a_visit" && $4=="China"` → 2010-03。
> **千万别用 `Host_a_visit`**: 在 X 文件里 `< Host_a_visit` 其实等于"X 去访问别人"(方向反了), 正是之前一直答错的根源。

## 固定对方 / 枢轴的精确匹配 (重要)

匹配"对方"列时, 先把短语解析成 catalog 规范名再**精确**比, 别用子串——
否则 "Thailand" 会误中 `Government_(Thailand)`、`Citizen_(Thailand)`。
```bash
# 错: $4 ~ /Thailand/      对: $4=="Thailand"
```

## 回溯预算 (任一步空结果就按序试, 上限约 8 条命令)

1. 换关系: 试同族另一个编码 (appeal↔request↔demand; visit make↔host)。
2. 翻转方向: `>` ↔ `<`，或把枢轴实体当锚实体重查。
3. 换实体: 回 catalog 换 token / 换候选行 (可能选错同名实体)。
4. 放宽/检查时间粒度。

## Grounding 硬规则

- 答案只能来自命令输出的行。查不到就回答 `知识库中无相关事实`，**绝不编造**。
- 永远 awk/grep 过滤, 绝不 cat 整个 data.txt (大实体 5 万行)。

## 输出格式

- 库内下划线 → 输出空格: `Jack_Straw` → `Jack Straw`。括号/逗号/变音字符原样保留。
- 多值答案: `sort -u` 去重, 列表返回。
- 时间答案按粒度截取: year=前4位, month=前7位, day=完整。
- 最终答案用一行 `FINAL: <答案>` 给出 (多值用 `; ` 分隔)。
