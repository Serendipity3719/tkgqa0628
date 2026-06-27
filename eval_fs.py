# -*- coding: utf-8 -*-
"""
eval_fs.py — 新文件系统方案(database/ + SKILL.md 配方)的基准评测器
===================================================================
忠实复现 SKILL.md 的 Agent 流程:
  1) LLM 把问句解析成结构化 facets:subject/object(其一为 "?")、
     relation_codes(从真实的 251 个关系编码里精确选取)、pivot、time。
  2) 解析为知识库的键:锚实体目录(demonym + token-overlap 解析)、方向、枢轴。
  3) 按 qtype 套用 SKILL.md 第 3 节配方,直接读 data.txt 取证(含方向回溯)。
  4) 与标准答案归一化集合比较,输出逐 qtype 命中率 + 失败样例。

用法:
    python eval_fs.py --n 100
    python eval_fs.py --n 500 --workers 8
    python eval_fs.py --all
"""
import argparse, json, os, re, sys, time, threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB = 'database'
client = OpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY", "set-DEEPSEEK_API_KEY-env-var"),
                base_url="https://api.deepseek.com")

# ----------------------------------------------------------------------------
# 加载 catalog 与 relations
# ----------------------------------------------------------------------------
def _toks(s):
    return [t for t in re.findall(r'[a-z0-9]+', s.replace('_', ' ').lower())]

_STOP = {'the','of','a','an','and','to','with','in','on','for','was','were','did','does',
         'who','which','what','when','whom','that','his','her','its','their','from','by','make','made'}
def _content_toks(s):
    out = []
    for t in _toks(s):
        if t in _STOP: continue
        t = re.sub(r'(ies)$', 'y', t)
        t = re.sub(r'(es|s)$', '', t) if len(t) > 3 else t
        out.append(t)
    return out

CATALOG = {}            # canonical -> dir_path
CAT_ENTRIES = []        # (canonical, set(content_tokens), count)
CAT_NORM = {}           # 'lower space' -> canonical
with open(os.path.join(DB, '_catalog.tsv'), encoding='utf-8') as f:
    for line in f:
        if line.startswith('#'): continue
        p = line.rstrip('\n').split('\t')
        if len(p) < 3: continue
        canon, path, cnt = p[0], p[1], int(p[2])
        CATALOG[canon] = path
        CAT_ENTRIES.append((canon, set(_content_toks(canon)), cnt))
        CAT_NORM[' '.join(_toks(canon))] = canon

ALL_RELATIONS = [l.split('\t')[0] for l in
                 open(os.path.join(DB, '_relations.txt'), encoding='utf-8') if not l.startswith('#')]
REL_SET = set(ALL_RELATIONS)

# 关系族:LLM 在近义关系间易混(尤其 appeal/request/demand、visit make/host)。
# 当主关系检索为空时,回溯扩展到同族关系再试一次。
def _fam(*subs):
    return set(r for r in ALL_RELATIONS if any(s in r.lower() for s in subs))
REL_FAMILIES = [
    _fam('appeal', 'request', 'demand'),
    _fam('make_a_visit', 'host_a_visit'),
    _fam('negotiat', 'meet'),
    _fam('cooperat'),
    _fam('criticiz', 'denounce', 'accus', 'condemn'),
    _fam('optimistic', 'pessimistic', 'empathetic', 'comment'),
]
def family_expand(relset):
    out = set(relset)
    for fam in REL_FAMILIES:
        if relset & fam:
            out |= fam
    return out

