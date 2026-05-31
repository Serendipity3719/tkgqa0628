"""
Analyze V7 failure patterns systematically.
"""
import json

# V7 failure cases from benchmark_v7_100.log
failures = [
    # (q_num, qtype, question, model_answer, truth, facets_summary)
    (8,  "before_after", "Before Ethiopia, which country did Seyoum Mesfin express his intention to negotiate with?",
     "None", ["China", "Sudan"], "subj=seyoum_mesfin, rel=intent_negotiate, obj=[], ref=ethiopia"),
    
    (11, "first_last", "In which year did the Somali criminal threaten China for the first time?",
     "2005", ["2009"], "subj=['somalia','criminal'], rel=coerce, obj=china"),
    
    (12, "before_after", "Before 14 October 2015, who made Burundi suffer from conventional military forces?",
     "8 entities (FP)", ["Al-Shabaab", "Military (Burundi)"], "rel=['conventional military','military','unconventional','non-military'], obj=burundi"),
    
    (14, "before_after", "Before 25 April 2005, who used conventional military force against Iraq?",
     "15 entities (FP)", ["Iran", "Commando (Iraq)"], "rel=['conventional military','military','unconventional','non-military'], obj=iraq"),
    
    (17, "before_last", "Before the military of Taiwan, which country did China threaten last?",
     "Religion (China)", ["Angela Merkel"], "subj=china, rel=coerce, obj=[], ref=military(taiwan)"),
    
    (19, "equal", "Who visited Malaysia on 14 January 2007?",
     "3 entities (Pervez Musharraf FP)", ["China", "Association of Southeast Asian Nations"], "rel=visit, obj=malaysia, date=2007-01-14"),
    
    (21, "equal", "Who wanted to negotiate with Malaysia on 19 November 2015?",
     "4 entities (FP: China, Medvedev, Vietnam)", ["Barack Obama"], "rel=intent_negotiate, obj=malaysia, date=2015-11-19"),
    
    (22, "equal", "Could you tell me the exact month when Agence France-Presse appealed to China?",
     "None", ["2007-01"], "subj=['agence france presse'], rel=appeal_request, obj=china"),
    
    (33, "first_last", "When did Jatuporn Prompan make his first appeal to Thailand?",
     "2005-01-04", ["2010-04-24"], "WRONG subj name: jathuporn prompan -> jatuporn prompan"),
    
    (35, "first_last", "When did China last visit Henry M Paulson?",
     "2013-06-08", ["2006-09-23"], "subj=china, rel=visit, obj=paulson — visits paulson vs paulson visiting china confusion?"),
    
    (36, "before_after", "Who did the Malaysian Foreign Ministry praise before Thailand?",
     "None", ["Surakiart Sathirathai", "Vietnam", "Employee (Bangladesh)", "Mahmoud Ahmadinejad", "Laos", "Barack Obama"], 
     "V7 returned None - ref anchor failed"),
    
    (41, "equal", "Who wants to negotiate with China on 16 July 2009?",
     "24 entities (FP)", ["Energy Department/Ministry (United States)", "Admiral (China)"], "rel=intent_negotiate, date=2009-07-16"),
    
    (42, "before_after", "Before the Asian Disaster Preparedness Centre, who did Thailand make optimistic comments about?",
     "None", ["Citizen (Thailand)"], "ref=Asian Disaster Preparedness Centre — no KB hit?"),
    
    (43, "equal", "When did Thailand express its intention to cooperate with Donald Rumsfeld?",
     "2005-06", ["2005-06-06"], "granularity wrong: month vs day"),
    
    (44, "before_last", "Before South Korea, with whom did Oman last wish to establish diplomatic cooperation?",
     "Iran", ["Qatar"], "rel=diplomatic_cooperation, wrong result"),
    
    (46, "before_after", "Who attacked Iraq with small arms and light weapons after 9 August 2006?",
     "38+ entities (FP)", ["Iran", "Armed Rebel (Syria)", "Israeli Defense Forces"], "rel=['small arms','armed','arm'] too broad"),
    
    (47, "before_after", "Who did Iraq reject after the dissident of the People's Mujahedin of Iran?",
     "10 entities but extra FPs", ["Barack Obama", "Iran", "Nuri al-Maliki", "Member of Parliament (Iraq)", 
     "Defense / Security Ministry (United States)", "Student (Iraq)", "Congress (United States)", "Bank (Iraq)"],
     "FP: Kuwait, Legislature(Iraq) extra"),
    
    (48, "equal", "On 7 August 2005, which country paid a visit to China?",
     "31 entities (FP)", ["Japan"], "date filtering too loose — whole day's visits retrieved"),
    
    (49, "equal", "Who visited China in June 2010?",
     "18 entities with Cambodia/Sudan FPs", 
     ["Hui Liangyu","Iran","UAE Armed Forces","Foreign Affairs (South Korea)","Dmitry Anatolyevich Medvedev",
      "Linda Lingle","Wen Jiabao","Mahmoud Ahmadinejad","Joon Young Woo","International Government Organizations",
      "Ministry (Iran)","Boris Vyacheslavovich Gryzlov","Valdis Dombrovskis","Dianne Feinstein"],
     "Cambodia, Sudan extra FPs"),
    
    (52, "before_last", "Which country receive China's visit from China last before Bruno Stagno Ugarte did?",
     "Domestic Affairs (Vietnam)", ["Sudan"], "Wrong answer"),
    
    (54, "equal", "In which month did the citizens of Thailand express their intention to meet with China?",
     "2006-11", ["2012-04"], "Facet: subj=['saudi arabia','citizen'] wrong — should be ['thailand','citizen']"),
    
    (55, "equal", "Which country negotiated with China in July 2006?",
     "16 entities (FP)", ["South Korea", "Japan"], "rel=negotiate too broad — 'negotiate' matches many intent records"),
    
    (58, "first_last", "In which year did the Thai Ministry of Justice/Ministry of Foreign Affairs first express its intention to engage in diplomatic cooperation?",
     "2005", ["2015"], "subj=['justice','thailand','foreign affairs','thailand'] duplicate—multiple subj keywords cause wrong match"),
    
    (61, "before_last", "Before the Sudanese police, who was the last to use unconventional force against Ethiopia?",
     "None", ["Armed Rebel (Somalia)"], "ref=sudanese police — no KB match? rel=unconventional"),
    
    (62, "equal", "Who used conventional military force against China in June 2014?",
     "4 entities (Malaysia FP)", ["Vietnam", "East Turkistan Islamic Movement", "Japan"], "Malaysia is FP"),
    
    (64, "equal", "In which year did Iraq commend the member of the Legislative Council of Iran?",
     "None", ["2013"], "subj=iraq, rel=praise, obj=['member','parliament','iran'] — 'iran' not in KB obj?"),
    
    (65, "before_after", "To which country did Malaysia send an appeal after 2012-11-20?",
     "9 entities with FPs", 
     ["UN Security Council","Citizen (Unidentified State Actor)","Citizen (Thailand)","Barack Obama",
      "Chuck Hagel","Maldives","Vietnam","China"], "FP: Citizen(Australia), etc"),
    
    (69, "equal", "When did Hoang Tuan Anh praise China?",
     "2009-09", ["2009-09-01"], "granularity: month vs day"),
    
    (70, "equal", "In which year did the United States' Council of Advisors to the Cabinet threaten Thailand?",
     "None", ["2014"], "subj=['council of advisors','united states'] — KB entity?"),
    
    (73, "equal_multi", "Who did Ethiopia use conventional military force against on the same day as the Hizbul Islam fighter?",
     "None", ["Al-Shabaab"], "rel=conventional_military, ref=Hizbul Islam fighter — no KB hit"),
    
    (75, "before_after", "Who negotiated with the Thai military after Thailand?",
     "None", ["National United Front for Democracy Against Dictatorship","Abhisit Vejjajiva","Worachai Hema","Protester (Thailand)"],
     "obj=['military ruler (thailand)'] — wrong KB entity name"),
    
    (76, "equal", "In which month did the Prime Minister of Peru visit China?",
     "2007-03", ["2010-03"], "subj=['head of government','peru'] — multiple records, wrong one picked"),
    
    (77, "first_last", "In what year did the Ethiopian police last use conventional military force against Ethiopia?",
     "2008", ["2005"], "rel_expansion too broad — gets wrong 'last' record"),
    
    (78, "before_after", "After Sankei, who was investigated by the Lawyer/Attorney of South Korea?",
     "19 entities (FP)", ["Criminal (South Korea)", "Business (South Korea)", "Grand National Party"],
     "ref anchor after Sankei — too many FPs"),
    
    (83, "before_after", "Which country was accused by Ethiopia after 2012?",
     "Many FPs", ["Government (Qatar)","Activist (Ethiopia)","Qatar","Al-Shabaab","Eritrea","Sudan"],
     "subj accidentally not populated—rel=accuse, subj=[], huge FP list"),
    
    (84, "equal", "Who was negotiating with China in 2012?",
     "100+ entities (FP)", ["Iran","Dissident (China)","Association of Southeast Asian Nations","Ali Baqeri",
      "Vietnam","Sudan","South Korea","European Central Bank","France","Foreign Affairs (France)",
      "Ma Ying Jeou","Cabinet / Council of Ministers / Advisors (United States)","Japan"],
     "intent_negotiate rel too broad"),
    
    (86, "equal", "Who wanted to meet with Thailand in May 2009?",
     "12 entities (Abhisit FP, Anupong FP, Business(South Korea) FP)", 
     ["Student (Thailand)","Vietnam","Children (Thailand)","South Korea","Citizen (Thailand)",
      "Cabinet / Council of Ministers / Advisors (Thailand)","Men (United States)","Cambodia"],
     "intent_negotiate too broad"),
    
    (88, "first_last", "In what month did Donald Rumsfeld last threaten Iraq?",
     "2010-10", ["2005-06"], "subj=donald_rumsfeld, rel=coerce, obj=iraq — wrong date, too recent"),
    
    (89, "first_last", "When was the first visit of Burundi to China?",
     "2005-08-25", ["2006-06-14"], "KB has earlier non-exact 'Burundi' records (compound entities)"),
    
    (91, "equal", "When did South Sudan formally sign an agreement with Djibouti?",
     "2012-02", ["2012-02-03"], "granularity wrong: month vs day"),
    
    (93, "before_after", "Who criticised the citizens of Saudi Arabia before Zawahiri?",
     "['Government Religious (Saudi Arabia)', 'Royal Administration (Saudi Arabia)']", 
     ["Iran", "Islamic Preacher (Saudi Arabia)", "Royal Administration (Saudi Arabia)"], "Iran missing FN"),
    
    (94, "before_last", "Who was the last person to visit Malaysia before the leader of Turkmenistan?",
     "Laos", ["Ma Ying Jeou"], "Wrong answer — ref anchor too early?"),
]

