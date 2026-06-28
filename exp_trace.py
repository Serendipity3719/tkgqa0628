# -*- coding: utf-8 -*-
"""
exp_trace.py — TKG2Skill 实验的 Trace 数据模式 (Schema) + 推断层
===================================================================
验证范式: KG -> Skill Library -> Agent Router -> Skill Navigation -> Answer

本模块只做两件事 (无 LLM、无网络、可离线单测):
  1. 定义每个 query 的规范 Trace JSON 结构 (build_trace)。
  2. 从一串 (cmd, obs) tool-call 里**推断**出: 选了哪个 skill、每步处于哪个导航阶段、
     绑定了哪些槽位 (D/REL/DIR/...)、是否回溯。  → 让 legacy 结果也能升级成富 trace。

设计原则: trace 是「可分析、可做 ablation」的事实记录, 不掺入评分逻辑 (评分在 exp_eval.py)。
"""
import re, json, datetime

SCHEMA_VERSION = "tkg-trace/1.0"

# qtype -> 该 qtype 的「正确 skill」(routing 的 gold)。与 skills/SKILLS.md 路由表一致。
GOLD_SKILL = {
    "equal": "equal", "equal_multi": "equal",
    "first_last": "first_last",
    "after_first": "after_first",
    "before_last": "before_last",
    "before_after": "before_after",
}

# ---- 命令模式识别 ----------------------------------------------------------
_RE_SKILL_LOAD = re.compile(r'skills/([A-Za-z_]+)/SKILL(?:\.v2)?\.md')
_RE_NAV_LOAD   = re.compile(r'_shared/NAVIGATION\.md')
_RE_CATALOG    = re.compile(r'_catalog\.tsv')
_RE_RELATIONS  = re.compile(r'_relations\.txt')
_RE_DATAFILE   = re.compile(r'/data\.txt')

# ---- 槽位抽取 (从 awk/grep 里反推 Agent 已绑定的导航键) --------------------
_RE_D   = re.compile(r'database/(.+?)/data\.txt')
_RE_REL = re.compile(r'(?:-v\s+rel=|\$3\s*==\s*)"([^"]+)"')
_RE_DIR = re.compile(r'(?:-v\s+dir=|\$2\s*==\s*)"([<>])"')
_RE_OTH = re.compile(r'\$4\s*==\s*"([^"]+)"')
_RE_P   = re.compile(r'-v\s+p=(\d+)')
_RE_T   = re.compile(r'-v\s+t="([^"]+)"')
# 显式 STATE 账本行 (v2 schema 的 Agent 会写; 旧 skill 不写, 则为 None)
_RE_STATE = re.compile(r'STATE:\s*(.+)', re.I)

# 空结果 / 错误 标记 (与 agent_nav.run_bash 的返回约定一致)
_EMPTY_MARKERS = ('[空结果]', '')
_ERR_MARKERS   = ('[超时]', '[blocked]', '[错误]', '[stderr]', '[pivot-not-found]')


def detect_skill_load(cmd):
    """命令是否在装载某个过程 skill; 返回 skill 名 (=qtype 目录) 或 None。"""
    m = _RE_SKILL_LOAD.search(cmd)
    return m.group(1) if m else None


def classify_phase(cmd):
    """把一条 tool-call 归到导航流水线的一个阶段。"""
    if _RE_NAV_LOAD.search(cmd):     return "load_nav"
    if _RE_SKILL_LOAD.search(cmd):   return "load_skill"
    if _RE_CATALOG.search(cmd) or _RE_RELATIONS.search(cmd): return "bind"
    if _RE_DATAFILE.search(cmd):     return "evidence"
    return "other"


def extract_facets(cmd):
    """从命令反推已绑定的导航槽位 (供 intermediate-state 重建)。缺失则不含该键。"""
    f = {}
    for key, rgx in (("D", _RE_D), ("REL", _RE_REL), ("DIR", _RE_DIR),
                      ("OTHER", _RE_OTH), ("T", _RE_T)):
        m = rgx.search(cmd)
        if m:
            f[key] = m.group(1).strip('"')
    m = _RE_P.search(cmd)
    if m:
        f["P"] = int(m.group(1))
    return f


def parse_state_line(thought):
    """若 Agent 推理里显式写了 `STATE: ...` 账本行, 解析成 dict; 否则 None。"""
    if not thought:
        return None
    m = _RE_STATE.search(thought)
    if not m:
        return None
    st = {}
    for tok in m.group(1).split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            st[k] = v
    return st or None


def obs_is_empty(obs):
    o = (obs or "").strip()
    return o in _EMPTY_MARKERS or o.startswith('[空结果]')


def obs_is_error(obs):
    o = (obs or "")
    return any(mk in o for mk in _ERR_MARKERS)


