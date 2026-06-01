"""Debug remaining failures to find best optimization targets."""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RECORDS = []
with open('full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            subj, rel, obj, date = parts
            RECORDS.append({'subj': subj.replace('_',' '), 'rel': rel.replace('_',' '),
                            'obj': obj.replace('_',' '), 'date': date})
print(f"KB: {len(RECORDS)} records")

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

# Failing questions from latest run:
# Q8, Q12, Q17, Q18, Q24, Q29, Q32, Q35, Q36, Q39, Q42, Q44, Q50, Q52, Q58, Q61, Q64, Q73, Q75, Q77, Q94, Q95

print("\n=== Q8 [before_after] GT: ['China', 'Sudan'] ===")
# "Before 22 October 2008, which country did Malaysia make optimistic remarks about?"
# Pred: None
recs = search(subj_kws=['malaysia'], rel_kws=['optimistic'], time_prefix='2008')
print(f"Malaysia+optimistic 2008: {len(recs)}")
recs2 = search(subj_kws=['malaysia'], rel_kws=['optimistic'])
print(f"Malaysia+optimistic all: {len(recs2)}")
for r in sorted(recs2, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print("\n=== Q12 [before_after] GT: ['Al-Shabaab', 'Military (Burundi)'] ===")
# Pred: None
# Need to find what Q12 is asking
# "Before [ref], who did [subj] [rel]?"
# Let's check Al-Shabaab + Military Burundi
recs = search(subj_kws=['al-shabaab'])
print(f"Al-Shabaab as subj: {len(recs)}")
recs2 = search(obj_kws=['al-shabaab'])
print(f"Al-Shabaab as obj: {len(recs2)}")
recs3 = search(subj_kws=['burundi'], rel_kws=['military'])
print(f"Burundi military: {len(recs3)}")
recs4 = search(obj_kws=['burundi'])
print(f"Burundi as obj: {len(recs4)}")

print("\n=== Q17 [before_last] GT: Angela Merkel ===")
# Pred: Japan
# "Before Military (Taiwan), who last did China threaten?"
recs = search(subj_kws=['china'], rel_kws=['threaten'])
print(f"China+threaten: {len(recs)}")
# Find Military Taiwan date
mil_tw = search(subj_kws=['military', 'taiwan'])
mil_tw2 = search(obj_kws=['military', 'taiwan'])
print(f"Military Taiwan as subj: {len(mil_tw)}, as obj: {len(mil_tw2)}")
# Find when China threatened Angela Merkel
am = search(subj_kws=['china'], rel_kws=['threaten'], obj_kws=['merkel'])
print(f"China threaten Merkel: {len(am)}")
for r in am[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
# Find when China threatened Japan
jp = search(subj_kws=['china'], rel_kws=['threaten'], obj_kws=['japan'])
print(f"China threaten Japan: {len(jp)}")
for r in sorted(jp, key=lambda x: x['date'])[-5:]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
# Find Military Taiwan dates
mil_tw_all = search(subj_kws=['military', 'taiwan'])
mil_tw_all += search(obj_kws=['military', 'taiwan'])
mil_tw_all.sort(key=lambda x: x['date'])
print(f"Military Taiwan all: {len(mil_tw_all)}")
if mil_tw_all:
    print(f"  Last date: {mil_tw_all[-1]['date']}")
    print(f"  First date: {mil_tw_all[0]['date']}")

print("\n=== Q32 [before_last] GT: Citizen (Thailand) ===")
# Pred: None
# Need to find what Q32 is asking
recs = search(obj_kws=['citizen', 'thailand'])
print(f"Citizen Thailand as obj: {len(recs)}")
recs2 = search(subj_kws=['citizen', 'thailand'])
print(f"Citizen Thailand as subj: {len(recs2)}")

print("\n=== Q42 [before_after] GT: Citizen (Thailand) ===")
# Pred: None
recs = search(subj_kws=['citizen', 'thailand'])
print(f"Citizen Thailand as subj: {len(recs)}")
recs2 = search(obj_kws=['citizen', 'thailand'])
print(f"Citizen Thailand as obj: {len(recs2)}")

print("\n=== Q50 [before_after] GT: Sergey Kuzhugetovich Shoygu ===")
# Pred: None
recs = search(subj_kws=['shoygu'])
print(f"Shoygu as subj: {len(recs)}")
recs2 = search(obj_kws=['shoygu'])
print(f"Shoygu as obj: {len(recs2)}")
if recs:
    for r in recs[:5]:
        print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print("\n=== Q61 [before_last] GT: Armed Rebel (Somalia) ===")
# Pred: None
recs = search(subj_kws=['armed rebel', 'somalia'])
print(f"Armed Rebel Somalia as subj: {len(recs)}")
recs2 = search(obj_kws=['armed rebel', 'somalia'])
print(f"Armed Rebel Somalia as obj: {len(recs2)}")

print("\n=== Q64 [equal] GT: 2013 ===")
# Pred: None
# Need to find what Q64 is asking
# Let's check test.json
import json
with open('test.json', 'r', encoding='utf-8') as f:
    test_data = json.load(f)
q64 = test_data[63]
print(f"Q64: {q64['question']}")
print(f"Q64 type: {q64.get('qtype', q64.get('type', ''))}")
print(f"Q64 answer: {q64.get('answers', q64.get('answer', ''))}")

print("\n=== Q73 [equal_multi] GT: Al-Shabaab ===")
q73 = test_data[72]
print(f"Q73: {q73['question']}")
print(f"Q73 answer: {q73.get('answers', q73.get('answer', ''))}")

print("\n=== Q95 [before_after] GT: ['South Africa', 'China', 'Angola', 'North Korea'] ===")
q95 = test_data[94]
print(f"Q95: {q95['question']}")
print(f"Q95 answer: {q95.get('answers', q95.get('answer', ''))}")
# Check what entities are involved
recs = search(obj_kws=['south africa'])
print(f"South Africa as obj: {len(recs)}")
recs2 = search(subj_kws=['south africa'])
print(f"South Africa as subj: {len(recs2)}")
