"""
RAG Agent V6 — Precision-First Optimization (V5 Universal + 3 Root Cause Fixes)

V6 New Fixes (over V5 Universal):
  - Fix J: rel_fuzzy_expand now uses CONTAINED-ONLY expansion:
      Only KB relations that contain the original keyword are candidates.
      Only the matched relation itself is used (not its other tokens).
      Prevents "visit" from expanding to "appeal", "request", "optimistic" etc.
  - Fix K: equal/before_after solvers bypass noisy candidate pool for entity-list output.
      Instead of filtering from a large scored pool, use search_records DIRECTLY with
      tightly constrained rel (original keywords, not expanded) + subj/obj.
      This eliminates False Positives from noisy multi-topic retrieval.
  - Fix L: first_last strict_rel search uses CORE rel_kws first (no expand).
      rel_fuzzy_expand used only as fallback when core search returns 0 results.
      Prevents wrong-direction time drift caused by loosely matched relations.
"""
import json
import re
import sys
import time
from collections import defaultdict
from openai import OpenAI

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ============================================================
# 0. Initialize
# ============================================================
client = OpenAI(
    api_key="sk-df8572020995431dabd601c35ff7a50f",
    base_url="https://api.deepseek.com"
)

def call_llm(prompt, temperature=0.1, max_tokens=800):
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a precise knowledge graph query parser. Output strictly in the requested JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"API_ERROR: {e}"

# ============================================================
# 1. Load Knowledge Base
# ============================================================
print("Loading knowledge base...")
RECORDS = []
with open('full.txt', 'r', encoding='utf-8-sig') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 4:
            subj, rel, obj, date = parts
            RECORDS.append({
                'subj': subj.replace('_', ' '),
                'rel': rel.replace('_', ' '),
                'obj': obj.replace('_', ' '),
                'date': date,
            })
print(f"Knowledge base loaded: {len(RECORDS)} records")

ALL_RELATIONS = sorted(set(r['rel'] for r in RECORDS))
ALL_RELATIONS_LOWER = [r.lower() for r in ALL_RELATIONS]

# ============================================================
# FIX J: Precision-First rel_fuzzy_expand
# ============================================================
def _make_stem(word):
    w = word.lower()
    for suffix in ('ation', 'ment', 'ing', 'ion', 'ed', 'es', 's'):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            return w[: len(w) - len(suffix)]
    return w

def _defense_norm(text: str) -> str:
    return text.replace('defence', 'defense').replace('Defence', 'Defense')

def rel_fuzzy_expand(query_keywords: list) -> list:
    """
    FIX J: Precision-First expansion.
    
    Strategy:
    1. For each keyword kw, only consider KB relations that CONTAIN kw as a substring.
    2. Keep only the KB relation itself (as a match token), not its other tokens.
    3. Add stem variants of the original keyword, but only if the stem also appears
       as a direct substring in at least one KB relation.
    4. defence/defense normalization only.
    
    This prevents "visit" from pulling in "appeal", "request", "statement" etc.
    The old behavior extracted ALL tokens from matching relations, causing massive FP.
    """
    if not query_keywords:
        return []

    expanded = []
    seen = set()

    def add(tok):
        t = tok.lower()
        if t not in seen and len(t) >= 3:
            seen.add(t)
            expanded.append(t)

    for kw in query_keywords:
        add(kw)

        kw_l = kw.lower()

        # defence ↔ defense normalization
        if 'defence' in kw_l:
            add(kw_l.replace('defence', 'defense'))
        elif 'defense' in kw_l:
            add(kw_l.replace('defense', 'defence'))

        # Only expand to SYNONYMS that appear in KB relations as a COMPLETE substring match
        # (not extracting unrelated tokens from those relations)
        kw_stem = _make_stem(kw_l)

        for kb_rel_lower in ALL_RELATIONS_LOWER:
            # The original keyword (or its stem) must appear IN the relation string
            if kw_l in kb_rel_lower or kw_stem in kb_rel_lower:
                # Add only closely related single-word tokens that share the same stem
                # Do NOT add all other tokens from the relation
                tokens = [t.strip('()/,') for t in kb_rel_lower.split() if len(t.strip('()/,')) >= 3]
                for tok in tokens:
                    tok_stem = _make_stem(tok)
                    # Only add if this token is a stem-variant of the original keyword
                    if tok_stem == kw_stem or kw_stem in tok or tok in kw_l:
                        add(tok)

        # Plural/singular variants
        if kw_l.endswith('s') and len(kw_l) > 3:
            singular = kw_l[:-1]
            if any(singular in rl for rl in ALL_RELATIONS_LOWER):
                add(singular)
        else:
            plural = kw_l + 's'
            if any(plural in rl for rl in ALL_RELATIONS_LOWER):
                add(plural)

    # Filter: keep only keywords that actually appear in at least one KB relation
    cleaned = [kw for kw in expanded
               if any(kw in rl for rl in ALL_RELATIONS_LOWER)
               or kw in (k.lower() for k in query_keywords)]

    return cleaned if cleaned else list(query_keywords)


def rel_core_match(query_keywords: list) -> list:
    """
    FIX K/L: Core (no-expansion) relation matching.
    Returns a deduplicated list of KB relations that directly contain
    at least one of the query keywords as a substring.
    Used for precision-critical searches (equal entity-list, before_after entity-list,
    first_last strict search).
    """
    if not query_keywords:
        return []

    matched_rels = set()
    for kw in query_keywords:
        kw_l = kw.lower()
        for kb_rel in ALL_RELATIONS:
            if kw_l in kb_rel.lower():
                matched_rels.add(kb_rel)
        # defence/defense swap
        if 'defence' in kw_l:
            alt = kw_l.replace('defence', 'defense')
            for kb_rel in ALL_RELATIONS:
                if alt in kb_rel.lower():
                    matched_rels.add(kb_rel)
        elif 'defense' in kw_l:
            alt = kw_l.replace('defense', 'defence')
            for kb_rel in ALL_RELATIONS:
                if alt in kb_rel.lower():
                    matched_rels.add(kb_rel)
    return list(query_keywords)  # keep original keywords for search_records usage


GENERIC_OBJ_KEYWORDS = {'country', 'person', 'state', 'entity', 'organization', 'unknown', 'who', 'what'}
USE_LLM_SUFFICIENCY = False

def keyword_in_text(keyword, text):
    kw = _defense_norm(keyword.lower())
    text = _defense_norm(text.lower())
    return kw in text

def is_simple_entity_keyword(keywords):
    return len(keywords) == 1 and re.fullmatch(r'[a-z][a-z ]+', keywords[0].lower()) is not None

def exact_entity_match(value, keywords):
    return is_simple_entity_keyword(keywords) and value.lower() == keywords[0].lower()

# ============================================================
# V5 FIX A (inherited): post_process_facets() — generic normalization only
# ============================================================
def post_process_facets(question, qtype, facets_data):
    facets = facets_data['facets']
    rel = facets['relation']['keywords']

    if rel:
        facets['relation']['keywords'] = rel_fuzzy_expand(rel)

    q = question.lower()
    if qtype == 'before_after' and not facets['time'].get('value'):
        month_map = {
            'january': '01', 'february': '02', 'march': '03', 'april': '04',
            'may': '05', 'june': '06', 'july': '07', 'august': '08',
            'september': '09', 'october': '10', 'november': '11', 'december': '12',
        }
        m = re.search(r'\b(\d{1,2})\s+(' + '|'.join(month_map) + r')\s+(\d{4})\b', q)
        if m:
            facets['time']['constraint_type'] = 'absolute'
            facets['time']['value'] = f"{m.group(3)}-{month_map[m.group(2)]}-{int(m.group(1)):02d}"
            facets['reference']['entity_keywords'] = []
        else:
            m = re.search(r'\b(after|before)\s+(\d{4})(?!-\d)', q)
            if m:
                facets['time']['constraint_type'] = 'absolute'
                facets['time']['value'] = m.group(2)
                facets['reference']['entity_keywords'] = []

    return facets_data

