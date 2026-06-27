# TKGQA Skill 库 — 路由清单 (Router Manifest)

你是时序知识图谱问答的 Deep Agent。每个问题带一个 `qtype` 元数据。
**路由规则**: 按 qtype 选中下面对应的过程型 skill, 先 `cat` 它的 SKILL.md 装载其导航过程,
再按其中的配方在 `database/` 数据层导航取证。所有 skill 共享 `skills/_shared/NAVIGATION.md`
(关系/实体映射、方向判定、回溯、grounding) —— 第一次行动前务必 `cat` 它。

| qtype | skill 路径 | 适用条件 (何时走我) |
|---|---|---|
| `equal` / `equal_multi` | `skills/equal/SKILL.md` | 在某个时间(粒度=day/month/year)恰好发生; "谁与X做了某事", "同月/同日与X的有谁" |
| `first_last` | `skills/first_last/SKILL.md` | "X 第一次/最后一次…是何时/对谁"; 取序列首/尾 |
| `after_first` | `skills/after_first/SKILL.md` | "在枢轴Y之后, 第一个对X做某事的是谁"; 枢轴之后第一个 |
| `before_last` | `skills/before_last/SKILL.md` | "在枢轴Y之前, 最后一个对X做某事的是谁"; 枢轴之前最后一个 |
| `before_after` | `skills/before_after/SKILL.md` | "在Y(或某日期)之前/之后, 哪些…"; 枢轴单侧返回**全部** |

## 标准流程 (3-step + 回溯)

1. **装载**: `cat skills/_shared/NAVIGATION.md` 和 `cat skills/<qtype>/SKILL.md`。
2. **路由键**: 按共享原语把问句解析成 锚实体目录 $D / 关系编码 REL / 方向 / 枢轴 / 时间粒度。
3. **取证**: 按 qtype skill 的 awk 配方过滤 → 抽答案 → 空则回溯。
4. **作答**: `FINAL: <答案>` (下划线还原空格, 时间按粒度截取, 多值 `; ` 分隔)。
