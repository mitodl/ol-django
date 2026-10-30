"""The checks: what a repository must declare for the floors it has set."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import tomllib
from mitol.dependency_floors.config import Config, ConfigError, Floor, lower_bound
from mitol.dependency_floors.graph import DependencyGraph
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

if TYPE_CHECKING:
    from collections.abc import Iterator

#: The install the base ``[project] dependencies`` describe, with no extras.
BASE = ""

#: The lockfile resolved a floored package below its floor.
LOCK_BELOW_FLOOR = "lock-below-floor"

#: A resolver constraint is weaker than the floor it is meant to guard.
CONSTRAINT_BELOW_FLOOR = "constraint-below-floor"

#: A package reaches a floored dependency but publishes no floor for it.
FLOOR_NOT_DECLARED = "floor-not-declared"

#: A package inherits a floor through a sibling it does not require at a
#: version that carries it, so an older release satisfies the dependency.
INHERITED_FLOOR_UNPINNED = "inherited-floor-unpinned"

#: A package declares a floor it already inherits from a sibling.
FLOOR_DECLARED_REDUNDANTLY = "floor-declared-redundantly"

#: A package declares a floor for something nothing in its graph reaches.
FLOOR_NOT_NEEDED = "floor-not-needed"


@dataclass(frozen=True)
class Violation:
    """One thing a repository has to change, and why."""

    rule: str
    path: str
    summary: str
    details: tuple[str, ...] = ()

    def render(self) -> str:
        """Human-readable block, as the CLI prints it."""
        lines = [f"{self.path}  {self.rule}  {self.summary}"]
        lines.extend(f"    {detail}" for detail in self.details)
        return "\n".join(lines)


@dataclass(frozen=True)
class Member:
    """A package in the workspace, as its own manifest declares it."""

    name: str
    path: str
    dependencies: tuple[Requirement, ...]
    extras: dict[str, tuple[Requirement, ...]] = field(default_factory=dict)

    def contexts(self) -> Iterator[tuple[str, tuple[Requirement, ...]]]:
        """Each install this member supports, as a flat requirement list.

        A floor has to hold in every install a consumer can ask for, and extras
        change both what is reachable and what is declared. Checking the base
        install and each extra separately is what catches a floor that is only
        declared inside an extra while the reach exists without it.
        """
        yield BASE, self.dependencies

        for extra, requirements in sorted(self.extras.items()):
            yield extra, (*self.dependencies, *requirements)


def _parse_requirements(raw: object, source: str) -> tuple[Requirement, ...]:
    if not isinstance(raw, list):
        return ()

    parsed = []

    for item in raw:
        if not isinstance(item, str):
            continue
        try:
            parsed.append(Requirement(item))
        except InvalidRequirement as error:
            message = f"{source} declares an unparseable requirement: {item}"
            raise ConfigError(message) from error

    return tuple(parsed)


def _read_member(manifest: Path, relative: str) -> Member | None:
    with manifest.open("rb") as handle:
        project = tomllib.load(handle).get("project")

    if not isinstance(project, dict) or not isinstance(project.get("name"), str):
        return None

    optional = project.get("optional-dependencies")
    extras = {}

    if isinstance(optional, dict):
        extras = {
            name: _parse_requirements(group, relative)
            for name, group in optional.items()
        }

    return Member(
        name=canonicalize_name(project["name"]),
        path=relative,
        dependencies=_parse_requirements(project.get("dependencies"), relative),
        extras=extras,
    )


def discover_members(config: Config) -> tuple[Member, ...]:
    """Every workspace member the configuration points the publishing rules at."""
    if config.members is None:
        return ()

    excluded = {(config.root / entry).resolve() for entry in config.exclude}
    candidates = (
        [config.root]
        if config.members == "."
        else sorted(config.root.glob(config.members))
    )

    members = []

    for directory in candidates:
        manifest = directory / "pyproject.toml"

        if not manifest.is_file() or directory.resolve() in excluded:
            continue

        relative = str(manifest.relative_to(config.root))
        member = _read_member(manifest, relative)

        if member is not None:
            members.append(member)

    return tuple(members)


def _declared(requirements: tuple[Requirement, ...], name: str) -> Requirement | None:
    for requirement in requirements:
        if canonicalize_name(requirement.name) == name:
            return requirement
    return None


def _meets(requirement: Requirement, minimum: Version) -> bool:
    bound = lower_bound(requirement.specifier)
    return bound is not None and bound >= minimum


def _where(context: str) -> str:
    if context == BASE:
        return "[project] dependencies"
    return f'[project.optional-dependencies] "{context}"'


def _why(floor: Floor) -> tuple[str, ...]:
    description = floor.describe()
    return (f"why:  {description}",) if description else ()


def check_lock(config: Config, graph: DependencyGraph) -> list[Violation]:
    """Every floored package the lockfile resolved satisfies its floor.

    This is what makes a resolver cooldown visible. A tool like uv's
    ``exclude-newer`` applies to every package with no carve-out for security
    releases, so an upgrade run can quietly resolve back under a floor; without
    this rule nothing fails and the lock just stops being safe.
    """
    violations = []

    for floor in config.floors:
        for version in graph.versions(floor.name):
            if floor.specifier.contains(version, prereleases=True):
                continue

            violations.append(
                Violation(
                    rule=LOCK_BELOW_FLOOR,
                    path=str(config.lock.relative_to(config.root)),
                    summary=(
                        f"resolves {floor.name} {version}, below the declared "
                        f"floor {floor.specifier}"
                    ),
                    details=(
                        f"fix:  re-lock so {floor.name} resolves at or above "
                        f"{floor.minimum}; if a release-age cooldown is holding "
                        f"it back, exempt {floor.name} from it",
                        *_why(floor),
                    ),
                )
            )

    return violations


def check_constraints(config: Config, manifest: Path) -> list[Violation]:
    """Check a resolver constraint for a floored package against the floor.

    Only checked where a constraint exists. Not every repository uses one, and
    a constraint is not a substitute for a declared floor in any case: it steers
    this repository's own resolution and never reaches a consumer.
    """
    with manifest.open("rb") as handle:
        constraints = (
            tomllib.load(handle)
            .get("tool", {})
            .get("uv", {})
            .get("constraint-dependencies", [])
        )

    parsed = _parse_requirements(constraints, "[tool.uv] constraint-dependencies")
    violations = []

    for floor in config.floors:
        declared = _declared(parsed, floor.name)

        if declared is None or _meets(declared, floor.minimum):
            continue

        violations.append(
            Violation(
                rule=CONSTRAINT_BELOW_FLOOR,
                path=str(manifest.relative_to(config.root)),
                summary=(
                    f"[tool.uv] constraint-dependencies pins {declared}, which "
                    f"is weaker than the declared floor {floor.specifier}"
                ),
                details=(f'fix:  "{floor.name}{floor.specifier}"',),
            )
        )

    return violations


@dataclass(frozen=True)
class Reach:
    """How — or whether — a member arrives at a floored package."""

    kind: str
    via: Requirement | None = None
    path: tuple[str, ...] | None = None

    @property
    def trail(self) -> str:
        """The dependency path, rendered for a message."""
        return " -> ".join(self.path or ())


def _first_reach(
    requirements: tuple[Requirement, ...],
    floor: Floor,
    graph: DependencyGraph,
) -> Reach | None:
    for requirement in requirements:
        found = graph.path_to(requirement.name, floor.name)

        if found is not None:
            return Reach(kind="", via=requirement, path=found)

    return None


def classify(
    requirements: tuple[Requirement, ...],
    floor: Floor,
    graph: DependencyGraph,
    siblings: frozenset[str],
) -> Reach:
    """Decide how this set of requirements reaches a floored package.

    A requirement *on the floored package itself* is excluded from the search.
    Without that, declaring the floor would be what makes the floor reachable,
    and a declaration could never be found redundant.
    """
    candidates = tuple(
        requirement
        for requirement in requirements
        if canonicalize_name(requirement.name) != floor.name
    )
    policy = floor.workspace.policy if floor.workspace else "entry-point"

    direct = tuple(
        requirement
        for requirement in candidates
        if canonicalize_name(requirement.name) not in siblings
    )

    if policy == "closure":
        found = _first_reach(candidates, floor, graph)
        return Reach("entry", found.via, found.path) if found else Reach("none")

    found = _first_reach(direct, floor, graph)

    if found is not None:
        return Reach("entry", found.via, found.path)

    inherited = tuple(
        requirement
        for requirement in candidates
        if canonicalize_name(requirement.name) in siblings
    )
    found = _first_reach(inherited, floor, graph)

    return Reach("inherited", found.via, found.path) if found else Reach("none")


def _provider_satisfied(requirements: tuple[Requirement, ...], floor: Floor) -> bool:
    providers = floor.workspace.providers if floor.workspace else {}

    return any(
        (declared := _declared(requirements, name)) is not None
        and _meets(declared, minimum)
        for name, minimum in providers.items()
    )


@dataclass(frozen=True)
class Scope:
    """One member, as seen from one of the installs it supports.

    The four things every message needs travel together: which member, which
    install of it, what that install requires, and what it already says about
    the floored package.
    """

    member: Member
    context: str
    requirements: tuple[Requirement, ...]
    declared: Requirement | None

    @classmethod
    def of(
        cls,
        member: Member,
        context: str,
        requirements: tuple[Requirement, ...],
        floor: Floor,
    ) -> Scope:
        """Build a scope, resolving what it declares for a given floor."""
        return cls(
            member=member,
            context=context,
            requirements=requirements,
            declared=_declared(requirements, floor.name),
        )


def _entry_violation(scope: Scope, floor: Floor, reach: Reach) -> Violation | None:
    member, context, declared = scope.member, scope.context, scope.declared

    if declared is not None and _meets(declared, floor.minimum):
        return None

    verb = (
        "declares no floor for it"
        if declared is None
        else f"declares {declared}, which is below the floor"
    )

    return Violation(
        rule=FLOOR_NOT_DECLARED,
        path=member.path,
        summary=(
            f"{member.name} reaches {floor.name} through its own dependencies "
            f"but {verb}"
        ),
        details=(
            f"path: {reach.trail}",
            f'fix:  add "{floor.name}{floor.specifier}" to {_where(context)}',
            *_why(floor),
        ),
    )


def _inherited_violations(
    scope: Scope, floor: Floor, reach: Reach, *, redundant: bool
) -> list[Violation]:
    member, context, declared = scope.member, scope.context, scope.declared
    requirements = scope.requirements
    sibling = canonicalize_name(reach.via.name) if reach.via else "a sibling"
    providers = floor.workspace.providers if floor.workspace else {}
    violations = []

    if declared is not None and redundant:
        violations.append(
            Violation(
                rule=FLOOR_DECLARED_REDUNDANTLY,
                path=member.path,
                summary=(
                    f"{member.name} declares {floor.name} directly, but reaches "
                    f"it only through {sibling}, which already carries the floor"
                ),
                details=(f'fix:  drop "{declared}" from {_where(context)}',),
            )
        )

    if _provider_satisfied(requirements, floor):
        return violations

    minimum = providers.get(sibling)
    fix = (
        f'fix:  "{sibling}" -> "{sibling}>={minimum}"'
        if minimum is not None
        else (
            f"fix:  record the first {sibling} release that declares this floor "
            f"under [tool.dependency-floors.floors.{floor.name}.workspace] "
            f"providers, then require it here at or above that version"
        )
    )

    violations.append(
        Violation(
            rule=INHERITED_FLOOR_UNPINNED,
            path=member.path,
            summary=(
                f"{member.name} reaches {floor.name} only through {sibling}, but "
                f"does not require a version of it that carries the floor"
            ),
            details=(f"path: {reach.trail}", fix, *_why(floor)),
        )
    )

    return violations


def check_member(
    member: Member, floor: Floor, graph: DependencyGraph, siblings: frozenset[str]
) -> list[Violation]:
    """Whether one member declares what one floor requires of it."""
    if member.name in floor.direct:
        # The member uses the floored package itself, so reachability says
        # nothing about whether it should declare the floor: it must.
        scope = Scope.of(member, BASE, member.dependencies, floor)
        violation = _entry_violation(scope, floor, Reach("entry", path=(floor.name,)))
        return [violation] if violation else []

    reaches = {
        context: (requirements, classify(requirements, floor, graph, siblings))
        for context, requirements in member.contexts()
    }
    kinds = {reach.kind for _, reach in reaches.values()}

    if kinds == {"none"}:
        declared = _declared(member.dependencies, floor.name) or next(
            (
                found
                for group in member.extras.values()
                if (found := _declared(group, floor.name))
            ),
            None,
        )

        if declared is None:
            return []

        return [
            Violation(
                rule=FLOOR_NOT_NEEDED,
                path=member.path,
                summary=(
                    f"{member.name} declares {declared}, but nothing in its "
                    f"dependency graph reaches {floor.name}"
                ),
                details=("fix:  drop the declaration",),
            )
        ]

    seen: set[str] = set()
    violations: list[Violation] = []

    for context, (requirements, reach) in reaches.items():
        if reach.kind == "none":
            continue

        scope = Scope.of(member, context, requirements, floor)

        found = (
            [_entry_violation(scope, floor, reach)]
            if reach.kind == "entry"
            else _inherited_violations(
                scope, floor, reach, redundant="entry" not in kinds
            )
        )

        for violation in found:
            # The base requirements are part of every extra's context, so a
            # problem there would otherwise be reported once per extra. The
            # base context is yielded first, so the first report is the one
            # that names the place an edit actually fixes.
            if violation is None:
                continue

            key = f"{violation.rule}:{violation.summary}"

            if key in seen:
                continue

            seen.add(key)
            violations.append(violation)

    return violations


def check(config: Config, manifest: Path) -> list[Violation]:
    """Every violation in a repository, most structural first."""
    graph = DependencyGraph.from_uv_lock(config.lock)
    members = discover_members(config)
    siblings = frozenset(member.name for member in members)

    violations = check_lock(config, graph) + check_constraints(config, manifest)

    for member in members:
        for floor in config.floors:
            violations.extend(check_member(member, floor, graph, siblings))

    return violations
