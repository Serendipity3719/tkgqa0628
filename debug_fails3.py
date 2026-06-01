"""Debug Q17, Q95, Q50, Q64, Q73 in detail."""
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

print("=== Q17: Before the military of Taiwan, which country did China threaten last? ===")
print("GT: Angela Merkel")
# Find China threaten Military(Taiwan) specifically
china_thr_mil_tw = search(subj_kws=['china'], rel_kws=['threaten'], obj_kws=['military', 'taiwan'])
print(f"China threaten Military(Taiwan): {len(china_thr_mil_tw)}")
for r in sorted(china_thr_mil_tw, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# So t_ref = last date of China threaten Military(Taiwan)
if china_thr_mil_tw:
    t_ref = sorted(china_thr_mil_tw, key=lambda x: x['date'])[-1]['date']
    print(f"t_ref (last China threaten Military Taiwan): {t_ref}")
    # China threaten before t_ref (excluding Military Taiwan)
    china_thr = search(subj_kws=['china'], rel_kws=['threaten'])
    before = [r for r in china_thr if r['date'] < t_ref and 'taiwan' not in r['obj'].lower()]
    before.sort(key=lambda x: x['date'])
    print(f"China threaten before {t_ref} (excl Taiwan): {len(before)}")
    if before:
        print(f"  Last: {before[-1]['date']} {before[-1]['subj']} | {before[-1]['rel']} | {before[-1]['obj']}")

print()
print("=== Q95: Who hosted the visit of Yang Hyong Sop before Cambodia did? ===")
print("GT: ['South Africa', 'China', 'Angola', 'Norodom Sihanouk']")
# Cambodia hosted Yang on 2012-10-20
# Find all who hosted Yang before 2012-10-20
yang_hosted = search(rel_kws=['host a visit'], obj_kws=['yang hyong sop'])
print(f"Host a visit Yang Hyong Sop: {len(yang_hosted)}")
for r in sorted(yang_hosted, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
before_cam = [r for r in yang_hosted if r['date'] < '2012-10-20']
print(f"Before Cambodia (2012-10-20): {len(before_cam)}")
hosts = sorted(set(r['subj'] for r in before_cam))
print(f"Hosts: {hosts}")

print()
print("=== Q50: Who criticised Chuck Hagel after China? ===")
print("GT: Sergey Kuzhugetovich Shoygu")
# Find China criticize Chuck Hagel date
china_crit_hagel = search(subj_kws=['china'], rel_kws=['criticize', 'criticise', 'denounce'], obj_kws=['hagel'])
print(f"China criticize Hagel: {len(china_crit_hagel)}")
for r in sorted(china_crit_hagel, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
# Find all who criticized Hagel
all_crit_hagel = search(rel_kws=['criticize', 'criticise', 'denounce'], obj_kws=['hagel'])
print(f"All criticize Hagel: {len(all_crit_hagel)}")
for r in sorted(all_crit_hagel, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print()
print("=== Q64: In which year did Iraq commend the member of the Legislative Council of Iran? ===")
print("GT: 2013")
# KB has "Member of Legislative (Govt) (Iran)"
recs = search(subj_kws=['iraq'], rel_kws=['praise'], obj_kws=['legislative', 'iran'])
print(f"Iraq praise legislative Iran: {len(recs)}")
for r in recs:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
# What does LLM map "Legislative Council" to?
# "member of parliament" vs "member of legislative"
recs2 = search(subj_kws=['iraq'], rel_kws=['praise'], obj_kws=['parliament', 'iran'])
print(f"Iraq praise parliament Iran: {len(recs2)}")
recs3 = search(subj_kws=['iraq'], rel_kws=['praise'], obj_kws=['member', 'iran'])
print(f"Iraq praise member Iran: {len(recs3)}")
for r in recs3:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print()
print("=== Q73: Ethiopia conventional military same day as Hizbul Islam fighter ===")
print("GT: Al-Shabaab")
# Find Hizbul Islam fighter events
hizbul = search(subj_kws=['hizbul'])
hizbul += search(obj_kws=['hizbul'])
print(f"Hizbul events: {len(hizbul)}")
for r in sorted(hizbul, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
# Find Ethiopia conventional military on same days
eth_conv = search(subj_kws=['ethiopia'], rel_kws=['conventional military'])
print(f"Ethiopia conventional military: {len(eth_conv)}")
for r in sorted(eth_conv, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
# Find Hizbul Islam fighter specifically
hizbul_fighter = search(subj_kws=['combatant', 'hizbul'])
hizbul_fighter += search(subj_kws=['insurgent', 'hizbul'])
print(f"Hizbul fighter events: {len(hizbul_fighter)}")
for r in sorted(hizbul_fighter, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
# Find dates of Hizbul fighter events
hizbul_dates = set(r['date'] for r in hizbul_fighter)
print(f"Hizbul fighter dates: {hizbul_dates}")
# Ethiopia conventional military on those dates
eth_same_day = [r for r in eth_conv if r['date'] in hizbul_dates]
print(f"Ethiopia conv military on Hizbul dates: {len(eth_same_day)}")
for r in eth_same_day:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
