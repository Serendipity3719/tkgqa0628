# -*- coding: utf-8 -*-
"""
exp_parse.py — S2a: 解析前端 (parse skill)
===================================================================
把之前**喂给 Agent 的 3 个 gold facet (qtype/answer_type/time_level)** 改成
**从问句自推**。一次 LLM 调用, 输出结构化 facet, 供 serve 循环路由与取证。

研究意义: 让系统在推理期不再依赖任何 gold 元数据 (P1 收尾), 并把 pipeline 拆成
可独立度量的两段 —— parse 段 (facet 准确率) + execute 段 (给定 facet 的导航能力)。

execute skill 完全不动; 本模块只新增前端。
"""
import json, re
import agent_nav as AN   # 复用同一个 LLM 客户端 (_chat) 与 DeepSeek 配置

QTYPES = ["equal", "equal_multi", "first_last", "after_first", "before_last", "before_after"]

PARSE_PROMPT = """你是时序知识图谱问答(TKGQA)的**问题解析器**。只读问句, 判断它的查询类型与答案形态。
输出**一行 JSON**, 字段恰好三个, 不要任何解释:
{"qtype": "...", "answer_type": "...", "time_level": "..."}

## qtype (六选一) —— 看是否有"枢轴(另一个实体或显式日期)"以及取首/尾/全部
- after_first : "After <枢轴>, who was the FIRST to ..." 有枢轴 + 取之后第一个
- before_last : "Before <枢轴>, who ... LAST" 有枢轴 + 取之前最后一个
- before_after: "Before/After <日期或枢轴>, which ... " 有枢轴, 取该侧**全部** (无 first/last)
- first_last  : "X 第一次/最后一次 ... 是何时/对谁" **无枢轴**, 取序列首/尾
- equal       : "在某日/某月/某年 ... " 或 "who ... on/in <时间>" 单一时刻
- equal_multi : "在与 X **同月/同年** ... " (same month/year as X) 这类需先定位 X 时间

## answer_type (二选一)
- time   : 问 when / what year / which month / at what time / 在哪一年/月
- entity : 问 who / which country / with whom / 谁/哪个国家

## time_level (三选一)
- year : 问句出现 year / 年
- month: 问句出现 month / 月
- day  : 其余 (默认, 含具体日期 DD)

只输出 JSON。"""


def parse_question(question):
    """一次 LLM 调用 → {qtype, answer_type, time_level}。失败则回退到保守默认。"""
    msgs = [{"role": "system", "content": PARSE_PROMPT},
            {"role": "user", "content": f"问句: {question}"}]
    reply = AN._chat(msgs)
    return _extract(reply)


def _extract(reply):
    m = re.search(r"\{.*\}", reply or "", re.S)
    out = {"qtype": None, "answer_type": None, "time_level": None}
    if m:
        try:
            d = json.loads(m.group(0))
            out["qtype"] = d.get("qtype")
            out["answer_type"] = d.get("answer_type")
            out["time_level"] = d.get("time_level")
        except Exception:
            pass
    # 归一化 + 保守回退 (绝不让 None 流入下游)
    if out["qtype"] not in QTYPES:
        out["qtype"] = "equal"
    if out["answer_type"] not in ("entity", "time"):
        out["answer_type"] = "entity"
    if out["time_level"] not in ("day", "month", "year"):
        out["time_level"] = "day"
    return out


# 路由层等价: equal 与 equal_multi 共用 skills/equal, 比较时归一到 skill 名
def parse_facet_correct(pred, gold_item):
    """逐 facet 对错 + 路由对错 (skill 级, equal/equal_multi 视为同)。"""
    from exp_trace import GOLD_SKILL
    g_qt = gold_item["qtype"]
    return {
        "qtype": pred["qtype"] == g_qt,
        "skill": GOLD_SKILL.get(pred["qtype"]) == GOLD_SKILL.get(g_qt),   # 路由是否会对
        "answer_type": pred["answer_type"] == gold_item.get("answer_type"),
        "time_level": pred["time_level"] == gold_item.get("time_level"),
    }


if __name__ == "__main__":
    # 离线无法调 LLM; 仅测 _extract 解析鲁棒性
    for s in ['{"qtype":"after_first","answer_type":"entity","time_level":"day"}',
              'json: {"qtype":"bad","answer_type":"time","time_level":"year"} 解释...',
              '乱七八糟无 JSON']:
        print(s[:40], "->", _extract(s))
