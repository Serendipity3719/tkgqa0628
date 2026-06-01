"""Debug remaining failures - part 2."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RECORDS = []
with open('full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            subj, rel, obj, date = parts
            RECORDS.append({'subj': subj.replace('_',' '), 'rel': rel.replace('_',' '),
                            'obj': obj.replace('_',' '), 'date': date})

def search(subj_kws=None, rel_kws=None, obj_kws=None, time_prefix=None):
    results = []
    for r in RECORDS:
        if time_prefix and not r['date'].startswith(time_prefix): continue
        if subj_kws:
            sl = r['subj'].lower()
            if not all(kw.lower() in sl for kw in subj_kws): continue
        if rel_kws:
            rl = r['rel'].lower()
            if not any(kw.lower() in rl for kw in rel_kws): continue
        if obj_kws:
            ol = r['obj'].lower()
            if not all(kw.lower() in ol for kw in obj_kws): continue
        results.append(r)
    return results

with open('test.json', 'r', encoding='utf-8') as f:
    test_data = json.load(f)

def show_q(idx):
    q = test_data[idx-1]
    print(f"Q{idx}: {q['question']}")
    print(f"  type: {q.get('qtype', q.get('type',''))}")
    print(f"  answer: {q.get('answers', q.get('answer',''))}")

# Q8: Malaysia optimistic before 22 Oct 2008
show_q(8)
print("Malaysia+optimistic before 2008-10-22:")
recs = search(subj_kws=['malaysia'], rel_kws=['optimistic'])
before = [r for r in recs if r['date'] < '2008-10-22']
print(f"  Count: {len(before)}")
for r in sorted(before, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print()
show_q(12)
# Q12: need to find what rel/subj/obj
# GT: Al-Shabaab, Military (Burundi)
# Let's check what connects them
recs = search(subj_kws=['al-shabaab'], obj_kws=['burundi'])
print(f"Al-Shabaab -> Burundi: {len(recs)}")
recs2 = search(subj_kws=['burundi'], obj_kws=['al-shabaab'])
print(f"Burundi -> Al-Shabaab: {len(recs2)}")
# Check what rel connects them
recs3 = search(obj_kws=['military', 'burundi'])
print(f"Military Burundi as obj: {len(recs3)}")
for r in sorted(recs3, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print()
show_q(17)
# Q17: Before Military (Taiwan), who last did China threaten?
# GT: Angela Merkel (2007-09-20)
# Military Taiwan last date: 2015-11-25
# China threaten Japan last: 2015-12-03 (AFTER 2015-11-25!)
# China threaten Merkel: 2007-09-20 (BEFORE 2015-11-25)
# So the issue is: what is the t_ref for "Military (Taiwan)"?
# The question says "Before Military (Taiwan)" - this means before the LAST event involving Military Taiwan
# OR before the FIRST event involving Military Taiwan?
# Let's check what the question actually says
# The t_ref should be the LAST event of Military Taiwan
mil_tw = search(subj_kws=['military', 'taiwan'])
mil_tw += search(obj_kws=['military', 'taiwan'])
mil_tw.sort(key=lambda x: x['date'])
print(f"Military Taiwan events: {len(mil_tw)}")
print(f"  First: {mil_tw[0]['date']} {mil_tw[0]['subj']} | {mil_tw[0]['rel']} | {mil_tw[0]['obj']}")
print(f"  Last: {mil_tw[-1]['date']} {mil_tw[-1]['subj']} | {mil_tw[-1]['rel']} | {mil_tw[-1]['obj']}")
# China threaten before 2015-11-25
china_thr = search(subj_kws=['china'], rel_kws=['threaten'])
before_mil = [r for r in china_thr if r['date'] < '2015-11-25']
before_mil.sort(key=lambda x: x['date'])
print(f"China threaten before 2015-11-25: {len(before_mil)}")
if before_mil:
    print(f"  Last: {before_mil[-1]['date']} {before_mil[-1]['subj']} | {before_mil[-1]['rel']} | {before_mil[-1]['obj']}")

print()
show_q(32)
# Q32: before_last, GT: Citizen (Thailand)
# Need to find what rel/subj/obj
# Let's check what connects to Citizen Thailand
recs = search(obj_kws=['citizen', 'thailand'])
print(f"Citizen Thailand as obj: {len(recs)}")
# What rels?
from collections import Counter
rels = Counter(r['rel'] for r in recs)
print("Top rels:", rels.most_common(5))

print()
show_q(42)
# Q42: before_after, GT: Citizen (Thailand)
recs = search(subj_kws=['citizen', 'thailand'])
print(f"Citizen Thailand as subj: {len(recs)}")
rels2 = Counter(r['rel'] for r in recs)
print("Top rels:", rels2.most_common(5))

print()
show_q(50)
# Q50: before_after, GT: Shoygu
# Pred: None
# Need to find what the question is asking
# Let's check what connects to Shoygu
recs = search(obj_kws=['shoygu'])
print(f"Shoygu as obj: {len(recs)}")
for r in sorted(recs, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print()
show_q(61)
# Q61: before_last, GT: Armed Rebel (Somalia)
recs = search(subj_kws=['armed rebel', 'somalia'])
print(f"Armed Rebel Somalia as subj: {len(recs)}")
for r in sorted(recs, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print()
show_q(64)
# Q64: equal, GT: 2013, "In which year did Iraq commend the member of the Legislative Council of Iran?"
recs = search(subj_kws=['iraq'], rel_kws=['commend', 'praise', 'endorse'])
print(f"Iraq+commend/praise: {len(recs)}")
recs2 = search(subj_kws=['iraq'], rel_kws=['praise'])
print(f"Iraq+praise: {len(recs2)}")
# member of parliament Iran
recs3 = search(subj_kws=['iraq'], rel_kws=['praise'], obj_kws=['member', 'iran'])
print(f"Iraq praise member Iran: {len(recs3)}")
for r in recs3[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
recs4 = search(subj_kws=['iraq'], obj_kws=['member', 'iran'])
print(f"Iraq -> member Iran: {len(recs4)}")
for r in recs4[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print()
show_q(73)
# Q73: equal_multi, GT: Al-Shabaab
# "Who did Ethiopia use conventional military force against on the same day as the Hizbul Islam fighter?"
recs = search(subj_kws=['ethiopia'], rel_kws=['conventional military'])
print(f"Ethiopia+conventional military: {len(recs)}")
recs2 = search(subj_kws=['hizbul'])
print(f"Hizbul as subj: {len(recs2)}")
recs3 = search(obj_kws=['hizbul'])
print(f"Hizbul as obj: {len(recs3)}")
for r in sorted(recs2, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print()
show_q(95)
# Q95: before_after, GT: ['South Africa', 'China', 'Angola', 'Norodom Sihanouk']
# "Who hosted the visit of Yang Hyong Sop before Cambodia did?"
recs = search(subj_kws=['yang hyong sop'])
print(f"Yang Hyong Sop as subj: {len(recs)}")
recs2 = search(obj_kws=['yang hyong sop'])
print(f"Yang Hyong Sop as obj: {len(recs2)}")
for r in sorted(recs2, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
# Cambodia date
cam = search(subj_kws=['cambodia'], obj_kws=['yang hyong sop'])
cam2 = search(obj_kws=['cambodia'], subj_kws=['yang hyong sop'])
cam3 = search(subj_kws=['yang hyong sop'], obj_kws=['cambodia'])
print(f"Cambodia+Yang: {len(cam)}, {len(cam2)}, {len(cam3)}")
for r in cam+cam2+cam3:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