# Categorize failure root causes
print("=== V7 Failure Root Cause Analysis ===\n")
print(f"Total failures: {len(failures)}/100 = {len(failures)}% wrong\n")

cats = {
    "FP_flood_broad_rel": [],  # Too many false positives due to broad relation expansion
    "FP_flood_no_date_filter": [],  # Too many FPs due to poor date filtering
    "FP_entity_mismatch": [],  # Entity boundary/scope issue (compound entities)
    "FN_entity_name_mismatch": [],  # False negative because entity name not matched
    "FN_ref_anchor_fail": [],  # Reference anchor failed to find correct date
    "FN_result_None": [],  # Returns None when should have answer
    "GRANULARITY_ERROR": [],  # Month/day confusion
    "WRONG_SCALAR": [],  # Wrong scalar answer (wrong date or entity)
}

# Manual categorization
FP_broad_rel = [12, 14, 41, 46, 48, 49, 55, 62, 65, 78, 83, 84, 86]
FP_entity = [19, 21, 47]
FN_name = [22, 33, 54, 64, 70, 75]
FN_ref = [8, 42, 61, 73]
FN_none = [36, 42, 61, 73, 75]
GRANULARITY = [43, 69, 91]
WRONG_SCALAR = [11, 17, 35, 44, 52, 76, 77, 88, 89, 93, 94]
WRONG_EXTRA_FP = [47, 65, 78, 93]