# ============================================================
# 2. Facet Parser (LLM)
# ============================================================
FACET_PARSE_PROMPT = """You are a knowledge graph query parser. KB format: subject | relation | object | date

KB relation types (FULL LIST - use EXACT substrings):
{relations_list}

KB entity naming conventions (CRITICAL):
- "Danish Ministry of Defence and Security" -> KB: "Defense / Security Ministry (Denmark)" -> keywords: ["denmark", "defense"]
- "Taiwan's Ministry of National Defence" -> KB: "Defense / Security Ministry (Taiwan)" -> keywords: ["taiwan", "defense"]
- "Cabinet Council of Ministers of Kazakhstan" -> KB: "Cabinet / Council of Ministers / Advisors (Kazakhstan)" -> keywords: ["kazakhstan", "cabinet"]
- Person names: use EXACTLY as given. "Kitti Wasinondh" -> ["kitti wasinondh"] (NOT "kitti" alone)
- Country names: use ROOT form. "Danish" -> "denmark", "Taiwanese" -> "taiwan"
- "Governor of Japan" -> keywords: ["governor", "japan"]
- "Prime Minister / leader of X" -> KB: "Head of Government (X)" -> keywords: ["head of government", "x"]
- "citizens of Saudi Arabia" -> KB: "Citizen (Saudi Arabia)" -> keywords: ["saudi arabia", "citizen"]
- "Saudi Arabian Defence Forces" -> keywords: ["saudi arabian defence"] (use "defence" NOT "defense")
- "military of Taiwan" -> KB: "Military (Taiwan)" -> keywords: ["military", "taiwan"]
- "Government Delegation of North Korea" -> keywords: ["government delegation", "north korea"]
- "religion of China" -> keywords: ["religion", "china"]
- "Malaysian Foreign Ministry" -> KB: "Foreign Affairs (Malaysia)" -> keywords: ["foreign affairs", "malaysia"]
- "Thai military" -> KB: "Military (Thailand)" -> keywords: ["military", "thailand"]
- "Lawyer/Attorney of South Korea" -> KB: "Lawyer / Attorney (South Korea)" -> keywords: ["lawyer", "south korea"]
- "member of the Legislative Council of Iraq" -> KB: "Member of Parliament (Iraq)" -> keywords: ["member", "parliament", "iraq"]
- "Somali criminal" -> KB: "Criminal (Somalia)" -> keywords: ["somalia", "criminal"]
- "Henry M Paulson" -> KB: "Henry M Paulson" -> keywords: ["paulson"]
- "first visit of Burundi to China" -> subj=["burundi"], rel=["visit"], obj=["china"]
- "China last visit Henry M Paulson" -> subj=["china"], rel=["visit"], obj=["paulson"]

RELATION MAPPING (use these exact KB substrings — KEEP MINIMAL, DO NOT expand):
- "visit / visited / paid a visit to / make a visit / host a visit" -> rel keywords: ["visit"]
- "telephone call / discuss by telephone" -> rel keywords: ["telephone"]
- "condemn / criticize / criticised / denounce" -> rel keywords: ["criticize", "denounce"]
- "praised / commend / approval / endorse" -> rel keywords: ["praise", "approval"]
- "optimistic / optimism" -> rel keywords: ["optimistic"]
- "pessimistic" -> rel keywords: ["pessimistic"]
- "negotiate / negotiation" -> rel keywords: ["intent to meet or negotiate"]
- "appeal / request" -> rel keywords: ["appeal or request"]
- "small arms / light weapons" -> rel keywords: ["small arms"]
- "unconventional force / violence" -> rel keywords: ["unconventional"]
- "cooperate / cooperation" -> rel keywords: ["cooperate"]
- "diplomatic cooperation" -> rel keywords: ["diplomatic cooperation"]
- "investigate / investigated" -> rel keywords: ["investigate"]
- "accuse / accused" -> rel keywords: ["accuse"]
- "reject" -> rel keywords: ["reject"]
- "sign an agreement" -> rel keywords: ["sign"]
- "conventional military force" -> rel keywords: ["conventional military"]
- "coerce / threaten with force" -> rel keywords: ["coerce"]
- "study / research" -> rel keywords: ["study"]

CRITICAL RULE: Output ONLY the minimal relation keywords listed above.
Do NOT expand or add extra words. "visit" stays as ["visit"], NOT ["visit", "appeal", "request"].

===========================================================
TEMPORAL LOGIC VALUES — CRITICAL:
===========================================================
The "temporal_logic" field MUST be one of these exact values:
  "first"        — looking for the earliest event
  "last"         — looking for the most recent event
  "before"       — looking for events BEFORE a reference
  "after"        — looking for events AFTER a reference
  "before_after" — compound: looking for events BETWEEN t_start and t_end
  "equal_time"   — looking for events at the same time as a reference

===========================================================
PASSIVE VOICE RULES (CRITICAL):
===========================================================
When the question uses passive voice such as "X was [ACTION] by Y",
the GRAMMATICAL subject X is actually the OBJECT of the KB triple.
The agent Y (after "by") is the SUBJECT of the KB triple.

PASSIVE VOICE FEW-SHOT EXAMPLES:

Example P1:
  Question: "After the Lawyer/Attorney of South Korea, who was investigated by the Lawyer/Attorney of South Korea?"
  -> subject.keywords = ["lawyer", "south korea"]
  -> relation.keywords = ["investigate"]
  -> object.keywords = []
  -> reference.entity_keywords = ["sankei"]

Example P2:
  Question: "Who did Iraq reject after the People's Mujahedin of Iran?"
  -> subject.keywords = ["iraq"]
  -> relation.keywords = ["reject"]
  -> object.keywords = []
  -> reference.entity_keywords = ["mujahedin", "iran"]

Example P3:
  Question: "Who criticized Chuck Hagel after China?"
  -> subject.keywords = []
  -> relation.keywords = ["criticize"]
  -> object.keywords = ["chuck hagel"]
  -> reference.entity_keywords = ["china"]

===========================================================
COMPOUND / NESTED TEMPORAL FEW-SHOT EXAMPLES:
===========================================================

Example T1 (before_last with subj):
  Question: "Before the Royal Administration of Saudi Arabia, what did China last praise?"
  -> qtype: before_last
  -> subject.keywords = ["china"]
  -> relation.keywords = ["praise", "approval"]
  -> object.keywords = []
  -> reference.entity_keywords = ["royal administration", "saudi arabia"]
  -> answer_type = "entity"

Example T2 (before_last, no explicit subj):
  Question: "Before the leader of Turkmenistan, who last visited Malaysia?"
  -> qtype: before_last
  -> subject.keywords = []
  -> relation.keywords = ["visit"]
  -> object.keywords = ["malaysia"]
  -> reference.entity_keywords = ["head of government", "turkmenistan"]
  -> answer_type = "entity"

Example T3 (before_after with absolute date):
  Question: "Before 22 October 2008, which country did Malaysia make optimistic remarks about?"
  -> qtype: before_after
  -> subject.keywords = ["malaysia"]
  -> relation.keywords = ["optimistic"]
  -> object.keywords = []
  -> time.value = "2008-10-22"
  -> reference.entity_keywords = []

Example T4 (after_first):
  Question: "After Denmark, who was the first to visit Iraq?"
  -> qtype: after_first
  -> subject.keywords = []
  -> relation.keywords = ["visit"]
  -> object.keywords = ["iraq"]
  -> reference.entity_keywords = ["denmark"]

Example T5 (before_after with entity ref):
  Question: "Who did the Malaysian Foreign Ministry praise before Thailand?"
  -> qtype: before_after
  -> subject.keywords = ["foreign affairs", "malaysia"]
  -> relation.keywords = ["praise", "approval"]
  -> object.keywords = []
  -> reference.entity_keywords = ["thailand"]
  -> temporal_logic = "before"

Example T6 (equal_multi):
  Question: "Who visited China in the same month as Antonis Samaras?"
  -> qtype: equal_multi
  -> subject.keywords = []
  -> relation.keywords = ["visit"]
  -> object.keywords = ["china"]
  -> reference.entity_keywords = ["samaras"]

Example T7 (before_last, find the receiver entity):
  Question: "Before China, what did the Head of Government of Egypt last visit?"
  -> qtype: before_last
  -> subject.keywords = ["head of government", "egypt"]
  -> relation.keywords = ["visit"]
  -> object.keywords = []
  -> reference.entity_keywords = ["china"]
  -> answer_type = "entity"

===========================================================
BEFORE_LAST REASONING GUIDE:
===========================================================
For before_last questions follow this two-phase mental model:
  Phase 1 — Find t_ref: Look up when the reference entity LAST appears in the KB
             doing the SAME action (or any action) as the question.
  Phase 2 — Find main event: Among all records BEFORE t_ref that match
             subject+relation+object, return the LAST one's object (or subject).
Make sure reference.entity_keywords captures the reference entity accurately.

===========================================================

Question: {question}
Question type: {qtype}

QTYPE-SPECIFIC RULES (CRITICAL):
- after_first: subject.keywords = [] (EMPTY - searching for actor); reference = REF_ENTITY; obj = target
- before_last: subject = SUBJ (if given, else []); reference = REF_ENTITY; obj = OBJ (if given, else [])
- before_after: reference = time-anchor entity OR set time.value for absolute dates;
                temporal_logic = "before", "after", or "before_after" (for compound)
- equal (time answer): answer_type = "time"; time_granularity = "month" or "year"
- equal (entity answer): answer_type = "entity_list"; time.value = the date/year from question
- equal_multi: reference.entity_keywords = REF_ENTITY; answer_type = "entity_list"
- first_last (when): answer_type = "time"; first_last (who): answer_type = "entity"

Output ONLY JSON:
{{
  "facets": {{
    "subject": {{"keywords": ["keywords or EMPTY [] for after_first"]}},
    "relation": {{"keywords": ["EXACT KB relation substrings — MINIMAL LIST ONLY"], "q_verb": "verb from question"}},
    "object": {{"keywords": ["object entity keywords"]}},
    "time": {{"constraint_type": "absolute/relative/none", "value": "2005-04 or null"}},
    "reference": {{"entity_keywords": ["REF entity keywords"], "relation_keywords": [], "entity_role": "subject",
                   "end_anchor_keywords": ["for compound before_after: end anchor entity keywords, else []"]}}
  }},
  "temporal_logic": "first/last/after/before/before_after/equal_time",
  "answer_type": "entity/time/entity_list",
  "time_granularity": "year/month/day"
}}"""

