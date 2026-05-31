RECORDS = []
with open('E:/RAG_Agent_Experiment/full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            RECORDS.append({'subj': parts[0].replace('_',' '), 'rel': parts[1].replace('_',' '), 'obj': parts[2].replace('_',' '), 'date': parts[3]})

# Q8: "Before Ethiopia, which country did Seyoum Mesfin express his intention to negotiate with?"
# Truth: ['China', 'Sudan']
# Ethiopia ref date = 2014-03-04 (when Seyoum negotiated with Ethiopia)
# Before 2014-03-04, Seyoum negotiated with: China (2005-11-22), Sudan (2007-01-03), Sudan (2007-01-04), China (2010-06-29)
# So truth = {China, Sudan} — CORRECT!
# The issue: current V6 produces 6 entities. Why?
# V6 uses ref='ethiopia', rel=['intent to meet or negotiate','intent','meet','negotiate','meeting'] 
# Then searches "Seyoum Mesfin + intent or negotiate + Ethiopia" 
# But stem-expanded rel_kws include 'meeting', 'intent', 'meet' -> too broad

print("=== Q8 Debug ===")
seyoum_all_intent = [r for r in RECORDS if 'seyoum' in r['subj'].lower() and 'intent to meet or negotiate' in r['rel'].lower()]
print("All Seyoum 'intent to meet or negotiate':")
for r in sorted(seyoum_all_intent, key=lambda x: x['date']):
    print(f"  {r['date']} | {r['subj']} | {r['rel']} | {r['obj']}")

# If we use ONLY the core relation and restrict to before Ethiopia date
t_ref = '2014-03-04'
before = [r for r in seyoum_all_intent if r['date'] < t_ref and 'ethiopia' not in r['obj'].lower()]
print(f"\nBefore {t_ref} (excl Ethiopia):")
entities = sorted(set(r['obj'] for r in before))
print(f"Entities: {entities}")

# Q29 is a major one (200+ FP for Seyoum+maliki): optimistic before a date
# Q29: "Before 22 October 2008, which country did Malaysia make optimistic remarks about?"
# Truth: ['Mahmoud Abbas', 'Thailand', 'Association of Southeast Asian Nations', 'Iran', 'Japan', ...]
# V6 returns 13 entities - model has: Malaysia, Men(Malaysia), National Front Malaysia, etc. as FP
malaysia_opt = [r for r in RECORDS if 'malaysia' in r['subj'].lower() and 'optimistic' in r['rel'].lower() and r['date'] < '2008-10-22']
print("\n=== Q29 Debug ===")
print(f"Malaysia optimistic before 2008-10-22: {len(malaysia_opt)}")
for r in sorted(malaysia_opt, key=lambda x: x['date']):
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
entities_q29 = sorted(set(r['obj'] for r in malaysia_opt if 'malaysia' in r['subj'].lower() and r['subj'].lower() == 'malaysia'))
print(f"Entities (exact 'malaysia' subj): {entities_q29}")
exact_malaysia = [r for r in malaysia_opt if r['subj'].lower() == 'malaysia']
print(f"Records with exact 'malaysia' subj: {len(exact_malaysia)}")
for r in exact_malaysia:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Q47: "Who did Iraq reject after the dissident of the People's Mujahedin of Iran?"
# This produced 500+ FP entities
print("\n=== Q47 Debug ===")
mujahedin = [r for r in RECORDS if 'mujahedin' in r['subj'].lower() or 'mujahedin' in r['obj'].lower()]
print(f"Records with mujahedin: {len(mujahedin)}")
for r in sorted(mujahedin, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

dissident_iran = [r for r in RECORDS if 'people' in r['subj'].lower() and 'mujahedin' in r['subj'].lower()]
print(f"\nPeople's Mujahedin records as subj: {len(dissident_iran)}")
for r in sorted(dissident_iran, key=lambda x: x['date'])[:5]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# Check reject records for Iraq AFTER the ref date
# First: find what the Mujahedin did (or was done to) closest to the question context
# "dissident of People's Mujahedin" = the Mujahedin entity itself
iraq_reject = [r for r in RECORDS if 'iraq' in r['subj'].lower() and 'reject' in r['rel'].lower()]
print(f"\nIraq reject records: {len(iraq_reject)}")
# Check what entity did Mujahedin represent
all_mujahedin = [r for r in RECORDS if "people" in r['subj'].lower() and "mujahedin" in r['subj'].lower() and "iran" in r['subj'].lower()]
print(f"\nPeople's Mujahedin of Iran as subj: {len(all_mujahedin)}")
for r in sorted(all_mujahedin, key=lambda x: x['date'])[:10]:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")

# The truth for Q47 is unknown from here - check if Iraq rejected mujahedin
iraq_rej_mujahedin = [r for r in RECORDS if 'iraq' in r['subj'].lower() and 'reject' in r['rel'].lower() and 'mujahedin' in r['obj'].lower()]
print(f"\nIraq reject mujahedin: {len(iraq_rej_mujahedin)}")
for r in iraq_rej_mujahedin:
    print(f"  {r['date']} {r['subj']} | {r['rel']} | {r['obj']}")
