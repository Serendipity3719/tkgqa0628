import math
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class SemanticCluster:
    """Stable ontology-like routing unit for Phase 3 semantic navigation."""

    cluster_id: str
    name: str
    description: str
    entity_type_hints: List[str]
    relation_family_hints: List[str]
    keywords: List[str]
    parent_domain: str
    routing_policy: str
    entity_aliases: List[str] = None
    relation_aliases: List[str] = None

    @property
    def slug(self) -> str:
        return f"{self.cluster_id}_{self.name}"

    def entity_signals(self) -> List[str]:
        return _clean_signal_list(self.entity_type_hints, self.keywords, self.entity_aliases or [])

    def relation_signals(self) -> List[str]:
        return _clean_signal_list(self.relation_family_hints, self.keywords, self.relation_aliases or [])


SEMANTIC_CLUSTERS: List[SemanticCluster] = [
    SemanticCluster(
        cluster_id="cluster_001",
        name="geopolitical_entities",
        description="Countries, states, territories, regions, cities, and geopolitical actor nodes used as KG anchors.",
        entity_type_hints=["country", "state", "region", "city", "province", "territory", "republic", "kingdom"],
        relation_family_hints=["diplo_relations", "visit", "meet_negotiate"],
        keywords=["country", "state", "region", "city", "border", "territory", "geopolitical"],
        parent_domain="Politics",
        routing_policy="Reduces entity search from the global catalog to sovereign, regional, and geographic actor candidates.",
        entity_aliases=[
            "united states", "us", "usa", "china", "russia", "iran", "iraq", "sudan", "cyprus",
            "israel", "palestine", "syria", "turkey", "thailand", "mongolia", "ethiopia",
            "peru", "kazakhstan", "cambodia", "denmark", "taiwan", "india", "pakistan",
        ],
        relation_aliases=["diplomatic relations", "visit", "negotiate"],
    ),
    SemanticCluster(
        cluster_id="cluster_002",
        name="government_institutions",
        description="Government bodies, ministries, cabinets, parliaments, embassies, and state administrative organizations.",
        entity_type_hints=["government", "ministry", "department", "cabinet", "parliament", "embassy", "council"],
        relation_family_hints=["leadership_policy", "statement_comment", "appeal_request", "demand"],
        keywords=["government", "ministry", "department", "cabinet", "parliament", "official", "administration"],
        parent_domain="Politics",
        routing_policy="Narrows entity candidates to institutional state actors before relation or temporal drill-down.",
        entity_aliases=["foreign ministry", "defense ministry", "security ministry", "head of government"],
        relation_aliases=["request", "appeal", "demand", "policy", "statement"],
    ),
    SemanticCluster(
        cluster_id="cluster_003",
        name="political_leadership",
        description="Heads of state, heads of government, ministers, presidents, party leaders, and senior officials.",
        entity_type_hints=["president", "minister", "leader", "governor", "ambassador", "secretary", "official"],
        relation_family_hints=["leadership_policy", "visit", "meet_negotiate", "statement_comment"],
        keywords=["president", "minister", "leader", "ambassador", "official", "head of government"],
        parent_domain="Politics",
        routing_policy="Routes person or role-like actor questions into leadership candidates instead of all entities.",
        entity_aliases=["prime minister", "head of state", "head of government"],
        relation_aliases=["meet", "negotiate", "visit", "comment"],
    ),
    SemanticCluster(
        cluster_id="cluster_004",
        name="military_security_actors",
        description="Military forces, police, defense ministries, security services, armed groups, and combatant actors.",
        entity_type_hints=["military", "army", "police", "defense", "security", "combatant", "forces"],
        relation_family_hints=["mobilize_military", "military_force", "arrest_detain", "threaten"],
        keywords=["military", "army", "police", "defense", "security", "combatant", "force"],
        parent_domain="Military",
        routing_policy="Reduces search to coercive and security actors for force, mobilization, arrest, and defense questions.",
        entity_aliases=["armed forces", "security forces", "defence", "military personnel"],
        relation_aliases=["mobilize", "military force", "arrest", "detain", "threaten"],
    ),
    SemanticCluster(
        cluster_id="cluster_005",
        name="diplomatic_events",
        description="Visits, hosting, meetings, negotiations, consultations, mediation, and diplomatic relation changes.",
        entity_type_hints=["embassy", "foreign ministry", "diplomat", "ambassador"],
        relation_family_hints=["visit", "receive_host", "mediate", "meet_negotiate", "consult", "diplo_relations"],
        keywords=["visit", "host", "meet", "negotiate", "consult", "mediate", "diplomatic"],
        parent_domain="Diplomacy",
        routing_policy="Routes relation-first questions into diplomatic relation families before selecting entities or years.",
        relation_aliases=["visited", "hosted", "meeting", "negotiation", "consultation", "diplomacy"],
    ),
    SemanticCluster(
        cluster_id="cluster_006",
        name="conflict_violence_events",
        description="Armed conflict, attacks, conventional force, threats, coercion, occupation, killings, and violent incidents.",
        entity_type_hints=["military", "armed", "rebel", "combatant", "security"],
        relation_family_hints=["military_force", "threaten", "mobilize_military", "reject_refuse"],
        keywords=["conflict", "attack", "force", "threat", "violence", "armed", "occupation"],
        parent_domain="Military",
        routing_policy="Reduces relation search to conflict and force families, useful when the query predicate is violent or coercive.",
        relation_aliases=["war", "fight", "assault", "bomb", "kill", "attack", "armed force"],
    ),
    SemanticCluster(
        cluster_id="cluster_007",
        name="legal_judicial_actions",
        description="Courts, lawsuits, investigations, arrests, detentions, charges, judicial actions, and legal restrictions.",
        entity_type_hints=["court", "judge", "judicial", "law", "police", "prosecutor"],
        relation_family_hints=["lawsuit_legal", "investigate", "arrest_detain"],
        keywords=["court", "lawsuit", "legal", "judicial", "investigate", "arrest", "detain"],
        parent_domain="Legal",
        routing_policy="Filters legal and enforcement questions to judicial actors and legal-action relation families.",
        relation_aliases=["charged", "trial", "sue", "sued", "investigation", "detention"],
    ),
    SemanticCluster(
        cluster_id="cluster_008",
        name="economic_financial_flows",
        description="Economic activity, material cooperation, companies, banks, trade, investment, financial flows, and resources.",
        entity_type_hints=["company", "bank", "finance", "economic", "trade", "business"],
        relation_family_hints=["material_economic", "cooperate", "sign_agreement"],
        keywords=["economic", "financial", "bank", "trade", "investment", "material", "company"],
        parent_domain="Economy",
        routing_policy="Constrains search to economic entities and exchange-like relation families for financial or trade predicates.",
        relation_aliases=["finance", "flow", "flows", "invest", "investment", "trade", "economic aid"],
    ),
    SemanticCluster(
        cluster_id="cluster_009",
        name="aid_humanitarian_support",
        description="Aid provision, humanitarian assistance, peacekeeping support, asylum, protection, and relief-oriented actions.",
        entity_type_hints=["aid", "humanitarian", "relief", "peacekeeping", "asylum"],
        relation_family_hints=["aid", "praise_support", "cooperate"],
        keywords=["aid", "humanitarian", "support", "relief", "asylum", "peacekeeping", "protection"],
        parent_domain="Humanitarian",
        routing_policy="Narrows relation search to aid and support families, especially for provider-recipient questions.",
        relation_aliases=["help", "assist", "assistance", "provide aid", "humanitarian aid"],
    ),
    SemanticCluster(
        cluster_id="cluster_010",
        name="protest_civil_unrest",
        description="Protests, demonstrations, riots, strikes, boycotts, dissent, opposition rallies, and civil unrest.",
        entity_type_hints=["protester", "opposition", "civil", "party", "movement"],
        relation_family_hints=["protest_dissent", "criticize_accuse", "reject_refuse"],
        keywords=["protest", "demonstration", "riot", "strike", "boycott", "dissent", "opposition"],
        parent_domain="Society",
        routing_policy="Routes unrest questions to protest and dissent relation families before entity matching.",
        relation_aliases=["demonstrate", "rally", "civil unrest", "boycotted"],
    ),
    SemanticCluster(
        cluster_id="cluster_011",
        name="international_organizations",
        description="International organizations, supranational bodies, UN-related entities, alliances, and multilateral institutions.",
        entity_type_hints=["united nations", "security council", "organization", "organisation", "alliance"],
        relation_family_hints=["mediate", "aid", "diplo_relations", "statement_comment"],
        keywords=["united nations", "security council", "international", "organization", "alliance", "multilateral"],
        parent_domain="International",
        routing_policy="Limits entity search to multilateral actors when queries mention institutional international bodies.",
        entity_aliases=["un", "u.n.", "nato", "european union", "african union"],
        relation_aliases=["mediate", "peacekeeping", "multilateral"],
    ),
    SemanticCluster(
        cluster_id="cluster_012",
        name="public_statements_and_media",
        description="Statements, comments, acknowledgements, denials, apologies, accusations, criticism, praise, and public messaging.",
        entity_type_hints=["spokesman", "spokesperson", "media", "press", "official"],
        relation_family_hints=["statement_comment", "criticize_accuse", "praise_support"],
        keywords=["statement", "comment", "deny", "apologize", "criticize", "accuse", "praise"],
        parent_domain="Communication",
        routing_policy="Reduces predicate search to speech-act relation families when the query is about public communication.",
        relation_aliases=["said", "says", "told", "announced", "denied", "apologized", "criticized", "accused"],
    ),
    SemanticCluster(
        cluster_id="cluster_013",
        name="agreements_and_cooperation",
        description="Formal agreements, accords, cooperation, collaboration, ceasefires, settlements, and negotiated commitments.",
        entity_type_hints=["government", "ministry", "organization", "party"],
        relation_family_hints=["sign_agreement", "cooperate", "meet_negotiate"],
        keywords=["agreement", "accord", "cooperate", "collaborate", "settle", "ceasefire", "truce"],
        parent_domain="Diplomacy",
        routing_policy="Routes agreement and cooperation predicates to compact relation families and likely institutional actors.",
        relation_aliases=["signed", "sign", "cooperation", "collaboration", "settlement"],
    ),
    SemanticCluster(
        cluster_id="cluster_014",
        name="sanctions_and_coercive_policy",
        description="Sanctions, embargoes, blockades, boycotts, demands, ultimatums, coercion, rejection, and policy pressure.",
        entity_type_hints=["government", "ministry", "state", "council"],
        relation_family_hints=["sanction_embargo", "demand", "threaten", "reject_refuse"],
        keywords=["sanction", "embargo", "blockade", "boycott", "demand", "ultimatum", "coerce"],
        parent_domain="Politics",
        routing_policy="Narrows policy-pressure questions to coercive relation families and state-level actors.",
        relation_aliases=["sanctions", "sanctioned", "embargoed", "blocked", "pressure"],
    ),
    SemanticCluster(
        cluster_id="cluster_015",
        name="residual_other",
        description="Fallback cluster for entities or relation families not yet covered by the static Phase 3 taxonomy.",
        entity_type_hints=[],
        relation_family_hints=["other", "yield_concede", "express_intent"],
        keywords=[],
        parent_domain="Other",
        routing_policy="Keeps uncovered KG units reachable while preserving a uniform semantic cluster schema.",
    ),
]


