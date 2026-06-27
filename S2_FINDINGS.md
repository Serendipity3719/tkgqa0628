# S2a parse 前端 — 结果与(被数据否决的)结论

> 2026-06-27 · n=100, 全部用修好的 UTF-8 plumbing · robust 重判 · 四臂对照。
> 结论: **parse-as-classifier 前端被数据否决**; 原 S2 计划需修正。

---

## 四臂对照 (robust e2e / routing)

| 配置 | robust e2e | routing | 说明 |
|---|---|---|---|
| **oracle** (全 3 个 gold facet) | **91%** | 97% | 上界 |
| **blind** (无任何 gold, 全自推) | **81%** | 88% | 诚实端到端基线 |
| **qtype-blind** (给 ans_type+time_level, qtype 自路由) | **79%** | 88% | ≈ blind (噪声内) |
| **parse** (前端预测 3 个 facet 硬喂) | **77%** | 82% | ⚠️ **比 blind 还差** |

## facet 价值拆解 (关键)

- **qtype 是唯一有价值的 facet**: oracle 91 → qtype-blind 79 = 移除 qtype 单独损失 **~12pt**。
- **answer_type + time_level ≈ 0 价值**: blind 81 vs qtype-blind 79 差 ~2pt(噪声内)。
  agent 从问句就能完美推断它们(parse 实测 answer_type 100% / time_level 99%)。
  → **整个 oracle 优势几乎全部 = 知道 qtype。**

## 为什么 parse 前端是负优化 (已逐条验证, 非噪声)

parse 逐 facet: `answer_type 100% · time_level 99% · qtype 仅 83%`。qtype 错**全部集中在 before_after**:
| gold | 预测 | 次数 |
|---|---|---|
| before_after → before_after | 8 ✓ |
| before_after → **after_first** | **7 ✗** |
| before_after → **before_last** | **5 ✗** |

机理: **agent 会无条件服从被喂入的 qtype 标签, 装载该 skill 且永不自纠**(误路由的 20→? before_after 全错)。
- blind 模式 agent 看完整问句自路由, before_after 还能 55%;
- parse 塞给它一个**自信但错的硬标签**, 压制了 agent 自身判断 → before_after 崩到 **25%**, routing_error 3→11。
- 根因: "After X, **which countries** did Y denounce?"(全部) 与 "After X, **who was first** to..."(单个)
  表面几乎一样, 唯一线索是 "first/last vs 全部"; 分类器抓不住, 把 before_after 当残差桶塞进 after_first/before_last。

## 结论 (修正原 S2 计划)

1. **parse-as-classifier 前端被否决** (77% ≤ blind 81%)。独立分类器在最难的 before_after 上
   **不比 agent 自路由强(都 ~88% skill)**, 且硬标签**会压制 agent**, 净负。
2. **answer_type / time_level 不必预测也不必喂** —— 零价值, agent 自推即可。
3. **诚实自洽基线 = blind 81%**(无需任何前端组件)。这就是系统不依赖 gold 时的真实水平。
4. **要从 81% 追向 91%(qtype 的 12pt), 唯一战场是 `before_after` 消歧** ——
   即 "返回单侧全部" vs "取第一个/最后一个" 的判别, 它线索天然不足。

## 修正后的下一步 (取代原 "parse 前端")

不再加独立分类器。两条都在 **skill 文档层**, 最小改动、可验证:

- **S2′ before_after 消歧 (新)**: 改 `skills/SKILLS.md` 路由表的"适用条件", 把
  "枢轴 + 无 first/last → 返回全部 = before_after" 这条判别**显式强化**, 让 agent 自路由时
  少把 before_after 误当 after_first/before_last。**验证**: 重跑 blind, 看 before_after routing 与 acc。
- **S2b relation/direction 绑定 (原计划)**: Host_a_visit vs Make_a_visit + 方向 `>`/`<`,
  两臂最大单一模型失败 (~5-6/run)。改 `NAVIGATION.md` 的 BIND-REL/BIND-DIR 与 visit 处理。
  **验证**: 重跑, 看 relation_direction_error 数下降。

> 一句话: **S2 的"加前端"思路被自己的实验否决了 —— 这正是诚实实验该有的样子。**
> 真正的杠杆是 before_after 消歧 + relation/direction 绑定, 都在 skill 层, 不需新组件。

## 噪声说明
n=100, ±2-3pt 属采样噪声。但定性结论稳: (a) parse 的 before_after 12/20 误判是真实模式;
(b) qtype 的 ~12pt 远超噪声; (c) answer_type/time_level ~0 价值。建议后续关键对照跑 n≥300 收紧。