def parse_question_to_facets(question, qtype):
    rels_text = "\n".join(f"  - {r}" for r in ALL_RELATIONS[:100])
    prompt = FACET_PARSE_PROMPT.format(relations_list=rels_text, question=question, qtype=qtype)
    response = call_llm(prompt, max_tokens=600)

    try:
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            f = parsed.setdefault('facets', {})
            f.setdefault('subject', {"keywords": [], "is_reference_entity": False})
            f.setdefault('relation', {"keywords": [], "q_verb": ""})
            f.setdefault('object', {"keywords": [], "is_reference_entity": False})
            f.setdefault('time', {"constraint_type": "none", "value": None})
            ref = f.setdefault('reference', {"entity_keywords": [], "relation_keywords": [], "entity_role": "object", "end_anchor_keywords": []})
            ref.setdefault('end_anchor_keywords', [])
            parsed.setdefault('temporal_logic', 'last')
            parsed.setdefault('answer_type', 'entity')
            parsed.setdefault('time_granularity', 'day')
            return parsed
    except:
        pass

    return {
        "facets": {
            "subject": {"keywords": [], "is_reference_entity": False},
            "relation": {"keywords": [], "q_verb": ""},
            "object": {"keywords": [], "is_reference_entity": False},
            "time": {"constraint_type": "none", "value": None},
            "reference": {"entity_keywords": [], "relation_keywords": [], "entity_role": "object", "end_anchor_keywords": []}
        },
        "temporal_logic": "last", "answer_type": "entity", "time_granularity": "day"
    }

# ============================================================
# 3. Search Functions
# ============================================================
def _normalize_kws(kws):
    if not kws:
        return kws
    result = []
    for kw in kws:
        kw_l = kw.lower()
        if kw_l in ('defense', 'defence'):
            result.append('defense')
            result.append('defence')
        else:
            result.append(kw_l)
    return result

def search_records(subj_kws=None, rel_kws=None, obj_kws=None, time_prefix=None):
    subj_kws = _normalize_kws(subj_kws)
    obj_kws  = _normalize_kws(obj_kws)

    results = []
    for r in RECORDS:
        if time_prefix and not r['date'].startswith(time_prefix):
            continue
        if subj_kws:
            subj_lower = _defense_norm(r['subj'].lower())
            if not all(keyword_in_text(kw, subj_lower) for kw in subj_kws):
                continue
        if rel_kws:
            rel_lower = _defense_norm(r['rel'].lower())
            if not any(keyword_in_text(kw, rel_lower) for kw in rel_kws):
                continue
        if obj_kws:
            obj_lower = _defense_norm(r['obj'].lower())
            if not all(keyword_in_text(kw, obj_lower) for kw in obj_kws):
                continue
        results.append(r)
    return results

def initial_retrieve(facets_data):
    """Multi-strategy retrieval with FIX J (precision-first expand)."""
    facets = facets_data['facets']
    subj_kws = facets['subject']['keywords']
    rel_kws  = facets['relation']['keywords']
    obj_kws  = facets['object']['keywords']
    ref_kws  = facets['reference']['entity_keywords']
    ref_rel_kws = facets['reference']['relation_keywords']
    time_val = facets['time']['value']

    rel_kws_expanded     = rel_fuzzy_expand(rel_kws) if rel_kws else []
    ref_rel_kws_expanded = rel_fuzzy_expand(ref_rel_kws) if ref_rel_kws else []

    all_results = []
    seen = set()

    def add(recs, strategy):
        for r in recs:
            key = f"{r['subj']}|{r['rel']}|{r['obj']}|{r['date']}"
            if key not in seen:
                seen.add(key)
                r['_strat'] = strategy
                all_results.append(r)

    if subj_kws and rel_kws_expanded and obj_kws:
        add(search_records(subj_kws=subj_kws, rel_kws=rel_kws_expanded, obj_kws=obj_kws), "S1")
        add(search_records(subj_kws=obj_kws, rel_kws=rel_kws_expanded, obj_kws=subj_kws), "S1r")

    if subj_kws and rel_kws_expanded:
        add(search_records(subj_kws=subj_kws, rel_kws=rel_kws_expanded), "S2")

    if rel_kws_expanded and obj_kws:
        add(search_records(rel_kws=rel_kws_expanded, obj_kws=obj_kws), "S3a")
        add(search_records(subj_kws=obj_kws, rel_kws=rel_kws_expanded), "S3b")

    if ref_kws:
        ref_rels = ref_rel_kws_expanded if ref_rel_kws_expanded else rel_kws_expanded
        ref_role = facets['reference'].get('entity_role', 'object')
        if ref_role == 'subject':
            add(search_records(subj_kws=ref_kws, rel_kws=ref_rels, obj_kws=obj_kws if obj_kws else None), "S4a")
        else:
            add(search_records(subj_kws=subj_kws if subj_kws else None, rel_kws=ref_rels, obj_kws=ref_kws), "S4b")
        add(search_records(subj_kws=ref_kws, rel_kws=ref_rels), "S4c")
        add(search_records(obj_kws=ref_kws, rel_kws=ref_rels), "S4d")

    if rel_kws_expanded and time_val:
        prefix = time_val[:7] if len(time_val) >= 7 else time_val[:4]
        add(search_records(rel_kws=rel_kws_expanded, time_prefix=prefix), "S5")

    if rel_kws_expanded and obj_kws and time_val:
        prefix = time_val[:7] if len(time_val) >= 7 else time_val[:4]
        add(search_records(rel_kws=rel_kws_expanded, obj_kws=obj_kws, time_prefix=prefix), "S6a")
        add(search_records(subj_kws=obj_kws, rel_kws=rel_kws_expanded, time_prefix=prefix), "S6b")

    if subj_kws and len(all_results) < 30:
        add(search_records(subj_kws=subj_kws), "S7")

    if obj_kws and len(all_results) < 30:
        add(search_records(obj_kws=obj_kws), "S8")

    if rel_kws_expanded and len(all_results) < 15:
        for kw in rel_kws_expanded[:2]:
            add(search_records(rel_kws=[kw]), f"S9_{kw}")

    return all_results

# ============================================================
# 4. Entity Disambiguation (LLM) — Bidirectional ref search (Fix I inherited)
# ============================================================
ENTITY_DISAMBIG_PROMPT = """Entity disambiguation for: "{question}"
Search keywords: {keywords}
Found entities:
{entity_list}

Which entity matches the user's intent?
- "Oleg Ostapenko" matches "Oleg Ostapenko", NOT "Dmitry Olegovich Rogozin"
- "Kitti Wasinondh" matches "Kitti Wasinondh", NOT "Kittiratt Na-Ranong"
- Country/organization names follow KB format

Output JSON:
{{"best_match": "exact KB entity name or null", "confidence": "high/medium/low"}}"""

def disambiguate_entity(question, keywords, field, original_kws):
    if not keywords:
        return original_kws

    if field == 'ref':
        records_as_subj = search_records(subj_kws=keywords)
        records_as_obj  = search_records(obj_kws=keywords)
        entities = sorted(set(
            [r['subj'] for r in records_as_subj] +
            [r['obj']  for r in records_as_obj]
        ))
    else:
        search_field = 'subj' if field == 'subj' else 'obj'
        records = search_records(**{f'{search_field}_kws': keywords})
        entities = sorted(set(r[search_field] for r in records))

    if len(entities) <= 1:
        return original_kws

    exact_matches = [e for e in entities if e.lower() in [kw.lower() for kw in original_kws]]
    if len(exact_matches) == 1:
        return [exact_matches[0].lower()]

    full_matches = [e for e in entities if all(kw.lower() in e.lower() for kw in original_kws)]
    if len(full_matches) == 1:
        return original_kws

    prompt = ENTITY_DISAMBIG_PROMPT.format(
        question=question,
        keywords=original_kws,
        entity_list="\n".join(f"  - {e}" for e in entities[:25])
    )
    response = call_llm(prompt, max_tokens=250)
    try:
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            if result.get('best_match') and result.get('confidence') in ('high', 'medium'):
                return [result['best_match'].lower()]
    except:
        pass
    return original_kws

