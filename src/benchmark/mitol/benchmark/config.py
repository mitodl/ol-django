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
from typing import Any, TypeVar

import tomllib
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

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
    {
        "benchmark",
        "knobs",
        "seed",
        "target",
        "auth",
        "measure",
        "memory",
        "trace",
        "calibration",
    }
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


class _Section(BaseModel):
    """A validated configuration section; the TOML mapping is the input."""

    model_config = ConfigDict(frozen=True)


_SectionT = TypeVar("_SectionT", bound=_Section)


class DjangoConfig(_Section):
    """How a step process bootstraps the application's Django."""

    settings_module: str
    pythonpath: tuple[str, ...] = ()
    chdir: str | None = None
    env: Mapping[str, str] = {}

    @field_validator("env", mode="before")
    @classmethod
    def _stringified(cls, value: Any) -> dict[str, str]:
        return {str(key): str(item) for key, item in (value or {}).items()}


class DatabaseConfig(_Section):
    """The scratch database: where it is, and how it is reached."""

    name: str
    url: str
    admin_url: str
    analyze: bool = True

    @model_validator(mode="before")
    @classmethod
    def _derived(cls, data: Any, info: ValidationInfo) -> Any:
        """Derive the name and URL the declared pieces describe."""
        if not isinstance(data, Mapping) or "url" in data:
            return data
        section = dict(data)
        prefix = section.pop("name_prefix", "bench_")
        benchmark_name = (info.context or {}).get("benchmark_name", "")
        name = section.get("name") or f"{prefix}{slugify(benchmark_name)}"
        if not name.startswith(REQUIRED_DB_NAME_PREFIX):
            msg = (
                f"[database].name resolved to {name!r}, which does not start with "
                f"{REQUIRED_DB_NAME_PREFIX!r}. This database is dropped and "
                f"recreated on every run, so the harness refuses any name that is "
                f"not obviously a scratch one."
            )
            raise ConfigError(msg)
        template = section.pop(
            "url_template", "postgres://postgres:postgres@localhost:5432/{name}"
        )
        if "{name}" not in template:
            msg = "[database].url_template must contain the {name} placeholder"
            raise ConfigError(msg)
        section["name"] = name
        section["url"] = template.format(name=name)
        section.setdefault(
            "admin_url", "postgres://postgres:postgres@localhost:5432/postgres"
        )
        if section["admin_url"] == section["url"]:
            msg = (
                "[database].admin_url points at the scratch database itself; it "
                "must connect to a different database, because DROP DATABASE "
                "cannot run from inside the database being dropped"
            )
            raise ConfigError(msg)
        return section


class BackendConfig(_Section):
    """Which execution backend runs the steps, and how it is configured."""

    kind: str = "local"
    options: Mapping[str, Any] = {}

    @model_validator(mode="before")
    @classmethod
    def _split(cls, data: Any) -> Any:
        """Everything in the section besides ``kind`` is backend options."""
        if not isinstance(data, Mapping) or "options" in data:
            return data
        section = dict(data)
        return {"kind": section.pop("kind", "local"), "options": section}


class MeasureConfig(_Section):
    """Measurement method: how many calls, and which preconditions to enforce."""

    warmup: int = 3
    iterations: int = 15
    trace_repeats: int = 7
    # Middleware substrings to strip before measuring. Stripping is recorded in
    # every result; there is no silent removal.
    middleware_exclude: tuple[str, ...] = ()
    allow_profilers: bool = False
    # Seeding a Wagtail or file-bearing model uploads through the default
    # storage. A developer environment commonly carries real credentials for a
    # real bucket, so a remote backend is refused rather than written to.
    allow_remote_storage: bool = False


class MemoryConfig(_Section):
    """
    The retention pass: what the process keeps after serving the endpoint.

    Separate from `[measure]` because it answers a different question and is
    run on one ref rather than two. A latency benchmark that exonerates an
    endpoint leaves open whether the request is growing the worker, and that
    is what makes a fast endpoint slow in production.
    """

    # A zero-request pass would report a confident "stable" about nothing,
    # so the floor is validated rather than clamped at the call sites.
    requests: int = Field(default=30, ge=1)
    warmup: int = Field(default=1, ge=0)
    # Name what is retained, and walk the reference graph to find what holds
    # it. Off makes the pass a pure growth measurement with no heap scans.
    attribute: bool = True
    # How many of the most-retained types to trace back to a named holder.
    holders: int = 3
    # Ceiling on `gc.get_referrers` calls across all walks. Each one is a
    # full-heap scan, so this is the real cost control.
    scan_budget: int = 400
    # Objects still reachable per request, after a forced collection, before
    # the verdict calls it a leak. Some growth is a cache warming; sustained
    # growth is something holding references across requests.
    retained_objects_per_request: float = 10.0
    # RSS growth per request that counts as a high-water mark when live
    # objects are flat — the allocator holding freed arenas, not retention.
    highwater_mib_per_request: float = 0.1


