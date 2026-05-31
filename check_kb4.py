"""Check Q44 ref anchor and more edge cases."""

with open('full.txt', 'r', encoding='utf-8-sig') as f:
    recs = []
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            recs.append({'s': parts[0].replace('_',' '), 'r': parts[1].replace('_',' '), 'o': parts[2].replace('_',' '), 'd': parts[3]})

# Q44: Oman+diplomatic cooperation before South Korea
# The question is "Before South Korea, with whom did Oman last wish to establish diplomatic cooperation?"
# ref=South Korea = when did South Korea appear in relation to diplomatic cooperation with OMAN?
# The CORRECT ref date logic: find South Korea first/last in context of Oman's diplomatic cooperation
# South Korea + Oman diplo coop
sk_oman = [r for r in recs if ('south korea' in r['s'].lower() or 'south korea' in r['o'].lower()) 
           and 'diplomatic cooperation' in r['r'].lower() 
           and ('oman' in r['s'].lower() or 'oman' in r['o'].lower())]
sk_oman.sort(key=lambda x: x['d'])
print("=== Q44: South Korea + Oman + diplo coop ===")
print(f"Records: {len(sk_oman)}")
for r in sk_oman:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

# Find JUST south korea + diplomatic cooperation (as subj or obj with Oman)
sk_as_subj = [r for r in recs if r['s'].lower()=='south korea' and 'diplomatic cooperation' in r['r'].lower()]
sk_as_obj = [r for r in recs if r['o'].lower()=='south korea' and 'diplomatic cooperation' in r['r'].lower()]
sk_as_subj.sort(key=lambda x: x['d'])
sk_as_obj.sort(key=lambda x: x['d'])
print(f"\nSouth Korea as SUBJ + diplo coop: {len(sk_as_subj)}")
for r in sk_as_subj[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")
print(f"\nSouth Korea as OBJ + diplo coop: {len(sk_as_obj)}")
for r in sk_as_obj[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

# The FIRST time South Korea appears in diplomatic cooperation (as ref entity)
all_sk = sk_as_subj + sk_as_obj
all_sk.sort(key=lambda x: x['d'])
print(f"\nSouth Korea first in diplo coop: {all_sk[0]['d']}")

# Oman diplo coop before South Korea FIRST appearance
sk_first_date = all_sk[0]['d']
oman_before_sk_first = [r for r in recs if r['s'].lower()=='oman' and 'diplomatic cooperation' in r['r'].lower() and r['d'] < sk_first_date]
oman_before_sk_first.sort(key=lambda x: x['d'])
print(f"Oman diplo coop before SK first ({sk_first_date}): {len(oman_before_sk_first)}")
for r in oman_before_sk_first[-5:]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")
# ANSWER should be Qatar

# Check: is Qatar the correct answer?
print("\n=== Oman diplo coop (all) ===")
oman_diplo = [r for r in recs if r['s'].lower()=='oman' and 'diplomatic cooperation' in r['r'].lower()]
oman_diplo.sort(key=lambda x: x['d'])
for r in oman_diplo:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print("\n=== Q44: With whom did Oman express INTENT for diplo coop? ===")
oman_intent = [r for r in recs if r['s'].lower()=='oman' and 'intent' in r['r'].lower() and 'diplomatic cooperation' in r['r'].lower()]
oman_intent.sort(key=lambda x: x['d'])
for r in oman_intent:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

# What is the Truth for Q44? "Qatar"
# Let's see: when does South Korea FIRST appear in any diplomatic cooperation context?
# And what was the LAST Oman diplo coop obj BEFORE that date?
print("\n=== Summary for Q44 fix ===")
sk_engage = [r for r in recs if r['s'].lower()=='south korea' and r['r']=='Engage in diplomatic cooperation']
sk_engage.sort(key=lambda x: x['d'])
print(f"South Korea engages diplo coop first: {sk_engage[0] if sk_engage else None}")

# The correct logic: find when "south korea" FIRST appears doing ANY diplomatic cooperation
# Then find what Oman LAST did for diplomatic cooperation BEFORE that date
