from __future__ import annotations

import argparse

from backend.app.db.session import SessionLocal
from backend.app.services.course_seed import sync_builtin_courses


def sync_courses() -> None:
    with SessionLocal() as db:
        result = sync_builtin_courses(db)

    print(
        "sync-builtin-courses "
        f"removed_legacy_courses={result.removed_legacy_courses} "
        f"removed_legacy_materials={result.removed_legacy_materials} "
        f"migrated_users={result.migrated_users} "
        f"created_courses={result.created_courses} "
        f"existing_courses={result.existing_courses}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="edunova")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sync-builtin-courses", help="替换旧内置课并同步数据结构课程")

    args = parser.parse_args()
    if args.command == "sync-builtin-courses":
        sync_courses()


if __name__ == "__main__":
    main()
