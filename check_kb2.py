"""Check more KB cases."""

with open('full.txt', 'r', encoding='utf-8-sig') as f:
    recs = []
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            recs.append({'s': parts[0].replace('_',' '), 'r': parts[1].replace('_',' '), 'o': parts[2].replace('_',' '), 'd': parts[3]})

print('=== Q11: Criminal (Somalia) + Threaten (KB exact name) ===')
hits = [r for r in recs if 'criminal (somalia)' == r['s'].lower() and ('threaten' in r['r'].lower() or 'coerce' in r['r'].lower())]
print(f"Criminal(Somalia)+threaten/coerce: {len(hits)}")
for r in sorted(hits, key=lambda x: x['d'])[:10]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

# What do Criminal (Somalia) actually do?
hits2 = [r for r in recs if 'criminal (somalia)' == r['s'].lower() and 'china' in r['o'].lower()]
print(f"\nCriminal(Somalia)+china: {len(hits2)}")
for r in hits2[:10]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print('\n=== Q11: What is "threaten" in KB? ===')
# "Threaten" is not "Coerce" -- let's check
hits = [r for r in recs if r['r'] == 'Threaten']
print(f"'Threaten' exact: {len(hits)}")
for r in sorted(hits, key=lambda x: x['d'])[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")
# "Coerce"
hits2 = [r for r in recs if r['r'] == 'Coerce']
print(f"\n'Coerce' exact: {len(hits2)}")
for r in sorted(hits2, key=lambda x: x['d'])[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print('\n=== Q88: Donald Rumsfeld "threaten/coerce" Iraq ===')
hits = [r for r in recs if 'rumsfeld' in r['s'].lower() and 'iraq' in r['o'].lower() and ('threaten' in r['r'].lower() or 'coerce' in r['r'].lower())]
print(f"Rumsfeld+Iraq+threaten/coerce: {len(hits)}")
for r in sorted(hits, key=lambda x: x['d'])[:10]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print('\n=== Q17: China coerce/threaten - what entities? ===')
hits = [r for r in recs if 'china' == r['s'].lower() and ('threaten' in r['r'].lower() or 'coerce' in r['r'].lower())]
print(f"China+threaten/coerce: {len(hits)}")
# Check records near military taiwan date
hits_mil = [r for r in recs if 'military' in r['s'].lower() and 'taiwan' in r['s'].lower()]
dates_mil = sorted([r['d'] for r in hits_mil])
print(f"Military(Taiwan) first date: {dates_mil[:3]}, last: {dates_mil[-3:]}")
# China threaten before military(taiwan) last
ml_last = dates_mil[-1]
china_before = [r for r in hits if r['d'] < ml_last]
print(f"China threaten/coerce before {ml_last}: {len(china_before)}")
if china_before:
    print(f"Last: {sorted(china_before, key=lambda x: x['d'])[-3:]}")

print('\n=== Q76: Prime Minister / Head of Government Peru visit China ===')
hits = [r for r in recs if 'peru' in r['s'].lower() and 'head of government' in r['s'].lower() and 'china' in r['o'].lower() and 'visit' in r['r'].lower()]
print(f"HoG(Peru)+visit+China: {len(hits)}")
for r in sorted(hits, key=lambda x: x['d'])[:10]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print('\n=== Q89: Burundi visit China ===')
hits = [r for r in recs if r['s'].lower() == 'burundi' and 'china' in r['o'].lower() and 'visit' in r['r'].lower()]
print(f"Burundi+visit+China (exact): {len(hits)}")
for r in sorted(hits, key=lambda x: x['d'])[:10]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

hits2 = [r for r in recs if 'burundi' in r['s'].lower() and 'china' in r['o'].lower() and 'visit' in r['r'].lower()]
print(f"\nBurundi(all)+visit+China: {len(hits2)}")
for r in sorted(hits2, key=lambda x: x['d'])[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print('\n=== Q35: China visit Henry M Paulson ===')
hits = [r for r in recs if 'china' == r['s'].lower() and 'paulson' in r['o'].lower() and 'visit' in r['r'].lower()]
print(f"China+visit+Paulson (exact): {len(hits)}")
for r in sorted(hits, key=lambda x: x['d']):
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

hits2 = [r for r in recs if 'paulson' in r['s'].lower() and 'china' in r['o'].lower() and 'visit' in r['r'].lower()]
print(f"\nPaulson+visit+China: {len(hits2)}")
for r in sorted(hits2, key=lambda x: x['d']):
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print('\n=== Q94: Head of Government Turkmenistan visits Malaysia ===')
hits = [r for r in recs if 'head of government' in r['s'].lower() and 'turkmenistan' in r['s'].lower() and 'malaysia' in r['o'].lower()]
print(f"HoG(Turkmenistan)+Malaysia: {len(hits)}")
for r in sorted(hits, key=lambda x: x['d'])[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

print('\n=== Q44: Oman + diplomatic cooperation + South Korea as ref ===')
hits = [r for r in recs if 'oman' == r['s'].lower() and 'diplomatic cooperation' in r['r'].lower()]
print(f"Oman+diplomatic_coop: {len(hits)}")
for r in sorted(hits, key=lambda x: x['d'])[:10]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

# South Korea first appears in Oman diplo coop?
hits_sk = [r for r in recs if 'south korea' in r['s'].lower() and 'diplomatic cooperation' in r['r'].lower() and 'oman' in r['o'].lower()]
hits_sk += [r for r in recs if 'oman' in r['s'].lower() and 'diplomatic cooperation' in r['r'].lower() and 'south korea' in r['o'].lower()]
hits_sk2 = [r for r in recs if 'south korea' in r['o'].lower() and 'diplomatic cooperation' in r['r'].lower()]
print(f"\nSouth Korea as ref in oman diplo: {len(hits_sk)}")
for r in sorted(hits_sk, key=lambda x: x['d'])[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")
