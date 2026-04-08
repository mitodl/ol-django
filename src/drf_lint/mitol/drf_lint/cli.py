"""CLI entry point for drf-lint.

Usage::

    drf-lint serializers.py
    drf-lint --generate-baseline --baseline baseline.json serializers.py
    drf-lint --baseline baseline.json serializers.py
    drf-lint --no-baseline serializers.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mitol.drf_lint import baseline as baseline_mod
from mitol.drf_lint.checker import check_file
from mitol.drf_lint.rules.base import Violation

_DEFAULT_BASELINE = "drf_lint_baseline.json"


def main(argv: list[str] | None = None) -> int:
    """Run the DRF serializer ORM checker on the given files.

    Returns 0 when no new violations are found, 1 otherwise.
    """
    parser = argparse.ArgumentParser(
        prog="drf-lint",
        description="Detect Django ORM queries inside DRF serializer methods.",
    )
    parser.add_argument("files", nargs="*", help="Source files to check")
    parser.add_argument(
        "--baseline",
        "-b",
        metavar="PATH",
        default=_DEFAULT_BASELINE,
        help=f"Baseline JSON file path (default: {_DEFAULT_BASELINE})",
    )
    parser.add_argument(
        "--generate-baseline",
        action="store_true",
        help="Record all current violations to the baseline file and exit with 0",
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Ignore any baseline file and report all violations",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        help="File glob to ignore",
        default=[],
    )
    args = parser.parse_args(argv)

    if not args.files:
        return 0

    baseline_path = Path(args.baseline)
    known: set[str] = set() if args.no_baseline else baseline_mod.load(baseline_path)
    excludes: set[str] = set()

    for exclude_arg in args.exclude:
        excludes |= set(Path().glob(exclude_arg))

    all_violations: list[tuple[str, Violation]] = []
    for file_arg in args.files:
        paths = list(Path().glob(file_arg))
        if not paths:
            print(f"drf-lint: {file_arg}: file(s) not found", file=sys.stderr)  # noqa: T201
            continue
        for path in paths:
            if path in excludes:
                continue
            all_violations.extend((str(path), v) for v in check_file(path))

    if args.generate_baseline:
        baseline_mod.save_all(baseline_path, all_violations)
        print(  # noqa: T201
            f"drf-lint: baseline written to {baseline_path} "
            f"({len(all_violations)} violation(s) recorded)"
        )
        return 0

    new_violations = [
        (filename, v)
        for filename, v in all_violations
        if v.baseline_key(filename) not in known
    ]
    for filename, violation in sorted(new_violations, key=lambda x: (x[0], x[1].line)):
        print(violation.format(filename))  # noqa: T201

    return 1 if new_violations else 0


if __name__ == "__main__":
    sys.exit(main())