# 国民形容词 -> 国名 token(用于实体解析)
DEMONYM = {
 'danish':'denmark','somali':'somalia','swedish':'sweden','finnish':'finland','spanish':'spain',
 'polish':'poland','turkish':'turkey','british':'united kingdom','english':'united kingdom',
 'french':'france','german':'germany','chinese':'china','japanese':'japan','indian':'india',
 'pakistani':'pakistan','russian':'russia','american':'united states','iranian':'iran','iraqi':'iraq',
 'israeli':'israel','egyptian':'egypt','syrian':'syria','lebanese':'lebanon','korean':'korea',
 'vietnamese':'vietnam','thai':'thailand','taiwanese':'taiwan','italian':'italy','greek':'greece',
 'norwegian':'norway','dutch':'netherlands','belgian':'belgium','portuguese':'portugal',
 'brazilian':'brazil','mexican':'mexico','canadian':'canada','australian':'australia',
 'indonesian':'indonesia','philippine':'philippines','filipino':'philippines','malaysian':'malaysia',
 'nigerian':'nigeria','kenyan':'kenya','ethiopian':'ethiopia','sudanese':'sudan','libyan':'libya',
 'afghan':'afghanistan','ukrainian':'ukraine','yemeni':'yemen','cuban':'cuba','argentine':'argentina',
 'argentinian':'argentina','chilean':'chile','colombian':'colombia','venezuelan':'venezuela',
 'swiss':'switzerland','austrian':'austria','saudi':'saudi','palestinian':'palestinian',
 'zimbabwean':'zimbabwe','ugandan':'uganda','rwandan':'rwanda','burmese':'myanmar',
}
SPELL = {'defence':'defense','organisation':'organization','centre':'center',
         'programme':'program','labour':'labor','honour':'honor'}
# 角色/泛指词 -> 库内规范角色短语(KK:leader -> head of government)
ROLE = {'leader':'head government', 'premier':'head government'}

def _expand(tokens):
    out = []
    for t in tokens:
        t = SPELL.get(t, t)
        if t in ROLE:
            out.extend(_content_toks(ROLE[t]))
        elif t in DEMONYM:
            out.extend(_content_toks(DEMONYM[t]))
        else:
            out.append(t)
    return out

# ----------------------------------------------------------------------------
# 实体解析:demonym 展开 + token 重叠打分
# ----------------------------------------------------------------------------
_ecache = {}
def resolve_canon(phrase):
    """实体短语 -> catalog 规范名(canonical);失败返回 None。"""
    if not phrase or phrase == '?': return None
    if phrase in _ecache: return _ecache[phrase]
    key = ' '.join(_toks(phrase))
    res = None
    if key in CAT_NORM:                       # 1) 精确(归一化)
        res = CAT_NORM[key]
    elif phrase.strip().replace(' ', '_') in CATALOG:   # 2) 直接下划线形
        res = phrase.strip().replace(' ', '_')
    else:                                      # 3) demonym/role 展开 + 重叠打分
        ptoks = set(_expand(_content_toks(phrase)))
        if ptoks:
            best = None
            for canon, ctoks, cnt in CAT_ENTRIES:
                inter = ptoks & ctoks
                if not inter: continue
                score = 2 * len(inter) - len(ctoks - ptoks) - len(ptoks - ctoks)
                if ptoks <= ctoks or ctoks <= ptoks: score += 1
                keyv = (score, len(inter), cnt)
                if best is None or keyv > best[0]:
                    best = (keyv, canon, len(inter))
            if best and best[2] >= 1 and best[0][0] >= 1:
                res = best[1]
    _ecache[phrase] = res
    return res

def resolve_entity(phrase):
    c = resolve_canon(phrase)
    return CATALOG.get(c) if c else None

# ----------------------------------------------------------------------------
# 读取实体序列(缓存)
# ----------------------------------------------------------------------------
_cache = {}
_lock = threading.Lock()
def load_rows(dir_path):
    with _lock:
        if dir_path in _cache: return _cache[dir_path]
    rows = []
    fp = os.path.join(DB, *dir_path.split('/'), 'data.txt')
    try:
        with open(fp, encoding='utf-8') as f:
            for line in f:
                p = line.rstrip('\n').split('\t')
                if len(p) == 4: rows.append(tuple(p))   # (date,dir,rel,other)
    except FileNotFoundError:
        pass
    with _lock:
        _cache[dir_path] = rows
    return rows

