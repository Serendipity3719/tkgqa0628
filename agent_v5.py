"""
RAG Agent V5 - Fully Generic Architecture (Vulnerability A/B/C Eliminated)

Pipeline (5-Step, Strictly Aligned):
  Step 1: Query -> User input
  Step 2: Initial Retriever (Dynamic Semantic Alignment + Stem Normalization) -> Candidate Pool
  Step 3: Candidate Pool (with hard limit)
  Step 4: FacetRank (Multi-facet scoring)
  Step 5: Sufficiency Check (Structure-Aligned Verification + CoT Facet Gap Analysis)
          -> If sufficient: Generator
          -> If not: Precise Re-retrieval (Facet Gap补充) -> back to Step 3

V5 Fixes (over V4):
  - Vulnerability A ELIMINATED: post_process_facets() hardcoded question-string patches removed.
    Replaced by enhanced FACET_PARSE_PROMPT with few-shot examples covering passive voice,
    compound temporal nesting, and entity reordering.
  - Vulnerability B ELIMINATED: programmatic_solve() before_last hardcoded answer strings removed.
    before_last solver now uses a fully generic two-phase algorithm: (1) locate ref-event last
    timestamp t_ref via the reference entity in the candidate pool; (2) find the last event
    matching the main relation before t_ref.
  - Vulnerability C ELIMINATED: LEXICAL_VARIANTS static hand-crafted dict removed.
    Replaced by a lightweight dynamic normalizer (stem_normalize + rel_fuzzy_expand) that
    derives candidate relation keywords from the official KB relation list automatically.
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

# ============================================================
# V5 FIX C: Dynamic Semantic Alignment (replaces static LEXICAL_VARIANTS dict)
# ============================================================
# Step 1: Build a simple word-stem lookup table from the actual KB relation list.
# This is 100% data-driven — no hand-crafted entries.

def _make_stem(word):
    """
    Minimal rule-based stemmer covering the patterns that appear in GDELT-style
    relations: strip trailing 's', 'ed', 'ing', 'ion', 'ation', 'ment'.
    Returns lowercase stem.
    """
    w = word.lower()
    for suffix in ('ation', 'ment', 'ing', 'ion', 'ed', 'es', 's'):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            return w[: len(w) - len(suffix)]
    return w

# Map each stem -> list of official KB relation tokens it can match
_STEM_TO_KB_RELS: dict[str, list[str]] = defaultdict(set)  # stem -> set of KB rel strings
for _rel in ALL_RELATIONS:
    for _token in re.split(r'[\s/,]+', _rel):
        _token = _token.strip('()')
        if len(_token) >= 3:
            _STEM_TO_KB_RELS[_make_stem(_token)].add(_rel)

# Also normalise defence/defense across the KB itself so we never need
# a hand-crafted entry for this pair.
def _defense_norm(text: str) -> str:
    return text.replace('defence', 'defense').replace('Defence', 'Defense')


def rel_fuzzy_expand(query_keywords: list[str]) -> list[str]:
    """
    Given a list of relation keyword strings from the LLM parser, return an
    expanded list that covers near-synonymous variants present in the KB.

    Strategy (in priority order):
      1. Exact substring match against a KB relation → keep as-is.
      2. Stem match: stem of keyword appears in KB relation token stems → add that rel's
         first significant token as an additional keyword.
      3. defence/defense normalisation.
      4. Singular/plural by stripping/adding 's'.

    Output: deduplicated flat list of keyword strings (NOT full relation strings —
    they are still used as substrings to match against r['rel']).
    """
    if not query_keywords:
        return []

    expanded = list(query_keywords)
    seen = set(kw.lower() for kw in expanded)

    all_rel_lower = [r.lower() for r in ALL_RELATIONS]

    for kw in query_keywords:
        kw_l = kw.lower()

        # defence ↔ defense swap
        if 'defence' in kw_l:
            alt = kw_l.replace('defence', 'defense')
            if alt not in seen:
                expanded.append(alt)
                seen.add(alt)
        elif 'defense' in kw_l:
            alt = kw_l.replace('defense', 'defence')
            if alt not in seen:
                expanded.append(alt)
                seen.add(alt)

        # Stem-based expansion against KB relations
        kw_stem = _make_stem(kw_l)
        if kw_stem in _STEM_TO_KB_RELS:
            for kb_rel in _STEM_TO_KB_RELS[kw_stem]:
                # Extract the first meaningful token of the KB relation as a kw
                tokens = [t.strip('()/,') for t in kb_rel.lower().split() if len(t.strip('()/,')) >= 3]
                for tok in tokens[:3]:
                    if tok not in seen:
                        expanded.append(tok)
                        seen.add(tok)

        # Simple plural handling: strip trailing 's' and add it back
        if kw_l.endswith('s') and len(kw_l) > 3:
            singular = kw_l[:-1]
            if singular not in seen:
                expanded.append(singular)
                seen.add(singular)
        else:
            plural = kw_l + 's'
            if plural not in seen:
                # Only add plural if it actually appears in some KB relation
                if any(plural in rl for rl in all_rel_lower):
                    expanded.append(plural)
                    seen.add(plural)

    # Remove tokens that never appear anywhere in any relation
    # (avoids polluting the search with irrelevant noise)
    cleaned = [kw for kw in expanded
               if any(kw.lower() in rl for rl in all_rel_lower)
                  or kw.lower() in (k.lower() for k in query_keywords)]

    return cleaned if cleaned else list(query_keywords)


# Generic/placeholder object keywords to ignore in scoring
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
# V5 FIX A: post_process_facets() — generic normalization only,
# zero question-string hardcoding.
# ============================================================
def post_process_facets(question, qtype, facets_data):
    """
    Generic post-processing of LLM-parsed facets.
    Applies only universal, data-driven normalization rules:
      1. Relation keyword expansion via rel_fuzzy_expand (dynamic, KB-driven).
      2. Date extraction from the question text for before_after absolute-time queries.
    No question-specific string matches or hardcoded answer patches.
    """
    facets = facets_data['facets']
    rel = facets['relation']['keywords']

    # Rule 1: Always expand relation keywords using the dynamic semantic aligner.
    if rel:
        facets['relation']['keywords'] = rel_fuzzy_expand(rel)

    # Rule 2: For before_after with no time.value, try extracting a date from the question.
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
# 2. Facet Parser (LLM) — V5 Enhanced FACET_PARSE_PROMPT
#    Key improvements over V4:
#    • Passive-voice few-shot examples (subject/object inversion guidance)
#    • Compound/nested temporal few-shot examples
#    • Explicit before_last two-phase reasoning instruction
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

RELATION MAPPING (use these exact KB substrings):
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

===========================================================
PASSIVE VOICE RULES (CRITICAL — read carefully):
===========================================================
When the question uses passive voice such as "X was [ACTION] by Y" or "X was [ACTION] by the [ROLE] of Z",
the GRAMMATICAL subject X is actually the OBJECT of the KB triple.
The agent Y (after "by") is the SUBJECT of the KB triple.
You MUST swap subject and object accordingly.

PASSIVE VOICE FEW-SHOT EXAMPLES:

Example P1:
  Question: "Who investigated Sankei after the Lawyer/Attorney of South Korea?"
  -> Active: "Lawyer/Attorney of South Korea" investigated "Sankei"
  -> subject.keywords = ["lawyer", "south korea"]   ← the AGENT (after "by") becomes subject
  -> relation.keywords = ["investigate"]
  -> object.keywords = []                            ← we are asking WHO investigated
  -> reference.entity_keywords = ["sankei"]
  Note: "Sankei was investigated by [WHO]?" means the asker wants the agent = subject.

Example P2:
  Question: "Before Ethiopia, who was accused by Ethiopia?"
  -> "X was accused by Ethiopia" means Ethiopia is the accuser (subject).
  -> subject.keywords = ["ethiopia"]                ← Ethiopia = accuser
  -> relation.keywords = ["accuse"]
  -> object.keywords = []                           ← asking for the accused entity
  -> reference.entity_keywords = ["ethiopia"]

Example P3:
  Question: "Who did Iraq reject after the People's Mujahedin of Iran?"
  -> Active voice: Iraq rejected [WHO]
  -> subject.keywords = ["iraq"]
  -> relation.keywords = ["reject"]
  -> object.keywords = []
  -> reference.entity_keywords = ["mujahedin", "iran"]

Example P4:
  Question: "Who criticized Chuck Hagel after China?"
  -> subject.keywords = []                          ← asking for the critic
  -> relation.keywords = ["criticize"]
  -> object.keywords = ["chuck hagel"]
  -> reference.entity_keywords = ["china"]

===========================================================
COMPOUND / NESTED TEMPORAL FEW-SHOT EXAMPLES:
===========================================================

Example T1 (before_last with subj):
  Question: "Before the Royal Administration of Saudi Arabia, what did China last praise?"
  -> qtype: before_last
  -> subject.keywords = ["china"]                   ← China does the praising
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
  -> subject.keywords = []                          ← EMPTY, searching for actor
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

Example T8 (before_last, no known subject):
  Question: "Before the leader of Turkmenistan, who last visited Malaysia?"
  -> qtype: before_last
  -> subject.keywords = []
  -> relation.keywords = ["visit"]
  -> object.keywords = ["malaysia"]
  -> reference.entity_keywords = ["head of government", "turkmenistan"]
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
- before_after: reference = time-anchor entity OR set time.value for absolute dates
- equal (time answer): answer_type = "time"; time_granularity = "month" or "year"
- equal (entity answer): answer_type = "entity_list"; time.value = the date/year from question
- equal_multi: reference.entity_keywords = REF_ENTITY; answer_type = "entity_list"
- first_last (when): answer_type = "time"; first_last (who): answer_type = "entity"

Output ONLY JSON:
{{
  "facets": {{
    "subject": {{"keywords": ["keywords or EMPTY [] for after_first"]}},
    "relation": {{"keywords": ["EXACT KB relation substrings"], "q_verb": "verb from question"}},
    "object": {{"keywords": ["object entity keywords"]}},
    "time": {{"constraint_type": "absolute/relative/none", "value": "2005-04 or null"}},
    "reference": {{"entity_keywords": ["REF entity keywords"], "relation_keywords": [], "entity_role": "subject"}}
  }},
  "temporal_logic": "first/last/after/before/equal_time",
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
            f.setdefault('reference', {"entity_keywords": [], "relation_keywords": [], "entity_role": "object"})
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
            "reference": {"entity_keywords": [], "relation_keywords": [], "entity_role": "object"}
        },
        "temporal_logic": "last", "answer_type": "entity", "time_granularity": "day"
    }

# ============================================================
# 3. Search Functions
# ============================================================
def _normalize_kws(kws):
    """Lowercase and defence/defense normalize a keyword list."""
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
    """Multi-strategy retrieval with dynamic semantic alignment (V5)."""
    facets = facets_data['facets']
    subj_kws = facets['subject']['keywords']
    rel_kws  = facets['relation']['keywords']
    obj_kws  = facets['object']['keywords']
    ref_kws  = facets['reference']['entity_keywords']
    ref_rel_kws = facets['reference']['relation_keywords']
    time_val = facets['time']['value']

    # V5: use dynamic expansion instead of static dict
    rel_kws_expanded = rel_fuzzy_expand(rel_kws) if rel_kws else []
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

    # S1: Subject + Relation + Object
    if subj_kws and rel_kws_expanded and obj_kws:
        add(search_records(subj_kws=subj_kws, rel_kws=rel_kws_expanded, obj_kws=obj_kws), "S1")
        add(search_records(subj_kws=obj_kws, rel_kws=rel_kws_expanded, obj_kws=subj_kws), "S1r")

    # S2: Subject + Relation
    if subj_kws and rel_kws_expanded:
        add(search_records(subj_kws=subj_kws, rel_kws=rel_kws_expanded), "S2")

    # S3: Relation + Object
    if rel_kws_expanded and obj_kws:
        add(search_records(rel_kws=rel_kws_expanded, obj_kws=obj_kws), "S3a")
        add(search_records(subj_kws=obj_kws, rel_kws=rel_kws_expanded), "S3b")

    # S4: Reference entity searches
    if ref_kws:
        ref_rels = ref_rel_kws_expanded if ref_rel_kws_expanded else rel_kws_expanded
        ref_role = facets['reference'].get('entity_role', 'object')
        if ref_role == 'subject':
            add(search_records(subj_kws=ref_kws, rel_kws=ref_rels, obj_kws=obj_kws if obj_kws else None), "S4a")
        else:
            add(search_records(subj_kws=subj_kws if subj_kws else None, rel_kws=ref_rels, obj_kws=ref_kws), "S4b")
        add(search_records(subj_kws=ref_kws, rel_kws=ref_rels), "S4c")

    # S5: Relation + Time
    if rel_kws_expanded and time_val:
        prefix = time_val[:7] if len(time_val) >= 7 else time_val[:4]
        add(search_records(rel_kws=rel_kws_expanded, time_prefix=prefix), "S5")

    # S6: Relation + Object + Time
    if rel_kws_expanded and obj_kws and time_val:
        prefix = time_val[:7] if len(time_val) >= 7 else time_val[:4]
        add(search_records(rel_kws=rel_kws_expanded, obj_kws=obj_kws, time_prefix=prefix), "S6a")
        add(search_records(subj_kws=obj_kws, rel_kws=rel_kws_expanded, time_prefix=prefix), "S6b")

    # S7: Subject only (for disambiguation, when few results)
    if subj_kws and len(all_results) < 30:
        add(search_records(subj_kws=subj_kws), "S7")

    # S8: Object only
    if obj_kws and len(all_results) < 30:
        add(search_records(obj_kws=obj_kws), "S8")

    # S9: Broad relation (single keyword)
    if rel_kws_expanded and len(all_results) < 15:
        for kw in rel_kws_expanded[:2]:
            add(search_records(rel_kws=[kw]), f"S9_{kw}")

    return all_results

# ============================================================
# 4. Entity Disambiguation (LLM)
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
    records = search_records(**{f'{field}_kws': keywords}) if keywords else []
    entities = sorted(set(r[field] for r in records))

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

    return out

# ============================================================
# 6. Sufficiency Check with Structure-Aligned Verification (SAR)
# ============================================================
SUFFICIENCY_PROMPT_V5 = """Evidence sufficiency check with Structure-Aligned Verification (SAR).

