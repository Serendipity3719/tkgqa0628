# -*- coding: utf-8 -*-
"""
agent_nav.py — 真·Deep Agent 导航实验 (双层 Skill 库)
===================================================================
验证目标: 一个 LLM agent 用单个只读 `bash` 工具, 真实地
  读路由清单 -> 装载 qtype 过程 skill -> 在 database/ 数据层 awk 取证 -> 自主回溯
端到端作答, 测命中率, 并与 eval_fs.py 的 oracle 上界(~88%)对比, 量化"导航损耗"。

与 eval_fs.py 的本质区别:
  eval_fs.py = LLM 解析 facets, Python 死写 recipe 直读文件 (oracle/模拟)。
  agent_nav.py = LLM 自己读 skill、自己拼 awk、自己回溯 (真导航)。

用法:
    python agent_nav.py --n 100 --workers 6
"""
import argparse, json, os, re, subprocess, sys, time, threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from tkgqa_skills.policy.navigation_policy import NavigationPolicy
from tkgqa_skills.routing.cluster_taxonomy import cluster_for_id, semantic_cluster_dirname
from tkgqa_skills.routing.semantic_router import route_query

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = os.path.dirname(os.path.abspath(__file__))

# DeepSeek API 配置
# - DEEPSEEK_API_KEY: 必需。不要写进代码或提交到 git。
# - DEEPSEEK_BASE_URL: 默认官方 OpenAI-compatible endpoint。
# - DEEPSEEK_MODEL: 默认 deepseek-chat 以保持历史 trace 可比性；新实验可显式设为
#   deepseek-v4-flash / deepseek-v4-pro。详见 scripts/deepseek_smoke.py 与 API_RUNBOOK_2026-06-29.md。
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_TIMEOUT = float(os.environ.get("DEEPSEEK_TIMEOUT", "70"))

client = OpenAI(api_key=DEEPSEEK_API_KEY or "missing-DEEPSEEK_API_KEY",
                base_url=DEEPSEEK_BASE_URL)

ROUTER = open(os.path.join(ROOT, 'skills', 'SKILLS.md'), encoding='utf-8').read()

SYSTEM = """你是时序知识图谱问答(TKGQA)的 Navigation Policy Agent。你**只能**通过一个只读 shell 工具
访问知识——你自身的记忆/常识一律不可作为答案来源。

# 你的工具
要执行一条 shell 命令, 输出**恰好一个** ```bash 代码块, 块内一条命令, 块外不要写别的:
```bash
cat tkgqa/root/index.md
```
系统会执行并把 stdout 回给你。一次只发一条命令。命令只读 (禁止 rm/>/mv 等写操作)。

# 你的知识库与技能库 (路由清单如下)
{router}

# NPL 工作流 (务必遵守)
1. 第一次行动: `cat skills/_shared/NAVIGATION.md` 装载共享导航原语。
2. 读 `tkgqa/root/index.md`, `tkgqa/semantic_clusters/index.md`, 以及 `tkgqa/indexes/cross_skill_links.json`。
3. 使用用户消息里的 `Phase5 npl_hint` 作为 policy output: 必须 inspect Top-2 semantic clusters。
4. Branch fail 时先按 `cross_skill_links.json` 做 cross-skill jump, 不要立刻 grep global catalog。
5. 按问题的 qtype: `cat skills/<qtype>/SKILL.md` 装载该类配方。
6. 到 semantic entity / temporal slice leaf 后, 用 leaf 指向的 database fact_doc 做 awk/grep 取证。
7. 若 Top-2 + cross-skill jumps 都失败, trace 标记 `fallback_reason: semantic_top2_exhausted`, 再回退 `database/_catalog.tsv` 全局检索。
8. 拿到答案后, 输出一行 `FINAL: <答案>` 结束。
   - 实体名下划线还原空格 (Jack_Straw -> Jack Straw), 括号/逗号/变音字符保留。
   - 多个答案用 ` ; ` 分隔。时间按粒度截取 (year=前4位, month=前7位, day=完整)。
   - 查不到 -> `FINAL: 知识库中无相关事实`。
不要在没跑命令、没看到证据行时就 FINAL。"""

SYSTEM = SYSTEM.replace('{router}', ROUTER)

_BLOCK = re.compile(r'```(?:bash|sh)?\s*\n(.*?)```', re.S)
# 只封禁破坏性命令名 + 重定向到受保护目录; 不碰 awk 里的 `>` 比较和 `> /tmp` 暂存
_BANNED_CMD = re.compile(r'(^|[\s;|&(])(rm|mv|cp|dd|chmod|chown|mkfifo|truncate|sudo|tee|rsync|install|shred|ln)([\s]|$)')
_BAD_REDIR = re.compile(r'>\s*(database|skills|\.\.|~|/(?!tmp))')

