"""Check Q44 correct logic and Q8/Q52/Q94 edge cases."""

with open('full.txt', 'r', encoding='utf-8-sig') as f:
    recs = []
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            recs.append({'s': parts[0].replace('_',' '), 'r': parts[1].replace('_',' '), 'o': parts[2].replace('_',' '), 'd': parts[3]})

# Q44: Oman last express INTENT for diplo coop before South Korea first APPEARS in that context with Oman
# The Oman+SK interaction starts 2012-01-15
# Oman intent for diplo coop before 2012-01-15:
print("=== Q44: Oman intent diplo coop before 2012-01-15 ===")
oman_intent = [r for r in recs if r['s'].lower()=='oman' and 'diplomatic cooperation' in r['r'].lower() and r['d'] < '2012-01-15']
oman_intent.sort(key=lambda x: x['d'])
print(f"Count: {len(oman_intent)}")
for r in oman_intent[-5:]:
    print(f"  {r['o']} | {r['d']}")
# Last before 2012-01-15 = Qatar (2011-04-26)

print('\n=== Q8: Seyoum Mesfin intent negotiate before Ethiopia ===')
# ref=Ethiopia -> when does Ethiopia first appear in intent_negotiate context?
eth = [r for r in recs if ('ethiopia' in r['s'].lower() or 'ethiopia' in r['o'].lower()) and 'intent to meet or negotiate' in r['r'].lower()]
eth.sort(key=lambda x: x['d'])
print(f"Ethiopia + intent_negotiate: {len(eth)}")
print(f"First: {eth[0]}")
eth_first_date = eth[0]['d']

# Seyoum Mesfin intent_negotiate before Ethiopia first date
sm = [r for r in recs if 'seyoum mesfin' in r['s'].lower() and 'intent to meet or negotiate' in r['r'].lower() and r['d'] < eth_first_date]
sm.sort(key=lambda x: x['d'])
print(f"\nSeyoum Mesfin intent_neg before {eth_first_date}: {len(sm)}")
for r in sm:
    print(f"  {r['s']} | {r['o']} | {r['d']}")

# What about Ethiopia as SUBJ specifically
sm_seyoum = [r for r in recs if 'seyoum' in r['s'].lower() and 'intent to meet or negotiate' in r['r'].lower()]
sm_seyoum.sort(key=lambda x: x['d'])
print(f"\nAll Seyoum Mesfin intent_neg: {len(sm_seyoum)}")
for r in sm_seyoum[:10]:
    print(f"  {r['s']} | {r['o']} | {r['d']}")

# When does Ethiopia first appear in same-rel context?
eth_subj = [r for r in recs if r['s'].lower()=='ethiopia' and 'intent to meet or negotiate' in r['r'].lower()]
eth_subj.sort(key=lambda x: x['d'])
print(f"\nEthiopia as SUBJ intent_neg: {len(eth_subj)}")
print(f"First 3: {[(r['o'],r['d']) for r in eth_subj[:3]]}")

# What about Seyoum Mesfin's records relative to Ethiopia subj date?
if eth_subj:
    eth_subj_date = eth_subj[0]['d']
    sm_before = [r for r in sm_seyoum if r['d'] < eth_subj_date]
    print(f"\nSeyoum before Ethiopia subj ({eth_subj_date}): {len(sm_before)}")
    for r in sm_before:
        print(f"  {r['s']} | {r['o']} | {r['d']}")

# Correct interpretation: "Before Ethiopia" means before Ethiopia did the SAME action (intent_negotiate)
# So find: when did Ethiopia FIRST express intent to negotiate?
# Then find: Seyoum Mesfin's intent_negotiate records BEFORE that date
# But Ethiopia is broad - many many records. The ref should be the FIRST Seyoum+Ethiopia event or Ethiopia's FIRST appearance in same rel
# Let's try: Ethiopia+negotiate as SUBJ
eth_neg = [r for r in recs if r['s'].lower()=='ethiopia' and ('intent to meet or negotiate' in r['r'].lower() or 'negotiate' in r['r'].lower())]
eth_neg.sort(key=lambda x: x['d'])
print(f"\nEthiopia intent/negotiate as SUBJ: first: {eth_neg[0] if eth_neg else None}")

print('\n=== Q52: China visit Sudan/Bruno Stagno ===')
# Before Bruno Stagno Ugarte, what did China last visit?
bsu = [r for r in recs if 'bruno stagno' in r['s'].lower() or 'bruno stagno' in r['o'].lower()]
bsu.sort(key=lambda x: x['d'])
print(f"Bruno Stagno records: {len(bsu)}")
for r in bsu[:5]:
    print(f"  {r['s']} | {r['r']} | {r['o']} | {r['d']}")

if bsu:
    bsu_first = bsu[0]['d']
    china_visit = [r for r in recs if r['s'].lower()=='china' and ('visit' in r['r'].lower()) and r['d'] < bsu_first]
    china_visit.sort(key=lambda x: x['d'])
    print(f"\nChina visit before Bruno Stagno first ({bsu_first}): {len(china_visit)}")
    if china_visit:
        print(f"Last: {china_visit[-5:]}")

print('\n=== Q94: Visits to Malaysia before HoG Turkmenistan ===')
# HoG Turkmenistan visit Malaysia = 2011-12-08
# Who last visited Malaysia before that?
mal_visits = [r for r in recs if 'malaysia' in r['o'].lower() and 'visit' in r['r'].lower() and r['d'] < '2011-12-08']
mal_visits.sort(key=lambda x: x['d'])
# Exclude head of government turkmenistan itself
mal_visits_filtered = [r for r in mal_visits if 'turkmenistan' not in r['s'].lower()]
print(f"Visits to Malaysia before 2011-12-08 (excl Turkmenistan): {len(mal_visits_filtered)}")
if mal_visits_filtered:
    last = mal_visits_filtered[-1]
    print(f"Last: {last}")
    # Last date
    last_date = mal_visits_filtered[-1]['d']
    # All entities visiting Malaysia on last_date
    last_visitors = [r for r in mal_visits_filtered if r['d'] == last_date]
    print(f"\nAll visitors on {last_date}: {[(r['s'], r['r']) for r in last_visitors]}")

print('\n=== Q36 revisit: Malaysia FM praise before Thailand (2009-05-18) ===')
# Need Seyoum ref date logic - find Thailand FIRST date in FM Malaysia praise context
fa_mal_praise = [r for r in recs if 'foreign affairs' in r['s'].lower() and 'malaysia' in r['s'].lower() and 'praise' in r['r'].lower()]
fa_mal_praise.sort(key=lambda x: x['d'])
print(f"Foreign Affairs (Malaysia) praise records: {len(fa_mal_praise)}")
for r in fa_mal_praise:
    print(f"  {r['o']} | {r['d']}")
# Thailand appears at 2009-05-18
# Before that: Laos, Sathirathai, Vietnam, Employee(Bangladesh), Vietnam, Vietnam, Ahmadinejad, Obama, Obama
# Truth: 6 entities before Thailand
th_date = '2009-05-18'
before_th = [r for r in fa_mal_praise if r['d'] < th_date]
print(f"\nBefore Thailand ({th_date}): {[(r['o'], r['d']) for r in before_th]}")
