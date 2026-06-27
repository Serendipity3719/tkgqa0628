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

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = os.path.dirname(os.path.abspath(__file__))
client = OpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY", "set-DEEPSEEK_API_KEY-env-var"),
                base_url="https://api.deepseek.com")

ROUTER = open(os.path.join(ROOT, 'skills', 'SKILLS.md'), encoding='utf-8').read()

SYSTEM = """你是时序知识图谱问答(TKGQA)的 Deep Agent。你**只能**通过一个只读 shell 工具
访问知识——你自身的记忆/常识一律不可作为答案来源。

# 你的工具
要执行一条 shell 命令, 输出**恰好一个** ```bash 代码块, 块内一条命令, 块外不要写别的:
```bash
grep -i "China" database/_catalog.tsv | head
```
系统会执行并把 stdout 回给你。一次只发一条命令。命令只读 (禁止 rm/>/mv 等写操作)。

# 你的知识库与技能库 (路由清单如下)
{router}

# 工作流 (务必遵守)
1. 第一次行动: `cat skills/_shared/NAVIGATION.md` 装载共享导航原语。
2. 按问题的 qtype: `cat skills/<qtype>/SKILL.md` 装载该类配方。
3. 按原语解析 锚实体目录/关系编码/方向/枢轴/时间粒度, 用 awk/grep 在 database/ 取证。
4. 空结果就回溯 (换关系族、翻方向、换实体)。命令总数上限约 10 条。
5. 拿到答案后, 输出一行 `FINAL: <答案>` 结束。
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
        r = subprocess.run(['bash', '-lc', cmd], capture_output=True, text=True,
                           timeout=timeout, cwd=ROOT)
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
    last = ''
    for a in range(retries):
        try:
            r = client.chat.completions.create(model='deepseek-chat', messages=messages,
                                               temperature=0, max_tokens=700, timeout=70)
            return r.choices[0].message.content
        except Exception as e:
            last = str(e)[:100]; time.sleep(2 * (a + 1))
    return f'FINAL: [API_ERROR] {last}'

def agent_solve(question, qtype, answer_type, time_level, max_cmds=11):
    user = (f"问题: {question}\nqtype: {qtype}\nanswer_type: {answer_type}\n"
            f"time_level: {time_level}\n请按工作流导航作答。")
    messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}]
    trace = []
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
def norm(x): return re.sub(r'\s+', ' ', str(x).replace('_', ' ')).strip().lower()
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
