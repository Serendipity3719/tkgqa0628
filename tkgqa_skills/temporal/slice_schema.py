from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple


SUPPORTED_TEMPORAL_STRATEGIES = ("fixed-year", "fixed-window", "adaptive-event")


@dataclass(frozen=True)
class TemporalSlice:
    """A navigable temporal knowledge unit for Phase 4 decomposition."""

    slice_id: str
    label: str
    start_date: str
    end_date: str
    granularity: str
    strategy: str
    event_count: int
    dominant_relations: List[str]
    dominant_neighbors: List[str]
    fact_doc: str
    filter_hint: str
    navigation_policy: str

    def covers_year(self, year: str) -> bool:
        y = str(year)
        return self.start_date[:4] <= y <= self.end_date[:4]

    def to_tsv_row(self) -> Tuple:
        return (
            self.slice_id,
            self.label,
            self.start_date,
            self.end_date,
            self.granularity,
            self.strategy,
            self.event_count,
            " ".join(self.dominant_relations),
            " ".join(self.dominant_neighbors),
            self.fact_doc,
            self.filter_hint,
            self.navigation_policy,
        )


def normalize_temporal_strategy(strategy: str) -> str:
    value = (strategy or "fixed-year").replace("_", "-").lower()
    if value not in SUPPORTED_TEMPORAL_STRATEGIES:
        raise ValueError(
            f"unsupported temporal decomposition strategy: {strategy}; "
            f"expected one of {', '.join(SUPPORTED_TEMPORAL_STRATEGIES)}"
        )
    return value


def fixed_window_ranges(min_year: int, max_year: int) -> List[Tuple[int, int]]:
    """Return interpretable windows anchored to the observed KG year range."""
    if min_year > max_year:
        return []
    canonical = [(2010, 2012), (2013, 2016), (2017, 2020), (2021, 2024)]
    windows = []
    for start, end in canonical:
        s = max(start, min_year)
        e = min(end, max_year)
        if s <= e:
            windows.append((s, e))
    covered = {y for s, e in windows for y in range(s, e + 1)}
    for year in range(min_year, max_year + 1):
        if year not in covered:
            windows.append((year, year))
    return sorted(windows)


