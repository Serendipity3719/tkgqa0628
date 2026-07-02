"""NPL-driven tree navigator with drill-down and backtracking execution.

Phase 5 Step 2 moves navigation decisions out of ad-hoc branch heuristics and
into the Navigation Policy Layer.  This module is intentionally defensive
around the exact schema implementation: Step 1 may expose dataclasses,
Pydantic models, or plain classes, so construction and serialization are kept
schema-aware but loosely coupled.
"""

from __future__ import annotations

import inspect
import json
import re
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


try:
    from tkgqa_skills.policy.navigation_policy import NavigationPolicy as NavigationPolicyEngine
    from tkgqa_skills.policy.policy_schema import DecisionTrace, PolicyDecision, PolicyInput
except Exception:  # pragma: no cover - compatibility for package layouts.
    try:
        from tkgqa_skills.policy import DecisionTrace, NavigationPolicyEngine, PolicyDecision, PolicyInput
    except Exception:  # pragma: no cover - local fallback keeps this module importable.
        NavigationPolicyEngine = None  # type: ignore
        PolicyDecision = None  # type: ignore
        PolicyInput = None  # type: ignore
        DecisionTrace = None  # type: ignore


class NavigationBranchError(RuntimeError):
    """Raised when a single semantic cluster branch cannot be drilled down."""

    def __init__(self, trigger: str, message: str, cluster_id: Optional[str] = None) -> None:
        super().__init__(message)
        self.trigger = trigger
        self.cluster_id = cluster_id


@dataclass
class NavigationBinding:
    """Concrete tree binding found by the navigator."""

    cluster_id: str
    entity: str
    time_slice: str
    source_path: str
    score: float
    preview: str = ""


@dataclass
class NavigationResult:
    """Stable return shape for downstream QA stages and smoke tests."""

    success: bool
    query: str
    decision: Dict[str, Any]
    trace: Any
    binding: Optional[NavigationBinding] = None
    selected_cluster: Optional[str] = None
    inspected_clusters: List[str] = field(default_factory=list)
    fallback_reason: Optional[str] = None
    candidate_paths: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "success": self.success,
            "query": self.query,
            "decision": self.decision,
            "trace": _to_plain(self.trace),
            "binding": _to_plain(self.binding),
            "selected_cluster": self.selected_cluster,
            "inspected_clusters": self.inspected_clusters,
            "fallback_reason": self.fallback_reason,
            "candidate_paths": self.candidate_paths,
        }
        return payload


def _to_plain(value: Any) -> Any:
    if value is None:
        return None
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, Mapping):
        return {str(k): _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "__dict__"):
        return {k: _to_plain(v) for k, v in vars(value).items() if not k.startswith("_")}
    return value


def _construct(cls: Any, payload: Mapping[str, Any]) -> Any:
    if cls is None:
        return dict(payload)
    if hasattr(cls, "model_validate"):
        try:
            return cls.model_validate(dict(payload))
        except Exception:
            pass
    try:
        signature = inspect.signature(cls)
        accepted = {
            name
            for name, parameter in signature.parameters.items()
            if parameter.kind in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY)
        }
        return cls(**{k: v for k, v in payload.items() if k in accepted})
    except Exception:
        try:
            return cls(**dict(payload))
        except Exception:
            return dict(payload)


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _set_or_append_trace(trace: Any, field_name: str, item: Any) -> None:
    if isinstance(trace, dict):
        trace.setdefault(field_name, []).append(item)
        return
    current = getattr(trace, field_name, None)
    if current is None:
        try:
            setattr(trace, field_name, [item])
        except Exception:
            pass
        return
    try:
        current.append(item)
    except Exception:
        try:
            setattr(trace, field_name, list(current) + [item])
        except Exception:
            pass


def _set_trace_value(trace: Any, field_name: str, value: Any) -> None:
    if isinstance(trace, dict):
        trace[field_name] = value
        return
    try:
        setattr(trace, field_name, value)
    except Exception:
        pass


def _normalise_tokens(query: str) -> List[str]:
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", query.lower())
    stop = {
        "the",
        "a",
        "an",
        "of",
        "in",
        "on",
        "for",
        "to",
        "and",
        "or",
        "what",
        "which",
        "who",
        "when",
        "where",
        "is",
        "are",
        "was",
        "were",
        "请问",
        "什么",
        "哪个",
        "时候",
    }
    return [token for token in tokens if token and token not in stop]


def _score_text(text: str, tokens: Sequence[str]) -> float:
    haystack = text.lower()
    if not tokens:
        return 0.0
    hits = sum(1 for token in tokens if token in haystack)
    phrase_bonus = 0.25 if " ".join(tokens[: min(4, len(tokens))]) in haystack else 0.0
    return hits / max(len(tokens), 1) + phrase_bonus


