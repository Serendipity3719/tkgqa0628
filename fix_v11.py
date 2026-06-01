"""Apply V11 fixes to agent_v9.py."""
with open('agent_v9.py', 'r', encoding='utf-8') as f:
    content = f.read()

# FIX II: "receive visit" direction
# "Which country received China's visit?" → China is visitor (obj), country is host (subj)
# This needs to be handled in _detect_visit_direction AND in post_process_facets
# The key: when "received X's visit" or "receive a visit from X", swap subj/obj

old_detect = '''    # Explicit "host" / "receive visit" patterns
    if any(p in q for p in ['hosted', 'host a visit', 'receive', 'received', 'hosting']):
        return 'host' '''

new_detect = '''    # Explicit "host" / "receive visit" patterns
    if any(p in q for p in ['hosted', 'host a visit', 'hosting']):
        return 'host'
    # "receive/received a visit" → the receiver is the host
    if any(p in q for p in ['receive a visit', 'received a visit', "receive china's visit",
                             "received china's visit", 'receive the visit', 'received the visit',
                             'receive visit', 'received visit']):
        return 'host' '''

if old_detect in content:
    content = content.replace(old_detect, new_detect)
    print('FIX II (detect) REPLACED OK')
else:
    print('FIX II (detect) NOT FOUND')
    idx = content.find("'receive', 'received'")
    print(f'  idx={idx}')
    if idx >= 0:
        print(repr(content[idx-100:idx+200]))

# FIX JJ: "Sudanese police" → ["police", "sudan"] in ref_kws
# Also handle other "Adjective + police/military" patterns
# "Sudanese police" → KB: "Police (Sudan)"
# "Thai military" → KB: "Military (Thailand)" or "Military Personnel (Thailand)"
# These are handled by the LLM prompt, but we can add post-processing

old_hh = '''        # FIX HH: "centre" vs "center" normalization in obj/ref keywords
        # KB uses "Center" (American spelling), questions may use "Centre" (British)
        for field in ['object', 'reference']:
            kws = facets[field]['keywords'] if field == 'object' else facets[field]['entity_keywords']
            if kws:
                normalized = [kw.replace('centre', 'center').replace('Centre', 'Center') for kw in kws]
                if field == 'object':
                    facets['object']['keywords'] = normalized
                else:
                    facets['reference']['entity_keywords'] = normalized'''

new_hh = '''        # FIX HH: "centre" vs "center" normalization in obj/ref keywords
        # KB uses "Center" (American spelling), questions may use "Centre" (British)
        for field in ['object', 'reference']:
            kws = facets[field]['keywords'] if field == 'object' else facets[field]['entity_keywords']
            if kws:
                normalized = [kw.replace('centre', 'center').replace('Centre', 'Center') for kw in kws]
                if field == 'object':
                    facets['object']['keywords'] = normalized
                else:
                    facets['reference']['entity_keywords'] = normalized

        # FIX JJ: Adjective-country → country keyword normalization in ref_kws
        # "Sudanese police" → KB: "Police (Sudan)" → ref_kws should include "sudan"
        # "Sudanese" → "sudan", "Thai" → "thailand", etc.
        ADJECTIVE_TO_COUNTRY = {
            'sudanese': 'sudan', 'thai': 'thailand', 'iraqi': 'iraq', 'iranian': 'iran',
            'chinese': 'china', 'japanese': 'japan', 'korean': 'korea', 'russian': 'russia',
            'american': 'united states', 'british': 'united kingdom', 'french': 'france',
            'german': 'germany', 'indian': 'india', 'pakistani': 'pakistan',
            'afghan': 'afghanistan', 'somali': 'somalia', 'ethiopian': 'ethiopia',
            'eritrean': 'eritrea', 'kenyan': 'kenya', 'ugandan': 'uganda',
            'libyan': 'libya', 'egyptian': 'egypt', 'yemeni': 'yemen',
            'syrian': 'syria', 'lebanese': 'lebanon', 'jordanian': 'jordan',
            'saudi': 'saudi arabia', 'turkish': 'turkey', 'israeli': 'israel',
            'palestinian': 'palestinian territory', 'indonesian': 'indonesia',
            'malaysian': 'malaysia', 'philippine': 'philippines', 'vietnamese': 'vietnam',
            'cambodian': 'cambodia', 'burmese': 'myanmar', 'myanmar': 'myanmar',
            'north korean': 'north korea', 'south korean': 'south korea',
        }
        ref_kws_cur2 = facets['reference']['entity_keywords']
        if ref_kws_cur2:
            expanded_ref = list(ref_kws_cur2)
            for kw in ref_kws_cur2:
                kw_l = kw.lower()
                if kw_l in ADJECTIVE_TO_COUNTRY:
                    country = ADJECTIVE_TO_COUNTRY[kw_l]
                    if country not in [k.lower() for k in expanded_ref]:
                        expanded_ref.append(country)
            if expanded_ref != ref_kws_cur2:
                facets['reference']['entity_keywords'] = expanded_ref

        # FIX KK: "leader of X" / "president of X" → ["head of government", "X"] in ref_kws
        # "leader of Turkmenistan" → KB: "Head of Government (Turkmenistan)"
        ref_kws_cur3 = facets['reference']['entity_keywords']
        if ref_kws_cur3:
            ref_str = ' '.join(ref_kws_cur3).lower()
            # Check if ref contains "leader" or "president" but not "head of government"
            if any(kw in ref_str for kw in ['leader', 'president', 'prime minister', 'premier']):
                if 'head of government' not in ref_str:
                    # Add "head of government" to ref_kws
                    new_ref = ['head of government'] + [kw for kw in ref_kws_cur3
                                                         if kw.lower() not in {'leader', 'president',
                                                                                'prime', 'minister',
                                                                                'premier', 'the'}]
                    if new_ref and len(new_ref) >= 2:  # Need at least "head of government" + country
                        facets['reference']['entity_keywords'] = new_ref'''

if old_hh in content:
    content = content.replace(old_hh, new_hh)
    print('FIX JJ+KK REPLACED OK')
else:
    print('FIX JJ+KK NOT FOUND')
    idx = content.find('FIX HH')
    print(f'  FIX HH idx={idx}')
    if idx >= 0:
        print(repr(content[idx:idx+300]))

with open('agent_v9.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('DONE')