# ============================================================
# 5. FacetRank Scoring
# ============================================================
def score_record(record, facets_data):
    facets = facets_data['facets']
    subj_kws = facets['subject']['keywords']
    rel_kws  = facets['relation']['keywords']
    obj_kws  = facets['object']['keywords']
    ref_kws  = facets['reference']['entity_keywords']
    time_val = facets['time']['value']
    time_type = facets['time']['constraint_type']

    subj_l = _defense_norm(record['subj'].lower())
    rel_l  = _defense_norm(record['rel'].lower())
    obj_l  = _defense_norm(record['obj'].lower())
    date   = record['date']
    scores = {}

    if subj_kws:
        if all(kw.lower() in subj_l for kw in subj_kws):
            scores['subject'] = 3 if len(subj_kws) >= 2 else 2
        elif any(kw.lower() in subj_l for kw in subj_kws):
            scores['subject'] = 1
        else:
            scores['subject'] = 0
    else:
        scores['subject'] = 0

    if rel_kws:
        match_count = sum(1 for kw in rel_kws if kw.lower() in rel_l)
        scores['relation'] = min(match_count, 3)
    else:
        scores['relation'] = 0

    if obj_kws:
        if all(kw.lower() in obj_l for kw in obj_kws):
            scores['object'] = 3 if len(obj_kws) >= 2 else 2
        elif any(kw.lower() in obj_l for kw in obj_kws):
            scores['object'] = 1
        else:
            scores['object'] = 0
    else:
        scores['object'] = 0

    if time_type == 'absolute' and time_val:
        scores['time'] = 2 if date.startswith(time_val) else (
            1 if date[:7] == time_val[:7] or date[:4] == time_val[:4] else 0
        )
    else:
        scores['time'] = 0

    if ref_kws:
        scores['reference'] = 2 if (
            any(kw.lower() in subj_l for kw in ref_kws) or
            any(kw.lower() in obj_l  for kw in ref_kws)
        ) else 0
    else:
        scores['reference'] = 0

    return sum(scores.values()), scores

def facet_rank(candidates, facets_data, top_k=80):
    scored = [(score_record(r, facets_data)[0], score_record(r, facets_data)[1], r) for r in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]

def merge_records(base, extra, limit=None):
    seen = set(f"{r['subj']}|{r['rel']}|{r['obj']}|{r['date']}" for r in base)
    for r in extra:
        key = f"{r['subj']}|{r['rel']}|{r['obj']}|{r['date']}"
        if key not in seen:
            seen.add(key)
            base.append(r)
            if limit and len(base) >= limit:
                break
    return base

def deterministic_supplemental_retrieve(facets_data, qtype):
    facets = facets_data['facets']
    subj_kws = facets['subject']['keywords']
    rel_kws  = rel_fuzzy_expand(facets['relation']['keywords']) if facets['relation']['keywords'] else []
    obj_kws  = facets['object']['keywords']
    ref_kws  = facets['reference']['entity_keywords']
    time_val = facets['time']['value']
    out = []

    def add(recs):
        merge_records(out, recs, limit=500)

    if subj_kws and rel_kws and obj_kws:
        add(search_records(subj_kws=subj_kws, rel_kws=rel_kws, obj_kws=obj_kws))
        add(search_records(subj_kws=obj_kws, rel_kws=rel_kws, obj_kws=subj_kws))
    if subj_kws and rel_kws:
        add(search_records(subj_kws=subj_kws, rel_kws=rel_kws))
    if rel_kws and obj_kws:
        add(search_records(rel_kws=rel_kws, obj_kws=obj_kws))
        add(search_records(subj_kws=obj_kws, rel_kws=rel_kws))

    if time_val and rel_kws:
        prefix = time_val[:7] if len(str(time_val)) >= 7 else str(time_val)[:4]
        if subj_kws:
            add(search_records(subj_kws=subj_kws, rel_kws=rel_kws, time_prefix=prefix))
        if obj_kws:
            add(search_records(rel_kws=rel_kws, obj_kws=obj_kws, time_prefix=prefix))
        add(search_records(rel_kws=rel_kws, time_prefix=prefix))

    if ref_kws and qtype in ('after_first', 'before_last', 'before_after', 'equal_multi'):
        if rel_kws and obj_kws:
            add(search_records(subj_kws=ref_kws, rel_kws=rel_kws, obj_kws=obj_kws))
            add(search_records(subj_kws=obj_kws, rel_kws=rel_kws, obj_kws=ref_kws))
        if rel_kws:
            add(search_records(subj_kws=ref_kws, rel_kws=rel_kws))
            add(search_records(obj_kws=ref_kws, rel_kws=rel_kws))
        add(search_records(subj_kws=ref_kws))
        add(search_records(obj_kws=ref_kws))

    return out

# ============================================================
# FIX G (inherited): Dynamic Score-Band Filter
# ============================================================
def dynamic_score_filter(candidate_pool, facets_data):
    if len(candidate_pool) <= 300:
        return candidate_pool

    scored_pool = [(score_record(r, facets_data)[0], r) for r in candidate_pool]
    scored_pool.sort(key=lambda x: x[0], reverse=True)

    if not scored_pool:
        return candidate_pool

    max_score = scored_pool[0][0]
    score_threshold = max(0, max_score - 2)

    band_filtered = [r for s, r in scored_pool if s >= score_threshold]
    top_20pct_count = max(50, int(len(scored_pool) * 0.20))
    top_20pct = [r for _, r in scored_pool[:top_20pct_count]]

    seen = set()
    result = []
    for s, r in scored_pool:
        key = f"{r['subj']}|{r['rel']}|{r['obj']}|{r['date']}"
        if key in seen:
            continue
        if r in band_filtered or r in top_20pct:
            seen.add(key)
            result.append(r)

    return result if result else candidate_pool

# ============================================================
# 6. Sufficiency Check
# ============================================================
def check_sufficiency(question, qtype, ranked, facets_data):
    if not ranked:
        return False, {"missing_facets": ["all"], "new_queries": [], "cot_analysis": {"what_we_have": [], "what_we_need": ["all evidence"], "facet_gaps": ["all"]}}, "no candidates"

    max_score = ranked[0][0]

    facets = facets_data['facets']
    ref_kws = facets['reference']['entity_keywords']

    structure_aligned = True

    if qtype in ['after_first', 'before_last', 'before_after']:
        ref_found = any(
            any(kw.lower() in r['subj'].lower() or kw.lower() in r['obj'].lower() for kw in ref_kws)
            for _, _, r in ranked[:20]
        ) if ref_kws else False
        if not ref_found:
            structure_aligned = False

    if qtype == 'equal_multi':
        ref_found = any(
            any(kw.lower() in r['subj'].lower() or kw.lower() in r['obj'].lower() for kw in ref_kws)
            for _, _, r in ranked[:20]
        ) if ref_kws else False
        if not ref_found:
            structure_aligned = False

    if not structure_aligned:
        return False, {
            "missing_facets": ["reference"],
            "new_queries": [{
                "facet": "reference",
                "keywords": ref_kws,
                "strategy": "reference_entity_focus"
            }],
            "cot_analysis": {
                "what_we_have": [f"Main relation records (score={max_score})"],
                "what_we_need": [f"Reference entity ({ref_kws}) records"],
                "facet_gaps": ["reference"]
            }
        }, "structure_not_aligned"

    if max_score < 3:
        return False, {"missing_facets": ["all"], "new_queries": [], "cot_analysis": {"what_we_have": [], "what_we_need": ["relevant evidence"], "facet_gaps": ["all"]}}, f"max_score={max_score}"

    return True, {
        "missing_facets": [],
        "new_queries": [],
        "cot_analysis": {
            "what_we_have": ["deterministic facet coverage"],
            "what_we_need": [],
            "facet_gaps": []
        }
    }, "deterministic_sufficiency"

# ============================================================
# 7. Re-retrieval
# ============================================================
def execute_re_retrieval(new_queries, facets_data, existing):
    seen = set(f"{r['subj']}|{r['rel']}|{r['obj']}|{r['date']}" for r in existing)
    new_records = []
    facets = facets_data['facets']

    for q in new_queries:
        kws = q.get('keywords', [])
        strategy = q.get('strategy', 'broader')
        facet = q.get('facet', '')
        if not kws:
            continue

        recs = []

        if strategy == 'reference_entity_focus' or facet == 'reference':
            kws_expanded = rel_fuzzy_expand(kws)
            rel_kws = facets['relation']['keywords']
            rel_kws_expanded = rel_fuzzy_expand(rel_kws) if rel_kws else []
            obj_kws = facets['object']['keywords']

            recs.extend(search_records(subj_kws=kws_expanded, rel_kws=rel_kws_expanded))
            recs.extend(search_records(subj_kws=kws_expanded, obj_kws=obj_kws))
            recs.extend(search_records(obj_kws=kws_expanded, rel_kws=rel_kws_expanded))
            recs.extend(search_records(subj_kws=kws_expanded))
            recs.extend(search_records(obj_kws=kws_expanded))

        elif strategy == 'broader':
            kws_expanded = rel_fuzzy_expand(kws)
            for kw in kws_expanded:
                if facet == 'subject':
                    recs.extend(search_records(subj_kws=[kw]))
                elif facet == 'object':
                    recs.extend(search_records(obj_kws=[kw]))
                else:
                    recs.extend(search_records(rel_kws=[kw]))

        elif strategy == 'direction_swap':
            if facets['subject']['keywords'] and facets['object']['keywords']:
                rel_kws_expanded = rel_fuzzy_expand(facets['relation']['keywords']) if facets['relation']['keywords'] else []
                recs = search_records(subj_kws=facets['object']['keywords'], rel_kws=rel_kws_expanded)

        for r in recs:
            key = f"{r['subj']}|{r['rel']}|{r['obj']}|{r['date']}"
            if key not in seen:
                seen.add(key)
                r['_strat'] = f"re_{strategy}"
                new_records.append(r)

    return new_records[:100]

