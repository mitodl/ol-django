"""Load and validate the ``[tool.dependency-floors]`` configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomllib
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

#: Operators that place a usable lower bound on a requirement. ``>`` is treated
#: as bounding at its own version, which is conservative: ``>1.0`` is reported
#: as not meeting a ``>=1.0.1`` floor even though no release may sit between
#: them. ``===`` is excluded because its operand is an arbitrary string rather
#: than a version.
LOWER_BOUND_OPERATORS = frozenset({">=", ">", "==", "~="})

POLICIES = frozenset({"entry-point", "closure"})

DEFAULT_LOCK = "uv.lock"


class ConfigError(Exception):
    """The configuration is missing, malformed or self-contradictory."""


@dataclass(frozen=True)
class WorkspaceRule:
    """How a floor applies across the members of a workspace.

    ``providers`` maps a workspace member to the first version of it that
    declares this floor. A member that reaches the floored package only through
    one of those siblings satisfies the floor by depending on the sibling at or
    above that version, rather than by declaring the floored package itself.
    """

    policy: str
    providers: dict[str, Version]


@dataclass(frozen=True)
class Floor:
    """A minimum version of a dependency that has to hold."""

    name: str
    specifier: SpecifierSet
    minimum: Version
    reason: str | None = None
    advisory: str | None = None
    workspace: WorkspaceRule | None = None
    #: Members that depend on the floored package in their own right — because
    #: they import it — rather than reaching it through something else. They
    #: must still declare the floor, but a declaration is never redundant for
    #: them and is never reported as unreachable.
    direct: frozenset[str] = frozenset()

    def describe(self) -> str:
        """One-line description of why this floor exists, if it says."""
        return " — ".join(part for part in (self.reason, self.advisory) if part)


@dataclass(frozen=True)
class Config:
    """Everything the checks need, resolved against a repository root."""

    root: Path
    lock: Path
    members: str | None
    exclude: tuple[str, ...]
    floors: tuple[Floor, ...]

    @property
    def is_workspace(self) -> bool:
        """Whether the publishing rules apply to this repository."""
        return self.members is not None


def lower_bound(specifier: SpecifierSet) -> Version | None:
    """Return the highest lower bound a specifier places, if it places one."""
    bounds = []

    for clause in specifier:
        if clause.operator not in LOWER_BOUND_OPERATORS:
            continue
        try:
            bounds.append(Version(clause.version))
        except InvalidVersion:
            continue

    return max(bounds) if bounds else None


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        message = f"{label} must be a table"
        raise ConfigError(message)
    return value


def _parse_specifier(raw: Any, label: str) -> SpecifierSet:
    if not isinstance(raw, str):
        message = f"{label}.specifier must be a string"
        raise ConfigError(message)

    try:
        return SpecifierSet(raw)
    except InvalidSpecifier as error:
        message = f"{label}.specifier is not a valid specifier: {raw}"
        raise ConfigError(message) from error


def _parse_providers(raw: Any, label: str) -> dict[str, Version]:
    providers = {}

    for name, version in _require_mapping(raw, f"{label}.providers").items():
        if not isinstance(version, str):
            message = f"{label}.providers.{name} must be a version string"
            raise ConfigError(message)
        try:
            providers[canonicalize_name(name)] = Version(version)
        except InvalidVersion as error:
            message = f"{label}.providers.{name} is not a valid version: {version}"
            raise ConfigError(message) from error

    return providers


def _parse_workspace(raw: Any, label: str) -> WorkspaceRule:
    table = _require_mapping(raw, f"{label}.workspace")
    policy = table.get("policy", "entry-point")

    if policy not in POLICIES:
        known = ", ".join(sorted(POLICIES))
        message = f"{label}.workspace.policy must be one of: {known}"
        raise ConfigError(message)

    providers = _parse_providers(table.get("providers", {}), f"{label}.workspace")

    if policy == "closure" and providers:
        message = (
            f"{label}.workspace.providers is meaningless under the 'closure' "
            "policy, where every member that reaches the floor declares it"
        )
        raise ConfigError(message)

    return WorkspaceRule(policy=policy, providers=providers)


def _parse_floor(name: str, raw: Any) -> Floor:
    label = f"[tool.dependency-floors.floors.{name}]"
    table = _require_mapping(raw, label)

    if "specifier" not in table:
        message = f"{label} is missing a specifier"
        raise ConfigError(message)

    specifier = _parse_specifier(table["specifier"], label)
    minimum = lower_bound(specifier)

    if minimum is None:
        message = (
            f"{label}.specifier places no lower bound on the version, so there "
            f"is no floor to enforce: {table['specifier']}"
        )
        raise ConfigError(message)

    workspace = (
        _parse_workspace(table["workspace"], label) if "workspace" in table else None
    )
    raw_direct = table.get("direct", [])

    if not isinstance(raw_direct, list):
        message = f"{label}.direct must be an array of package names"
        raise ConfigError(message)

    return Floor(
        name=canonicalize_name(name),
        specifier=specifier,
        minimum=minimum,
        reason=table.get("reason"),
        advisory=table.get("advisory"),
        workspace=workspace,
        direct=frozenset(canonicalize_name(entry) for entry in raw_direct),
    )


def load(manifest: Path) -> Config:
    """Read the configuration out of a repository's ``pyproject.toml``.

    Raises ``ConfigError`` if the file, the table or any floor is unusable. A
    repository that declares no floors is a configuration error rather than a
    silent pass, so a deleted table cannot look like a clean run.
    """
    if not manifest.is_file():
        message = f"no such file: {manifest}"
        raise ConfigError(message)

    with manifest.open("rb") as handle:
        document = tomllib.load(handle)

    table = document.get("tool", {}).get("dependency-floors")

    if table is None:
        message = f"{manifest} declares no [tool.dependency-floors] table"
        raise ConfigError(message)

    table = _require_mapping(table, "[tool.dependency-floors]")
    options = _require_mapping(
        table.get("options", {}), "[tool.dependency-floors.options]"
    )
    floors = _require_mapping(
        table.get("floors", {}), "[tool.dependency-floors.floors]"
    )

    if not floors:
        message = f"{manifest} declares no floors under [tool.dependency-floors.floors]"
        raise ConfigError(message)

    root = manifest.parent

    return Config(
        root=root,
        lock=root / options.get("lock", DEFAULT_LOCK),
        members=options.get("members"),
        exclude=tuple(options.get("exclude", ())),
        floors=tuple(_parse_floor(name, raw) for name, raw in sorted(floors.items())),
    )
