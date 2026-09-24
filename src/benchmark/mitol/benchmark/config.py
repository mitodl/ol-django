"""
Discovery, merging and validation of the three benchmark configuration layers.

A benchmark is described by three files, because the three have different
owners and different lifetimes:

``benchmark.toml``        committed, project-wide: how to start Django and where
                          the scratch database lives.
``<name>.toml``           committed, per benchmark: the target, the shape knobs,
                          the seed, and the production evidence it is calibrated
                          against. This is the file an agent edits.
``benchmark.local.toml``  **not** committed: which execution backend this
                          developer's machine uses, and any connection strings
                          that go with it.

Nothing is repeated between the three, and a file that declares a section
belonging to another layer is rejected rather than silently ignored — that is
what stops the separation drifting back into copy-paste.

Merge precedence, lowest to highest:
project -> benchmark -> local -> environment -> CLI flags.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomllib

PROJECT_CONFIG_NAME = "benchmark.toml"
LOCAL_CONFIG_NAME = "benchmark.local.toml"
LOCAL_CONFIG_ENV_VAR = "OL_BENCHMARK_LOCAL_CONFIG"
CONFIG_ENV_VAR = "OL_BENCHMARK_CONFIG_JSON"
IDS_ENV_VAR = "OL_BENCHMARK_IDS_JSON"
LABEL_ENV_VAR = "OL_BENCHMARK_LABEL"
KNOB_ENV_PREFIX = "BENCH_"

# A scratch database is dropped and recreated on every run. Refusing any name
# that is not obviously scratch is what keeps that away from a real database
# in a shared cluster.
REQUIRED_DB_NAME_PREFIX = "bench"

_PROJECT_SECTIONS = frozenset({"django", "database", "defaults"})
_LOCAL_SECTIONS = frozenset({"backend", "database", "django", "defaults"})
_BENCHMARK_SECTIONS = frozenset(
    {"benchmark", "knobs", "seed", "target", "auth", "measure", "trace", "calibration"}
)
# Sections whose string values are expanded against the environment.
_INTERPOLATED_SECTIONS = ("django", "database", "backend")

_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_NON_SLUG = re.compile(r"[^a-z0-9]+")
_CREDENTIALS = re.compile(r"(?<=//)[^/@\s]+:[^/@\s]+(?=@)")

SEED_STEP_KINDS = frozenset({"factory", "model", "fixture", "sql", "hook"})


class ConfigError(ValueError):
    """A benchmark configuration is missing, malformed or self-contradictory."""


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------


def _deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    """Merge ``overlay`` onto ``base``, recursing into nested tables."""
    merged = dict(base)
    for key, value in overlay.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def expand_env(value: Any, environ: Mapping[str, str] | None = None) -> Any:
    """
    Expand ``${VAR}`` and ``${VAR:-default}`` in every string within ``value``.

    An unset variable with no default is an error naming the variable: an empty
    connection string produces a confusing failure a long way from its cause.
    """
    env = os.environ if environ is None else environ
    if isinstance(value, str):
        return _expand_string(value, env)
    if isinstance(value, Mapping):
        return {key: expand_env(item, env) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [expand_env(item, env) for item in value]
    return value


def _closing_brace(value: str, start: int) -> int:
    """
    Return the index just past the ``}`` that closes the ``${`` at ``start``.

    Braces are counted rather than matched with a regex because a default may
    itself contain them — a URL template's ``{name}`` placeholder is the usual
    case, and a non-greedy pattern gets it wrong in both directions.
    """
    depth, position = 1, start + 2
    while position < len(value):
        if value[position] == "{":
            depth += 1
        elif value[position] == "}":
            depth -= 1
            if depth == 0:
                return position + 1
        position += 1
    return -1


def _expand_string(value: str, env: Mapping[str, str]) -> str:
    pieces: list[str] = []
    position = 0
    while position < len(value):
        start = value.find("${", position)
        if start == -1:
            pieces.append(value[position:])
            break
        end = _closing_brace(value, start)
        if end == -1:
            pieces.append(value[position:])
            break
        pieces.append(value[position:start])
        pieces.append(_expand_token(value[start + 2 : end - 1], env))
        position = end
    return "".join(pieces)


def _expand_token(token: str, env: Mapping[str, str]) -> str:
    name, separator, default = token.partition(":-")
    if not _ENV_NAME.match(name):
        # Not an environment reference at all; leave it exactly as written.
        return "${" + token + "}"
    if name in env:
        return env[name]
    if separator:
        return default
    msg = (
        f"${{{token}}}: environment variable {name!r} is not set and the "
        f"reference declares no ':-default'"
    )
    raise ConfigError(msg)


def redact(value: Any) -> Any:
    """Mask ``user:password@`` credentials in every string within ``value``."""
    if isinstance(value, str):
        return _CREDENTIALS.sub("***:***", value)
    if isinstance(value, Mapping):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


def slugify(name: str) -> str:
    """Turn a benchmark name into something safe to use as a database name."""
    return _NON_SLUG.sub("_", name.strip().lower()).strip("_")


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError as exc:
        msg = f"{path}: no such configuration file"
        raise ConfigError(msg) from exc
    except tomllib.TOMLDecodeError as exc:
        msg = f"{path}: invalid TOML — {exc}"
        raise ConfigError(msg) from exc


def _check_sections(
    path: Path, data: Mapping[str, Any], allowed: frozenset[str], layer: str
) -> None:
    for section in data:
        if section in allowed:
            continue
        home = _section_home(section)
        msg = (
            f"{path}: [{section}] does not belong in the {layer} config"
            f"{home}. See the layer table in the mitol-django-benchmark README."
        )
        raise ConfigError(msg)


def _section_home(section: str) -> str:
    if section == "backend":
        return (
            f"; the execution backend is a per-developer choice, so it lives in "
            f"{LOCAL_CONFIG_NAME} (which is not committed)"
        )
    if section in _PROJECT_SECTIONS:
        return f"; it is project-wide, so it lives in {PROJECT_CONFIG_NAME}"
    if section in _BENCHMARK_SECTIONS:
        return "; it describes one benchmark, so it lives in that benchmark's file"
    return ""


def find_upwards(start: Path, name: str) -> Path | None:
    """Return the nearest ``name`` at or above ``start``, if there is one."""
    start = start.resolve()
    directories = [start, *start.parents] if start.is_dir() else list(start.parents)
    for directory in directories:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


# --------------------------------------------------------------------------
# resolved configuration
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DjangoConfig:
    """How a step process bootstraps the application's Django."""

    settings_module: str
    pythonpath: tuple[str, ...] = ()
    chdir: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DatabaseConfig:
    """The scratch database: where it is, and how it is reached."""

    name: str
    url: str
    admin_url: str
    analyze: bool = True


@dataclass(frozen=True)
class BackendConfig:
    """Which execution backend runs the steps, and how it is configured."""

    kind: str = "local"
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MeasureConfig:
    """Measurement method: how many calls, and which preconditions to enforce."""

    warmup: int = 3
    iterations: int = 15
    trace_repeats: int = 7
    # Middleware substrings to strip before measuring. Stripping is recorded in
    # every result; there is no silent removal.
    middleware_exclude: tuple[str, ...] = ()
    allow_profilers: bool = False


@dataclass(frozen=True)
class TargetConfig:
    """The request under test."""

    reverse: str | None = None
    reverse_args: tuple[Any, ...] = ()
    reverse_kwargs: Mapping[str, Any] = field(default_factory=dict)
    path: str | None = None
    method: str = "get"
    params: Mapping[str, Any] = field(default_factory=dict)
    data: Mapping[str, Any] | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    expect_status: int = 200
    # Where the equivalence check finds its counts in the response body.
    count_key: str = "count"
    results_key: str = "results"
    # Nested collections whose serialized length is worth reporting per request.
    nested_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuthConfig:
    """Who the request is made as. All fields unset means anonymous."""

    user_id: Any = None
    username: str | None = None


@dataclass(frozen=True)
class SeedStep:
    """One step of the declarative seed."""

    name: str
    kind: str = "factory"
    factory: str | None = None
    model: str | None = None
    hook: str | None = None
    count: Any = 1
    kwargs: Mapping[str, Any] = field(default_factory=dict)
    m2m: Mapping[str, Any] = field(default_factory=dict)
    fixtures: tuple[str, ...] = ()
    statements: tuple[str, ...] = ()
    # Build in memory and bulk_create. Much faster for large steps, but skips
    # post-generation hooks and leaves m2m to the m2m block.
    bulk: bool = False


@dataclass(frozen=True)
class SeedConfig:
    """The dataset to build, and the scalars it exports to later steps."""

    steps: tuple[SeedStep, ...] = ()
    export: Mapping[str, str] = field(default_factory=dict)
    random_seed: int = 1234


@dataclass(frozen=True)
class Classifier:
    """
    One rule mapping a SQL statement to a logical query label.

    ``targeted`` marks a query the change under test is meant to affect. It
    is what lets the production comparison tell a deliberate improvement apart
    from a seed that is the wrong shape: an untargeted query drifting from
    production is a calibration problem, the same query drifting when it *is*
    the target is the result.
    """

    label: str
    pattern: str
    targeted: bool = False


@dataclass(frozen=True)
class TraceConfig:
    """Span capture and how spans are grouped for attribution."""

    classify: tuple[Classifier, ...] = ()
    otlp_endpoint: str | None = None


@dataclass(frozen=True)
class Observable:
    """
    One production measurement the seed is calibrated against.

    Calibrate only on observables the change under test does not affect:
    tuning the seed against the query you changed is circular. Set
    ``seed_step`` where the observable corresponds to a seed step's row count
    and the report can fill the comparison in for you.
    """

    name: str
    source: str = ""
    production: Any = None
    seed_step: str = ""
    note: str = ""


@dataclass(frozen=True)
class CalibrationConfig:
    """Production evidence, echoed into the report next to the numbers."""

    observables: tuple[Observable, ...] = ()
    # A committed baseline distilled from production traces: per-query
    # medians keyed by classifier label, carrying no statement text. Built by
    # `ol-benchmark baseline`; see mitol.benchmark.baseline for why the raw
    # trace is never the committed artifact.
    baseline: Path | None = None
    # How far a query the change does not touch may differ from production
    # before the report calls the seed into question. Local is expected to be
    # faster; the alarm is local being slower.
    drift_factor: float = 5.0
    # Row-count floors per seed step, from IN-list placeholder counts in a
    # production trace. Falling short of one is a warning, not an error: a
    # truncated export makes these lower bounds.
    floors: Mapping[str, int] = field(default_factory=dict)
    notes: str = ""


@dataclass(frozen=True)
class BenchmarkConfig:
    """A fully merged, environment-expanded benchmark configuration."""

    name: str
    django: DjangoConfig
    database: DatabaseConfig
    target: TargetConfig
    description: str = ""
    backend: BackendConfig = field(default_factory=BackendConfig)
    measure: MeasureConfig = field(default_factory=MeasureConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    seed: SeedConfig = field(default_factory=SeedConfig)
    trace: TraceConfig = field(default_factory=TraceConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    knobs: Mapping[str, Any] = field(default_factory=dict)
    # The merged mapping this was built from. Serializing it is how a step
    # process in a container receives the configuration: the files themselves
    # may not exist there, and the host's environment is the authority on
    # ${VAR} expansion.
    raw: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def slug(self) -> str:
        """The benchmark name in a form safe for filenames and DB names."""
        return slugify(self.name)

    def as_dict(self) -> dict[str, Any]:
        """Return the merged mapping, for handing to a step process."""
        return dict(self.raw)

    def redacted_dict(self) -> dict[str, Any]:
        """Return the merged mapping with connection credentials masked."""
        return {
            "config": redact(self.as_dict()),
            "provenance": {key: list(value) for key, value in self.provenance.items()},
        }


# --------------------------------------------------------------------------
# construction from a merged mapping
# --------------------------------------------------------------------------


def _require(data: Mapping[str, Any], section: str, key: str) -> Any:
    try:
        return data[section][key]
    except KeyError as exc:
        msg = f"[{section}].{key} is required"
        raise ConfigError(msg) from exc


def _django_from(data: Mapping[str, Any]) -> DjangoConfig:
    section = data.get("django", {})
    return DjangoConfig(
        settings_module=_require(data, "django", "settings_module"),
        pythonpath=tuple(section.get("pythonpath", ())),
        chdir=section.get("chdir"),
        env={str(k): str(v) for k, v in section.get("env", {}).items()},
    )


def _database_from(data: Mapping[str, Any], benchmark_name: str) -> DatabaseConfig:
    section = data.get("database", {})
    prefix = section.get("name_prefix", "bench_")
    name = section.get("name") or f"{prefix}{slugify(benchmark_name)}"
    if not name.startswith(REQUIRED_DB_NAME_PREFIX):
        msg = (
            f"[database].name resolved to {name!r}, which does not start with "
            f"{REQUIRED_DB_NAME_PREFIX!r}. This database is dropped and "
            f"recreated on every run, so the harness refuses any name that is "
            f"not obviously a scratch one."
        )
        raise ConfigError(msg)
    template = section.get(
        "url_template", "postgres://postgres:postgres@localhost:5432/{name}"
    )
    if "{name}" not in template:
        msg = "[database].url_template must contain the {name} placeholder"
        raise ConfigError(msg)
    admin_url = section.get(
        "admin_url", "postgres://postgres:postgres@localhost:5432/postgres"
    )
    url = template.format(name=name)
    if admin_url == url:
        msg = (
            "[database].admin_url points at the scratch database itself; it "
            "must connect to a different database, because DROP DATABASE "
            "cannot run from inside the database being dropped"
        )
        raise ConfigError(msg)
    return DatabaseConfig(
        name=name,
        url=url,
        admin_url=admin_url,
        analyze=bool(section.get("analyze", True)),
    )


def _backend_from(data: Mapping[str, Any]) -> BackendConfig:
    section = dict(data.get("backend", {}))
    kind = section.pop("kind", "local")
    return BackendConfig(kind=kind, options=section)


def _measure_from(data: Mapping[str, Any]) -> MeasureConfig:
    section = data.get("measure", {})
    return MeasureConfig(
        warmup=int(section.get("warmup", 3)),
        iterations=int(section.get("iterations", 15)),
        trace_repeats=int(section.get("trace_repeats", 7)),
        middleware_exclude=tuple(section.get("middleware_exclude", ())),
        allow_profilers=bool(section.get("allow_profilers", False)),
    )


def _target_from(data: Mapping[str, Any]) -> TargetConfig:
    section = data.get("target")
    if not section:
        msg = "[target] is required: there is nothing to benchmark without it"
        raise ConfigError(msg)
    reverse, path = section.get("reverse"), section.get("path")
    if bool(reverse) == bool(path):
        msg = "[target] needs exactly one of 'reverse' or 'path'"
        raise ConfigError(msg)
    return TargetConfig(
        reverse=reverse,
        reverse_args=tuple(section.get("reverse_args", ())),
        reverse_kwargs=section.get("reverse_kwargs", {}),
        path=path,
        method=str(section.get("method", "get")).lower(),
        params=section.get("params", {}),
        data=section.get("data"),
        headers=section.get("headers", {}),
        expect_status=int(section.get("expect_status", 200)),
        count_key=section.get("count_key", "count"),
        results_key=section.get("results_key", "results"),
        nested_keys=tuple(section.get("nested_keys", ())),
    )


def _seed_step_from(index: int, entry: Mapping[str, Any]) -> SeedStep:
    name = entry.get("name")
    if not name:
        msg = f"[[seed.step]] #{index + 1} has no 'name'"
        raise ConfigError(msg)
    kind = entry.get("kind") or ("hook" if entry.get("hook") else None)
    if kind is None:
        kind = "model" if entry.get("model") and not entry.get("factory") else "factory"
    if kind not in SEED_STEP_KINDS:
        known = sorted(SEED_STEP_KINDS)
        msg = f"seed step {name!r}: unknown kind {kind!r} (known: {known})"
        raise ConfigError(msg)
    step = SeedStep(
        name=name,
        kind=kind,
        factory=entry.get("factory"),
        model=entry.get("model"),
        hook=entry.get("hook"),
        count=entry.get("count", 1),
        kwargs=entry.get("kwargs", {}),
        m2m=entry.get("m2m", {}),
        fixtures=tuple(entry.get("fixtures", ())),
        statements=tuple(entry.get("statements", ())),
        bulk=bool(entry.get("bulk", False)),
    )
    _check_step_requirements(step)
    return step


_STEP_REQUIREMENTS = {
    "factory": ("factory", "a dotted path such as 'app.factories:ThingFactory'"),
    "model": ("model", "a dotted path such as 'app.models:Thing'"),
    "hook": ("hook", "a dotted path such as 'app.bench:build_things'"),
    "fixture": ("fixtures", "a list of fixture paths for loaddata"),
    "sql": ("statements", "a list of SQL statements"),
}


def _check_step_requirements(step: SeedStep) -> None:
    attribute, description = _STEP_REQUIREMENTS[step.kind]
    if not getattr(step, attribute):
        msg = (
            f"seed step {step.name!r} is kind '{step.kind}' but sets no "
            f"'{attribute}' ({description})"
        )
        raise ConfigError(msg)


def _seed_from(data: Mapping[str, Any]) -> SeedConfig:
    section = data.get("seed", {})
    steps = tuple(
        _seed_step_from(index, entry)
        for index, entry in enumerate(section.get("step", ()))
    )
    seen: set[str] = set()
    for step in steps:
        if step.name in seen:
            msg = f"seed step {step.name!r} is declared twice; names must be unique"
            raise ConfigError(msg)
        seen.add(step.name)
    return SeedConfig(
        steps=steps,
        export=section.get("export", {}),
        random_seed=int(section.get("random_seed", 1234)),
    )


def _trace_from(data: Mapping[str, Any]) -> TraceConfig:
    section = data.get("trace", {})
    classify = []
    for index, entry in enumerate(section.get("classify", ())):
        if not entry.get("label") or not entry.get("pattern"):
            msg = f"[[trace.classify]] #{index + 1} needs both 'label' and 'pattern'"
            raise ConfigError(msg)
        try:
            re.compile(entry["pattern"])
        except re.error as exc:
            msg = f"[[trace.classify]] {entry['label']!r}: invalid regex — {exc}"
            raise ConfigError(msg) from exc
        classify.append(
            Classifier(
                label=entry["label"],
                pattern=entry["pattern"],
                targeted=bool(entry.get("targeted", False)),
            )
        )
    return TraceConfig(
        classify=tuple(classify), otlp_endpoint=section.get("otlp_endpoint")
    )


def _calibration_from(data: Mapping[str, Any]) -> CalibrationConfig:
    section = data.get("calibration", {})
    observables = tuple(
        Observable(
            name=entry.get("name", ""),
            source=entry.get("source", ""),
            production=entry.get("production"),
            seed_step=entry.get("seed_step", ""),
            note=entry.get("note", ""),
        )
        for entry in section.get("observable", ())
    )
    floors = {str(k): int(v) for k, v in section.get("floors", {}).items()}
    return CalibrationConfig(
        observables=observables,
        floors=floors,
        notes=section.get("notes", ""),
        baseline=_baseline_path(data, section.get("baseline")),
        drift_factor=float(section.get("drift_factor", 5.0)),
    )


def _baseline_path(data: Mapping[str, Any], declared: Any) -> Path | None:
    """
    Resolve ``[calibration].baseline`` against the benchmark file's directory.

    Relative to the benchmark, not the working directory: the two live
    together in ``benchmarks/`` and are committed together, so the reference
    has to survive being run from anywhere in the repository.
    """
    if not declared:
        return None
    path = Path(str(declared))
    if path.is_absolute():
        return path
    benchmark_file = (data.get("_layers") or {}).get("benchmark")
    base = Path(benchmark_file).parent if benchmark_file else Path()
    return base / path


def from_merged(
    data: Mapping[str, Any],
    provenance: Mapping[str, tuple[str, ...]] | None = None,
) -> BenchmarkConfig:
    """Build a :class:`BenchmarkConfig` from an already-merged mapping."""
    name = data.get("benchmark", {}).get("name")
    if not name:
        msg = "[benchmark].name is required"
        raise ConfigError(msg)
    return BenchmarkConfig(
        name=name,
        description=data.get("benchmark", {}).get("description", ""),
        django=_django_from(data),
        database=_database_from(data, name),
        backend=_backend_from(data),
        measure=_measure_from(data),
        target=_target_from(data),
        auth=AuthConfig(
            user_id=data.get("auth", {}).get("user_id"),
            username=data.get("auth", {}).get("username"),
        ),
        seed=_seed_from(data),
        trace=_trace_from(data),
        calibration=_calibration_from(data),
        knobs=data.get("knobs", {}),
        raw=data,
        provenance=provenance or {},
    )


# --------------------------------------------------------------------------
# knob overrides
# --------------------------------------------------------------------------


def knob_env_var(name: str) -> str:
    """Return the environment variable that overrides the knob ``name``."""
    return f"{KNOB_ENV_PREFIX}{name.upper()}"


def _coerce(name: str, value: Any, declared: Any) -> Any:
    if not isinstance(value, str) or isinstance(declared, str):
        return value
    if isinstance(declared, bool):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        msg = f"knob {name!r} expects a boolean, got {value!r}"
        raise ConfigError(msg)
    for kind in (int, float):
        if isinstance(declared, kind):
            try:
                return kind(value)
            except ValueError as exc:
                msg = f"knob {name!r} expects {kind.__name__}, got {value!r}"
                raise ConfigError(msg) from exc
    return value


def apply_knob_overrides(
    knobs: Mapping[str, Any],
    overrides: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """
    Layer environment and explicit overrides onto the declared knobs.

    Environment overrides only touch knobs the benchmark declares: the
    ``BENCH_`` namespace is shared with the harness's own variables, so an
    unrecognised one is not an error. An explicit override *is* checked, because
    a mistyped ``--knob`` that silently does nothing would be reported as a
    result at the wrong shape.
    """
    env = os.environ if environ is None else environ
    resolved = dict(knobs)
    for name, declared in knobs.items():
        raw = env.get(knob_env_var(name))
        if raw is not None:
            resolved[name] = _coerce(name, raw, declared)
    for name, value in (overrides or {}).items():
        if name not in knobs:
            known = ", ".join(sorted(knobs)) or "none declared"
            msg = f"unknown knob {name!r} (declared knobs: {known})"
            raise ConfigError(msg)
        resolved[name] = _coerce(name, value, knobs[name])
    return resolved


# --------------------------------------------------------------------------
# layer discovery and loading
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Layers:
    """Where each configuration layer was found."""

    benchmark: Path
    project: Path | None = None
    local: Path | None = None

    def describe(self) -> dict[str, str | None]:
        """Return the layer paths as strings, for reporting."""
        return {
            "project": str(self.project) if self.project else None,
            "benchmark": str(self.benchmark),
            "local": str(self.local) if self.local else None,
        }


def discover_layers(
    benchmark_path: Path | str,
    project_path: Path | str | None = None,
    local_path: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Layers:
    """
    Locate the project and local layers that go with a benchmark file.

    Both are searched for at or above the benchmark file's directory, so the
    conventional ``benchmarks/`` directory and a repository root both work.
    The local layer is optional; its absence means the defaults apply.
    """
    env = os.environ if environ is None else environ
    benchmark = Path(benchmark_path).resolve()
    if not benchmark.is_file():
        msg = f"{benchmark}: no such benchmark configuration file"
        raise ConfigError(msg)

    if project_path is not None:
        project = Path(project_path).resolve()
        if not project.is_file():
            msg = f"{project}: no such project configuration file"
            raise ConfigError(msg)
    else:
        project = find_upwards(benchmark.parent, PROJECT_CONFIG_NAME)

    if local_path is None:
        local_path = env.get(LOCAL_CONFIG_ENV_VAR)
    if local_path is not None:
        local = Path(local_path).resolve()
        if not local.is_file():
            msg = f"{local}: no such local configuration file"
            raise ConfigError(msg)
    else:
        local = find_upwards(benchmark.parent, LOCAL_CONFIG_NAME)

    return Layers(benchmark=benchmark, project=project, local=local)


def _apply_defaults(merged: dict[str, Any]) -> dict[str, Any]:
    """Fold ``[defaults.<section>]`` in underneath ``[<section>]``."""
    defaults = merged.pop("defaults", None)
    if not defaults:
        return merged
    for section, values in defaults.items():
        if not isinstance(values, Mapping):
            msg = f"[defaults].{section} must be a table"
            raise ConfigError(msg)
        merged[section] = _deep_merge(values, merged.get(section, {}))
    return merged


def load(
    benchmark_path: Path | str,
    project_path: Path | str | None = None,
    local_path: Path | str | None = None,
    knob_overrides: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> BenchmarkConfig:
    """
    Load, merge and validate the three configuration layers.

    Precedence, lowest to highest: project, benchmark, local, environment,
    ``knob_overrides``.
    """
    layers = discover_layers(benchmark_path, project_path, local_path, environ)

    merged: dict[str, Any] = {}
    provenance: dict[str, list[str]] = {}
    sources = (
        ("project", layers.project, _PROJECT_SECTIONS),
        ("benchmark", layers.benchmark, _BENCHMARK_SECTIONS),
        ("local", layers.local, _LOCAL_SECTIONS),
    )
    for label, path, allowed in sources:
        if path is None:
            continue
        data = _read_toml(path)
        _check_sections(path, data, allowed, label)
        for section in data:
            provenance.setdefault(section, []).append(label)
        merged = _deep_merge(merged, data)

    merged = _apply_defaults(merged)
    for section in _INTERPOLATED_SECTIONS:
        if section in merged:
            merged[section] = expand_env(merged[section], environ)

    merged["knobs"] = apply_knob_overrides(
        merged.get("knobs", {}), knob_overrides, environ
    )
    merged["_layers"] = layers.describe()

    return from_merged(merged, {k: tuple(v) for k, v in provenance.items()})


def from_dict(data: Mapping[str, Any]) -> BenchmarkConfig:
    """
    Rebuild a configuration inside a step process.

    The step never re-reads the files or re-expands ``${VAR}``: the files may
    not exist in a container, and the host's environment is the authority on
    what a reference expanded to.
    """
    return from_merged(dict(data), _provenance_from(data))


def _provenance_from(data: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    layers = data.get("_layers") or {}
    return {"_layers": tuple(str(v) for v in layers.values() if v)} if layers else {}
