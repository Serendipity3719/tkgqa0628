import json
RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'subj': parts[0].replace('_',' '), 'rel': parts[1].replace('_',' '), 'obj': parts[2].replace('_',' '), 'date': parts[3]})

with open('E:/RAG_Agent_Experiment/test.json', 'r', encoding='utf-8') as f:
    all_data = json.load(f)[:100]

# Check ALL remaining before_after wrong cases in V6 log
# Q34, Q50, Q60, Q65, Q75, Q78, Q83, Q95

print("=== Q34 ===")
item = all_data[33]
print(f"Q: {item['question']}")
print(f"A: {item['answers']}")

print("=== Q50 ===")
item = all_data[49]
print(f"Q: {item['question']}")
print(f"A: {item['answers']}")

print("=== Q60 ===")
item = all_data[59]
print(f"Q: {item['question']}")
print(f"A: {item['answers']}")

print("=== Q65 ===")
item = all_data[64]
print(f"Q: {item['question']}")
print(f"A: {item['answers']}")

print("=== Q75 ===")
item = all_data[74]
print(f"Q: {item['question']}")
print(f"A: {item['answers']}")

print("=== Q78 ===")
item = all_data[77]
print(f"Q: {item['question']}")
print(f"A: {item['answers']}")

print("=== Q83 ===")
item = all_data[82]
print(f"Q: {item['question']}")
print(f"A: {item['answers']}")

print("=== Q95 ===")
item = all_data[94]
print(f"Q: {item['question']}")
print(f"A: {item['answers']}")

# Q83 deep dive: "After Ethiopia, who did Qatar accuse?"
# Truth: ['Government (Qatar)', 'Activist (Ethiopia)', 'Qatar', 'Al-Shabaab', 'Eritrea', 'Sudan']
# This looks like Qatar accuse Ethiopia ref date
print("\n=== Q83 Deep Dive ===")
# Find when Ethiopia did what to Qatar or when Qatar accused Ethiopia
qatar_acc_eth = [r for r in RECORDS if 'qatar' in r['subj'].lower() and 'accuse' in r['rel'].lower() and 'ethiopia' in r['obj'].lower()]
print(f"Qatar accuse Ethiopia: {len(qatar_acc_eth)}")
for r in sorted(qatar_acc_eth, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

eth_acc_qatar = [r for r in RECORDS if 'ethiopia' in r['subj'].lower() and 'accuse' in r['rel'].lower() and 'qatar' in r['obj'].lower()]
print(f"Ethiopia accuse Qatar: {len(eth_acc_qatar)}")

eth_any_qatar = [r for r in RECORDS if 'ethiopia' in r['subj'].lower() and 'qatar' in r['obj'].lower()]
print(f"Ethiopia * Qatar: {len(eth_any_qatar)}")
for r in sorted(eth_any_qatar, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Actually Q83 answer includes: 'Government (Qatar)', 'Qatar', 'Al-Shabaab', 'Eritrea', 'Sudan'
# Who did Ethiopia accuse? The ref should be "ethiopia" appearing somewhere in accuse chain
# "After Ethiopia" - after Ethiopia who/what? After Ethiopia's action (accuse)
print("\nEthiopia accuse records:")
eth_accuse = [r for r in RECORDS if 'ethiopia' in r['subj'].lower() and 'accuse' in r['rel'].lower()]
# sort and show first date
if eth_accuse:
    eth_accuse.sort(key=lambda x: x['date'])
    print(f"First Ethiopia accuse: {eth_accuse[0]['date']}")

# Q83 truth suggests AFTER Ethiopia (as ref entity), someone accused someone
# Let's check: "After Ethiopia, who did Qatar accuse?"
# Wait - check Q83 question carefully in test.json
print(f"\nQ83 question: {all_data[82]['question']}")

# Q50 deep dive
print("\n=== Q50 Deep Dive ===")
print(f"Q50: {all_data[49]['question']}")
# Check the Asian Disaster Preparedness Centre records
asian_recs = [r for r in RECORDS if 'asian disaster' in r['subj'].lower() or 'asian disaster' in r['obj'].lower()]
print(f"Asian Disaster records: {len(asian_recs)}")
for r in sorted(asian_recs, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