def _matcher(phrase):
    """返回一个判定函数:other 是否匹配 phrase。
    优先把 phrase 解析成 catalog 规范名做【精确】匹配(避免 'Thailand' 误中
    Government_(Thailand) 等带括号实体);解析失败再退回 token 重叠。"""
    canon = resolve_canon(phrase)
    if canon:
        cn = norm(canon)
        return lambda other: norm(other) == cn
    ptoks = set(_expand(_content_toks(phrase)))
    def f(other):
        if not ptoks: return False
        otoks = set(_expand(_content_toks(other)))
        if ptoks <= otoks: return True
        if len(ptoks) == 1: return ptoks <= otoks
        return len(ptoks & otoks) >= max(2, len(ptoks))
    return f
def norm(s): return re.sub(r'\s+', ' ', s.replace('_', ' ')).strip().lower()

PFX = {'day': 10, 'month': 7, 'year': 4}

# ----------------------------------------------------------------------------
# 配方执行(按 qtype) —— 复现 SKILL.md 第 3 节
# ----------------------------------------------------------------------------
def run_recipe(qtype, f, time_level, answer_type):
    relset = set(c for c in (f.get('relation_codes') or []) if c in REL_SET)
    subj, obj, pivot = f.get('subject'), f.get('object'), f.get('pivot')
    tval = f.get('time')
    ql = f.get('_q', '').lower()

    # 锚实体与答案侧
    if subj == '?' and obj not in (None, '?'):
        anchor_phrase, other_phrase, ans_side = obj, None, 'subject'
    elif obj == '?' and subj not in (None, '?'):
        anchor_phrase, other_phrase, ans_side = subj, None, 'object'
    else:
        anchor_phrase = subj if subj not in (None, '?') else obj
        other_phrase = obj if (subj not in (None, '?') and obj not in (None, '?')) else None
        ans_side = 'time'
    D = resolve_entity(anchor_phrase)
    if not D: return None, f'anchor-unresolved:{anchor_phrase}'
    rows = load_rows(D)
    if not rows: return None, 'empty-rows'
    def relok(r): return (not relset) or (r in relset)
    if not relset: return None, 'rel-unresolved'   # 关系未命中:剪枝(不 match-all)

    dirs = ['<', '>'] if ans_side == 'subject' else (['>', '<'] if ans_side == 'object' else ['>', '<', None])
    m_other = _matcher(other_phrase) if other_phrase else None
    m_pivot = _matcher(pivot) if pivot else None

    # ===== equal / equal_multi =====
    if qtype in ('equal', 'equal_multi'):
        P = PFX.get(time_level, 10)
        # (a) 答案是时间:返回 (anchor, rel, other) 事件的日期前缀集合
        if answer_type == 'time':
            for d in dirs:
                ds = set()
                for (dt, dr, r, o) in rows:
                    if relok(r) and (d is None or dr == d) and (not m_other or m_other(o)):
                        ds.add(dt[:P])
                if ds: return ds, f'time-equal dir={d}'
            return set(), 'equal-time-empty'
        # (b) 答案是实体:按粒度截前缀匹配,返回全部对方
        is_first = 'first' in ql; is_last = 'last' in ql
        for d in dirs:
            t = tval[:P] if tval else None
            if t is None and m_pivot:               # "same ... as X" 先求 X 的事件粒度
                for (dt, dr, r, o) in rows:
                    if relok(r) and (d is None or dr == d) and m_pivot(o):
                        t = dt[:P]; break
            if not t: continue
            hits = []
            for (dt, dr, r, o) in rows:
                if relok(r) and (d is None or dr == d) and dt[:P] == t:
                    if m_pivot and m_pivot(o): continue   # 剔除枢轴本身
                    hits.append((dt, o))
            if not hits: continue
            if is_first or is_last:                 # "该粒度内第一个/最后一个"
                hits.sort(); return {hits[0][1] if is_first else hits[-1][1]}, f'dir={d} t={t} pos'
            return set(o for _, o in hits), f'dir={d} t={t}'
        return set(), 'equal-empty'

    # ===== first_last =====
    if qtype == 'first_last':
        is_first = 'first' in ql
        for d in dirs:
            seq = sorted((dt, o) for (dt, dr, r, o) in rows
                         if relok(r) and (d is None or dr == d)
                         and (not m_other or m_other(o)))
            if not seq: continue
            dt, o = seq[0] if is_first else seq[-1]
            if answer_type == 'time':
                return (dt[:PFX.get(time_level, 10)]), f'dir={d} n={len(seq)}'
            return {o}, f'dir={d} n={len(seq)}'
        return (None if answer_type == 'time' else set()), 'fl-empty'

    # ===== after_first / before_last / before_after =====
    for d in dirs:
        seq = sorted((dt, o) for (dt, dr, r, o) in rows if relok(r) and (d is None or dr == d))
        if not seq: continue
        # 枢轴日期 t0:优先实体枢轴;否则用显式时间
        t0 = None
        if m_pivot:
            for (dt, o) in seq:
                if m_pivot(o): t0 = dt; break
        if t0 is None and tval:
            t0 = tval                    # 日期枢轴(字典序可直接比较)
        if t0 is None: continue
        if qtype == 'after_first':
            for (dt, o) in seq:
                if dt > t0: return {o}, f'dir={d} t0={t0}'
            return set(), 'af-none-after'
        if qtype == 'before_last':
            prev = [o for (dt, o) in seq if dt < t0]
            if prev: return {prev[-1]}, f'dir={d} t0={t0}'
            return set(), 'bl-none'
        if qtype == 'before_after':
            after = ('after' in ql) and ('before' not in ql)
            # 日期枢轴时,"before DATE" 含义为 < 该日;粒度按 day 比较
            res = {o for (dt, o) in seq if (dt > t0 if after else dt < t0)}
            if res: return res, f'dir={d} t0={t0} side={"after" if after else "before"}'
            return set(), 'ba-empty'
    return (None if (qtype == 'first_last' and answer_type == 'time') else set()), 'no-pivot'