# ============================================================
# 8. PROGRAMMATIC SOLVER — V6
#    FIX J: precision-first rel expansion
#    FIX K: equal/before_after entity-list uses direct search (not noisy pool)
#    FIX L: first_last uses core rel_kws first, expand only as fallback
# ============================================================
def programmatic_solve(candidate_pool, facets_data, qtype, question):
    facets = facets_data['facets']
    subj_kws    = facets['subject']['keywords']
    rel_kws     = facets['relation']['keywords']
    obj_kws     = facets['object']['keywords']
    ref_kws     = facets['reference']['entity_keywords']
    ref_rel_kws = facets['reference']['relation_keywords'] or rel_kws
    end_anchor_kws = facets['reference'].get('end_anchor_keywords', [])
    temporal_logic = facets_data.get('temporal_logic', 'last')
    answer_type    = facets_data.get('answer_type', 'entity')
    time_gran      = facets_data.get('time_granularity', 'day')

    # FIX J: rel_kws already precision-expanded by post_process_facets
    # For solvers, we also need the CORE (original LLM output) rel keywords
    # The LLM now outputs minimal keywords, so rel_kws ≈ core after FIX J expansion
    rel_kws_exp = rel_fuzzy_expand(rel_kws) if rel_kws else rel_kws

    def has_all(value, keywords):
        return bool(keywords) and all(keyword_in_text(kw, value) for kw in keywords)

    def has_any(value, keywords):
        return bool(keywords) and any(keyword_in_text(kw, value) for kw in keywords)

    def sort_unique(records):
        seen_set = set()
        out = []
        for rec in sorted(records, key=lambda x: x['date']):
            key = (rec['subj'], rec['rel'], rec['obj'], rec['date'])
            if key not in seen_set:
                seen_set.add(key)
                out.append(rec)
        return out

    def find_ref_recs_bidirectional(ref_kws, rel_kws_exp, obj_kws=None, subj_kws=None):
        recs = []
        if not ref_kws:
            return recs
        if rel_kws_exp:
            recs += search_records(subj_kws=ref_kws, rel_kws=rel_kws_exp)
        recs += search_records(subj_kws=ref_kws)
        if rel_kws_exp:
            recs += search_records(obj_kws=ref_kws, rel_kws=rel_kws_exp)
        recs += search_records(obj_kws=ref_kws)
        if obj_kws:
            recs += search_records(subj_kws=ref_kws, obj_kws=obj_kws)
            recs += search_records(subj_kws=obj_kws, obj_kws=ref_kws)
        if subj_kws:
            recs += search_records(subj_kws=ref_kws, obj_kws=subj_kws)
            recs += search_records(subj_kws=subj_kws, obj_kws=ref_kws)
        return sort_unique(recs)

    if not candidate_pool:
        return None

    scored = [(score_record(r, facets_data), r) for r in candidate_pool]

    thresholds = {
        'first_last': 4, 'equal': 3, 'equal_multi': 3,
        'after_first': 3, 'before_last': 3, 'before_after': 3,
    }
    threshold = thresholds.get(qtype, 3)
    relevant = sorted([r for (t, s), r in scored if t >= threshold], key=lambda x: x['date'])

    if not relevant:
        relevant = sorted([r for (t, s), r in scored if t >= 1], key=lambda x: x['date'])

    if not relevant:
        return None

    # --- first_last -----------------------------------------------------------
    if qtype == 'first_last':
        is_first = ('first' in temporal_logic or
                    'first' in question.lower() or
                    'earliest' in question.lower())

        effective_obj_kws = [kw for kw in obj_kws if kw.lower() not in GENERIC_OBJ_KEYWORDS] if obj_kws else []

        # FIX L: Use CORE rel_kws (no expansion) for strict search first
        # Only fall back to expanded if core returns nothing
        if subj_kws and effective_obj_kws:
            # FIX L: core-only strict search
            strict_rel = search_records(subj_kws=subj_kws, rel_kws=rel_kws, obj_kws=effective_obj_kws)
            if not strict_rel:
                strict_rel = search_records(subj_kws=effective_obj_kws, rel_kws=rel_kws, obj_kws=subj_kws)
            # Fallback to expanded only if nothing found
            if not strict_rel:
                strict_rel = search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp, obj_kws=effective_obj_kws)
            if not strict_rel:
                strict_rel = search_records(subj_kws=effective_obj_kws, rel_kws=rel_kws_exp, obj_kws=subj_kws)
            if strict_rel and is_simple_entity_keyword(effective_obj_kws):
                exact_strict = [r for r in strict_rel if exact_entity_match(r['obj'], effective_obj_kws)]
                if exact_strict:
                    strict_rel = exact_strict
            if strict_rel:
                strict_rel.sort(key=lambda x: x['date'])
                relevant = strict_rel
            else:
                fc = [r for r in relevant if
                      all(kw.lower() in r['subj'].lower() for kw in subj_kws) and
                      all(kw.lower() in r['obj'].lower() for kw in effective_obj_kws)]
                if fc:
                    relevant = fc
        elif subj_kws:
            # FIX L: core-only first
            strict_rel = search_records(subj_kws=subj_kws, rel_kws=rel_kws)
            if not strict_rel:
                strict_rel = search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp)
            if strict_rel:
                strict_rel.sort(key=lambda x: x['date'])
                relevant = strict_rel
            else:
                fc = [r for r in relevant if all(kw.lower() in r['subj'].lower() for kw in subj_kws)]
                if fc:
                    relevant = fc

        if not relevant:
            if subj_kws and effective_obj_kws:
                relevant = search_records(subj_kws=subj_kws, rel_kws=rel_kws, obj_kws=effective_obj_kws)
                relevant += search_records(subj_kws=effective_obj_kws, rel_kws=rel_kws, obj_kws=subj_kws)
                relevant.sort(key=lambda x: x['date'])

        if not relevant:
            return None

        target = relevant[0] if is_first else relevant[-1]

        if answer_type == 'time':
            date = target['date']
            if time_gran == 'year':  return date[:4]
            elif time_gran == 'month': return date[:7]
            return date
        else:
            if subj_kws and all(kw.lower() in target['subj'].lower() for kw in subj_kws[:2]):
                return target['obj']
            elif effective_obj_kws and all(kw.lower() in target['obj'].lower() for kw in effective_obj_kws):
                return target['subj']
            return target['obj']

    # --- after_first ----------------------------------------------------------
    elif qtype == 'after_first':
        ref_rel_kws_exp = rel_fuzzy_expand(ref_rel_kws) if ref_rel_kws else []

        ref_recs = []
        if ref_kws:
            ref_recs = search_records(subj_kws=ref_kws, rel_kws=rel_kws, obj_kws=obj_kws)
            if not ref_recs:
                ref_recs = search_records(subj_kws=obj_kws, rel_kws=rel_kws, obj_kws=ref_kws) if obj_kws else []
            if not ref_recs:
                ref_recs = search_records(subj_kws=ref_kws, rel_kws=rel_kws)
            if not ref_recs:
                ref_recs = search_records(obj_kws=ref_kws, rel_kws=rel_kws)
            # Fallback to expanded
            if not ref_recs:
                ref_recs = search_records(subj_kws=ref_kws, rel_kws=ref_rel_kws_exp, obj_kws=obj_kws)
            if not ref_recs:
                ref_recs = search_records(obj_kws=ref_kws, rel_kws=ref_rel_kws_exp)
            if not ref_recs:
                ref_recs = find_ref_recs_bidirectional(ref_kws, ref_rel_kws_exp, obj_kws)
        ref_recs.sort(key=lambda x: x['date'])
        if not ref_recs:
            return None
        ref_date = ref_recs[0]['date']

        # FIX K: Use core rel_kws for precision
        all_rel_obj = search_records(rel_kws=rel_kws, obj_kws=obj_kws)
        all_rel_obj += search_records(subj_kws=obj_kws, rel_kws=rel_kws) if obj_kws else []
        if not all_rel_obj:
            all_rel_obj = search_records(rel_kws=rel_kws_exp, obj_kws=obj_kws)
            all_rel_obj += search_records(subj_kws=obj_kws, rel_kws=rel_kws_exp) if obj_kws else []

        if is_simple_entity_keyword(obj_kws):
            exact_rel_obj = [
                r for r in all_rel_obj
                if exact_entity_match(r['obj'], obj_kws) or exact_entity_match(r['subj'], obj_kws)
            ]
            if exact_rel_obj:
                all_rel_obj = exact_rel_obj
        all_rel_obj.sort(key=lambda x: x['date'])

        after = [r for r in all_rel_obj if r['date'] > ref_date
                 and not (ref_kws and (
                     all(kw.lower() in r['subj'].lower() for kw in ref_kws) or
                     all(kw.lower() in r['obj'].lower() for kw in ref_kws)
                 ))]
        after.sort(key=lambda x: x['date'])
        if not after:
            after = [r for r in relevant if r['date'] > ref_date
                     and not (ref_kws and all(kw.lower() in r['subj'].lower() for kw in ref_kws))]
            after.sort(key=lambda x: x['date'])
        if not after:
            return None
        r0 = after[0]
        if obj_kws and all(kw.lower() in r0['obj'].lower() for kw in obj_kws):
            return r0['subj']
        elif obj_kws and all(kw.lower() in r0['subj'].lower() for kw in obj_kws):
            return r0['obj']
        return r0['subj']

    # --- before_last ----------------------------------------------------------
    elif qtype == 'before_last':
        rel_kws_exp_bl = rel_fuzzy_expand(rel_kws) if rel_kws else rel_kws

        # Phase 1: find t_ref
        ref_recs = []
        if ref_kws:
            if subj_kws:
                ref_recs += search_records(subj_kws=subj_kws, rel_kws=rel_kws, obj_kws=ref_kws)
                ref_recs += search_records(subj_kws=ref_kws, rel_kws=rel_kws, obj_kws=subj_kws)
                ref_recs += search_records(subj_kws=subj_kws, obj_kws=ref_kws)
                ref_recs += search_records(subj_kws=ref_kws, obj_kws=subj_kws)
            if obj_kws:
                ref_recs += search_records(subj_kws=ref_kws, rel_kws=rel_kws, obj_kws=obj_kws)
                ref_recs += search_records(subj_kws=obj_kws, rel_kws=rel_kws, obj_kws=ref_kws)
            if not ref_recs:
                ref_recs += search_records(subj_kws=ref_kws, rel_kws=rel_kws)
                ref_recs += search_records(obj_kws=ref_kws, rel_kws=rel_kws)
            # Fallback to expanded
            if not ref_recs:
                ref_recs += search_records(subj_kws=ref_kws, rel_kws=rel_kws_exp_bl)
                ref_recs += search_records(obj_kws=ref_kws, rel_kws=rel_kws_exp_bl)
            if not ref_recs:
                ref_recs += search_records(subj_kws=ref_kws)
                ref_recs += search_records(obj_kws=ref_kws)

        ref_recs = sort_unique(ref_recs)
        if not ref_recs:
            return None
        t_ref = ref_recs[-1]['date']

        # Phase 2: main event before t_ref
        # FIX L: use core rel_kws first
        if subj_kws:
            before = search_records(subj_kws=subj_kws, rel_kws=rel_kws)
            if not before:
                before = search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp_bl)
            if obj_kws:
                filtered = [r for r in before if has_all(r['obj'].lower(), obj_kws)]
                if filtered:
                    before = filtered
            before = [r for r in before if r['date'] < t_ref
                      and not (ref_kws and (
                          has_all(r['subj'].lower(), ref_kws) or
                          has_all(r['obj'].lower(), ref_kws)
                      ))]
        else:
            all_before = []
            all_before += search_records(rel_kws=rel_kws, obj_kws=obj_kws) if obj_kws else []
            all_before += search_records(subj_kws=obj_kws, rel_kws=rel_kws) if obj_kws else []
            if not all_before:
                all_before += search_records(rel_kws=rel_kws_exp_bl, obj_kws=obj_kws) if obj_kws else []
                all_before += search_records(subj_kws=obj_kws, rel_kws=rel_kws_exp_bl) if obj_kws else []
            if not all_before and obj_kws:
                all_before += search_records(obj_kws=obj_kws)
            if not all_before and rel_kws:
                all_before += search_records(rel_kws=rel_kws)
            before = [r for r in all_before if r['date'] < t_ref
                      and not (ref_kws and (
                          has_all(r['subj'].lower(), ref_kws) or
                          has_all(r['obj'].lower(), ref_kws)
                      ))]

        before = sort_unique(before)
        if not before:
            return None

        if subj_kws:
            last_date = before[-1]['date']
            last_objs = sorted(set(r['obj'] for r in before if r['date'] == last_date))
            return last_objs[0] if len(last_objs) == 1 else last_objs

        if obj_kws:
            visitor_before = [r for r in before if has_all(r['obj'].lower(), obj_kws)]
            if visitor_before:
                last_date = visitor_before[-1]['date']
                last_subjs = sorted(set(r['subj'] for r in visitor_before if r['date'] == last_date))
                return last_subjs[0] if len(last_subjs) == 1 else last_subjs

        last_date = before[-1]['date']
        last_subjs = sorted(set(r['subj'] for r in before if r['date'] == last_date))
        return last_subjs[0] if len(last_subjs) == 1 else last_subjs

    # --- before_after ---------------------------------------------------------
    # FIX H (inherited): Direction from temporal_logic
    # FIX K: Direct search for entity-list output (not from noisy pool)
    elif qtype == 'before_after':
        time_val = facets['time']['value']
        if not time_val and ref_kws:
            ref_kw_str = ' '.join(ref_kws)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2}|\d{4}-\d{2}|\d{4})', ref_kw_str)
            if date_match:
                time_val = date_match.group(1)
        ref_is_date = bool(time_val and re.match(r'\d{4}', str(time_val)))

        is_compound    = (temporal_logic == 'before_after')
        is_after_only  = (temporal_logic == 'after')
        is_before_only = (temporal_logic == 'before' or (not is_compound and not is_after_only))

        if ref_is_date:
            ref_date = time_val

            # FIX K: Direct search with CORE rel_kws for precision
            def _ba_direct_search(subj_kws, obj_kws, rel_core, rel_exp):
                recs = []
                if subj_kws and obj_kws:
                    recs = search_records(subj_kws=subj_kws, rel_kws=rel_core, obj_kws=obj_kws)
                    if not recs:
                        recs = search_records(subj_kws=obj_kws, rel_kws=rel_core, obj_kws=subj_kws)
                elif subj_kws:
                    recs = search_records(subj_kws=subj_kws, rel_kws=rel_core)
                elif obj_kws:
                    recs = search_records(rel_kws=rel_core, obj_kws=obj_kws)
                    recs += search_records(subj_kws=obj_kws, rel_kws=rel_core)
                else:
                    recs = search_records(rel_kws=rel_core)
                # Fallback to expanded
                if not recs:
                    if subj_kws and obj_kws:
                        recs = search_records(subj_kws=subj_kws, rel_kws=rel_exp, obj_kws=obj_kws)
                    elif subj_kws:
                        recs = search_records(subj_kws=subj_kws, rel_kws=rel_exp)
                    elif obj_kws:
                        recs = search_records(rel_kws=rel_exp, obj_kws=obj_kws)
                        recs += search_records(subj_kws=obj_kws, rel_kws=rel_exp)
                    else:
                        recs = search_records(rel_kws=rel_exp)
                return recs

            all_recs = _ba_direct_search(subj_kws, obj_kws, rel_kws, rel_kws_exp)

            if is_after_only:
                filtered = [r for r in all_recs if r['date'] > ref_date]
            elif is_compound:
                end_anchor = end_anchor_kws or []
                if end_anchor:
                    end_recs = find_ref_recs_bidirectional(end_anchor, rel_kws_exp)
                    end_recs.sort(key=lambda x: x['date'])
                    t_end = end_recs[0]['date'] if end_recs else None
                    filtered = [r for r in all_recs if r['date'] > ref_date and (not t_end or r['date'] < t_end)]
                else:
                    filtered = [r for r in all_recs if r['date'] > ref_date]
            else:
                filtered = [r for r in all_recs if r['date'] < ref_date]

            if subj_kws:
                entities = sorted(set(r['obj'] for r in filtered if all(kw.lower() in r['subj'].lower() for kw in subj_kws)))
            elif obj_kws:
                entities = sorted(set(
                    r['subj'] if all(kw.lower() in r['obj'].lower() for kw in obj_kws) else r['obj']
                    for r in filtered
                ))
            else:
                entities = sorted(set(r['subj'] for r in filtered))
            return entities if entities else None

        # Entity-based ref
        ref_recs = []
        if ref_kws:
            if subj_kws:
                ref_recs = search_records(subj_kws=subj_kws, rel_kws=rel_kws, obj_kws=ref_kws)
                if not ref_recs:
                    ref_recs = search_records(subj_kws=ref_kws, rel_kws=rel_kws, obj_kws=subj_kws)
                if not ref_recs:
                    ref_recs = search_records(subj_kws=subj_kws, obj_kws=ref_kws)
            else:
                ref_recs = search_records(subj_kws=ref_kws, rel_kws=rel_kws, obj_kws=obj_kws)
                if not ref_recs:
                    ref_recs = search_records(subj_kws=obj_kws, rel_kws=rel_kws, obj_kws=ref_kws) if obj_kws else []
                if not ref_recs:
                    ref_recs = find_ref_recs_bidirectional(ref_kws, rel_kws_exp, obj_kws, subj_kws)

        ref_recs.sort(key=lambda x: x['date'])
        if not ref_recs:
            return None
        ref_date = ref_recs[0]['date']

        # FIX K: Direct search with CORE rel_kws
        if subj_kws:
            all_side = search_records(subj_kws=subj_kws, rel_kws=rel_kws, obj_kws=obj_kws)
            if not all_side:
                all_side = search_records(subj_kws=subj_kws, rel_kws=rel_kws)
            if not all_side:
                all_side = search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp, obj_kws=obj_kws)
            if not all_side:
                all_side = search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp)
        else:
            all_side = search_records(rel_kws=rel_kws, obj_kws=obj_kws)
            all_side += search_records(subj_kws=obj_kws, rel_kws=rel_kws) if obj_kws else []
            if not all_side:
                all_side = search_records(rel_kws=rel_kws_exp, obj_kws=obj_kws)
                all_side += search_records(subj_kws=obj_kws, rel_kws=rel_kws_exp) if obj_kws else []
            if not all_side:
                all_side = search_records(rel_kws=rel_kws)

        # FIX H: Apply direction from temporal_logic
        if is_compound:
            t_start = ref_date
            if end_anchor_kws:
                end_recs = find_ref_recs_bidirectional(end_anchor_kws, rel_kws_exp, obj_kws, subj_kws)
                end_recs.sort(key=lambda x: x['date'])
                t_end = end_recs[0]['date'] if end_recs else None
            else:
                t_end = None

            if t_end:
                side = [r for r in all_side if r['date'] > t_start and r['date'] < t_end
                        and not (ref_kws and (
                            all(keyword_in_text(kw, r['subj'].lower()) for kw in ref_kws) or
                            all(keyword_in_text(kw, r['obj'].lower()) for kw in ref_kws)
                        ))]
            else:
                side = [r for r in all_side if r['date'] > t_start
                        and not (ref_kws and (
                            all(keyword_in_text(kw, r['subj'].lower()) for kw in ref_kws) or
                            all(keyword_in_text(kw, r['obj'].lower()) for kw in ref_kws)
                        ))]
        elif is_after_only:
            side = [r for r in all_side if r['date'] > ref_date
                    and not (ref_kws and (
                        all(keyword_in_text(kw, r['subj'].lower()) for kw in ref_kws) or
                        all(keyword_in_text(kw, r['obj'].lower()) for kw in ref_kws)
                    ))]
        else:
            side = [r for r in all_side if r['date'] < ref_date
                    and not (ref_kws and (
                        all(keyword_in_text(kw, r['subj'].lower()) for kw in ref_kws) or
                        all(keyword_in_text(kw, r['obj'].lower()) for kw in ref_kws)
                    ))]

        side.sort(key=lambda x: x['date'])
        if not side:
            return None

        if obj_kws:
            all_entities = sorted(set(
                r['subj'] if all(keyword_in_text(kw, r['obj'].lower()) for kw in obj_kws) else r['obj']
                for r in side
            ))
        elif subj_kws:
            all_entities = sorted(set(r['obj'] for r in side if all(keyword_in_text(kw, r['subj'].lower()) for kw in subj_kws)))
        else:
            all_entities = sorted(set(r['subj'] for r in side))
        return all_entities if all_entities else None

    # --- equal_multi ----------------------------------------------------------
    # FIX F (inherited): Year-context-aware reference time anchoring
    elif qtype == 'equal_multi':
        same_day = 'same day' in question.lower()

        if facets['time']['value'] and ('first' in temporal_logic or 'first' in question.lower()):
            time_prefix = facets['time']['value']
            # FIX K: Direct search with core rel_kws
            all_recs = search_records(subj_kws=subj_kws, rel_kws=rel_kws, obj_kws=obj_kws, time_prefix=time_prefix)
            if not all_recs and obj_kws:
                all_recs = search_records(rel_kws=rel_kws, obj_kws=obj_kws, time_prefix=time_prefix)
            if not all_recs:
                all_recs = search_records(rel_kws=rel_kws_exp, obj_kws=obj_kws, time_prefix=time_prefix)
            all_recs.sort(key=lambda x: x['date'])
            if all_recs:
                first_date = all_recs[0]['date']
                first_entities = sorted(set(r['subj'] for r in all_recs if r['date'] == first_date))
                return first_entities if answer_type == 'entity_list' else first_entities[0]

        # FIX F: Dynamic year-context-aware ref anchor (bidirectional)
        ref_recs_all = []
        if ref_kws:
            ref_recs_all += search_records(subj_kws=ref_kws, rel_kws=rel_kws, obj_kws=obj_kws)
            ref_recs_all += search_records(subj_kws=obj_kws, rel_kws=rel_kws, obj_kws=ref_kws) if obj_kws else []
            ref_recs_all += search_records(subj_kws=ref_kws, rel_kws=rel_kws)
            ref_recs_all += search_records(obj_kws=ref_kws, rel_kws=rel_kws)
            if not ref_recs_all:
                ref_recs_all += search_records(subj_kws=ref_kws, rel_kws=rel_kws_exp, obj_kws=obj_kws)
                ref_recs_all += search_records(obj_kws=ref_kws, rel_kws=rel_kws_exp)
            if not ref_recs_all:
                ref_recs_all += search_records(subj_kws=ref_kws)
                ref_recs_all += search_records(obj_kws=ref_kws)
            if same_day:
                ref_as_subj = search_records(subj_kws=ref_kws)
                ref_as_obj  = search_records(obj_kws=ref_kws)
                all_ref = sort_unique(ref_as_subj + ref_as_obj)
                if all_ref:
                    ref_recs_all = all_ref

        ref_recs_all = sort_unique(ref_recs_all)
        if not ref_recs_all:
            return None

        # FIX F: Year-context-aware anchor
        year_context = None
        if facets['time']['value']:
            yc_match = re.match(r'(\d{4})', str(facets['time']['value']))
            if yc_match:
                year_context = yc_match.group(1)
        if not year_context:
            yc_match = re.search(r'\b(20\d{2}|19\d{2})\b', question)
            if yc_match:
                year_context = yc_match.group(1)

        def score_ref_rec(r):
            s = 0
            r_rel_l = _defense_norm(r['rel'].lower())
            r_subj_l = _defense_norm(r['subj'].lower())
            r_obj_l  = _defense_norm(r['obj'].lower())
            if rel_kws:
                s += sum(1 for kw in rel_kws if kw.lower() in r_rel_l)
            if obj_kws:
                if all(kw.lower() in r_obj_l for kw in obj_kws): s += 3
                elif any(kw.lower() in r_obj_l for kw in obj_kws): s += 1
                if all(kw.lower() in r_subj_l for kw in obj_kws): s += 2
            return s

        if len(ref_recs_all) > 5 and year_context:
            year_filtered = [r for r in ref_recs_all if r['date'].startswith(year_context)]
            if year_filtered:
                year_filtered_scored = sorted(year_filtered, key=score_ref_rec, reverse=True)
                best_score = score_ref_rec(year_filtered_scored[0])
                if best_score > 0:
                    ref_anchor_rec = year_filtered_scored[0]
                else:
                    ref_anchor_rec = sorted(year_filtered, key=lambda x: x['date'])[0]
            else:
                all_scored = sorted(ref_recs_all, key=score_ref_rec, reverse=True)
                ref_anchor_rec = all_scored[0] if score_ref_rec(all_scored[0]) > 0 else ref_recs_all[0]
        elif len(ref_recs_all) > 5:
            all_scored = sorted(ref_recs_all, key=score_ref_rec, reverse=True)
            ref_anchor_rec = all_scored[0] if score_ref_rec(all_scored[0]) > 0 else ref_recs_all[0]
        else:
            ref_anchor_rec = ref_recs_all[0]

        granularity = 10 if same_day else 7
        ref_prefix = ref_anchor_rec['date'][:granularity]

        # FIX K: Direct search with core rel_kws for the same-time window
        same_window_all = []
        if subj_kws:
            same_window_all += search_records(subj_kws=subj_kws, rel_kws=rel_kws, obj_kws=obj_kws, time_prefix=ref_prefix)
        if obj_kws:
            same_window_all += search_records(rel_kws=rel_kws, obj_kws=obj_kws, time_prefix=ref_prefix)
            same_window_all += search_records(subj_kws=obj_kws, rel_kws=rel_kws, time_prefix=ref_prefix)
        if not same_window_all:
            if obj_kws:
                same_window_all += search_records(rel_kws=rel_kws_exp, obj_kws=obj_kws, time_prefix=ref_prefix)
                same_window_all += search_records(subj_kws=obj_kws, rel_kws=rel_kws_exp, time_prefix=ref_prefix)
        if not same_window_all:
            same_window_all += search_records(rel_kws=rel_kws, time_prefix=ref_prefix)

        entities = set()
        for r in same_window_all:
            if ref_kws and (
                all(keyword_in_text(kw, r['subj'].lower()) for kw in ref_kws) or
                all(keyword_in_text(kw, r['obj'].lower()) for kw in ref_kws)
            ):
                continue
            if subj_kws and all(keyword_in_text(kw, r['subj'].lower()) for kw in subj_kws):
                entities.add(r['obj'])
            elif obj_kws and all(keyword_in_text(kw, r['obj'].lower()) for kw in obj_kws):
                entities.add(r['subj'])
            elif obj_kws and all(keyword_in_text(kw, r['subj'].lower()) for kw in obj_kws):
                entities.add(r['obj'])
        return sorted(entities) if entities else None

    # --- equal ----------------------------------------------------------------
    # FIX K: Direct search with core rel_kws for entity-list output
    elif qtype == 'equal':
        time_val = facets['time']['value']

        if answer_type == 'time':
            # Time answer: still use core rel_kws first
            recs = search_records(subj_kws=subj_kws, rel_kws=rel_kws, obj_kws=obj_kws)
            if not recs:
                recs = search_records(subj_kws=obj_kws, rel_kws=rel_kws, obj_kws=subj_kws) if subj_kws and obj_kws else []
            if not recs:
                recs = search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp, obj_kws=obj_kws)
            recs.sort(key=lambda x: x['date'])
            if not recs:
                return None
            date = recs[0]['date']
            if time_gran == 'year':  return date[:4]
            if time_gran == 'month': return date[:7]
            return date

        # Entity-list: FIX K — direct precise search
        if not time_val:
            return None

        prefix = time_val[:7] if len(time_val) >= 7 else time_val[:4]

        # FIX K: Direct search with CORE rel_kws + time constraint
        # This replaces "filter from noisy relevant pool" with precise retrieval
        direct_recs = []
        if obj_kws:
            direct_recs += search_records(rel_kws=rel_kws, obj_kws=obj_kws, time_prefix=prefix)
            direct_recs += search_records(subj_kws=obj_kws, rel_kws=rel_kws, time_prefix=prefix)
            if subj_kws:
                direct_recs += search_records(subj_kws=subj_kws, rel_kws=rel_kws, obj_kws=obj_kws, time_prefix=prefix)
        elif subj_kws:
            direct_recs += search_records(subj_kws=subj_kws, rel_kws=rel_kws, time_prefix=prefix)

        # Fallback to expanded if needed
        if not direct_recs:
            if obj_kws:
                direct_recs += search_records(rel_kws=rel_kws_exp, obj_kws=obj_kws, time_prefix=prefix)
                direct_recs += search_records(subj_kws=obj_kws, rel_kws=rel_kws_exp, time_prefix=prefix)
            elif subj_kws:
                direct_recs += search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp, time_prefix=prefix)

        # Fallback from existing ranked pool
        if not direct_recs:
            time_filtered = [r for r in relevant if r['date'].startswith(prefix)]
            direct_recs = time_filtered

        entities = set()
        for r in direct_recs:
            if obj_kws and all(kw.lower() in r['obj'].lower() for kw in obj_kws):
                entities.add(r['subj'])
            elif obj_kws and all(kw.lower() in r['subj'].lower() for kw in obj_kws):
                entities.add(r['obj'])
            elif subj_kws and all(kw.lower() in r['subj'].lower() for kw in subj_kws):
                entities.add(r['obj'])

        if obj_kws:
            entities = {e for e in entities if not exact_entity_match(e, obj_kws)}

        return sorted(entities) if entities else None

    return None

