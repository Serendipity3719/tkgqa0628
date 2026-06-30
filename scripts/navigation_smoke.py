import argparse
import json

from tkgqa_skills.navigation.navigator import SkillNavigator


def main():
    parser = argparse.ArgumentParser(description="Smoke-test Phase 3 semantic navigation.")
    parser.add_argument(
        "query",
        nargs="?",
        default="What did the US Military do in 2024?",
        help="Query to route through the semantic navigator.",
    )
    parser.add_argument("--tkgqa-root", default="tkgqa")
    args = parser.parse_args()

    result = SkillNavigator(tkgqa_root=args.tkgqa_root).navigate(args.query)
    print(json.dumps({
        "selected_skill": result.selected_skill,
        "doc_ids": result.doc_ids,
        "routing_path": result.routing_path,
        "trace": result.trace,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
