"""Debug Q44, Q52, Q94, Q95, Q73, Q32, Q42 in detail."""
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

print("=== Q44 [before_last] GT: Qatar ===")
show_q(44)
# "Before X, who last did Y do Z?"
# Need to find what the question is
recs = search(subj_kws=['qatar'])
print(f"Qatar as subj: {len(recs)}")
recs2 = search(obj_kws=['qatar'])
print(f"Qatar as obj: {len(recs2)}")

print()
print("=== Q52 [before_last] GT: Sudan ===")
show_q(52)
recs = search(subj_kws=['sudan'])
print(f"Sudan as subj: {len(recs)}")
recs2 = search(obj_kws=['sudan'])
print(f"Sudan as obj: {len(recs2)}")

print()
print("=== Q94 [before_last] GT: Ma Ying Jeou ===")
show_q(94)
recs = search(subj_kws=['ma ying'])
print(f"Ma Ying Jeou as subj: {len(recs)}")
recs2 = search(obj_kws=['ma ying'])
print(f"Ma Ying Jeou as obj: {len(recs2)}")
for r in sorted(recs2, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print()
print("=== Q32 [before_last] GT: Citizen (Thailand) ===")
show_q(32)
# "Before Thailand, who last wanted to negotiate with the Governor of Thailand?"
# ref=Thailand, rel=negotiate, obj=Governor of Thailand
# KB: "Governor (Thailand)" or "Head of Government (Thailand)"?
gov_th = search(subj_kws=['governor', 'thailand'])
gov_th2 = search(obj_kws=['governor', 'thailand'])
print(f"Governor Thailand as subj: {len(gov_th)}, as obj: {len(gov_th2)}")
head_th = search(subj_kws=['head of government', 'thailand'])
head_th2 = search(obj_kws=['head of government', 'thailand'])
print(f"Head of Government Thailand as subj: {len(head_th)}, as obj: {len(head_th2)}")
# Check what KB has for "governor"
from collections import Counter
gov_recs = search(subj_kws=['governor'])
gov_recs2 = search(obj_kws=['governor'])
gov_entities = Counter(r['subj'] for r in gov_recs) + Counter(r['obj'] for r in gov_recs2)
print(f"Governor entities: {list(gov_entities.most_common(10))}")

print()
print("=== Q42 [before_after] GT: Citizen (Thailand) ===")
show_q(42)
# "Before the Asian Disaster Preparedness Centre, who did Thailand make optimistic comments about?"
# ref=Asian Disaster Preparedness Center, subj=Thailand, rel=optimistic
# Find ADPC date
adpc = search(subj_kws=['asian disaster'])
adpc2 = search(obj_kws=['asian disaster'])
print(f"Asian Disaster as subj: {len(adpc)}, as obj: {len(adpc2)}")
for r in sorted(adpc+adpc2, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
# Thailand optimistic
th_opt = search(subj_kws=['thailand'], rel_kws=['optimistic'])
print(f"Thailand optimistic: {len(th_opt)}")
for r in sorted(th_opt, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print()
print("=== Q95 [before_after] GT: ['South Africa', 'China', 'Angola', 'Norodom Sihanouk'] ===")
show_q(95)
# "Who hosted the visit of Yang Hyong Sop before Cambodia did?"
# find_ref_date_contextual: ref=Cambodia, rel=visit, obj=yang hyong sop
# Level 2b: search(subj_kws=['cambodia'], rel_kws=['visit'], obj_kws=['yang hyong sop'])
cam_yang = search(subj_kws=['cambodia'], rel_kws=['visit'], obj_kws=['yang hyong sop'])
print(f"Cambodia visit Yang Hyong Sop: {len(cam_yang)}")
for r in cam_yang:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
# Level 3: ref+rel
cam_visit = search(subj_kws=['cambodia'], rel_kws=['visit'])
print(f"Cambodia visit (all): {len(cam_visit)}")
# Level 5: ref only
cam_all = search(subj_kws=['cambodia'])
cam_all2 = search(obj_kws=['cambodia'])
print(f"Cambodia as subj: {len(cam_all)}, as obj: {len(cam_all2)}")
# The issue: find_ref_date_contextual uses obj_kws=['yang hyong sop']
# Level 2b: search(subj_kws=['cambodia'], rel_kws=['visit'], obj_kws=['yang hyong sop'])
# This should find Cambodia | Host a visit | Yang Hyong Sop on 2012-10-20
# But 'visit' in rel_kws matches 'Host a visit' → should work
# Let's check if 'yang hyong sop' is in obj_kws
yang_recs = search(obj_kws=['yang hyong sop'])
print(f"Yang Hyong Sop as obj: {len(yang_recs)}")
for r in yang_recs[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
# Check exact: Cambodia | Host a visit | Yang Hyong Sop
cam_host_yang = search(subj_kws=['cambodia'], rel_kws=['host a visit'], obj_kws=['yang hyong sop'])
print(f"Cambodia host a visit Yang Hyong Sop: {len(cam_host_yang)}")
for r in cam_host_yang:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print()
print("=== Q73 [equal_multi] GT: Al-Shabaab ===")
show_q(73)
# "Who did Ethiopia use conventional military force against on the same day as the Hizbul Islam fighter?"
# ref="Hizbul Islam fighter" → KB: "Combatant (Hizbul Islam)"
# find_ref_date_contextual: ref_kws=['hizbul', 'islam', 'fighter'] or ['combatant', 'hizbul']?
# LLM likely parses ref_kws=['hizbul', 'islam', 'fighter']
hizbul_fighter = search(subj_kws=['hizbul'])
hizbul_fighter2 = search(obj_kws=['hizbul'])
print(f"Hizbul as subj: {len(hizbul_fighter)}, as obj: {len(hizbul_fighter2)}")
# Check what LLM would parse for "Hizbul Islam fighter"
# ref_kws=['hizbul', 'islam', 'fighter'] → search(subj_kws=['hizbul','islam','fighter'])
hizbul_all = search(subj_kws=['hizbul', 'islam'])
print(f"Hizbul Islam as subj: {len(hizbul_all)}")
for r in sorted(hizbul_all, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
# The issue: "fighter" is not in KB entity name "Combatant (Hizbul Islam)"
# ref_kws=['hizbul', 'islam', 'fighter'] → search fails because 'fighter' not in 'combatant (hizbul islam)'
hizbul_fighter_kws = search(subj_kws=['hizbul', 'islam', 'fighter'])
print(f"Hizbul Islam fighter (all 3 kws): {len(hizbul_fighter_kws)}")
# Fix: drop 'fighter' from ref_kws
hizbul_no_fighter = search(subj_kws=['hizbul', 'islam'])
print(f"Hizbul Islam (no fighter): {len(hizbul_no_fighter)}")
# Dates of Hizbul Islam events
hizbul_dates = set(r['date'] for r in hizbul_all)
print(f"Hizbul Islam dates: {hizbul_dates}")
# Ethiopia conv military on those dates
eth_conv = search(subj_kws=['ethiopia'], rel_kws=['conventional military'])
eth_same = [r for r in eth_conv if r['date'] in hizbul_dates]
print(f"Ethiopia conv military on Hizbul dates: {len(eth_same)}")
for r in eth_same:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