def adaptive_event_ranges(year_counts: Dict[str, int], target_slices: int = 4) -> List[Tuple[int, int]]:
    """Density-aware global windows using observed yearly event counts."""
    years = sorted(int(y) for y, count in year_counts.items() if count > 0)
    if not years:
        return []
    target_slices = max(1, min(target_slices, len(years)))
    total = sum(year_counts.get(str(y), 0) for y in years)
    target_events = max(1, total // target_slices)

    ranges = []
    start = years[0]
    acc = 0
    previous = years[0]
    for year in years:
        count = year_counts.get(str(year), 0)
        contiguous_break = year != previous and year != previous + 1
        should_cut = acc >= target_events and len(ranges) < target_slices - 1
        if (contiguous_break or should_cut) and year > start:
            ranges.append((start, previous))
            start = year
            acc = 0
        acc += count
        previous = year
    ranges.append((start, previous))
    return ranges


def make_filter_hint(start_date: str, end_date: str) -> str:
    if start_date[:4] == end_date[:4]:
        return f'substr($1,1,4)=="{start_date[:4]}"'
    return f'$1>="{start_date}" && $1<="{end_date}"'


def make_navigation_policy(strategy: str, granularity: str, start_date: str, end_date: str) -> str:
    if strategy == "fixed-year":
        return (
            "Use this slice when the query explicitly names this year. "
            "For first/last global extrema, bypass the slice and use full data.txt."
        )
    if strategy == "fixed-window":
        return (
            f"Use this {granularity} slice for queries whose temporal condition falls between "
            f"{start_date} and {end_date}; backtrack to adjacent windows when pivot evidence is absent."
        )
    return (
        f"Use this event-density slice for long entities when the query falls between {start_date} "
        f"and {end_date}; if evidence is sparse, inspect neighboring adaptive slices before global fallback."
    )


def build_temporal_slices(strategy: str, year_counts: Dict[str, int],
                          fact_doc: str = "", dominant_relations: Sequence[str] = (),
                          dominant_neighbors: Sequence[str] = ()) -> List[TemporalSlice]:
    strategy = normalize_temporal_strategy(strategy)
    years = sorted(int(y) for y, count in year_counts.items() if count > 0)
    if not years:
        return []

    if strategy == "fixed-year":
        ranges = [(year, year) for year in years]
        granularity = "year"
    elif strategy == "fixed-window":
        ranges = fixed_window_ranges(years[0], years[-1])
        granularity = "multi_year_window"
    else:
        ranges = adaptive_event_ranges(year_counts)
        granularity = "adaptive_event_window"

    slices = []
    for start_year, end_year in ranges:
        start_date = f"{start_year:04d}-01-01"
        end_date = f"{end_year:04d}-12-31"
        if start_year == end_year:
            slice_id = f"{start_year:04d}"
            label = f"{start_year:04d}"
        else:
            slice_id = f"{start_year:04d}_{end_year:04d}"
            label = f"{start_year:04d}-{end_year:04d}"
        event_count = sum(year_counts.get(str(y), 0) for y in range(start_year, end_year + 1))
        slices.append(TemporalSlice(
            slice_id=slice_id,
            label=label,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            strategy=strategy,
            event_count=event_count,
            dominant_relations=list(dominant_relations),
            dominant_neighbors=list(dominant_neighbors),
            fact_doc=fact_doc,
            filter_hint=make_filter_hint(start_date, end_date),
            navigation_policy=make_navigation_policy(strategy, granularity, start_date, end_date),
        ))
    return slices


def strategy_overview_rows(year_counts: Dict[str, int]) -> List[Tuple]:
    return [
        (
            strategy,
            len(build_temporal_slices(strategy, year_counts)),
            "yes" if strategy == "fixed-year" else "no",
            "entity -> temporal/<year>" if strategy == "fixed-year" else "entity -> temporal_slices/<slice_id>",
        )
        for strategy in SUPPORTED_TEMPORAL_STRATEGIES
    ]


def temporal_slice_tsv_rows(slices: Iterable[TemporalSlice]) -> List[Tuple]:
    return [s.to_tsv_row() for s in slices]


def fallback_policy_for_slice(slice_obj: TemporalSlice) -> str:
    return (
        "If this slice yields no evidence, inspect adjacent temporal slices that overlap the query intent. "
        "For first/last, before_last, and after_first global ordering tasks, bypass slice-only evidence "
        "and fall back to the parent entity full data.txt."
    )


def when_to_use_slice(slice_obj: TemporalSlice) -> str:
    if slice_obj.granularity == "year":
        return f"Use when the query explicitly names {slice_obj.start_date[:4]} or asks for events within that year."
    if slice_obj.granularity == "multi_year_window":
        return (
            f"Use when the query year/range falls inside {slice_obj.label}, including before/after pivots "
            "whose candidate evidence is expected in this window."
        )
    return (
        f"Use for long temporal entities when event density suggests {slice_obj.label} is the smallest useful "
        "navigation window for the query."
    )


def render_entity_temporal_slices_index(entity_name: str, slices: Sequence[TemporalSlice],
                                        strategy: str) -> str:
    lines = [
        f"# Temporal Slices: {entity_name}",
        "",
        f"- strategy: {normalize_temporal_strategy(strategy)}",
        f"- slices: {len(slices)}",
        "",
        "## Navigation Policy",
        "",
        "- Prefer temporal slices for bounded year/range questions.",
        "- Use the legacy `../temporal/<year>/index.md` path when a caller expects year-level compatibility.",
        "- For first/last global extrema, use the parent entity `data.txt` rather than any slice.",
        "",
        "| slice_id | label | range | event_count | index |",
        "|---|---|---|---:|---|",
    ]
    for s in slices:
        lines.append(
            f"| {s.slice_id} | {s.label} | {s.start_date}..{s.end_date} | "
            f"{s.event_count:,} | {s.slice_id}/index.md |"
        )
    return "\n".join(lines) + "\n"


def render_entity_temporal_slice_leaf(entity_name: str, slice_obj: TemporalSlice) -> str:
    dominant_relations = ", ".join(slice_obj.dominant_relations) if slice_obj.dominant_relations else "(none)"
    dominant_neighbors = ", ".join(slice_obj.dominant_neighbors) if slice_obj.dominant_neighbors else "(none)"
    return "\n".join([
        f"# Temporal Slice: {entity_name} / {slice_obj.label}",
        "",
        f"- slice_id: {slice_obj.slice_id}",
        f"- label: {slice_obj.label}",
        f"- time_range: {slice_obj.start_date}..{slice_obj.end_date}",
        f"- granularity: {slice_obj.granularity}",
        f"- strategy: {slice_obj.strategy}",
        f"- event_count: {slice_obj.event_count:,}",
        f"- dominant_relations: {dominant_relations}",
        f"- dominant_neighbors: {dominant_neighbors}",
        f"- fact_doc: `{slice_obj.fact_doc}`",
        f"- filter_hint: `{slice_obj.filter_hint}`",
        "",
        "## When To Use",
        "",
        when_to_use_slice(slice_obj),
        "",
        "## Navigation Policy",
        "",
        slice_obj.navigation_policy,
        "",
        "## Fallback Policy",
        "",
        fallback_policy_for_slice(slice_obj),
        "",
    ])


def render_temporal_schema_index(year_counts: Dict[str, int], selected_strategy: str,
                                 slices: Sequence[TemporalSlice]) -> str:
    selected_strategy = normalize_temporal_strategy(selected_strategy)
    lines = [
        "# Temporal Decomposition Schema",
        "",
        "Phase 4 defines temporal slices as first-class navigation units.",
        "",
        f"- selected_strategy: {selected_strategy}",
        f"- observed_years: {len(year_counts)}",
        f"- schema_slices: {len(slices)}",
        "",
        "## TemporalSlice Fields",
        "",
        "| field | meaning |",
        "|---|---|",
        "| slice_id | stable directory/key identifier |",
        "| label | human-readable time span |",
        "| start_date / end_date | inclusive date bounds |",
        "| granularity | year, multi_year_window, or adaptive_event_window |",
        "| strategy | fixed-year, fixed-window, or adaptive-event |",
        "| event_count | observed event count under the slice scope |",
        "| dominant_relations | relation summary for navigation |",
        "| dominant_neighbors | neighbor summary for navigation |",
        "| fact_doc | fact document to read at the leaf |",
        "| filter_hint | awk-compatible temporal predicate |",
        "| navigation_policy | when and how to use the slice |",
        "",
        "## Strategies",
        "",
        "| strategy | schema_slices | reproduces_current_year_leaf | expected_path |",
        "|---|---:|---|---|",
    ]
    for strategy, count, reproduces, path in strategy_overview_rows(year_counts):
        lines.append(f"| {strategy} | {count} | {reproduces} | {path} |")
    lines.extend([
        "",
        "## Selected Strategy Slices",
        "",
        "| slice_id | label | range | event_count | filter_hint |",
        "|---|---|---|---:|---|",
    ])
    for s in slices:
        lines.append(
            f"| {s.slice_id} | {s.label} | {s.start_date}..{s.end_date} | "
            f"{s.event_count:,} | `{s.filter_hint}` |"
        )
    return "\n".join(lines) + "\n"