SEMANTIC_CLUSTER_BY_ID: Dict[str, SemanticCluster] = {c.cluster_id: c for c in SEMANTIC_CLUSTERS}
SEMANTIC_CLUSTER_BY_NAME: Dict[str, SemanticCluster] = {c.name: c for c in SEMANTIC_CLUSTERS}
FALLBACK_CLUSTER_ID = "cluster_015"

MATCH_WEIGHTS = {
    "entity_type_hints": 3.0,
    "relation_family_hints": 4.0,
    "keywords": 1.5,
    "entity_aliases": 4.0,
    "relation_aliases": 3.0,
    "parent_domain": 0.75,
    "cluster_name": 0.5,
}

TEMPORAL_OPERATOR_HINTS = {
    "first": ["first", "earliest", "initial"],
    "last": ["last", "latest", "most recent"],
    "before": ["before", "prior to", "earlier than"],
    "after": ["after", "following", "later than"],
    "equal": ["same day", "same month", "same year", "in which year", "when did"],
}


def semantic_cluster_dirname(cluster: SemanticCluster) -> str:
    return cluster.slug


def iter_semantic_clusters() -> Iterable[SemanticCluster]:
    return tuple(SEMANTIC_CLUSTERS)


def cluster_for_id(cluster_id: str) -> SemanticCluster:
    return SEMANTIC_CLUSTER_BY_ID.get(cluster_id, SEMANTIC_CLUSTER_BY_ID[FALLBACK_CLUSTER_ID])


