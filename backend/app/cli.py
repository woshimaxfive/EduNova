from __future__ import annotations

import argparse

from backend.app.db.session import SessionLocal
from backend.app.services.course_seed import seed_builtin_ai_intro_course


def seed_ai_intro() -> None:
    with SessionLocal() as db:
        result = seed_builtin_ai_intro_course(db)
        db.commit()

    status = "created" if result.created else "exists"
    print(
        "seed-ai-intro "
        f"status={status} "
        f"course_id={result.course_id} "
        f"knowledge_points={result.knowledge_points} "
        f"chunks={result.chunks}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="edunova")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("seed-ai-intro", help="导入人工智能导论内置课程包")

    args = parser.parse_args()
    if args.command == "seed-ai-intro":
        seed_ai_intro()


if __name__ == "__main__":
    main()