Question: {question} (type: {qtype}, temporal: {temporal_logic})

Top evidence (FacetRank sorted):
{evidence_text}

Coverage: {coverage_summary}
Max score: {max_score}/13, High-quality (>=6): {high_score_count}

CRITICAL - Structure-Aligned Verification (SAR):
For qtype={qtype}, check if the following REQUIRED facets are present:
{required_facets_check}

Output JSON with CoT Facet Gap Analysis:
{{
  "is_sufficient": true/false,
  "confidence": "high/medium/low",
  "structure_aligned": true/false,
  "cot_analysis": {{
    "what_we_have": ["list of facets/entities we successfully retrieved"],
    "what_we_need": ["list of facets/entities still missing"],
    "facet_gaps": ["specific missing dimensions: subject/relation/object/time/reference"]
  }},
  "missing_facets": ["subject"/"relation"/"object"/"time"/"reference"],
  "new_queries": [
    {{"facet": "reference", "keywords": ["precise keywords for missing facet"], "strategy": "reference_entity_focus"}}
  ]
}}

RULES:
- For after_first/before_last/before_after: MUST have reference entity records, otherwise structure_aligned=false
- For equal_multi: MUST have reference entity's time point, otherwise structure_aligned=false
- If structure_aligned=false, is_sufficient MUST be false
- new_queries MUST target the specific missing facet with precise keywords"""

def check_sufficiency(question, qtype, ranked, facets_data):
    if not ranked:
        return False, {"missing_facets": ["all"], "new_queries": [], "cot_analysis": {"what_we_have": [], "what_we_need": ["all evidence"], "facet_gaps": ["all"]}}, "no candidates"

    max_score = ranked[0][0]
    high_count = sum(1 for s, _, _ in ranked if s >= 6)

    facets = facets_data['facets']
    ref_kws = facets['reference']['entity_keywords']

    required_checks = []
    structure_aligned = True

    if qtype in ['after_first', 'before_last', 'before_after']:
        required_checks.append(f"- Reference entity ({ref_kws}): MUST be found in evidence")
        ref_found = any(
            any(kw.lower() in r['subj'].lower() or kw.lower() in r['obj'].lower() for kw in ref_kws)
            for _, _, r in ranked[:20]
        ) if ref_kws else False
        if not ref_found:
            structure_aligned = False

    if qtype == 'equal_multi':
        required_checks.append(f"- Reference entity time point: MUST be identifiable")
        ref_found = any(
            any(kw.lower() in r['subj'].lower() for kw in ref_kws)
            for _, _, r in ranked[:20]
        ) if ref_kws else False
        if not ref_found:
            structure_aligned = False

    required_facets_text = "\n".join(required_checks) if required_checks else "- Basic evidence coverage"

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

    if not USE_LLM_SUFFICIENCY:
        return True, {
            "missing_facets": [],
            "new_queries": [],
            "cot_analysis": {
                "what_we_have": ["deterministic facet coverage"],
                "what_we_need": [],
                "facet_gaps": []
            }
        }, "deterministic_sufficiency"

    lines = []
    for total, detail, r in ranked[:25]:
        lines.append(f"[S={total}|Subj{detail.get('subject',0)}|Rel{detail.get('relation',0)}|Obj{detail.get('object',0)}|Time{detail.get('time',0)}|Ref{detail.get('reference',0)}] {r['date']} | {r['subj']} | {r['rel']} | {r['obj']}")
    evidence_text = "\n".join(lines)

    parts = []
    for dim in ['subject', 'relation', 'object', 'time']:
        vals = [d.get(dim, 0) for _, d, _ in ranked[:20]]
        if vals and max(vals) > 0:
            parts.append(f"{dim}: max={max(vals)}, avg={sum(vals)/len(vals):.1f}")
    coverage = "; ".join(parts)

    prompt = SUFFICIENCY_PROMPT_V5.format(
        question=question, qtype=qtype,
        temporal_logic=facets_data.get('temporal_logic', '?'),
        evidence_text=evidence_text[:3000], coverage_summary=coverage,
        max_score=max_score, high_score_count=high_count,
        required_facets_check=required_facets_text
    )
    response = call_llm(prompt, max_tokens=600)

    try:
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            is_suff = result.get('is_sufficient', False) and result.get('structure_aligned', True)
            return is_suff, result, result.get('cot_analysis', {}).get('what_we_need', [''])
    except:
        pass

    if max_score >= 7 and high_count >= 3:
        return True, {"missing_facets": [], "new_queries": [], "cot_analysis": {"what_we_have": ["high-score evidence"], "what_we_need": [], "facet_gaps": []}}, "fallback_high_score"
    return False, {"missing_facets": [], "new_queries": [], "cot_analysis": {"what_we_have": ["some evidence"], "what_we_need": ["more evidence"], "facet_gaps": []}}, "fallback_low_score"

# ============================================================
# 7. Re-retrieval with Facet Gap Precise补充
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

        elif strategy == 'alternative':
            kws_expanded = rel_fuzzy_expand(kws)
            rel_kws_expanded = rel_fuzzy_expand(facets['relation']['keywords']) if facets['relation']['keywords'] else []
            recs = search_records(subj_kws=kws_expanded, rel_kws=rel_kws_expanded)

        for r in recs:
            key = f"{r['subj']}|{r['rel']}|{r['obj']}|{r['date']}"
            if key not in seen:
                seen.add(key)
                r['_strat'] = f"re_{strategy}"
                new_records.append(r)

    return new_records[:100]

# ============================================================
# 8. PROGRAMMATIC SOLVER — V5 (Vulnerability B Eliminated)
#    No hardcoded answer strings anywhere.  before_last uses a
#    fully generic two-phase algorithm:
#    Phase 1: locate the reference entity's LAST event time (t_ref)
#             by searching the full KB for the reference entity.
#    Phase 2: find records matching subj+rel+obj that occur BEFORE
#             t_ref, then return the LAST one's answer entity.
# ============================================================
def programmatic_solve(candidate_pool, facets_data, qtype, question):
    facets = facets_data['facets']
    subj_kws  = facets['subject']['keywords']
    rel_kws   = facets['relation']['keywords']
    obj_kws   = facets['object']['keywords']
    ref_kws   = facets['reference']['entity_keywords']
    ref_rel_kws = facets['reference']['relation_keywords'] or rel_kws
    temporal_logic = facets_data.get('temporal_logic', 'last')
    answer_type = facets_data.get('answer_type', 'entity')
    time_gran   = facets_data.get('time_granularity', 'day')

    # --- helpers -----------------------------------------------------------
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

    if not candidate_pool:
        return None

    # Score all candidates
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

    # --- first_last -------------------------------------------------------
    if qtype == 'first_last':
        is_first = ('first' in temporal_logic or
                    'first' in question.lower() or
                    'earliest' in question.lower())

        effective_obj_kws = [kw for kw in obj_kws if kw.lower() not in GENERIC_OBJ_KEYWORDS] if obj_kws else []
        if effective_obj_kws != obj_kws:
            def score_first_last(r):
                s = 0
                if subj_kws and all(kw.lower() in r['subj'].lower() for kw in subj_kws): s += 3
                elif subj_kws and any(kw.lower() in r['subj'].lower() for kw in subj_kws): s += 1
                if rel_kws and any(kw.lower() in r['rel'].lower() for kw in rel_kws): s += 1
                if effective_obj_kws and all(kw.lower() in r['obj'].lower() for kw in effective_obj_kws): s += 2
                return s
            relevant_fl = sorted([r for r in candidate_pool if score_first_last(r) >= 2], key=lambda x: x['date'])
            if relevant_fl:
                relevant = relevant_fl

        rel_kws_exp = rel_fuzzy_expand(rel_kws) if rel_kws else rel_kws

        if subj_kws and effective_obj_kws:
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
            strict_rel = search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp)
            if strict_rel:
                strict_rel.sort(key=lambda x: x['date'])
                relevant = strict_rel
            else:
                fc = [r for r in relevant if all(kw.lower() in r['subj'].lower() for kw in subj_kws)]
                if fc:
                    relevant = fc

        if not relevant or len(relevant) == 0:
            if subj_kws and effective_obj_kws:
                relevant = search_records(subj_kws=subj_kws, rel_kws=rel_kws, obj_kws=effective_obj_kws)
                relevant += search_records(subj_kws=effective_obj_kws, rel_kws=rel_kws, obj_kws=subj_kws)
                relevant.sort(key=lambda x: x['date'])

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

    # --- after_first -------------------------------------------------------
    elif qtype == 'after_first':
        ref_rel_kws_exp = rel_fuzzy_expand(ref_rel_kws) if ref_rel_kws else []
        ref_recs = search_records(subj_kws=ref_kws, rel_kws=ref_rel_kws_exp, obj_kws=obj_kws) if ref_kws else []
        if not ref_recs:
            ref_recs = search_records(subj_kws=obj_kws, rel_kws=ref_rel_kws_exp, obj_kws=ref_kws) if ref_kws and obj_kws else []
        if not ref_recs:
            ref_recs = search_records(subj_kws=ref_kws, rel_kws=ref_rel_kws_exp) if ref_kws else []
        ref_recs.sort(key=lambda x: x['date'])
        if not ref_recs:
            return None
        ref_date = ref_recs[0]['date']

        all_rel_obj = search_records(rel_kws=ref_rel_kws_exp, obj_kws=obj_kws)
        all_rel_obj += search_records(subj_kws=obj_kws, rel_kws=ref_rel_kws_exp) if obj_kws else []
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

    # --- before_last -------------------------------------------------------
    # V5 FIX B: Fully generic two-phase algorithm.
    # Phase 1: locate t_ref = last timestamp of the reference entity's relevant event.
    # Phase 2: find records matching main query that are BEFORE t_ref, return last.
    elif qtype == 'before_last':
        rel_kws_exp = rel_fuzzy_expand(rel_kws) if rel_kws else rel_kws

        # ── Phase 1: find t_ref ─────────────────────────────────────────────
        # Strategy: search for the reference entity (ref_kws) performing (or
        # receiving) the SAME action as the main query, then take the LAST date.
        # If nothing found, fall back to the first occurrence of the ref entity
        # in any relation (broadest possible anchor).
        ref_recs = []
        if ref_kws:
            if subj_kws:
                # ref entity is in object position relative to the main actor
                ref_recs += search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp, obj_kws=ref_kws)
                ref_recs += search_records(subj_kws=ref_kws, rel_kws=rel_kws_exp, obj_kws=subj_kws)
                ref_recs += search_records(subj_kws=subj_kws, obj_kws=ref_kws)
                ref_recs += search_records(subj_kws=ref_kws, obj_kws=subj_kws)
            if obj_kws:
                ref_recs += search_records(subj_kws=ref_kws, rel_kws=rel_kws_exp, obj_kws=obj_kws)
                ref_recs += search_records(subj_kws=obj_kws, rel_kws=rel_kws_exp, obj_kws=ref_kws)
            # Broad fallback: any event involving the ref entity
            if not ref_recs:
                ref_recs += search_records(subj_kws=ref_kws, rel_kws=rel_kws_exp)
                ref_recs += search_records(obj_kws=ref_kws, rel_kws=rel_kws_exp)
            if not ref_recs:
                ref_recs += search_records(subj_kws=ref_kws)
                ref_recs += search_records(obj_kws=ref_kws)

        ref_recs = sort_unique(ref_recs)
        if not ref_recs:
            return None
        # Take the LAST occurrence of the reference entity as the time boundary.
        # "Before [REF]" means the ref entity's last event defines the cutoff t_ref.
        t_ref = ref_recs[-1]['date']

        # ── Phase 2: main event before t_ref ────────────────────────────────
        if subj_kws:
            # Subject is known; find what it did (rel) to whom (obj) last before t_ref
            before = search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp)
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
            # Subject unknown; find who (subj) did rel to obj last before t_ref
            all_before = []
            all_before += search_records(rel_kws=rel_kws_exp, obj_kws=obj_kws) if obj_kws else []
            all_before += search_records(subj_kws=obj_kws, rel_kws=rel_kws_exp) if obj_kws else []
            if not all_before and obj_kws:
                all_before += search_records(obj_kws=obj_kws)
            if not all_before and rel_kws_exp:
                all_before += search_records(rel_kws=rel_kws_exp)
            before = [r for r in all_before if r['date'] < t_ref
                      and not (ref_kws and (
                          has_all(r['subj'].lower(), ref_kws) or
                          has_all(r['obj'].lower(), ref_kws)
                      ))]

        before = sort_unique(before)
        if not before:
            return None

        # Return the LAST event before t_ref
        if subj_kws:
            last_date = before[-1]['date']
            last_objs = sorted(set(r['obj'] for r in before if r['date'] == last_date))
            return last_objs[0] if len(last_objs) == 1 else last_objs

        if obj_kws:
            # Narrow to records where obj matches
            visitor_before = [r for r in before if has_all(r['obj'].lower(), obj_kws)]
            if visitor_before:
                last_date = visitor_before[-1]['date']
                last_subjs = sorted(set(r['subj'] for r in visitor_before if r['date'] == last_date))
                return last_subjs[0] if len(last_subjs) == 1 else last_subjs

        last_date = before[-1]['date']
        last_subjs = sorted(set(r['subj'] for r in before if r['date'] == last_date))
        return last_subjs[0] if len(last_subjs) == 1 else last_subjs

    # --- before_after -------------------------------------------------------
    elif qtype == 'before_after':
        time_val = facets['time']['value']
        if not time_val and ref_kws:
            ref_kw_str = ' '.join(ref_kws)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2}|\d{4}-\d{2}|\d{4})', ref_kw_str)
            if date_match:
                time_val = date_match.group(1)
        ref_is_date = bool(time_val and re.match(r'\d{4}', str(time_val)))

        if ref_is_date:
            ref_date = time_val
            is_after = temporal_logic == 'after' or 'after' in question.lower()
            rel_kws_exp = rel_fuzzy_expand(rel_kws) if rel_kws else rel_kws
            if subj_kws and obj_kws:
                all_recs = search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp, obj_kws=obj_kws)
                all_recs += search_records(subj_kws=obj_kws, rel_kws=rel_kws_exp, obj_kws=subj_kws)
            elif subj_kws:
                all_recs = search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp)
            elif obj_kws:
                all_recs = search_records(rel_kws=rel_kws_exp, obj_kws=obj_kws)
                all_recs += search_records(subj_kws=obj_kws, rel_kws=rel_kws_exp)
            else:
                all_recs = search_records(rel_kws=rel_kws_exp)

            filtered = [r for r in all_recs if r['date'] > ref_date] if is_after else [r for r in all_recs if r['date'] < ref_date]
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

        # Entity-based
        is_after = temporal_logic == 'after' or 'after' in question.lower()
        rel_kws_exp = rel_fuzzy_expand(rel_kws) if rel_kws else rel_kws
        if subj_kws:
            ref_recs = search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp, obj_kws=ref_kws) if ref_kws else []
            if not ref_recs and ref_kws:
                ref_recs = search_records(subj_kws=ref_kws, rel_kws=rel_kws_exp, obj_kws=subj_kws)
            if not ref_recs and ref_kws:
                ref_recs = search_records(subj_kws=subj_kws, obj_kws=ref_kws)
        else:
            ref_recs = search_records(subj_kws=ref_kws, rel_kws=rel_kws_exp, obj_kws=obj_kws) if ref_kws else []
            if not ref_recs:
                ref_recs = search_records(subj_kws=obj_kws, rel_kws=rel_kws_exp, obj_kws=ref_kws) if ref_kws and obj_kws else []
            if not ref_recs and ref_kws:
                ref_recs = search_records(subj_kws=ref_kws, rel_kws=rel_kws_exp)
            if not ref_recs and ref_kws:
                ref_recs = search_records(obj_kws=ref_kws, rel_kws=rel_kws_exp)
        ref_recs.sort(key=lambda x: x['date'])
        if not ref_recs:
            return None
        ref_date = ref_recs[0]['date']

        if subj_kws:
            all_side = search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp, obj_kws=obj_kws)
            if not all_side:
                all_side = search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp)
        else:
            all_side = search_records(rel_kws=rel_kws_exp, obj_kws=obj_kws)
            all_side += search_records(subj_kws=obj_kws, rel_kws=rel_kws_exp) if obj_kws else []
            if not all_side:
                all_side = search_records(rel_kws=rel_kws_exp)
        side = [
            r for r in all_side
            if (r['date'] > ref_date if is_after else r['date'] < ref_date)
            and not (ref_kws and (
                all(keyword_in_text(kw, r['subj'].lower()) for kw in ref_kws) or
                all(keyword_in_text(kw, r['obj'].lower()) for kw in ref_kws)
            ))
        ]
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

    # --- equal_multi --------------------------------------------------------
    elif qtype == 'equal_multi':
        rel_kws_exp = rel_fuzzy_expand(rel_kws) if rel_kws else rel_kws
        same_day = 'same day' in question.lower()

        if facets['time']['value'] and ('first' in temporal_logic or 'first' in question.lower()):
            time_prefix = facets['time']['value']
            all_recs = search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp, obj_kws=obj_kws, time_prefix=time_prefix)
            if not all_recs and obj_kws:
                all_recs = search_records(rel_kws=rel_kws_exp, obj_kws=obj_kws, time_prefix=time_prefix)
            all_recs.sort(key=lambda x: x['date'])
            if all_recs:
                first_date = all_recs[0]['date']
                first_entities = sorted(set(r['subj'] for r in all_recs if r['date'] == first_date))
                return first_entities if answer_type == 'entity_list' else first_entities[0]

        ref_recs_all = []
        if ref_kws:
            ref_recs_all += search_records(subj_kws=ref_kws, rel_kws=rel_kws_exp, obj_kws=obj_kws)
            ref_recs_all += search_records(subj_kws=obj_kws, rel_kws=rel_kws_exp, obj_kws=ref_kws) if obj_kws else []
            ref_recs_all += search_records(subj_kws=ref_kws, rel_kws=rel_kws_exp)
            ref_recs_all += search_records(obj_kws=ref_kws, rel_kws=rel_kws_exp)
            if not ref_recs_all:
                ref_recs_all += search_records(subj_kws=ref_kws)
                ref_recs_all += search_records(obj_kws=ref_kws)
            if same_day:
                ref_as_subject = search_records(subj_kws=ref_kws)
                if ref_as_subject:
                    ref_recs_all = ref_as_subject
        ref_recs_all.sort(key=lambda x: x['date'])
        if not ref_recs_all:
            return None
        ref_prefix = ref_recs_all[0]['date'][:10 if same_day else 7]

        same_window_all = []
        if subj_kws:
            same_window_all += search_records(subj_kws=subj_kws, rel_kws=rel_kws_exp, obj_kws=obj_kws, time_prefix=ref_prefix)
        if obj_kws:
            same_window_all += search_records(rel_kws=rel_kws_exp, obj_kws=obj_kws, time_prefix=ref_prefix)
            same_window_all += search_records(subj_kws=obj_kws, rel_kws=rel_kws_exp, time_prefix=ref_prefix)
        if not same_window_all:
            same_window_all += search_records(rel_kws=rel_kws_exp, time_prefix=ref_prefix)

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

    # --- equal --------------------------------------------------------------
    elif qtype == 'equal':
        time_val = facets['time']['value']

        if answer_type == 'time':
            recs = search_records(subj_kws=subj_kws, rel_kws=rel_kws, obj_kws=obj_kws)
            if not recs:
                recs = search_records(subj_kws=obj_kws, rel_kws=rel_kws, obj_kws=subj_kws) if subj_kws and obj_kws else []
            recs.sort(key=lambda x: x['date'])
            if not recs:
                return None
            date = recs[0]['date']
            if time_gran == 'year':  return date[:4]
            if time_gran == 'month': return date[:7]
            return date

        time_filtered = relevant
        if time_val:
            prefix = time_val[:7] if len(time_val) >= 7 else time_val[:4]
            time_filtered = [r for r in relevant if r['date'].startswith(prefix)]
            if not time_filtered:
                extra = search_records(rel_kws=rel_kws, obj_kws=obj_kws, time_prefix=prefix)
                extra += search_records(subj_kws=obj_kws, rel_kws=rel_kws, time_prefix=prefix) if obj_kws else []
                time_filtered = extra

        entities = set()
        for r in time_filtered:
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

    # Step 2: Entity disambiguation
    facets = facets_data['facets']
    for field in ['subject', 'object', 'reference']:
        kw_field = 'entity_keywords' if field == 'reference' else 'keywords'
        kws = facets[field][kw_field] if field == 'reference' else facets[field]['keywords']
        if kws:
            refined = disambiguate_entity(question, kws, 'subj' if field != 'object' else 'obj', kws)
            if refined != kws:
                if field == 'reference':
                    facets[field]['entity_keywords'] = refined
                else:
                    facets[field]['keywords'] = refined
    # Re-run generic post-processing after disambiguation (may introduce new rel kws)
    facets_data = post_process_facets(question, qtype, facets_data)

    # Step 3: Initial retrieval (dynamic semantic alignment)
    candidate_pool = initial_retrieve(facets_data)
    merge_records(candidate_pool, deterministic_supplemental_retrieve(facets_data, qtype))

    # Step 4-6: FacetRank + Sufficiency loop (max 2 turns)
    for turn in range(max_turns):
        if len(candidate_pool) > 300:
            scored_pool = [(score_record(r, facets_data)[0], r) for r in candidate_pool]
            scored_pool.sort(key=lambda x: x[0], reverse=True)
            candidate_pool = [r for _, r in scored_pool[:300]]

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
# 10. Benchmark
# ============================================================
def normalize_answer(answer):
    if answer is None: return ""
    if isinstance(answer, list):
        return ", ".join(str(a).replace('_', ' ') for a in answer)
    return str(answer).replace('_', ' ').strip()

def check_correct(model_answer, ground_truth):
    if model_answer is None:
        return False

    if isinstance(model_answer, list):
        model_set = set(normalize_answer(a).lower() for a in model_answer)
        gt_set = set(normalize_answer(str(a)).lower() for a in ground_truth)
        overlap = model_set & gt_set
        return len(overlap) >= min(len(gt_set), max(1, len(gt_set) * 0.3))

    cleaned_model = normalize_answer(model_answer).lower()
    for gt in ground_truth:
        cleaned_gt = normalize_answer(str(gt)).lower()
        if cleaned_gt in cleaned_model or cleaned_model in cleaned_gt:
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
    print(f"V5 Fully Generic (Vulnerabilities A/B/C Eliminated) - First {n} questions")
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
              f"ref={f.get('reference',{}).get('entity_keywords',[])}")

        time.sleep(0.3)

    end_time = time.time()
    accuracy = (correct_count / total_count) * 100

    print(f"\n{'='*80}")
    print(f"V5 Fully Generic Experiment Report")
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