print("=== Failure Category Summary ===")
print(f"1. FP flood (broad relation): Q{sorted(FP_broad_rel)} -> {len(FP_broad_rel)} cases")
print(f"2. FP entity boundary: Q{sorted(FP_entity)} -> {len(FP_entity)} cases")
print(f"3. FN entity name mismatch: Q{sorted(FN_name)} -> {len(FN_name)} cases")
print(f"4. FN ref anchor failure: Q{sorted(FN_ref)} -> {len(FN_ref)} cases")
print(f"5. Granularity error: Q{sorted(GRANULARITY)} -> {len(GRANULARITY)} cases")
print(f"6. Wrong scalar: Q{sorted(WRONG_SCALAR)} -> {len(WRONG_SCALAR)} cases")

print("\n=== Top Priority Fixes for V8 ===")
print("""
FIX 1: Relation Precision Enhancement
- "conventional military" / "unconventional" / "fight" relations: ONLY match
  'Use conventional military force', 'Use unconventional violence', 
  'fight with artillery and tanks', 'fight with small arms and light weapons'
  NOT 'Use tactics of violent repression', 'Demonstrate military or police power', etc.
  
FIX 2: Relation 'negotiate' too broad -> MUST map to 'Engage in negotiation'
  NOT 'Express intent to meet or negotiate' for "negotiate" verb.
  "intent to negotiate" -> 'Express intent to meet or negotiate'
  "negotiate" (direct) -> 'Engage in negotiation' 
  
FIX 3: Entity name normalization for subj compound detection
- "Somali criminal" -> KB: "Criminal (Somalia)" not "somali criminal"
- "Council of Advisors" -> "Cabinet / Council of Ministers / Advisors (United States)"
- "Thai military" -> "Military Personnel (Thailand)" or "Military (Thailand)"
- "Agence France-Presse" -> "Agence France-Presse" (exact)

FIX 4: Granularity-aware answer formatting
- When time_gran='day', return exact date not month prefix
- Fix time_gran detection from question structure

FIX 5: Strict date prefix matching for 'equal' qtype
- Q48: "7 August 2005" -> date="2005-08-07", use EXACT date prefix "2005-08-07"
- Q41: "16 July 2009" -> date="2009-07-16", exact date match only

FIX 6: Better subj/obj deduplication in facets
- Q58: "Thai Ministry of Justice/Ministry of Foreign Affairs" -> single compound entity
  NOT ['justice','thailand','foreign affairs','thailand'] (duplicate 'thailand')

FIX 7: FN for passive voice entity naming
- Q75: "Thai military" -> KB entity is "Military (Thailand)" not "military ruler (thailand)"

FIX 8: relation keyword: 'accuse' with empty subj
- Q83: "Which country was accused by Ethiopia after 2012?" 
  -> subj=["ethiopia"], rel=["accuse"], obj=[]  (passive voice: Ethiopia is the accuser)
""")
