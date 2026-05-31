
"""
Before_after Root Cause Analysis Summary for V7 fixes.

Based on KB analysis, here are the precise root causes and required fixes:

=== FIXABLE (15+ questions) ===

FIX M: Exact Subject Match for entity-list output (before_after, equal, etc.)
  Problem: When subj_kws=['malaysia'], current code retrieves records where 'malaysia'
  appears ANYWHERE in subject, including 'Foreign Affairs (Malaysia)', 'Police (Malaysia)' etc.
  This creates FP entities from compound entities acting on behalf of the country.
  Fix: In before_after/equal entity-list output, when subj_kws is a simple country name,
  filter to EXACT subj match (or at least "standalone" match where subj == country_name exactly).
  Affected: Q8, Q18, Q29, Q34, Q46, Q47, Q50, Q60, Q65, Q75, Q78, Q83, Q93, Q95, Q98

FIX N: Object-context-aware Reference Time Anchor for before_after
  Problem: For "X before/after REF_ENTITY", the solver finds t_ref by searching
  any record of REF_ENTITY, regardless of whether it matches the question's OBJ.
  For Q93: "before Zawahiri", Zawahiri has 17 criticize records but only 1 criticizes
  Citizen(Saudi Arabia). The solver should find t_ref by searching REF_ENTITY + OBJ,
  falling back to REF_ENTITY + REL, and only as last resort to just REF_ENTITY.
  
  CORRECT ALGORITHM:
  1. Find ref_recs = search(ref_kws + rel_kws + obj_kws)  -> most specific
  2. Fallback: search(ref_kws + rel_kws)
  3. Fallback: search(ref_kws) (any records)
  Use t_ref from the MOST SPECIFIC search that returns results.
  Affected: Q8, Q18, Q29, Q34, Q37, Q42, Q47, Q50, Q60, Q75, Q78, Q83, Q93, Q95, Q98

FIX O: Fix "small arms" / "conventional military" / "accuse" relation mapping in LLM prompt
  Problem: Q12/Q14/Q46/Q98/Q83 get wrong relations because LLM is outputting wrong rel_kws.
  - "small arms" -> LLM outputs ["conventional military", ...] instead of ["small arms"]
  - "study" -> no KB relation exists; should use ["investigate"]
  - "accuse" -> should match "Accuse", not "Accuse of X" variants when unspecified
  Fix: Improve LLM prompt with better relation mapping, especially for:
  - "attacked with small arms" -> ["small arms"]
  - "study/research/investigate" -> ["investigate"]
  - passive voice with "accused by" -> ["accuse"]
  - "conventional military force/forces" -> ["conventional military"]
  These should also be handled by post_process_facets() as a rule-based fallback
  when LLM gets them wrong.

FIX P: Solve "exact OBJ entity" filter in before_after
  Problem: Q12 truth=['Al-Shabaab','Military(Burundi)'] but we retrieve all records
  where 'burundi' appears in OBJ (including Rebel Group(Burundi), Criminal(Burundi)).
  The question says "made Burundi suffer" = the OBJ must BE "Burundi" exactly.
  Fix: When obj_kws is a simple country name (single word), prefer exact match on OBJ
  field (r['obj'].lower() == country) over substring match.
  Affected: Q12, Q14, Q46, Q60, Q83, Q98
  
=== NOT FIXABLE WITHOUT SCHEMA CHANGE ===

FIX Q75: Cannot solve perfectly
  Q75: "Who negotiated with the Thai military after Thailand?"
  KB shows: The correct ref is "Thailand's last negotiate with Military(Thailand)" = 2014-05-24
  After that, only 4 records match (Worachai, Foreign Affairs Malaysia, Jatuporn, Thailand)
  But truth = [NUFDD, Abhisit, Worachai, Protester(Thailand)] which spans 2009-2014
  This question seems to require a DIFFERENT interpretation than our current schema.
  The "after Thailand" may mean: show ALL who negotiated with Thai military AFTER
  Thailand became the "first" entity to do so (i.e., reference = first occurrence).
  This is Q75 specific and hard to generalize.
"""
print("Root cause summary written. Proceed to implement V7.")
FIXES = {
    'M': 'Exact subject match for entity-list output (prevent FP from compound entities)',
    'N': 'Object-context-aware ref time anchor (find t_ref using most specific search)',
    'O': 'Relation keyword mapping rules in LLM prompt + post_process_facets() fallback',
    'P': 'Exact OBJ match when obj_kws is simple country name',
}
for k, v in FIXES.items():
    print(f"Fix {k}: {v}")
