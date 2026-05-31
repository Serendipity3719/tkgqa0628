import json
RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'subj': parts[0].replace('_',' '), 'rel': parts[1].replace('_',' '), 'obj': parts[2].replace('_',' '), 'date': parts[3]})

with open('E:/RAG_Agent_Experiment/test.json', 'r', encoding='utf-8') as f:
    all_data = json.load(f)[:100]

# Q83: "Which country was accused by Ethiopia after 2012?"
# Truth: ['Government (Qatar)', 'Activist (Ethiopia)', 'Qatar', 'Al-Shabaab', 'Eritrea', 'Sudan']
# Passive voice: X was accused by Ethiopia -> subj=Ethiopia, obj=X
# After 2012 = date > 2012
print("=== Q83 ===")
eth_accuse_after_2012 = [r for r in RECORDS if r['subj'].lower() == 'ethiopia' and 'accuse' in r['rel'].lower() and r['date'] > '2012']
print(f"Ethiopia accuse after 2012: {len(eth_accuse_after_2012)}")
for r in sorted(eth_accuse_after_2012, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
entities = sorted(set(r['obj'] for r in eth_accuse_after_2012))
print(f"Entities: {entities}")

# Q34: "Before Oman, with which country did Thailand formally sign an agreement?"
# Truth: ['China', 'Malaysia']
print("\n=== Q34 ===")
# Find when Thailand signed with Oman
thai_sign_oman = [r for r in RECORDS if 'thailand' in r['subj'].lower() and 'sign' in r['rel'].lower() and 'oman' in r['obj'].lower()]
print(f"Thailand sign Oman: {len(thai_sign_oman)}")
for r in sorted(thai_sign_oman, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
oman_sign_thai = [r for r in RECORDS if 'oman' in r['subj'].lower() and 'sign' in r['rel'].lower() and 'thailand' in r['obj'].lower()]
print(f"Oman sign Thailand: {len(oman_sign_thai)}")
for r in sorted(oman_sign_thai, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Try broader: all Oman sign
oman_sign = [r for r in RECORDS if 'oman' in r['subj'].lower() and 'sign' in r['rel'].lower()]
thai_sign = [r for r in RECORDS if 'thailand' in r['subj'].lower() and 'sign' in r['rel'].lower()]
print(f"Oman sign*: {len(oman_sign)}, Thailand sign*: {len(thai_sign)}")

# If "Thailand sign Oman" is empty, maybe Oman signs Thailand?
if not thai_sign_oman and not oman_sign_thai:
    # broader search
    oman_any = [r for r in RECORDS if 'oman' in r['subj'].lower() or 'oman' in r['obj'].lower()]
    print(f"Any Oman records: {len(oman_any)}, first:", end=' ')
    if oman_any:
        oman_any.sort(key=lambda x: x['date'])
        print(oman_any[0])
    
# Q50: "Who criticised Chuck Hagel after China?"
# Truth: ['Sergey Kuzhugetovich Shoygu']
print("\n=== Q50 ===")
china_crit_hagel = [r for r in RECORDS if 'china' in r['subj'].lower() and 'criticize' in r['rel'].lower() and 'hagel' in r['obj'].lower()]
print(f"China criticize Hagel: {len(china_crit_hagel)}")
for r in sorted(china_crit_hagel, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
if china_crit_hagel:
    t_ref = sorted(china_crit_hagel, key=lambda x: x['date'])[0]['date']
    crit_hagel_after = [r for r in RECORDS if 'criticize' in r['rel'].lower() and 'hagel' in r['obj'].lower() and r['date'] > t_ref]
    print(f"Criticize Hagel after {t_ref}: {len(crit_hagel_after)}")
    for r in sorted(crit_hagel_after, key=lambda x: x['date'])[:10]:
        print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Q60: "After 12 May 2011, which country did Cambodia denounce?"
# Truth: ['Vietnam', 'Abhisit Vejjajiva', 'China', 'Thailand']
print("\n=== Q60 ===")
camb_crit_after = [r for r in RECORDS if r['subj'].lower() == 'cambodia' and 'criticize' in r['rel'].lower() and r['date'] > '2011-05-12']
print(f"Cambodia criticize after 2011-05-12: {len(camb_crit_after)}")
for r in sorted(camb_crit_after, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
entities = sorted(set(r['obj'] for r in camb_crit_after))
print(f"Entities: {entities}")

# Q65: "To which country did Malaysia send an appeal after 2012-11-20?"
# Truth: ['UN Security Council', 'Citizen (Unidentified State Actor)', 'Citizen (Thailand)', 'Barack Obama', 'Chuck Hagel', 'Maldives', 'Vietnam', 'China']
print("\n=== Q65 ===")
# appeal = "Make an appeal or request"
malaysia_appeal = [r for r in RECORDS if r['subj'].lower() == 'malaysia' and 'appeal' in r['rel'].lower() and r['date'] > '2012-11-20']
print(f"Malaysia appeal after 2012-11-20: {len(malaysia_appeal)}")
for r in sorted(malaysia_appeal, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
entities = sorted(set(r['obj'] for r in malaysia_appeal))
print(f"Entities: {entities}")

# Q75: "Who negotiated with the Thai military after Thailand?"
# Truth: ['National United Front for Democracy Against Dictatorship', 'Abhisit Vejjajiva', 'Worachai Hema', 'Protester (Thailand)']
print("\n=== Q75 ===")
# Thai military = "Military (Thailand)"
thai_mil_neg = [r for r in RECORDS if 'military' in r['subj'].lower() and 'thailand' in r['subj'].lower() and 'negotiate' in r['rel'].lower()]
print(f"Military(Thailand) negotiate: {len(thai_mil_neg)}")
for r in sorted(thai_mil_neg, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# ref = Thailand, what date?
thai_neg = [r for r in RECORDS if r['subj'].lower() == 'thailand' and 'negotiate' in r['rel'].lower()]
print(f"Thailand negotiate: {len(thai_neg)}")
for r in sorted(thai_neg, key=lambda x: x['date'])[:3]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Q78: "After Sankei, who was investigated by the Lawyer/Attorney of South Korea?"
# Truth: ['Criminal (South Korea)', 'Business (South Korea)', 'Grand National Party']
print("\n=== Q78 ===")
# Sankei as ref: find when Lawyer/Attorney (South Korea) investigated Sankei
sankei_inv = [r for r in RECORDS if 'lawyer' in r['subj'].lower() and 'south korea' in r['subj'].lower() and 'investigate' in r['rel'].lower() and 'sankei' in r['obj'].lower()]
print(f"Lawyer(SK) investigate Sankei: {len(sankei_inv)}")
for r in sankei_inv:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
if sankei_inv:
    t_ref = sorted(sankei_inv, key=lambda x: x['date'])[0]['date']
    sk_inv_after = [r for r in RECORDS if 'lawyer' in r['subj'].lower() and 'south korea' in r['subj'].lower() and 'investigate' in r['rel'].lower() and r['date'] > t_ref]
    print(f"Lawyer(SK) investigate after {t_ref}: {len(sk_inv_after)}")
    for r in sorted(sk_inv_after, key=lambda x: x['date'])[:10]:
        print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
    entities = sorted(set(r['obj'] for r in sk_inv_after))
    print(f"Entities: {entities}")

# Q95: "Who hosted the visit of Yang Hyong Sop before Cambodia did?"
# Truth: ['South Africa', 'China', 'Angola', 'Norodom Sihanouk']
print("\n=== Q95 ===")
# yang_hyong_sop as visitor, Cambodia as host
camb_host_yang = [r for r in RECORDS if 'cambodia' in r['subj'].lower() and 'host' in r['rel'].lower() and 'yang' in r['obj'].lower()]
print(f"Cambodia host Yang: {len(camb_host_yang)}")
yang_visit_camb = [r for r in RECORDS if 'yang' in r['subj'].lower() and 'visit' in r['rel'].lower() and 'cambodia' in r['obj'].lower()]
print(f"Yang visit Cambodia: {len(yang_visit_camb)}")
# Try general: yang hyong sop
yang_recs = [r for r in RECORDS if 'yang' in r['subj'].lower() and ('hyong' in r['subj'].lower() or 'sop' in r['subj'].lower())]
print(f"Yang Hyong Sop as subj: {len(yang_recs)}")
for r in sorted(yang_recs, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
yang_obj = [r for r in RECORDS if 'yang' in r['obj'].lower() and ('hyong' in r['obj'].lower() or 'sop' in r['obj'].lower())]
print(f"Yang Hyong Sop as obj: {len(yang_obj)}")
for r in sorted(yang_obj, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
