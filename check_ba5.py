RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'subj': parts[0].replace('_',' '), 'rel': parts[1].replace('_',' '), 'obj': parts[2].replace('_',' '), 'date': parts[3]})

# Check ALL before_after failure cases to understand remaining patterns

# Q37: "Which country did China study before the religion of China?"
# China study* = 0. So KB relation is "Investigate"?
print("=== Q37 ===")
china_investigate = [r for r in RECORDS if 'china' in r['subj'].lower() and 'investigate' in r['rel'].lower()]
print(f"China investigate: {len(china_investigate)}")
for r in sorted(china_investigate, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# What's the KB entity for 'study'?
all_study_rels = sorted(set(r['rel'] for r in RECORDS if 'study' in r['rel'].lower() or 'research' in r['rel'].lower()))
print(f"\nStudy/research relations: {all_study_rels}")

# Q47 deeper: "Who did Iraq reject after the dissident of People's Mujahedin of Iran?"
# KB: Iraq | Reject | Dissident (People's Mujahedin of Iran) | 2008-12-27
# ref: "Dissident (People's Mujahedin of Iran)" appears as OBJ
# ref_date = 2008-12-27
# After 2008-12-27, Iraq reject: 41 records with 15 unique entities
# But 'iraq' in subj is too broad (includes 'National Alliance (Iraq)', etc.)
print("\n=== Q47 exact ===")
iraq_rej_exact = [r for r in RECORDS if r['subj'].lower() == 'iraq' and 'reject' in r['rel'].lower() and r['date'] > '2008-12-27']
print(f"Iraq (exact) reject after 2008-12-27: {len(iraq_rej_exact)}")
for r in sorted(iraq_rej_exact, key=lambda x: x['date'])[:15]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
entities = sorted(set(r['obj'] for r in iraq_rej_exact))
print(f"Entities: {entities}")

# Q47: The correct answer has to be obtained from check_ba5 - need test.json
import json
with open('E:/RAG_Agent_Experiment/test.json', 'r', encoding='utf-8') as f:
    all_data = json.load(f)
# Print question 47 (0-indexed = item 46)
for i, item in enumerate(all_data[:100]):
    if item.get('qtype') == 'before_after' and i in [7, 11, 13, 17, 28, 36, 37, 41, 45, 46, 47, 92, 97]:
        print(f"\nQ{i+1} (index {i}): {item['question']}")
        print(f"  qtype={item['qtype']}, answers={item['answers']}")

print("\n=== Q83 ===")
# Q83: accuse ethiopia  
accuse_eth = [r for r in RECORDS if 'accuse' in r['rel'].lower() and 'ethiopia' in r['subj'].lower()]
print(f"Ethiopia accuse: {len(accuse_eth)}")
for r in sorted(accuse_eth, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