def semantic_cluster_tsv_rows() -> List[tuple]:
    return [
        (
            c.cluster_id,
            c.name,
            c.parent_domain,
            c.description,
            " ".join(c.entity_type_hints),
            " ".join(c.relation_family_hints),
            " ".join(c.keywords),
            c.routing_policy,
        )
        for c in SEMANTIC_CLUSTERS
    ]


def _clean_signal_list(*groups: Optional[List[str]]) -> List[str]:
    out = []
    seen = set()
    for group in groups:
        for item in group or []:
            val = str(item).strip().lower().replace("_", " ")
            if val and val not in seen:
                seen.add(val)
                out.append(val)
    return out


RELATION_FAMILY_ALIASES = {
    c.cluster_id: _clean_signal_list(c.relation_family_hints, c.relation_aliases or [])
    for c in SEMANTIC_CLUSTERS
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).replace("_", " ").lower()).strip()


def signal_match_score(text: str, signals: List[str], weight: float) -> float:
    haystack = normalize_text(text)
    score = 0.0
    for signal in signals:
        needle = normalize_text(signal)
        if not needle:
            continue
        if " " in needle:
            if needle in haystack:
                score += weight * (1.0 + min(len(needle.split()) - 1, 3) * 0.15)
        else:
            if re.search(rf"\b{re.escape(needle)}s?\b", haystack):
                score += weight
    return score