def run_bash(cmd, timeout=25):
    if _BANNED_CMD.search(cmd) or _BAD_REDIR.search(cmd):
        return '[blocked] 只读环境: 禁止破坏性命令/写入 database|skills。awk 的 `>` 比较和 `> /tmp/...` 暂存允许。'
    try:
        # KG 实体名含变音字符(Keïta/Gül 等)→ 必须 utf-8 解码, 否则 Windows 默认 GBK 会崩
        r = subprocess.run(['bash', '-lc', cmd], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=timeout, cwd=ROOT)
        out = r.stdout
        if r.returncode != 0 and r.stderr:
            out += '\n[stderr] ' + r.stderr
        out = out.strip()
        if not out:
            return '[空结果]'
        if len(out) > 2500:
            out = out[:2500] + '\n[...截断...]'
        return out
    except subprocess.TimeoutExpired:
        return '[超时] 命令耗时过长, 换更精确的 awk 过滤。'
    except Exception as e:
        return f'[错误] {e}'

def _chat(messages, retries=4):
    if not DEEPSEEK_API_KEY:
        return 'FINAL: [API_ERROR] missing DEEPSEEK_API_KEY; run scripts/deepseek_smoke.py before experiments'

    last = ''
    for a in range(retries):
        try:
            r = client.chat.completions.create(model=DEEPSEEK_MODEL, messages=messages,
                                               temperature=0, max_tokens=700, timeout=DEEPSEEK_TIMEOUT)
            return r.choices[0].message.content
        except Exception as e:
            last = f'{type(e).__name__}: {str(e)}'[:300]
            time.sleep(2 * (a + 1))
    return f'FINAL: [API_ERROR] {last}'

def semantic_route_hint(question):
    try:
        routed = route_query(question, mode=os.environ.get("SEMANTIC_ROUTING_MODE", "lexical"), top_k=2)
        npl = NavigationPolicy(inspect_k=2).decide(question, routed)
        cluster_dirs = [semantic_cluster_dirname(cluster_for_id(cid)) for cid in routed.get("semantic_clusters", [])]
        routing_path = {
            "semantic_cluster": cluster_dirs[0] if cluster_dirs else None,
            "entity_candidate": routed.get("entity_candidates", [None])[0] if routed.get("entity_candidates") else None,
            "relation_cluster": routed.get("relation_clusters", [None])[0] if routed.get("relation_clusters") else None,
            "temporal_leaf": routed.get("temporal_candidates", [None])[0] if routed.get("temporal_candidates") else None,
        }
        routed["semantic_cluster_dirs"] = cluster_dirs
        routed["routing_path"] = routing_path
        routed["npl_decision"] = npl.get("decision", {})
        routed["npl_trace"] = npl.get("trace", {})
        routed["metrics"] = {
            "top_level_routing_accuracy": None,
            "semantic_cluster_hit": None,
            "cluster_backtracking_count": 0,
        }
        return routed
    except Exception as e:
        return {
            "semantic_clusters": [],
            "semantic_cluster_dirs": [],
            "entity_candidates": [],
            "relation_clusters": [],
            "temporal_candidates": [],
            "routing_scores": {},
            "npl_decision": {},
            "npl_trace": {},
            "routing_path": {
                "semantic_cluster": None,
                "entity_candidate": None,
                "relation_cluster": None,
                "temporal_leaf": None,
            },
            "metrics": {
                "top_level_routing_accuracy": None,
                "semantic_cluster_hit": False,
                "cluster_backtracking_count": 0,
            },
            "fallback_reason": f"semantic_router_error:{type(e).__name__}",
        }