class TargetConfig(_Section):
    """The request under test."""

    reverse: str | None = None
    reverse_args: tuple[Any, ...] = ()
    reverse_kwargs: Mapping[str, Any] = {}
    path: str | None = None
    method: str = "get"
    params: Mapping[str, Any] = {}
    expect_status: int = 200
    # Where the equivalence check finds its counts in the response body.
    count_key: str = "count"
    results_key: str = "results"
    # Nested collections whose serialized length is worth reporting per request.
    nested_keys: tuple[str, ...] = ()
    # An empty collection is refused rather than timed: both arms would agree,
    # so nothing downstream could tell you the measurement described nothing.
    # Set this only where an empty response is the thing being measured.
    allow_empty: bool = False

    @field_validator("method")
    @classmethod
    def _lowercased(cls, value: str) -> str:
        return value.lower()

    @model_validator(mode="after")
    def _exactly_one_of_reverse_or_path(self) -> TargetConfig:
        if bool(self.reverse) == bool(self.path):
            msg = "[target] needs exactly one of 'reverse' or 'path'"
            raise ConfigError(msg)
        return self


class AuthConfig(_Section):
    """Who the request is made as. All fields unset means anonymous."""

    user_id: Any = None
    username: str | None = None


class SeedStep(_Section):
    """One step of the declarative seed."""

    name: str
    kind: str = "factory"
    factory: str | None = None
    model: str | None = None
    hook: str | None = None
    count: Any = 1
    kwargs: Mapping[str, Any] = {}
    m2m: Mapping[str, Any] = {}
    fixtures: tuple[str, ...] = ()
    statements: tuple[str, ...] = ()
    # Build in memory and bulk_create. Much faster for large steps, but skips
    # post-generation hooks and leaves m2m to the m2m block.
    bulk: bool = False

    @model_validator(mode="before")
    @classmethod
    def _inferred_kind(cls, entry: Any) -> Any:
        """Infer an undeclared kind from which dotted path the step sets."""
        if not isinstance(entry, Mapping) or entry.get("kind"):
            return entry
        entry = dict(entry)
        if entry.get("hook"):
            entry["kind"] = "hook"
        elif entry.get("model") and not entry.get("factory"):
            entry["kind"] = "model"
        else:
            entry["kind"] = "factory"
        return entry

    @model_validator(mode="after")
    def _kind_requirements(self) -> SeedStep:
        if self.kind not in SEED_STEP_KINDS:
            known = sorted(SEED_STEP_KINDS)
            msg = (
                f"seed step {self.name!r}: unknown kind {self.kind!r} (known: {known})"
            )
            raise ConfigError(msg)
        attribute, description = _STEP_REQUIREMENTS[self.kind]
        if not getattr(self, attribute):
            msg = (
                f"seed step {self.name!r} is kind '{self.kind}' but sets no "
                f"'{attribute}' ({description})"
            )
            raise ConfigError(msg)
        return self


_STEP_REQUIREMENTS = {
    "factory": ("factory", "a dotted path such as 'app.factories:ThingFactory'"),
    "model": ("model", "a dotted path such as 'app.models:Thing'"),
    "hook": ("hook", "a dotted path such as 'app.bench:build_things'"),
    "fixture": ("fixtures", "a list of fixture paths for loaddata"),
    "sql": ("statements", "a list of SQL statements"),
}


class SeedConfig(_Section):
    """The dataset to build, and the scalars it exports to later steps."""

    steps: tuple[SeedStep, ...] = Field(default=(), alias="step")
    export: Mapping[str, str] = {}
    random_seed: int = 1234

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    @model_validator(mode="after")
    def _unique_names(self) -> SeedConfig:
        seen: set[str] = set()
        for step in self.steps:
            if step.name in seen:
                msg = f"seed step {step.name!r} is declared twice; names must be unique"
                raise ConfigError(msg)
            seen.add(step.name)
        return self


