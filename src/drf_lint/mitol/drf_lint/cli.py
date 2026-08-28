"""CLI entry point for drf-lint.

Usage::

    drf-lint serializers.py
    drf-lint --generate-baseline --baseline baseline.json serializers.py
    drf-lint --baseline baseline.json serializers.py
    drf-lint --no-baseline serializers.py
    drf-lint --no-cross-file serializers.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mitol.drf_lint import baseline as baseline_mod
from mitol.drf_lint.checker import ALL_RULES, LOCAL_RULES, CheckContext, check_file
from mitol.drf_lint.index import (
    DEFAULT_EXCLUDES,
    ProjectIndex,
    build_index,
    find_project_root,
    load_config,
    module_for_path,
)
from mitol.drf_lint.index.cache import DEFAULT_CACHE_NAME
from mitol.drf_lint.index.propagate import propagate
from mitol.drf_lint.index.resolve import FALLBACK_MODES
from mitol.drf_lint.index.scan import scan_file
from mitol.drf_lint.rules import prefetch
from mitol.drf_lint.rules.base import Violation

_DEFAULT_BASELINE = "drf_lint_baseline.json"


def _build_parser() -> argparse.ArgumentParser:
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

    cross = parser.add_argument_group("cross-file analysis")
    cross.add_argument(
        "--project-root",
        metavar="PATH",
        help="Root to index (default: nearest .git / pyproject.toml / manage.py)",
    )
    cross.add_argument(
        "--no-cross-file",
        action="store_true",
        help="Skip the project index; run only ORM001 and ORM002",
    )
    cross.add_argument(
        "--index-exclude",
        action="append",
        default=None,
        metavar="GLOB",
        help="Globs to leave out of the index (repeatable, or comma-separated)",
    )
    cross.add_argument(
        "--index-cache",
        metavar="PATH",
        help=f"Index cache location (default: <root>/{DEFAULT_CACHE_NAME})",
    )
    cross.add_argument(
        "--no-index-cache",
        action="store_true",
        help="Always rebuild the index instead of reusing the cache",
    )
    cross.add_argument(
        "--build-index",
        action="store_true",
        help="Build or refresh the index cache, then exit",
    )
    cross.add_argument(
        "--model-resolution",
        choices=FALLBACK_MODES,
        default=None,
        help="Fallback when Meta.model cannot be resolved through imports",
    )
    cross.add_argument(
        "--receiver-heuristic",
        choices=("strict", "names"),
        default=None,
        help="How confidently a name must denote the model instance",
    )
    cross.add_argument(
        "--prefetch-base",
        action="append",
        default=None,
        metavar="DOTTED",
        help="Base classes carrying the required_prefetches contract (repeatable)",
    )
    cross.add_argument(
        "--warn-unresolved",
        action="store_true",
        help="Report unresolvable Meta.model values on stderr (exit code unaffected)",
    )

    rules = parser.add_argument_group("rule selection")
    # These take one value per flag rather than `nargs="+"`, so that a trailing
    # file argument cannot be silently swallowed into the rule list.
    rules.add_argument(
        "--select",
        action="append",
        default=None,
        metavar="CODE",
        help="Only run these rules (repeatable, or comma-separated)",
    )
    rules.add_argument(
        "--ignore",
        action="append",
        default=None,
        metavar="CODE",
        help="Skip these rules (repeatable, or comma-separated)",
    )
    return parser


def _split(values: list[str] | None) -> list[str] | None:
    """Accept both ``--ignore A B`` and ``--ignore A,B``."""
    if values is None:
        return None
    return [item for value in values for item in value.split(",") if item]


def _expand(globs: list[str]) -> set[Path]:
    """Expand a list of glob patterns relative to the working directory."""
    found: set[Path] = set()
    for pattern in globs:
        found |= set(Path().glob(pattern))
    return found


def _enabled_rules(config: dict, args: argparse.Namespace) -> frozenset[str]:
    """Resolve ``--select`` / ``--ignore``, with the CLI overriding pyproject."""
    select = _split(args.select) or config.get("select")
    ignore = _split(args.ignore) or config.get("ignore")
    enabled = frozenset(select) & ALL_RULES if select else ALL_RULES
    enabled -= frozenset(ignore or ())
    if args.no_cross_file:
        # The flag promises the pre-index behaviour, so everything that reads
        # the project index or a required_prefetches declaration steps aside.
        enabled &= LOCAL_RULES
    return enabled


def _prepare_index(
    args: argparse.Namespace, config: dict, paths: list[Path], root: Path | None
) -> ProjectIndex | None:
    """Build the project index, or return None if cross-file analysis is off.

    Every failure here is soft: an unindexable project falls back to the
    single-file rules rather than blocking a commit.
    """
    if args.no_cross_file or root is None:
        return None
    extra = _split(args.index_exclude) or config.get("index_exclude")
    excludes = (*DEFAULT_EXCLUDES, *(extra or ()))
    cache_path = (
        Path(args.index_cache) if args.index_cache else root / DEFAULT_CACHE_NAME
    )
    fallback = args.model_resolution or config.get("model_resolution") or "unique"
    try:
        index = build_index(
            root,
            excludes=excludes,
            cache_path=cache_path,
            use_cache=not args.no_index_cache,
            fallback=fallback,
        )
    except OSError:
        return None
    _ensure_indexed(index, paths, root, fallback)
    return index


def _ensure_indexed(
    index: ProjectIndex, paths: list[Path], root: Path, fallback: str
) -> None:
    """Pull in any checked file the exclusion rules kept out of the index."""
    added = False
    for path in paths:
        resolved = str(path.resolve())
        if resolved in index.by_path or str(path) in index.by_path:
            continue
        dotted, is_package = module_for_path(path, root)
        module = scan_file(path.resolve(), dotted, is_package=is_package)
        if module is not None:
            index.add(module)
            added = True
    if added:
        index.reindex_names()
        propagate(index, fallback=fallback)


def main(argv: list[str] | None = None) -> int:
    """Run the DRF serializer ORM checker on the given files.

    Returns 0 when no new violations are found, 1 otherwise.
    """
    args = _build_parser().parse_args(argv)

    root = (
        Path(args.project_root).resolve()
        if args.project_root
        else find_project_root(Path())
    )
    config = load_config(root) if root else {}

    if args.build_index:
        if root is None:
            print("drf-lint: no project root found", file=sys.stderr)  # noqa: T201
            return 0
        _prepare_index(args, config, [], root)
        print(f"drf-lint: index cache refreshed for {root}")  # noqa: T201
        return 0

    if not args.files:
        return 0

    excludes = _expand(args.exclude)
    paths: list[Path] = []
    for file_arg in args.files:
        matched = sorted(Path().glob(file_arg))
        if not matched:
            print(f"drf-lint: {file_arg}: file(s) not found", file=sys.stderr)  # noqa: T201
            continue
        paths.extend(path for path in matched if path not in excludes)

    index = _prepare_index(args, config, paths, root)
    enabled = _enabled_rules(config, args)
    bases = _split(args.prefetch_base) or config.get("prefetch_base_serializers")
    receiver = args.receiver_heuristic or config.get("receiver_heuristic") or "strict"
    fallback = args.model_resolution or config.get("model_resolution") or "unique"

    all_violations: list[tuple[str, Violation]] = []
    for path in paths:
        module = module_for_path(path, root)[0] if index is not None and root else None
        context = CheckContext(
            index=index,
            module=module,
            receiver_mode=receiver,
            model_resolution=fallback,
            enabled_rules=enabled,
            prefetch_bases=(
                frozenset(bases) if bases else prefetch.DEFAULT_PREFETCH_BASES
            ),
            prefetch_aware=not args.no_cross_file,
        )
        all_violations.extend((str(path), v) for v in check_file(path, context))
        if args.warn_unresolved:
            for line, expression in context.unresolved:
                print(  # noqa: T201
                    f"{path}:{line}: could not resolve Meta.model = {expression}",
                    file=sys.stderr,
                )

    return _report(args, all_violations)


def _report(
    args: argparse.Namespace, all_violations: list[tuple[str, Violation]]
) -> int:
    """Apply the baseline, print what remains, and pick the exit code."""
    baseline_path = Path(args.baseline)
    if args.generate_baseline:
        baseline_mod.save_all(baseline_path, all_violations)
        print(  # noqa: T201
            f"drf-lint: baseline written to {baseline_path} "
            f"({len(all_violations)} violation(s) recorded)"
        )
        return 0

    known: set[str] = set() if args.no_baseline else baseline_mod.load(baseline_path)
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
