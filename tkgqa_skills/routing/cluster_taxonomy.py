from dataclasses import dataclass
from typing import Dict, Iterable, List


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

    @property
    def slug(self) -> str:
        return f"{self.cluster_id}_{self.name}"


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


def assign_entity_to_semantic_cluster(entity_name: str) -> SemanticCluster:
    """Step 1 deterministic assignment; Step 2 can replace this with hybrid routing."""
    low = entity_name.replace("_", " ").lower()
    best = None
    best_score = 0
    for cluster in SEMANTIC_CLUSTERS:
        score = 0
        for hint in cluster.entity_type_hints:
            if hint and hint.lower() in low:
                score += 3
        for keyword in cluster.keywords:
            if keyword and keyword.lower() in low:
                score += 1
        if score > best_score:
            best = cluster
            best_score = score
    if best:
        return best

    tokens = [t for t in low.split() if t]
    if 1 <= len(tokens) <= 3:
        return SEMANTIC_CLUSTER_BY_ID["cluster_001"]
    return SEMANTIC_CLUSTER_BY_ID[FALLBACK_CLUSTER_ID]


def relation_family_semantic_clusters(family: str) -> List[SemanticCluster]:
    hits = [c for c in SEMANTIC_CLUSTERS if family in c.relation_family_hints]
    return hits or [SEMANTIC_CLUSTER_BY_ID[FALLBACK_CLUSTER_ID]]