class Classifier(_Section):
    """
    One rule mapping a SQL statement to a logical query label.

    ``targeted`` marks a query the change under test is meant to affect. It
    is what lets the production comparison tell a deliberate improvement apart
    from a seed that is the wrong shape: an untargeted query drifting from
    production is a calibration problem, the same query drifting when it *is*
    the target is the result.
    """

    label: str = Field(min_length=1)
    pattern: str = Field(min_length=1)
    targeted: bool = False

    @model_validator(mode="after")
    def _pattern_compiles(self) -> Classifier:
        try:
            re.compile(self.pattern)
        except re.error as exc:
            msg = f"[[trace.classify]] {self.label!r}: invalid regex — {exc}"
            raise ConfigError(msg) from exc
        return self


class TraceConfig(_Section):
    """Span capture and how spans are grouped for attribution."""

    classify: tuple[Classifier, ...] = ()
    otlp_endpoint: str | None = None


class Observable(_Section):
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
    # Where to read this observable back out of the *response*, as a key in a
    # result's equivalence block: "response_bytes", "count", "results", or
    # "nested.<key>". Seed row counts prove what was created; only the response
    # proves what the endpoint did with it, and a seed can be right while the
    # request still returns a fraction of production's payload.
    response: str = ""
    # How far the measured value may sit from `production` before the report
    # calls the seed into question, as a fraction.
    tolerance: float = 0.25


class CalibrationConfig(_Section):
    """Production evidence, echoed into the report next to the numbers."""

    observables: tuple[Observable, ...] = Field(default=(), alias="observable")
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
    floors: Mapping[str, int] = {}
    notes: str = ""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _resolved_baseline(cls, data: Any, info: ValidationInfo) -> Any:
        """
        Resolve ``[calibration].baseline`` against the benchmark file's directory.

        Relative to the benchmark, not the working directory: the two live
        together in ``benchmarks/`` and are committed together, so the reference
        has to survive being run from anywhere in the repository.
        """
        if not isinstance(data, Mapping) or not data.get("baseline"):
            return data
        section = dict(data)
        path = Path(str(section["baseline"]))
        if not path.is_absolute():
            layers = (info.context or {}).get("layers") or {}
            benchmark_file = layers.get("benchmark")
            base = Path(benchmark_file).parent if benchmark_file else Path()
            path = base / path
        section["baseline"] = path
        return section


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
    memory: MemoryConfig = field(default_factory=MemoryConfig)
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


def _as_config_error(section: str, exc: ValidationError) -> ConfigError:
    """
    Translate a pydantic failure into this module's one-line prose contract.

    Only the first error is reported, matching the loader's fail-fast style,
    and the input value is never echoed: connection strings carry credentials,
    which is the reason :func:`redact` exists.
    """
    error = exc.errors(include_url=False, include_input=False)[0]
    if error["type"] == "value_error":
        # One of this module's own messages; it already names its subject.
        return ConfigError(error["msg"].removeprefix("Value error, "))
    location = ".".join(str(piece) for piece in error["loc"])
    subject = f"[{section}].{location}" if location else f"[{section}]"
    if error["type"] == "missing":
        return ConfigError(f"{subject} is required")
    return ConfigError(f"{subject}: {error['msg']}")


def _section(
    model: type[_SectionT],
    name: str,
    data: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
) -> _SectionT:
    try:
        return model.model_validate(data.get(name) or {}, context=context)
    except ValidationError as exc:
        raise _as_config_error(name, exc) from exc


def from_merged(
    data: Mapping[str, Any],
    provenance: Mapping[str, tuple[str, ...]] | None = None,
) -> BenchmarkConfig:
    """Build a :class:`BenchmarkConfig` from an already-merged mapping."""
    name = data.get("benchmark", {}).get("name")
    if not name:
        msg = "[benchmark].name is required"
        raise ConfigError(msg)
    if not data.get("target"):
        msg = "[target] is required: there is nothing to benchmark without it"
        raise ConfigError(msg)
    context = {"benchmark_name": name, "layers": data.get("_layers") or {}}
    return BenchmarkConfig(
        name=name,
        description=data.get("benchmark", {}).get("description", ""),
        django=_section(DjangoConfig, "django", data),
        database=_section(DatabaseConfig, "database", data, context),
        backend=_section(BackendConfig, "backend", data),
        measure=_section(MeasureConfig, "measure", data),
        memory=_section(MemoryConfig, "memory", data),
        target=_section(TargetConfig, "target", data),
        auth=_section(AuthConfig, "auth", data),
        seed=_section(SeedConfig, "seed", data),
        trace=_section(TraceConfig, "trace", data),
        calibration=_section(CalibrationConfig, "calibration", data, context),
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