# ----------------------------------------------------------------------------
# LLM facet 解析(含 251 关系编码精确选取)
# ----------------------------------------------------------------------------
_REL_BLOCK = "\n".join(ALL_RELATIONS)
PARSE_PROMPT = """Convert a temporal-knowledge-graph question into a structured query. Output ONLY JSON.

You are given the COMPLETE list of valid relation codes. Pick the exact code(s) that match the question's predicate — copy them verbatim.

RELATION CODES:
""" + _REL_BLOCK + """

Output schema:
{{"subject": <entity phrase or "?">, "object": <entity phrase or "?">,
  "relation_codes": [<one or more EXACT codes from the list above>],
  "pivot": <reference entity in a "before X"/"after X"/"same ... as X" clause, else null>,
  "time": <"YYYY" | "YYYY-MM" | "YYYY-MM-DD" if the question explicitly states a date, else null>}}

Rules:
- Exactly one of subject/object is the unknown answer "?", the other is the known anchor entity.
  "Who signed an agreement with China?" -> subject "?", object "China".
  "With whom did Ashton wish to meet?" -> subject "Ashton", object "?".
- EXCEPTION: if the question asks for a TIME (when / which year / which month), BOTH subject and object are the known entities (no "?").
  "In which year did Taiwan's MND last request China?" -> subject "Taiwan's Ministry of National Defence", object "China".
  "When did Vasilis Skouris visit China?" -> subject "Vasilis Skouris", object "China".
- pivot is ONLY the reference entity in before/after/same-as clauses, never the anchor.
  "After the Danish Ministry of Defence, who first visited Iraq?" -> object "Iraq", pivot "Danish Ministry of Defence".
  If the before/after reference is a DATE (e.g. "Before 25 April 2005"), put it in "time", pivot null.
- Keep entity phrases close to surface form (articles may be dropped). Use the relation that best matches the verb,
  e.g. "condemned"->Criticize_or_denounce, "visited"->Make_a_visit, "received a visit"->Host_a_visit,
  "expressed intent to negotiate"->Express_intent_to_meet_or_negotiate, "attacked with small arms"->fight_with_small_arms_and_light_weapons.

qtype: {qtype}
question: {q}
JSON:"""

