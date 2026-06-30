import argparse
import json

from tkgqa_skills.routing.semantic_router import route_query


def main():
    parser = argparse.ArgumentParser(description="Smoke-test Phase 3 semantic routing.")
    parser.add_argument(
        "query",
        nargs="?",
        default="What did the US Military do in 2024?",
        help="Query to route through the semantic routing layer.",
    )
    parser.add_argument("--mode", choices=["lexical", "embedding", "hybrid"], default="lexical")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    print(json.dumps(route_query(args.query, mode=args.mode, top_k=args.top_k),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