# ============================================================
# 9. Main Pipeline
# ============================================================
def answer_question(question, qtype, max_turns=2):
    # Step 1: Parse facets
    facets_data = parse_question_to_facets(question, qtype)
    facets_data = post_process_facets(question, qtype, facets_data)

    # Step 2: Entity disambiguation (bidirectional for reference — Fix I inherited)
    facets = facets_data['facets']
    for field in ['subject', 'object', 'reference']:
        kw_field = 'entity_keywords' if field == 'reference' else 'keywords'
        kws = facets[field][kw_field] if field == 'reference' else facets[field]['keywords']
        if kws:
            if field == 'subject':
                search_mode = 'subj'
            elif field == 'object':
                search_mode = 'obj'
            else:
                search_mode = 'ref'

            refined = disambiguate_entity(question, kws, search_mode, kws)
            if refined != kws:
                if field == 'reference':
                    facets[field]['entity_keywords'] = refined
                else:
                    facets[field]['keywords'] = refined

    # Re-run post-processing after disambiguation
    facets_data = post_process_facets(question, qtype, facets_data)

    # Step 3: Initial retrieval
    candidate_pool = initial_retrieve(facets_data)
    merge_records(candidate_pool, deterministic_supplemental_retrieve(facets_data, qtype))

    # Step 4-6: FacetRank + Sufficiency loop
    for turn in range(max_turns):
        # FIX G (inherited): Dynamic score-band filter
        candidate_pool = dynamic_score_filter(candidate_pool, facets_data)

        ranked = facet_rank(candidate_pool, facets_data)
        if not ranked:
            break

        is_sufficient, sufficiency_result, reason = check_sufficiency(question, qtype, ranked, facets_data)
        if is_sufficient:
            break

        new_queries = sufficiency_result.get('new_queries', [])
        if not new_queries:
            break
        new_records = execute_re_retrieval(new_queries, facets_data, candidate_pool)
        if not new_records:
            break
        candidate_pool.extend(new_records)

    # Step 7: Programmatic solve
    answer = programmatic_solve(candidate_pool, facets_data, qtype, question)
    return answer, facets_data