class NavigationPolicyNavigator:
    """Execute NPL drill-down plans over the local TKG tree."""

    def __init__(
        self,
        knowledge_root: Optional[str | Path] = None,
        policy_engine: Optional[Any] = None,
        inspect_k: int = 2,
    ) -> None:
        self.knowledge_root = Path(knowledge_root or ".").resolve()
        self.inspect_k = max(2, int(inspect_k))
        if policy_engine is not None:
            self.policy_engine = policy_engine
        elif NavigationPolicyEngine is not None:
            try:
                self.policy_engine = NavigationPolicyEngine(inspect_k=self.inspect_k)
            except TypeError:
                self.policy_engine = NavigationPolicyEngine()
        else:
            self.policy_engine = None
        self.cross_skill_links = self._load_cross_skill_links()

    def navigate(self, query: str, **features: Any) -> NavigationResult:
        policy_input = self._build_policy_input(query, features)
        decision = self._plan(policy_input)
        decision_plain = _to_plain(decision)
        trace = self._build_trace(query, decision_plain)

        selected_clusters = self._selected_clusters(decision_plain)
        if not selected_clusters:
            selected_clusters = self._infer_cluster_candidates(query)
        selected_clusters = selected_clusters[: max(self.inspect_k, int(decision_plain.get("inspect_k", 2) or 2))]

        inspected: List[str] = []
        last_trigger = "semantic_top2_exhausted"
        for index, cluster_id in enumerate(selected_clusters):
            inspected.append(cluster_id)
            _set_or_append_trace(
                trace,
                "drilldown_events",
                {
                    "step": "enter_cluster",
                    "cluster": cluster_id,
                    "cluster_index": index,
                    "source": "policy.selected_clusters",
                },
            )
            try:
                binding, candidate_paths = self._drilldown_cluster(cluster_id, query, decision_plain, trace)
                _set_trace_value(trace, "final_cluster", cluster_id)
                _set_trace_value(trace, "final_time_slice", binding.time_slice)
                _set_trace_value(trace, "fallback_reason", None)
                return NavigationResult(
                    success=True,
                    query=query,
                    decision=decision_plain,
                    trace=trace,
                    binding=binding,
                    selected_cluster=cluster_id,
                    inspected_clusters=inspected,
                    candidate_paths=candidate_paths,
                )
            except NavigationBranchError as exc:
                last_trigger = exc.trigger
                next_cluster = selected_clusters[index + 1] if index + 1 < len(selected_clusters) else None
                if next_cluster is None:
                    related = self._related_semantic_clusters(cluster_id)
                    next_cluster = next((cluster for cluster in related if cluster not in inspected), None)
                    if next_cluster:
                        selected_clusters.append(next_cluster)
                self._record_backtrack(trace, exc, cluster_id, next_cluster, decision_plain)
                if next_cluster is None:
                    break

        fallback_reason = "temporal_slice_empty" if last_trigger == "temporal_slice_empty" else "semantic_top2_exhausted"
        _set_trace_value(trace, "fallback_reason", fallback_reason)
        _set_or_append_trace(
            trace,
            "terminal_events",
            {
                "event": "global_fallback_allowed",
                "reason": fallback_reason,
                "inspected_clusters": inspected,
            },
        )
        return NavigationResult(
            success=False,
            query=query,
            decision=decision_plain,
            trace=trace,
            inspected_clusters=inspected,
            fallback_reason=fallback_reason,
        )

    def _build_policy_input(self, query: str, features: Mapping[str, Any]) -> Any:
        tokens = _normalise_tokens(query)
        payload = {
            "query": query,
            "query_text": query,
            "tokens": tokens,
            "route_features": dict(features),
            "inspect_k": self.inspect_k,
            "candidate_clusters": features.get("candidate_clusters"),
            "temporal_hints": features.get("temporal_hints") or self._extract_temporal_hints(query),
            "entity_hints": features.get("entity_hints") or tokens,
        }
        return _construct(PolicyInput, payload)

    def _plan(self, policy_input: Any) -> Any:
        if self.policy_engine is None:
            return {
                "selected_clusters": [],
                "inspect_k": self.inspect_k,
                "drilldown_plan": [],
                "backtracking_plan": [
                    {"trigger": "cluster_branch_empty", "action": "inspect_next_cluster"},
                    {"trigger": "entity_unmatched", "action": "try_next_entity_candidate"},
                    {"trigger": "temporal_slice_empty", "action": "inspect_adjacent_or_parent_slice"},
                ],
            }
        decision = self.policy_engine.plan(policy_input)
        decision_matches_schema = False
        if PolicyDecision is not None and isinstance(PolicyDecision, type):
            decision_matches_schema = isinstance(decision, PolicyDecision)
        if PolicyDecision is not None and not isinstance(decision, dict) and not decision_matches_schema:
            return _construct(PolicyDecision, _to_plain(decision))
        return decision

    def _build_trace(self, query: str, decision_plain: Mapping[str, Any]) -> Any:
        payload = {
            "query": query,
            "selected_clusters": decision_plain.get("selected_clusters", []),
            "inspect_k": decision_plain.get("inspect_k", self.inspect_k),
            "drilldown_events": [],
            "backtrack_events": [],
            "terminal_events": [],
            "fallback_reason": None,
        }
        return _construct(DecisionTrace, payload)

    def _selected_clusters(self, decision_plain: Mapping[str, Any]) -> List[str]:
        clusters = decision_plain.get("selected_clusters") or decision_plain.get("clusters") or []
        if isinstance(clusters, str):
            clusters = [clusters]
        normalised = [str(cluster) for cluster in clusters if cluster]
        return normalised[: max(2, int(decision_plain.get("inspect_k", self.inspect_k) or self.inspect_k))]

    def _infer_cluster_candidates(self, query: str) -> List[str]:
        tokens = _normalise_tokens(query)
        scored: List[Tuple[float, str]] = []
        for path in self.knowledge_root.rglob("cluster_*"):
            if path.is_dir():
                score = _score_text(path.name + " " + str(path), tokens)
                scored.append((score, path.name))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [cluster for _, cluster in scored[: self.inspect_k]]

    def _drilldown_cluster(
        self,
        cluster_id: str,
        query: str,
        decision_plain: Mapping[str, Any],
        trace: Any,
    ) -> Tuple[NavigationBinding, List[str]]:
        cluster_paths = self._find_cluster_paths(cluster_id)
        if not cluster_paths:
            raise NavigationBranchError("cluster_branch_empty", f"cluster branch not found: {cluster_id}", cluster_id)

        tokens = _normalise_tokens(query)
        candidate_files: List[Path] = []
        for cluster_path in cluster_paths:
            files = [path for path in cluster_path.rglob("*") if path.is_file()]
            candidate_files.extend(files)

        if not candidate_files:
            raise NavigationBranchError("cluster_branch_empty", f"cluster branch has no files: {cluster_id}", cluster_id)

        entity_candidates = self._rank_entity_candidates(candidate_files, tokens)
        if not entity_candidates:
            raise NavigationBranchError("entity_unmatched", f"no entity matched under {cluster_id}", cluster_id)

        _set_or_append_trace(
            trace,
            "drilldown_events",
            {
                "step": "entity_candidates_ranked",
                "cluster": cluster_id,
                "candidates": [self._entity_name(path) for _, path in entity_candidates[:5]],
            },
        )

        temporal_hints = set(self._extract_temporal_hints(query))
        best: Optional[Tuple[float, Path, str]] = None
        candidate_paths: List[str] = []
        for entity_score, path in entity_candidates:
            candidate_paths.append(str(path))
            if not path.exists() or path.stat().st_size <= 0:
                continue
            text = self._read_preview(path)
            if not text.strip():
                continue
            slice_name = self._time_slice_name(path)
            temporal_bonus = 0.35 if temporal_hints and any(hint in str(path) for hint in temporal_hints) else 0.0
            content_score = _score_text(text, tokens)
            score = entity_score + content_score + temporal_bonus
            if best is None or score > best[0]:
                best = (score, path, text)

        if best is None:
            raise NavigationBranchError("temporal_slice_empty", f"no readable temporal slice under {cluster_id}", cluster_id)

        score, path, preview = best
        binding = NavigationBinding(
            cluster_id=cluster_id,
            entity=self._entity_name(path),
            time_slice=self._time_slice_name(path),
            source_path=str(path),
            score=round(float(score), 6),
            preview=preview[:500],
        )
        _set_or_append_trace(
            trace,
            "drilldown_events",
            {
                "step": "time_slice_bound",
                "cluster": cluster_id,
                "entity": binding.entity,
                "time_slice": binding.time_slice,
                "source_path": binding.source_path,
                "score": binding.score,
            },
        )
        return binding, candidate_paths

    def _find_cluster_paths(self, cluster_id: str) -> List[Path]:
        candidates: List[Path] = []
        common_roots = [
            self.knowledge_root,
            self.knowledge_root / "data",
            self.knowledge_root / "dataset",
            self.knowledge_root / "datasets",
            self.knowledge_root / "knowledge",
            self.knowledge_root / "tkg",
            self.knowledge_root / "tkg_data",
            self.knowledge_root / "semantic_clusters",
        ]
        for root in common_roots:
            direct = root / cluster_id
            if direct.is_dir():
                candidates.append(direct)
            if root.is_dir():
                candidates.extend(path for path in root.glob(f"{cluster_id}*") if path.is_dir())
        if not candidates:
            for path in self.knowledge_root.rglob(f"{cluster_id}*"):
                if path.is_dir():
                    candidates.append(path)
        unique: Dict[str, Path] = {str(path.resolve()): path for path in candidates}
        return list(unique.values())

    def _load_cross_skill_links(self) -> Dict[str, Any]:
        candidates = [
            self.knowledge_root / "tkgqa" / "indexes" / "cross_skill_links.json",
            self.knowledge_root / "indexes" / "cross_skill_links.json",
        ]
        for path in candidates:
            if path.is_file():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    return {}
        return {}

    def _related_semantic_clusters(self, cluster_id: str) -> List[str]:
        links = self.cross_skill_links.get("semantic_cluster_links", {})
        related = links.get(cluster_id, {}).get("related_semantic_clusters", [])
        return [str(cluster) for cluster in related if cluster]

    def _rank_entity_candidates(self, files: Sequence[Path], tokens: Sequence[str]) -> List[Tuple[float, Path]]:
        scored: List[Tuple[float, Path]] = []
        for path in files:
            path_text = " ".join(path.parts[-4:])
            score = _score_text(path_text, tokens)
            if score <= 0:
                preview = self._read_preview(path)
                score = _score_text(preview, tokens) * 0.75
            if score > 0:
                scored.append((score, path))
        scored.sort(key=lambda item: (-item[0], len(str(item[1])), str(item[1])))
        return scored

    def _read_preview(self, path: Path, limit: int = 8192) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:limit]
        except UnicodeDecodeError:
            return path.read_text(encoding="gb18030", errors="ignore")[:limit]
        except Exception:
            return ""

    def _extract_temporal_hints(self, query: str) -> List[str]:
        hints = re.findall(r"(?:19|20)\d{2}(?:[-_/]\d{1,2}(?:[-_/]\d{1,2})?)?", query)
        hints.extend(re.findall(r"\bq[1-4]\b|\b[12]\d{3}s\b", query.lower()))
        return list(dict.fromkeys(hints))

    def _entity_name(self, path: Path) -> str:
        if path.name.lower() == "index.md":
            return path.parent.name
        for parent in path.parents:
            if parent.name.startswith("entity") or parent.name.startswith("ent_"):
                return parent.name
        return path.stem

    def _time_slice_name(self, path: Path) -> str:
        for part in reversed(path.parts):
            if re.search(r"(?:19|20)\d{2}|slice|time|quarter|q[1-4]", part, re.IGNORECASE):
                return part
        return path.stem

    def _record_backtrack(
        self,
        trace: Any,
        exc: NavigationBranchError,
        current_cluster: str,
        next_cluster: Optional[str],
        decision_plain: Mapping[str, Any],
    ) -> None:
        plan_action = self._action_for_trigger(decision_plain.get("backtracking_plan", []), exc.trigger)
        event = {
            "trigger": exc.trigger,
            "action": plan_action or ("inspect_next_cluster" if next_cluster else "exhaust_branch"),
            "from_cluster": current_cluster,
            "to_cluster": next_cluster,
            "message": str(exc),
        }
        _set_or_append_trace(trace, "backtrack_events", event)
        if next_cluster:
            jump = {
                "from": current_cluster,
                "to": next_cluster,
                "reason": self._cross_jump_reason(current_cluster, next_cluster, exc.trigger),
            }
            _set_or_append_trace(trace, "cross_skill_jumps", jump)
            _set_trace_value(trace, "cross_skill_jump", jump)

    def _cross_jump_reason(self, current_cluster: str, next_cluster: str, trigger: str) -> str:
        links = self.cross_skill_links.get("semantic_cluster_links", {})
        if next_cluster in links.get(current_cluster, {}).get("related_semantic_clusters", []):
            return f"{trigger}; related semantic cluster from cross_skill_links.json"
        return f"{trigger}; inspect Top-K policy fallback branch"

    def _action_for_trigger(self, plan: Any, trigger: str) -> Optional[str]:
        if not isinstance(plan, Iterable) or isinstance(plan, (str, bytes)):
            return None
        for item in plan:
            if _get(item, "trigger") == trigger:
                return _get(item, "action")
        return None


Navigator = NavigationPolicyNavigator
TKGNavigator = NavigationPolicyNavigator


def navigate(query: str, knowledge_root: Optional[str | Path] = None, **features: Any) -> NavigationResult:
    """Functional entrypoint kept for smoke tests and older callers."""

    return NavigationPolicyNavigator(knowledge_root=knowledge_root).navigate(query, **features)


def navigate_to_json(query: str, knowledge_root: Optional[str | Path] = None, **features: Any) -> str:
    result = navigate(query=query, knowledge_root=knowledge_root, **features)
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
