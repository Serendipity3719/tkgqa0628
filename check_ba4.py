RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'subj': parts[0].replace('_',' '), 'rel': parts[1].replace('_',' '), 'obj': parts[2].replace('_',' '), 'date': parts[3]})

# Q47: "Who did Iraq reject after the dissident of the People's Mujahedin of Iran?"
# KB: Iraq | Reject | Dissident (People's Mujahedin of Iran) | 2008-12-27
# So ref = "Dissident (People's Mujahedin of Iran)", which appears as OBJ
# ref_date = 2008-12-27
# After 2008-12-27, who did Iraq reject?
print("=== Q47 ===")
iraq_reject_after = [r for r in RECORDS if 'iraq' in r['subj'].lower() and 'reject' in r['rel'].lower() and r['date'] > '2008-12-27']
print(f"Iraq reject after 2008-12-27: {len(iraq_reject_after)}")
for r in sorted(iraq_reject_after, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
entities = sorted(set(r['obj'] for r in iraq_reject_after))
print(f"Entities: {entities}")

# Q29 second look: The issue is that subj_kws=['malaysia'] matches 
# Foreign Affairs (Malaysia), Police (Malaysia), etc.
# FIX: For before_after entity search, if subj_kws is given, 
# we need EXACT or at least require it to be "standalone" subject
print("\n=== Q29 exact subj='Malaysia' only ===")
# The truth: 9 entities when subj='Malaysia' (exact)
# V6 returns 13 with: 'Citizen (Singapore)', 'Malaysia', 'Men (Malaysia)', 'National Front Malaysia'
# which come from: Police(Malaysia) -> Citizen(Singapore), High Commission(Malaysia)->Malaysia, etc.
# So the FP comes from subj matching "malaysia" as a substring

# FIX: In before_after entity list output, check if the subject is an EXACT match for the entity
# Or require subj to NOT be a compound entity if we have non-compound subj_kws
all_malaysia_opt_before = [r for r in RECORDS if 'malaysia' in r['subj'].lower() and 'optimistic' in r['rel'].lower() and r['date'] < '2008-10-22']
print(f"All 'malaysia*' optimistic before 2008-10-22: {len(all_malaysia_opt_before)}")
for r in all_malaysia_opt_before:
    if r['subj'].lower() != 'malaysia':
        print(f"  FP: {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Q98: "After 27 June 2008, who made Djibouti suffer from conventional military forces?"
# Truth: ['Al-Shabaab', 'Eritrea', 'African Union']
print("\n=== Q98 ===")
conv_djibouti = [r for r in RECORDS if 'conventional military' in r['rel'].lower() and r['obj'].lower() == 'djibouti' and r['date'] > '2008-06-27']
print(f"conventional military vs Djibouti (exact) after 2008-06-27: {len(conv_djibouti)}")
for r in conv_djibouti:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
entities = sorted(set(r['subj'] for r in conv_djibouti))
print(f"Entities: {entities}")

# Q37: "Which country did China study before the religion of China?"
# Truth: ['Japan']
# ref = 'religion of china' -> KB entity?
print("\n=== Q37 ===")
religion_china = [r for r in RECORDS if 'religion' in r['subj'].lower() and 'china' in r['subj'].lower()]
print(f"Religion (China) as subj: {len(religion_china)}")
for r in sorted(religion_china, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

religion_china_obj = [r for r in RECORDS if 'religion' in r['obj'].lower() and 'china' in r['obj'].lower()]
print(f"Religion (China) as obj: {len(religion_china_obj)}")
for r in sorted(religion_china_obj, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

china_study = [r for r in RECORDS if 'china' in r['subj'].lower() and 'study' in r['rel'].lower()]
print(f"China study*: {len(china_study)}")
for r in sorted(china_study, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Q42: "Before the Asian Disaster Preparedness Centre, who did Thailand make optimistic comments about?"
print("\n=== Q42 ===")
asian_disaster = [r for r in RECORDS if 'asian disaster' in r['subj'].lower() or 'asian disaster' in r['obj'].lower()]
print(f"Asian Disaster records: {len(asian_disaster)}")
for r in sorted(asian_disaster, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