def cluster_lexical_scores(text: str, *, include_entity=True, include_relation=True) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for cluster in SEMANTIC_CLUSTERS:
        score = 0.0
        if include_entity:
            score += signal_match_score(text, cluster.entity_type_hints, MATCH_WEIGHTS["entity_type_hints"])
            score += signal_match_score(text, cluster.entity_aliases or [], MATCH_WEIGHTS["entity_aliases"])
        if include_relation:
            score += signal_match_score(text, cluster.relation_family_hints, MATCH_WEIGHTS["relation_family_hints"])
            score += signal_match_score(text, cluster.relation_aliases or [], MATCH_WEIGHTS["relation_aliases"])
        score += signal_match_score(text, cluster.keywords, MATCH_WEIGHTS["keywords"])
        score += signal_match_score(text, [cluster.parent_domain], MATCH_WEIGHTS["parent_domain"])
        score += signal_match_score(text, [cluster.name], MATCH_WEIGHTS["cluster_name"])
        if score > 0:
            scores[cluster.cluster_id] = round(score, 4)
    return scores


def normalize_scores(scores: Dict[str, float]) -> Dict[str, float]:
    if not scores:
        return {}
    total = sum(math.exp(v) for v in scores.values())
    return {k: round(math.exp(v) / total, 6) for k, v in scores.items()}


def rank_cluster_scores(scores: Dict[str, float], top_k: Optional[int] = None) -> List[Tuple[SemanticCluster, float]]:
    ranked = sorted(
        ((cluster_for_id(cid), score) for cid, score in scores.items()),
        key=lambda item: (-item[1], item[0].cluster_id),
    )
    return ranked[:top_k] if top_k else ranked


def embedding_cluster_scores(text: str) -> Dict[str, float]:
    """Optional semantic hook; returns empty scores when embedding dependencies are absent."""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
    except Exception:
        return {}

    model = SentenceTransformer("all-MiniLM-L6-v2")
    query_vec = model.encode([normalize_text(text)], normalize_embeddings=True)[0]
    scores = {}
    for cluster in SEMANTIC_CLUSTERS:
        doc = " ".join([
            cluster.name,
            cluster.description,
            " ".join(cluster.entity_signals()),
            " ".join(cluster.relation_signals()),
            cluster.parent_domain,
        ])
        vec = model.encode([doc], normalize_embeddings=True)[0]
        sim = float(np.dot(query_vec, vec))
        if sim > 0:
            scores[cluster.cluster_id] = round(sim, 4)
    return scores


def combined_cluster_scores(text: str, mode: str = "lexical", *, include_entity=True,
                            include_relation=True) -> Dict[str, float]:
    mode = (mode or "lexical").lower()
    lexical = cluster_lexical_scores(text, include_entity=include_entity, include_relation=include_relation)
    if mode == "lexical":
        return lexical

    embedding = embedding_cluster_scores(text)
    if mode == "embedding":
        return embedding or lexical

    if mode == "hybrid":
        if not embedding:
            return lexical
        merged = dict(lexical)
        for cid, score in embedding.items():
            merged[cid] = round(merged.get(cid, 0.0) + score * 2.0, 4)
        return merged
    return lexical


def assign_entity_to_semantic_cluster(entity_name: str, mode: str = "lexical") -> SemanticCluster:
    scores = combined_cluster_scores(entity_name, mode, include_entity=True, include_relation=False)
    ranked = rank_cluster_scores(scores, top_k=1)
    return ranked[0][0] if ranked else SEMANTIC_CLUSTER_BY_ID[FALLBACK_CLUSTER_ID]


def relation_family_semantic_clusters(family: str, mode: str = "lexical", top_k: int = 3) -> List[SemanticCluster]:
    scores = combined_cluster_scores(family, mode, include_entity=False, include_relation=True)
    ranked = rank_cluster_scores(scores, top_k=top_k)
    return [cluster for cluster, _score in ranked] or [SEMANTIC_CLUSTER_BY_ID[FALLBACK_CLUSTER_ID]]


def extract_temporal_candidates(text: str) -> List[str]:
    q = normalize_text(text)
    out = []
    out.extend(re.findall(r"(?:19|20)\d{2}", q))
    for op, signals in TEMPORAL_OPERATOR_HINTS.items():
        if any(signal in q for signal in signals):
            out.append(op)
    return list(dict.fromkeys(out))
