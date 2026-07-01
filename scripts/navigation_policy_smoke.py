import argparse
import json

from tkgqa_skills.policy.navigation_policy import NavigationPolicy
from tkgqa_skills.routing.semantic_router import SemanticRouter


def main():
    parser = argparse.ArgumentParser(description="Smoke-test Phase 5 Navigation Policy Layer.")
    parser.add_argument(
        "query",
        nargs="?",
        default="What did the US Military do after 2014?",
        help="Query to route and plan over the semantic skill tree.",
    )
    parser.add_argument("--mode", choices=["lexical", "embedding", "hybrid"], default="lexical")
    parser.add_argument("--inspect-k", type=int, default=2)
    args = parser.parse_args()

    routing = SemanticRouter(mode=args.mode, top_k=max(args.inspect_k, 2)).route(args.query)
    policy = NavigationPolicy(inspect_k=args.inspect_k)
    result = policy.decide(args.query, routing)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
