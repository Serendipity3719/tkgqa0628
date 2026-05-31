RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'subj': parts[0].replace('_',' '), 'rel': parts[1].replace('_',' '), 'obj': parts[2].replace('_',' '), 'date': parts[3]})

# Deep-dive into before_after failures to find precise root causes

# Q93: "Who criticised the citizens of Saudi Arabia before Zawahiri?"
# Key insight: zawahiri recs starts 2005-10-24, but the FIRST one is Pervez Musharraf, not Citizen Saudi Arabia
# The question "before Zawahiri" means: find when Zawahiri did the SAME action (criticize citizen saudi) 
# NOT when Zawahiri first appeared in KB
# Zawahiri criticize citizen(saudi) = 2008-12-01
# So ref_date should be 2008-12-01, not 2005-10-24 (first zawahiri record)
print("=== Q93 Analysis ===")
zawahiri_crit_saudi = [r for r in RECORDS if 'zawahiri' in r['subj'].lower() and 'criticize' in r['rel'].lower() and 'citizen' in r['obj'].lower() and 'saudi' in r['obj'].lower()]
print(f"Zawahiri criticize citizen(saudi): {len(zawahiri_crit_saudi)}")
for r in zawahiri_crit_saudi:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# So the right t_ref = 2008-12-01. Before that, who criticize citizen(saudi)?
t_ref = '2008-12-01'
before_q93 = [r for r in RECORDS if 'criticize' in r['rel'].lower() and 'citizen' in r['obj'].lower() and 'saudi' in r['obj'].lower() and r['date'] < t_ref and 'zawahiri' not in r['subj'].lower()]
print(f"\nBefore {t_ref}, criticize citizen(saudi) (excl zawahiri): {len(before_q93)}")
for r in before_q93:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

print()
print("=== Q12 Analysis ===")
# Q12: "Before 14 October 2015, who made Burundi suffer from conventional military forces?"
# Truth: ['Al-Shabaab', 'Military (Burundi)']
# But 26 records match. Why are we getting all of them?
# The question says "made Burundi suffer" -> the OBJ should be "Burundi", not "Rebel Group" or "Criminal"
conv_burundi_exact = [r for r in RECORDS if 'conventional military' in r['rel'].lower() and r['obj'].lower() == 'burundi' and r['date'] < '2015-10-14']
print(f"Use conventional military force vs Burundi (exact) before 2015-10-14: {len(conv_burundi_exact)}")
for r in conv_burundi_exact:
    print(f"  {r['subj']} | {r['rel']} | {r['obj']} | {r['date']}")
entities = sorted(set(r['subj'] for r in conv_burundi_exact))
print(f"Entities: {entities}")

print()
print("=== Q14 Analysis ===")
# Q14: "Before 25 April 2005, who used conventional military force against Iraq?"
# Truth: ['Iran', 'Commando (Iraq)']
conv_iraq_exact = [r for r in RECORDS if 'conventional military' in r['rel'].lower() and r['obj'].lower() == 'iraq' and r['date'] < '2005-04-25']
print(f"Use conventional military force vs Iraq (exact) before 2005-04-25: {len(conv_iraq_exact)}")
for r in conv_iraq_exact:
    print(f"  {r['subj']} | {r['rel']} | {r['obj']} | {r['date']}")
entities = sorted(set(r['subj'] for r in conv_iraq_exact))
print(f"Entities: {entities}")

print()
print("=== Q46 Analysis ===")
# Q46: "Who attacked Iraq with small arms and light weapons after 9 August 2006?"
# Truth: ['Iran', 'Armed Rebel (Syria)', 'Israeli Defense Forces']
# 'fight' keyword — keyword is "small arms" but the rel is "fight with small arms..."
small_iraq = [r for r in RECORDS if 'small arms' in r['rel'].lower() and r['obj'].lower() == 'iraq' and r['date'] > '2006-08-09']
print(f"Small arms vs Iraq (exact OBJ) after 2006-08-09: {len(small_iraq)}")
for r in small_iraq:
    print(f"  {r['subj']} | {r['rel']} | {r['obj']} | {r['date']}")
entities = sorted(set(r['subj'] for r in small_iraq))
print(f"Entities: {entities}")

print()
print("=== Q8 Analysis ===")
# Q8: "Before Ethiopia, which country did Seyoum Mesfin express his intention to negotiate with?"
# Truth: ['China', 'Sudan']
# ref=Ethiopia, but what action did Ethiopia do? OR what action did Seyoum Mesfin do WITH Ethiopia?
# "before Ethiopia" means: before Seyoum Mesfin negotiated with Ethiopia
# Find when Seyoum Mesfin did intent-to-negotiate with Ethiopia
seyoum_neg_eth = [r for r in RECORDS if 'seyoum' in r['subj'].lower() and 'negotiate' in r['rel'].lower() and 'ethiopia' in r['obj'].lower()]
print(f"Seyoum negotiate Ethiopia: {len(seyoum_neg_eth)}")
for r in seyoum_neg_eth:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# What relations does "negotiate" expand to?
all_negotiate_rels = sorted(set(r['rel'] for r in RECORDS if 'negotiate' in r['rel'].lower()))
print(f"\nRelations with negotiate: {all_negotiate_rels}")

seyoum_int_neg = [r for r in RECORDS if 'seyoum' in r['subj'].lower() and 'intent' in r['rel'].lower()]
print(f"\nSeyoum intent to*: {len(seyoum_int_neg)}")
for r in seyoum_int_neg[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

seyoum_int_neg_eth = [r for r in RECORDS if 'seyoum' in r['subj'].lower() and 'intent to meet or negotiate' in r['rel'].lower() and 'ethiopia' in r['obj'].lower()]
print(f"\nSeyoum intent to meet or negotiate Ethiopia: {len(seyoum_int_neg_eth)}")
for r in seyoum_int_neg_eth:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
