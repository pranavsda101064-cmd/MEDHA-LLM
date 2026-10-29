"""Inspect and index the persistent lesson library."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import config

from .models import LibraryFilter
from .repository import LessonLibrary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medha-library", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    index = subparsers.add_parser("index", help="index lesson JSON files")
    index.add_argument("--dir", default=str(config.LESSON_CONTENT_DIR))

    listing = subparsers.add_parser("list", help="list indexed lessons")
    listing.add_argument("--query")
    listing.add_argument("--subject")
    listing.add_argument("--language")
    listing.add_argument("--favorites", action="store_true")
    listing.add_argument("--limit", type=int, default=200)
    listing.add_argument("--json", action="store_true")

    search = subparsers.add_parser("search", help="search lesson titles")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=50)
    search.add_argument("--json", action="store_true")

    stats = subparsers.add_parser("stats", help="library totals")
    stats.add_argument("--json", action="store_true")

    attempts_parser = subparsers.add_parser("attempts", help="checkpoint history")
    attempts_parser.add_argument("lesson_id")
    attempts_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    config.ensure_dirs()
    library = LessonLibrary()

    if args.command == "index":
        report = library.index_directory(Path(args.dir))
        print(
            f"indexed={report.indexed} skipped={report.skipped} "
            f"errors={len(report.errors)}"
        )
        for error in report.errors:
            print(f"  {error}")
        return 0 if not report.errors else 1

    if args.command == "list":
        filters = LibraryFilter(
            query=args.query,
            subject=args.subject,
            language=args.language,
            favorite=True if args.favorites else None,
            limit=args.limit,
        )
        lessons = library.list_lessons(filters)
        if args.json:
            print(
                json.dumps(
                    [lesson.model_dump(mode="json") for lesson in lessons],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        for lesson in lessons:
            star = "*" if lesson.favorite else " "
            print(
                f"{star} {lesson.score:3d} {lesson.language} "
                f"{lesson.lesson_id:<42} {lesson.title}"
            )
        return 0

    if args.command == "search":
        lessons = library.list_lessons(LibraryFilter(query=args.query, limit=args.limit))
        if args.json:
            print(
                json.dumps(
                    [lesson.model_dump(mode="json") for lesson in lessons],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        for lesson in lessons:
            print(f"{lesson.score:3d} {lesson.lesson_id:<42} {lesson.title}")
        return 0

    if args.command == "stats":
        result = library.statistics()
        if args.json:
            print(result.model_dump_json(indent=2))
        else:
            minutes = result.total_duration_ms / 60000
            print(
                f"{result.lessons} lesson(s), {result.favorites} favorite(s), "
                f"{minutes:.1f} min, avg {result.average_score:.0f}/100, "
                f"{result.checkpoint_attempts} checkpoint attempt(s)"
            )
        return 0

    if args.command == "attempts":
        summary = library.checkpoint_summary(args.lesson_id)
        attempts = library.checkpoint_attempts(args.lesson_id)
        if args.json:
            print(
                json.dumps(
                    {
                        "summary": summary.model_dump(mode="json"),
                        "attempts": [
                            attempt.model_dump(mode="json") for attempt in attempts
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        print(
            f"{args.lesson_id}: {summary.correct}/{summary.attempts} correct "
            f"({summary.accuracy * 100:.0f}%)"
        )
        for attempt in attempts:
            mark = "ok" if attempt.correct else "no"
            print(f"  {mark} {attempt.step_id}: {attempt.question} -> {attempt.answer}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
