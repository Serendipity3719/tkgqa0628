"""Check more KB edge cases for V8 fixes."""

with open('full.txt', 'r', encoding='utf-8-sig') as f:
    recs = []
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            recs.append({'s': parts[0].replace('_',' '), 'r': parts[1].replace('_',' '), 'o': parts[2].replace('_',' '), 'd': parts[3]})

# Q35: China "visit" Henry M Paulson - last date
# The question asks "When did China last visit Henry M Paulson?"
# Truth: 2006-09-23
# "Visit" KB relations include: "Make a visit", "Host a visit"
# China "Host a visit" Henry M. Paulson last = 2013-06-08 -- WRONG
# China "Make a visit" Henry M. Paulson last = 2006-09-23 -- CORRECT!
print("=== Q35: China Visit Paulson - Make a visit vs Host a visit ===")
make_visit = [r for r in recs if r['s'].lower()=='china' and 'paulson' in r['o'].lower() and r['r'] == 'Make a visit']
host_visit = [r for r in recs if r['s'].lower()=='china' and 'paulson' in r['o'].lower() and r['r'] == 'Host a visit']
print(f"Make a visit: {len(make_visit)}, last: {sorted(make_visit, key=lambda x: x['d'])[-1]['d']}")
print(f"Host a visit: {len(host_visit)}, last: {sorted(host_visit, key=lambda x: x['d'])[-1]['d']}")
# So "China last visit Paulson" should only use "Make a visit" not "Host a visit"

# Q89: Burundi first visit to China
# Truth: 2006-06-14 (Burundi Make a visit China)
# But there's Burundi Host a visit China 2005-08-25 (earlier!)
# The question "first visit OF Burundi TO China" = Burundi goes TO China = Make a visit
print("\n=== Q89: Burundi TO China (Make a visit) vs Host ===")
burundi_make = [r for r in recs if r['s'].lower()=='burundi' and 'china' in r['o'].lower() and r['r'] == 'Make a visit']
burundi_host = [r for r in recs if r['s'].lower()=='burundi' and 'china' in r['o'].lower() and r['r'] == 'Host a visit']
print(f"Make a visit (Burundi to China): {sorted(burundi_make, key=lambda x: x['d'])}")
print(f"Host a visit (China visits Burundi): {sorted(burundi_host, key=lambda x: x['d'])}")

# Q76: Head of Government Peru visit China
# Truth: 2010-03 (Make a visit)
# V7 got 2007-03 (Host a visit)
print("\n=== Q76: HoG Peru visit China - Make vs Host ===")
peru_make = [r for r in recs if 'peru' in r['s'].lower() and 'china' in r['o'].lower() and r['r'] == 'Make a visit']
peru_host = [r for r in recs if 'peru' in r['s'].lower() and 'china' in r['o'].lower() and r['r'] == 'Host a visit']
print(f"Make a visit: {peru_make}")
print(f"Host a visit: {peru_host}")

# Q17: China threaten before Military(Taiwan) last date
# Military(Taiwan) last = 2015-10-30
# China last threaten before that date = should be "Angela Merkel"?
print("\n=== Q17: China Threaten before Military(Taiwan) ===")
mil_tw = [r for r in recs if 'military' in r['s'].lower() and 'taiwan' in r['s'].lower()]
mil_tw.sort(key=lambda x: x['d'])
ref_date = mil_tw[-1]['d']
print(f"Military(Taiwan) last = {ref_date}")

china_threaten = [r for r in recs if r['s'].lower()=='china' and r['r']=='Threaten']
before = [r for r in china_threaten if r['d'] < ref_date]
before.sort(key=lambda x: x['d'])
print(f"China+Threaten before {ref_date}: {len(before)}")
if before:
    print(f"Last 5: {[(r['o'], r['d']) for r in before[-5:]]}")

# Q88: Donald Rumsfeld threaten Iraq last 
print("\n=== Q88: Donald Rumsfeld Threaten Iraq ===")
hits = [r for r in recs if 'rumsfeld' in r['s'].lower() and 'iraq' in r['o'].lower() and r['r'] == 'Threaten']
hits.sort(key=lambda x: x['d'])
print(f"Rumsfeld+Threaten+Iraq: {[(r['o'], r['d']) for r in hits]}")

# Q11: Criminal(Somalia) threaten China first time
print("\n=== Q11: Criminal(Somalia) Threaten China ===")
hits = [r for r in recs if r['s'].lower()=='criminal (somalia)' and r['r']=='Threaten' and r['o'].lower()=='china']
hits.sort(key=lambda x: x['d'])
print(f"Criminal(Somalia)+Threaten+China: {hits}")

# Q77: Ethiopian Police "Use conventional military force" against Ethiopia
print("\n=== Q77: Ethiopian Police conv military Ethiopia ===")
# What's the KB entity for "Ethiopian police"?
hits = [r for r in recs if 'ethiopian' in r['s'].lower() and 'police' in r['s'].lower()]
ents = set(r['s'] for r in hits)
print(f"Ethiopian police entities: {ents}")
hits2 = [r for r in recs if 'police' in r['s'].lower() and 'ethiopia' in r['s'].lower()]
ents2 = set(r['s'] for r in hits2)
print(f"Police(Ethiopia) entities: {ents2}")
hits3 = [r for r in recs if 'police' in r['s'].lower() and 'ethiopia' in r['s'].lower() and 'conventional' in r['r'].lower()]
print(f"Police(Ethiopia)+conventional: {len(hits3)}")
for r in sorted(hits3, key=lambda x: x['d'])[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

# Reveal the truth: "last" use conventional force against Ethiopia by Ethiopian Police
hits4 = [r for r in recs if 'police' in r['s'].lower() and 'ethiopia' in r['s'].lower() and 'ethiopia' in r['o'].lower() and 'conventional' in r['r'].lower()]
print(f"\nPolice(Ethiopia)+conv+Ethiopia: {len(hits4)}")
for r in sorted(hits4, key=lambda x: x['d'])[:10]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

# Q44: Oman diplomatic coop before South Korea last
print("\n=== Q44: Find South Korea in Oman diplo coop context ===")
# Need to find: when did South Korea last appear in context of diplomatic cooperation?
sk_diplo = [r for r in recs if ('south korea' in r['s'].lower() or 'south korea' in r['o'].lower()) and 'diplomatic cooperation' in r['r'].lower()]
sk_diplo.sort(key=lambda x: x['d'])
print(f"South Korea + diplomatic coop: {len(sk_diplo)}")
print(f"Last: {[(r['s'],r['o'],r['d']) for r in sk_diplo[-5:]]}")

# Oman diplo coop before South Korea last date
if sk_diplo:
    sk_last = sk_diplo[-1]['d']
    oman_before = [r for r in recs if r['s'].lower()=='oman' and 'diplomatic cooperation' in r['r'].lower() and r['d'] < sk_last]
    oman_before.sort(key=lambda x: x['d'])
    print(f"\nOman+diplo+before {sk_last}: {len(oman_before)}")
    if oman_before:
        print(f"Last: {oman_before[-3:]}")
