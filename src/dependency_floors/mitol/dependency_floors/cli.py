"""CLI entry point for dependency-floors.

Usage::

    dependency-floors check
    dependency-floors check --config path/to/pyproject.toml --format json
    dependency-floors explain certifi
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mitol.dependency_floors import __version__
from mitol.dependency_floors.config import Config, ConfigError, load
from mitol.dependency_floors.graph import DependencyGraph, LockError
from mitol.dependency_floors.rules import (
    BASE,
    Violation,
    check,
    classify,
    discover_members,
)

EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_CONFIG = 2

DEFAULT_MANIFEST = "pyproject.toml"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dependency-floors",
        description=(
            "Check that a repository's manifests and lockfile enforce the "
            "dependency version floors it declares."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--config",
        "-c",
        metavar="PATH",
        default=DEFAULT_MANIFEST,
        help=(
            "pyproject.toml holding the [tool.dependency-floors] table "
            f"(default: {DEFAULT_MANIFEST})"
        ),
    )
    parser.add_argument(
        "--lock",
        "-l",
        metavar="PATH",
        help="Lockfile to read, overriding the configured one",
    )

    commands = parser.add_subparsers(dest="command", required=True)

    checker = commands.add_parser("check", help="Report every floor violation")
    checker.add_argument(
        "--format",
        "-f",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )

    explainer = commands.add_parser(
        "explain", help="Show how each member reaches a floored package"
    )
    explainer.add_argument("floor", help="Name of a declared floor, e.g. certifi")

    return parser


def _resolve(args: argparse.Namespace) -> tuple[Config, Path]:
    manifest = Path(args.config).resolve()
    config = load(manifest)

    if args.lock:
        config = Config(
            root=config.root,
            lock=Path(args.lock).resolve(),
            members=config.members,
            exclude=config.exclude,
            floors=config.floors,
        )

    return config, manifest


def _emit_text(config: Config, violations: list[Violation]) -> None:
    if not violations:
        scope = (
            f"{len(discover_members(config))} members"
            if config.is_workspace
            else "the lockfile"
        )
        print(  # noqa: T201
            f"dependency-floors: {len(config.floors)} floor(s) hold across {scope}."
        )
        return

    for violation in violations:
        print(violation.render(), file=sys.stderr)  # noqa: T201
        print(file=sys.stderr)  # noqa: T201

    print(  # noqa: T201
        f"dependency-floors: {len(violations)} violation(s).", file=sys.stderr
    )


def _run_check(args: argparse.Namespace) -> int:
    config, manifest = _resolve(args)
    violations = check(config, manifest)

    if args.format == "json":
        print(  # noqa: T201
            json.dumps(
                [
                    {
                        "rule": violation.rule,
                        "path": violation.path,
                        "summary": violation.summary,
                        "details": list(violation.details),
                    }
                    for violation in violations
                ],
                indent=2,
            )
        )
    else:
        _emit_text(config, violations)

    return EXIT_VIOLATIONS if violations else EXIT_OK


def _run_explain(args: argparse.Namespace) -> int:
    config, _ = _resolve(args)
    wanted = args.floor.strip()
    floor = next(
        (entry for entry in config.floors if entry.name == wanted.lower()), None
    )

    if floor is None:
        known = ", ".join(entry.name for entry in config.floors)
        message = f"no floor named {wanted!r} is declared. Declared: {known}"
        raise ConfigError(message)

    graph = DependencyGraph.from_uv_lock(config.lock)
    members = discover_members(config)
    siblings = frozenset(member.name for member in members)

    resolved = ", ".join(str(version) for version in graph.versions(floor.name))
    print(f"{floor.name}{floor.specifier}")  # noqa: T201
    print(f"  locked:  {resolved or 'not present in the lockfile'}")  # noqa: T201
    if floor.describe():
        print(f"  why:     {floor.describe()}")  # noqa: T201
    print()  # noqa: T201

    for member in members:
        for context, requirements in member.contexts():
            reach = classify(requirements, floor, graph, siblings)
            label = member.name if context == BASE else f"{member.name}[{context}]"
            trail = f"  {reach.trail}" if reach.path else ""
            print(f"{label:46} {reach.kind:9}{trail}")  # noqa: T201

    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the requested command and return an exit code."""
    args = _build_parser().parse_args(argv)

    try:
        if args.command == "check":
            return _run_check(args)
        return _run_explain(args)
    except (ConfigError, LockError) as error:
        print(f"dependency-floors: {error}", file=sys.stderr)  # noqa: T201
        return EXIT_CONFIG


if __name__ == "__main__":
    sys.exit(main())
