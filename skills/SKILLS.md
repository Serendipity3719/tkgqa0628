# TKGQA Skill 库 — 路由清单 (Router Manifest)

你是时序知识图谱问答的 Deep Agent。问题**可能**带一个 `qtype` 元数据:
- 若给了 `qtype` → 直接选对应行的 skill, `cat` 它的 SKILL.md。
- 若**没给** `qtype` → 按下面的【路由决策树】**从问句自行判定**再选 skill。

所有 skill 共享 `skills/_shared/NAVIGATION.md`(关系/实体映射、方向判定、回溯、grounding)
—— 第一次行动前务必 `cat` 它。

## 路由决策树 (最易错, 先判这一步)

**第 1 问: 句中有没有"枢轴"?** —— 枢轴 = 一个参照点(另一个实体 Y 或一个显式日期),
形如 "**After/Before** \<Y 或 某日期\>, …"。

### A. 无枢轴
- "X **第一次/最后一次** (first / last) … 是何时 / 对谁" → **`first_last`**(取整条序列的首/尾)
- "在某日/某月/某年恰好…" 或 "与 X **同月/同年**…" → **`equal` / `equal_multi`**

### B. 有枢轴 (After/Before \<Y 或日期\>) —— **第 2 问: 句中有没有 first/last?**
| 线索 | skill | 返回 |
|---|---|---|
| 含 **first / earliest / 第一个** | **`after_first`** | 枢轴**之后第一个**(**单个**) |
| 含 **last / latest / 最后一个** | **`before_last`** | 枢轴**之前最后一个**(**单个**) |
| **不含 first/last**(问 "**which countries / who / 哪些**", 要一批) | **`before_after`** | 枢轴**单侧全部**(**多个**) |

> ⚠️ **最高频的路由错(务必避免)**: 看到 "**After X**" 就直接选 `after_first`。
> **先查有没有 "first/last"**。"After/Before X, **which** …" 这种**没有 first/last** 的,
> 要的是单侧**一批**答案 → 一律 **`before_after`**, 不是 after_first / before_last。
> 口诀: **有 first/last = 取一个(after_first/before_last);没有 = 取全部(before_after)。**

## 路由表 (qtype → skill)

| qtype | skill 路径 | 触发(何时走我) |
|---|---|---|
| `equal` / `equal_multi` | `skills/equal/SKILL.md` | **无枢轴**; 在某时间(day/month/year)恰好发生; "谁与X做了某事"、"同月/同日与X的有谁" |
| `first_last` | `skills/first_last/SKILL.md` | **无枢轴** + 含 first/last; "X 第一次/最后一次…何时/对谁"; 取序列首/尾 |
| `after_first` | `skills/after_first/SKILL.md` | **有枢轴** + 含 **first**; "在枢轴Y之后, 第一个…是谁"; 返回**单个** |
| `before_last` | `skills/before_last/SKILL.md` | **有枢轴** + 含 **last**; "在枢轴Y之前, 最后一个…是谁"; 返回**单个** |
| `before_after` | `skills/before_after/SKILL.md` | **有枢轴** + **无 first/last**; "在Y(或某日期)之前/之后, 哪些…"; 单侧返回**全部** |

## 标准流程 (3-step + 回溯)

1. **路由**: 按上面决策树定 qtype; `cat skills/_shared/NAVIGATION.md` 和 `cat skills/<qtype>/SKILL.md`。
2. **路由键**: 按共享原语把问句解析成 锚实体目录 $D / 关系编码 REL / 方向 / 枢轴 / 时间粒度。
3. **取证**: 按 qtype skill 的 awk 配方过滤 → 抽答案 → 空则回溯。
4. **作答**: `FINAL: <答案>`(下划线还原空格, 时间按粒度截取, 多值 `; ` 分隔)。
