# 共享导航原语 (所有 qtype skill 都依赖)

你在导航一个时序知识图谱的文件系统知识库 `database/`。本文件是所有技能共用的底层操作手册。

## 数据源布局

```
database/
  _catalog.tsv     实体规范名 -> 安全目录路径。列: name \t dir_path \t count \t min_date \t max_date
  _relations.txt   全部 251 个关系编码 + 频次 (按频次降序)。列: code \t freq
  entities/<桶>/<安全名>/data.txt   该实体全部事件, 已按日期升序
```

`data.txt` 每行 (以本实体为视角): `日期 \t 方向 \t 关系 \t 对方`
- 方向 `>` = 本实体是 head (本实体 → 对方)
- 方向 `<` = 本实体是 tail (对方 → 本实体)
- 日期 `YYYY-MM-DD`, **字典序即时间序**。双向冗余: 每条事实在 head 与 tail 两个目录各存一份。

## 第 1 步: 关系映射 (先做, 最易错)

把问句谓词映射到精确关系编码。先 grep, 再从输出里挑:
```bash
grep -iE "visit|appeal|request|negotiat|sign" database/_relations.txt
```
常见映射:
- visit → `Make_a_visit` (主动访问) 或 `Host_a_visit` (接待访问)
- sign agreement → `Sign_formal_agreement`
- negotiate / intend to meet → `Express_intent_to_meet_or_negotiate`
- request / appeal / demand → 多为 `Make_an_appeal_or_request` (易和 `Appeal_for_diplomatic_cooperation_(such_as_policy_support)`、`Demand` 混; 取不到结果就换族内另一个)
- condemn / criticize → `Criticize_or_denounce`；accuse → `Accuse`
- optimistic → `Make_optimistic_comment`；attack with small arms → `fight_with_small_arms_and_light_weapons`
- cooperate → `Express_intent_to_cooperate` / `Engage_in_diplomatic_cooperation`

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