# ---- Fallback 检测 (回溯原因标记) -------------------------------------------
# 从 cmd 序列中识别已知的 fallback 模式, 产出可统计的标签
_RE_BY_YEAR   = re.compile(r'by_year/')
_RE_DATAFILE  = re.compile(r'/data\.txt')
_RE_REL_FAM   = re.compile(r'_relation_families\.tsv')
_RE_FLIP_DIR  = re.compile(r'\$2\s*==\s*"([<>])"')
_RE_CATALOG_RE= re.compile(r'_catalog\.tsv')


def _detect_fallback_patterns(steps_list):
    """扫描已富化的 steps, 识别常见回溯模式。返回 fallback_log 列表。"""
    log = []
    prev_cmds = []  # 前几条 cmd 文本
    prev_empty = False
    for s in steps_list:
        cmd = s.get("tool_call", {}).get("cmd", "")
        empty = s.get("obs_empty", False)

        # 模式 A: by_year 切片空 → 回退 data.txt 全量
        if _RE_DATAFILE.search(cmd) and not _RE_BY_YEAR.search(cmd):
            prev_by_year = any(_RE_BY_YEAR.search(c) for c in prev_cmds[-3:])
            if prev_by_year and not empty:
                log.append({"turn": s["turn"],
                           "reason": "by_year_to_full",
                           "detail": "切片无结果或不全, 回退全量 data.txt"})

        # 模式 B: 方向翻转 ($2=="<" → $2==">" 或反之)
        dirs = _RE_FLIP_DIR.findall(cmd)
        prev_dirs = []
        for pc in prev_cmds[-4:]:
            prev_dirs.extend(_RE_FLIP_DIR.findall(pc))
        if dirs and prev_dirs and dirs[0] != prev_dirs[-1] and prev_empty:
            log.append({"turn": s["turn"],
                       "reason": "flip_direction",
                       "detail": f"方向 {prev_dirs[-1]} → {dirs[0]} (前次空结果)"})

        # 模式 C: 尝试不同关系码 (同族 fallback)
        if _RE_REL_FAM.search(cmd) and prev_empty:
            log.append({"turn": s["turn"],
                       "reason": "alt_relation_family",
                       "detail": "重新查 _relation_families.tsv 换码"})

        # 模式 D: 换实体 (grep catalog 不同 token)
        if _RE_CATALOG_RE.search(cmd) and prev_empty:
            # check if previous catalog grep used different tokens
            pass

        prev_cmds.append(cmd)
        if len(prev_cmds) > 6:
            prev_cmds = prev_cmds[-6:]
        prev_empty = empty

    return log


# ---- Trace 组装 ------------------------------------------------------------
def build_steps(raw_steps):
    """
    raw_steps: [{'cmd':..., 'obs':..., 'thought':...(可选)}]  按时间序
    返回富化后的 navigation steps + 汇总统计 + fallback_log + 推断出的 selected_skill。
    """
    steps, carry = [], {}          # carry = 截至当前已绑定的槽位 (前向累积)
    selected_skill, routing_turn = None, None
    prev_evidence_empty = False
    num_evidence = num_backtrack = 0
    used_by_year = False           # P2: 是否访问了 by_year/ 时序切片
    used_index = False             # P2: 是否读了 INDEX.md
    used_rel_fam = False           # P1: 是否查了 _relation_families.tsv

    for i, s in enumerate(raw_steps):
        cmd, obs = s.get("cmd", ""), s.get("obs", "")
        thought = s.get("thought", "")
        phase = classify_phase(cmd)

        sk = detect_skill_load(cmd)
        if sk and selected_skill is None:
            selected_skill, routing_turn = sk, i + 1

        # P1/P2 使用标记
        if "by_year/" in cmd:      used_by_year = True
        if "INDEX.md" in cmd:      used_index = True
        if "_relation_families.tsv" in cmd: used_rel_fam = True

        carry = {**carry, **extract_facets(cmd)}   # 前向累积绑定
        empty = obs_is_empty(obs)
        is_backtrack = (phase == "evidence" and prev_evidence_empty)
        if phase == "evidence":
            num_evidence += 1
            if is_backtrack:
                num_backtrack += 1
            prev_evidence_empty = empty

        steps.append({
            "turn": i + 1,
            "phase": "backtrack" if is_backtrack else phase,
            "thought": (thought or "")[:500],
            "tool_call": {"tool": "bash", "cmd": cmd,
                          "blocked": "[blocked]" in (obs or "")},
            "observation": (obs or "")[:600],
            "obs_empty": empty,
            "obs_error": obs_is_error(obs),
            # intermediate state: 优先用显式 STATE 行, 否则用反推的累积槽位
            "state": parse_state_line(thought) or dict(carry),
        })

    fallback_log = _detect_fallback_patterns(steps)

    return steps, {
        "selected_skill": selected_skill,
        "routing_turn": routing_turn,
        "num_steps": len(steps),
        "num_tool_calls": len(steps),
        "num_evidence_calls": num_evidence,
        "num_backtracks": num_backtrack,
        "final_state": dict(carry),
        # P1/P2 行为标记
        "used_relation_families": used_rel_fam,
        "used_index_md": used_index,
        "used_by_year": used_by_year,
        # 回溯原因标记
        "fallback_log": fallback_log,
    }