def agent_solve(question, qtype, answer_type, time_level, max_cmds=11):
    semantic_hint = semantic_route_hint(question)
    user = (f"问题: {question}\nqtype: {qtype}\nanswer_type: {answer_type}\n"
            f"time_level: {time_level}\n"
            f"Phase5 npl_hint:\n{json.dumps(semantic_hint, ensure_ascii=False, indent=2)}\n"
            f"请按工作流导航作答。")
    messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}]
    trace = [{'semantic_route': semantic_hint, 'routing_path': semantic_hint.get('routing_path'),
              'metrics': semantic_hint.get('metrics')}]
    cmds = 0
    for _turn in range(max_cmds + 4):
        reply = _chat(messages)
        messages.append({'role': 'assistant', 'content': reply})
        # 先看是否给了 FINAL
        mfin = re.search(r'FINAL:\s*(.+)', reply, re.S)
        mblk = _BLOCK.search(reply)
        # FINAL 被错误包进 ```bash 块时, 当作 FINAL 处理而非命令
        if mblk and mblk.group(1).strip().upper().startswith('FINAL:'):
            return mblk.group(1).strip()[6:].strip(), trace, cmds
        if mblk and (not mfin or mblk.start() < mfin.start()):
            cmd = mblk.group(1).strip()
            cmds += 1
            obs = run_bash(cmd)
            trace.append({'cmd': cmd, 'obs': obs[:600]})
            if cmds > max_cmds:
                messages.append({'role': 'user', 'content': '命令数已达上限, 请基于已有证据给出 FINAL。'})
            else:
                messages.append({'role': 'user', 'content': f'命令输出:\n{obs}'})
            continue
        if mfin:
            return mfin.group(1).strip(), trace, cmds
        # 既无命令也无 FINAL: 提示
        messages.append({'role': 'user', 'content': '请输出一个 ```bash 命令块, 或给出 FINAL:。'})
    return '[无答案]', trace, cmds

# -------- 评分 (与 eval_fs 同口径: 实体=集合精确, 时间=交集非空) --------
def norm(x):
    s = re.sub(r'[*`#]', '', str(x).replace('_', ' '))   # 去 markdown(LLM 常给答案加 ** 等)
    return re.sub(r'\s+', ' ', s).strip().strip(' .,:;!?"\'').lower()
def parse_final(s):
    s = re.sub(r'^\s*\[?API_ERROR.*$', '', s)
    parts = [p for p in re.split(r'\s*;\s*|\s*、\s*', s.strip()) if p.strip()]
    return parts

def is_correct(final, gold, answer_type):
    if '知识库中无相关事实' in final or '[无答案]' in final or '[API_ERROR' in final:
        return False
    pred = set(norm(p) for p in parse_final(final))
    g = set(norm(x) for x in gold)
    if not pred: return False
    if answer_type == 'time':
        # 任一 gold 时间出现在预测里 (粒度容错: 互为前缀)
        for a in pred:
            for b in g:
                if a == b or a.startswith(b) or b.startswith(a):
                    return True
        return False
    return pred == g

def evaluate_one(item):
    final, trace, cmds = agent_solve(item['question'], item['qtype'],
                                     item.get('answer_type'), item.get('time_level', 'day'))
    ok = is_correct(final, item['answers'], item.get('answer_type'))
    return {'quid': item['quid'], 'qtype': item['qtype'], 'ok': ok, 'cmds': cmds,
            'final': final, 'gold': item['answers'], 'trace': trace}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=100)
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--out', default='agent_nav_results.json')
    args = ap.parse_args()

    data = json.load(open(os.path.join('data', 'test.json'), encoding='utf-8'))[:args.n]
    print(f'真 Agent 导航实验: {len(data)} 题, {args.workers} 并发 ...')
    print(f'DeepSeek API: base_url={DEEPSEEK_BASE_URL} model={DEEPSEEK_MODEL} key_present={bool(DEEPSEEK_API_KEY)}')
    t0 = time.time(); results = []; done = 0
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(evaluate_one, it) for it in data]
        for fut in as_completed(futs):
            r = fut.result()
            with lock:
                results.append(r); done += 1
                if done % 10 == 0:
                    acc = sum(x['ok'] for x in results) / len(results)
                    avgc = sum(x['cmds'] for x in results) / len(results)
                    print(f'  {done}/{len(data)}  acc={acc:.1%}  avg_cmds={avgc:.1f}  ({time.time()-t0:.0f}s)')

    results.sort(key=lambda r: r['quid'])
    total = len(results); correct = sum(r['ok'] for r in results)
    by = defaultdict(lambda: [0, 0])
    for r in results:
        by[r['qtype']][1] += 1; by[r['qtype']][0] += int(r['ok'])
    print('\n' + '=' * 54)
    print(f'真 Agent 导航端到端: {correct}/{total} = {correct/total:.1%}   ({time.time()-t0:.0f}s)')
    print(f'平均命令数/题: {sum(r["cmds"] for r in results)/total:.1f}')
    print('-' * 54)
    for qt in sorted(by):
        c, n = by[qt]; print(f'  {qt:15s} {c:4d}/{n:<4d} = {c/n:.1%}')
    print('=' * 54)
    json.dump(results, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'轨迹 -> {args.out}')

if __name__ == '__main__':
    main()