def parse_facets(question, qtype):
    last = ''
    for attempt in range(4):                      # 重试以抵抗瞬时网络错误
        try:
            r = client.chat.completions.create(
                model='deepseek-chat',
                messages=[{'role':'system','content':'Output strictly valid JSON only.'},
                          {'role':'user','content':PARSE_PROMPT.format(qtype=qtype, q=question)}],
                temperature=0, max_tokens=400, timeout=60)
            txt = r.choices[0].message.content.strip()
            m = re.search(r'\{.*\}', txt, re.S)
            return json.loads(m.group()) if m else {}
        except Exception as e:
            last = str(e)[:100]
            time.sleep(2 * (attempt + 1))
    return {'_err': last}

# ----------------------------------------------------------------------------
# 答案归一化 + 比较
# ----------------------------------------------------------------------------
def norm_ans(x):
    return re.sub(r'\s+', ' ', str(x).replace('_', ' ')).strip().lower()
def is_correct(pred, gold, answer_type):
    g = set(norm_ans(x) for x in gold)
    if pred is None: return False
    p = set(norm_ans(x) for x in pred) if isinstance(pred, (set, list)) else {norm_ans(pred)}
    if answer_type == 'time':
        return bool(p & g)
    return p == g

def _empty(pred):
    return pred is None or (isinstance(pred, (set, list)) and len(pred) == 0)

def evaluate_one(item):
    q, qt = item['question'], item['qtype']
    tl, at = item.get('time_level', 'day'), item.get('answer_type')
    f = parse_facets(q, qt); f['_q'] = q
    try:
        pred, info = run_recipe(qt, f, tl, at)
        if _empty(pred):                       # 回溯:关系族扩展后重试一次
            relset = {c for c in (f.get('relation_codes') or []) if c in REL_SET}
            exp = family_expand(relset)
            if exp != relset:
                f2 = dict(f); f2['relation_codes'] = list(exp)
                pred2, info2 = run_recipe(qt, f2, tl, at)
                if not _empty(pred2):
                    pred, info = pred2, info2 + '|fam'
    except Exception as e:
        pred, info = None, f'EXC:{type(e).__name__}:{e}'
    ok = is_correct(pred, item['answers'], item.get('answer_type'))
    return {'quid': item['quid'], 'qtype': qt, 'ok': ok,
            'pred': sorted(pred) if isinstance(pred, set) else pred, 'gold': item['answers'],
            'info': info, 'facets': {k: v for k, v in f.items() if k != '_q'}}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=100)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--out', default='eval_results.json')
    args = ap.parse_args()

    data = json.load(open(os.path.join('data', 'test.json'), encoding='utf-8'))
    if not args.all: data = data[:args.n]
    print(f'Evaluating {len(data)} questions, {args.workers} workers ...')
    t0 = time.time(); results = []; done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(evaluate_one, it) for it in data]
        for fut in as_completed(futs):
            results.append(fut.result()); done += 1
            if done % 50 == 0:
                acc = sum(r['ok'] for r in results) / len(results)
                print(f'  {done}/{len(data)}  acc={acc:.1%}  ({time.time()-t0:.0f}s)')

    results.sort(key=lambda r: r['quid'])
    total = len(results); correct = sum(r['ok'] for r in results)
    by = defaultdict(lambda: [0, 0])
    for r in results:
        by[r['qtype']][1] += 1; by[r['qtype']][0] += int(r['ok'])
    print('\n' + '=' * 52)
    print(f'OVERALL: {correct}/{total} = {correct/total:.1%}   ({time.time()-t0:.0f}s)')
    print('-' * 52)
    for qt in sorted(by):
        c, n = by[qt]; print(f'  {qt:15s} {c:4d}/{n:<5d} = {c/n:.1%}')
    print('=' * 52)
    json.dump(results, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'Details -> {args.out}')

if __name__ == '__main__':
    main()