ALL_FACETS = ["qtype", "answer_type", "time_level"]


def build_trace(quid, question, gold_qtype, answer_type, time_level,
                raw_steps, final, gold, correct,
                revealed_facets=None, predicted_facets=None, model=None):
    """组装一条规范 Trace。raw_steps=[{cmd,obs,thought?}]。
    revealed_facets: 推理期喂给 Agent 的 gold 元数据子集 (S1 facet-blind ablation)。
      含 'qtype' → routing_mode=oracle; 否则 blind。默认全给 (= 旧 oracle 行为)。"""
    if revealed_facets is None:
        revealed_facets = list(ALL_FACETS)
    # parse 模式喂的是预测 facet(非 gold), 不算 oracle
    if predicted_facets is not None:
        routing_mode = "parse"
    else:
        routing_mode = "oracle" if "qtype" in revealed_facets else "blind"
    steps, agg = build_steps(raw_steps)
    sel = agg["selected_skill"]
    gold_skill = GOLD_SKILL.get(gold_qtype)
    routing_correct = (sel is not None and sel == gold_skill)
    return {
        "schema_version": SCHEMA_VERSION,
        "quid": quid,
        "question": question,
        "meta": {
            "gold_qtype": gold_qtype,
            "answer_type": answer_type,
            "time_level": time_level,
            "routing_mode": routing_mode,    # oracle = qtype 已喂给 Agent; blind = 仅凭问句路由
            "revealed_facets": revealed_facets,   # 哪些 gold 元数据被喂入 (ablation 维度)
            "predicted_facets": predicted_facets, # parse 模式: 前端自推的 facet (非 gold)
            "model": model,
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        "routing": {
            "selected_skill": sel,
            "selected_skill_path": f"skills/{sel}/SKILL.md" if sel else None,
            "gold_skill": gold_skill,
            "routing_observed": sel is not None,
            "routing_correct": routing_correct,
            "routing_turn": agg["routing_turn"],
        },
        "navigation": {
            "steps": steps,
            "num_steps": agg["num_steps"],
            "num_tool_calls": agg["num_tool_calls"],
            "num_evidence_calls": agg["num_evidence_calls"],
            "num_backtracks": agg["num_backtracks"],
            "reconstructed_state": agg["final_state"],
        },
        "answer": {"final": final, "gold": gold, "correct": bool(correct)},
        # failure.* 由 exp_eval.classify_failure 填充, 保持 trace 与评分解耦
        "failure": {"is_failure": not bool(correct), "category": None, "evidence": None},
    }


# ---- legacy 适配: 把 agent_nav_*.json 的旧记录升级成富 trace -----------------
def from_legacy(rec, question=None, answer_type=None, time_level=None):
    """
    旧记录形如 {quid,qtype,ok,cmds,final,gold,trace:[{cmd,obs}]} (无 question/answer_type)。
    legacy 一律标 routing_mode='oracle' (旧 runner 把 qtype 喂给了 Agent)。
    """
    return build_trace(
        quid=rec.get("quid"),
        question=question or rec.get("question", ""),
        gold_qtype=rec.get("qtype"),
        answer_type=answer_type or rec.get("answer_type"),
        time_level=time_level or rec.get("time_level"),
        raw_steps=rec.get("trace", []),
        final=rec.get("final", ""),
        gold=rec.get("gold", []),
        correct=rec.get("ok", False),
        revealed_facets=list(ALL_FACETS),   # legacy runner 喂了全部 3 个 gold facet
        model=rec.get("model", "deepseek-chat"),
    )


def normalize_record(rec, **kw):
    """统一入口: 已是富 trace 直接返回; 否则按 legacy 升级。"""
    if rec.get("schema_version") == SCHEMA_VERSION:
        return rec
    return from_legacy(rec, **kw)


if __name__ == "__main__":
    # 自检: 用一条最小 legacy 记录跑通推断
    demo = {
        "quid": 1, "qtype": "after_first", "ok": True, "final": "Jack Straw",
        "gold": ["Jack Straw"], "trace": [
            {"cmd": "cat skills/_shared/NAVIGATION.md", "obs": "...(primitives)..."},
            {"cmd": "cat skills/after_first/SKILL.md", "obs": "...(recipe)..."},
            {"cmd": 'grep -i "Iraq" database/_catalog.tsv', "obs": "Iraq\tentities/i/Iraq\t..."},
            {"cmd": 'awk -F"\\t" -v rel="Make_a_visit" \'$2=="<" && $3==rel\' database/entities/i/Iraq/data.txt',
             "obs": "2005-04-12\t<\tMake_a_visit\tJack_Straw"},
        ],
    }
    t = from_legacy(demo, question="After Denmark, who first visited Iraq?")
    print(json.dumps(t, ensure_ascii=False, indent=2))