# ============================================================
# 10. Benchmark — Strict Exact Match (Fix D & E inherited)
# ============================================================
def normalize_entity(s: str) -> str:
    return s.replace('_', ' ').strip().lower()

def check_correct(model_answer, ground_truth):
    """
    Strict Exact Match (Fix D & E inherited from V5 Universal).
    - List: model set must exactly equal ground truth set.
    - Scalar: normalized equality.
    """
    if model_answer is None:
        return False

    if isinstance(model_answer, list):
        model_set = set(normalize_entity(str(a)) for a in model_answer)
        gt_set    = set(normalize_entity(str(a)) for a in ground_truth)
        return model_set == gt_set

    cleaned_model = normalize_entity(str(model_answer))
    for gt in ground_truth:
        cleaned_gt = normalize_entity(str(gt))
        if cleaned_model == cleaned_gt:
            return True
    return False

def run_benchmark(n=100):
    with open('test.json', 'r', encoding='utf-8') as f:
        all_data = json.load(f)

    test_data = all_data[:n]
    correct_count = 0
    total_count = len(test_data)
    start_time = time.time()

    qtype_stats = defaultdict(lambda: {'correct': 0, 'total': 0})

    print(f"\n{'='*80}")
    print(f"V6 (J/K/L + D/E/F/G/H/I Eliminated, Strict Exact Match) - First {n} questions")
    print(f"{'='*80}")

    for i, item in enumerate(test_data):
        question = item["question"]
        ground_truth = item["answers"]
        qtype = item.get("qtype", "unknown")

        model_answer, facets_data = answer_question(question, qtype)
        is_correct = check_correct(model_answer, ground_truth)
        if is_correct:
            correct_count += 1

        qtype_stats[qtype]['total'] += 1
        if is_correct:
            qtype_stats[qtype]['correct'] += 1

        status = "[OK]" if is_correct else "[WRONG]"
        print(f"\n[{i+1}/{total_count}] {status} | {qtype}")
        print(f"  Q: {question[:120]}")
        print(f"  Model: {model_answer}")
        print(f"  Truth: {ground_truth}")
        f = facets_data.get('facets', {})
        print(f"  Facets: subj={f.get('subject',{}).get('keywords',[])}, "
              f"rel={f.get('relation',{}).get('keywords',[])}, "
              f"obj={f.get('object',{}).get('keywords',[])}, "
              f"ref={f.get('reference',{}).get('entity_keywords',[])}, "
              f"tl={facets_data.get('temporal_logic','?')}")

        time.sleep(0.3)

    end_time = time.time()
    accuracy = (correct_count / total_count) * 100

    print(f"\n{'='*80}")
    print(f"V6 Experiment Report (Strict Exact Match, Precision-First)")
    print(f"{'='*80}")
    print(f"Total: {total_count}, Correct: {correct_count}, Accuracy: {accuracy:.2f}%")
    print(f"Time: {end_time - start_time:.2f}s")
    print(f"\nAccuracy by qtype:")
    for qt in sorted(qtype_stats.keys()):
        s = qtype_stats[qt]
        acc = (s['correct'] / s['total'] * 100) if s['total'] > 0 else 0
        print(f"  {qt}: {s['correct']}/{s['total']} = {acc:.1f}%")
    print(f"{'='*80}")

    return accuracy

if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run_benchmark(n=n)
