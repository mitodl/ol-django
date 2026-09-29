"""
The declarative seed engine.

Factory defaults are nothing like production — blank rich-text columns, one
related row where production has dozens — so a benchmark seeded from them
measures a shape no user ever sees. This module builds the dataset from the
benchmark's own data file instead, with every shape dimension named as a knob
so the same benchmark can be re-run at another shape without editing anything.

Structure matters more than sizing. How rows fan out across joins dominates how
wide they are, which is why steps can reference each other (``$cycle``,
``$sample``) rather than only declaring counts, and why the result reports
many-to-many pair totals: join multiplicity is invisible in an API response, so
printing it is the only way a report can state it.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from random import Random
from typing import TYPE_CHECKING, Any

from mitol.benchmark.resolve import ResolutionContext, ResolutionError, resolve
from mitol.benchmark.resolve import resolve_count as _resolve_count

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence

    from mitol.benchmark.config import BenchmarkConfig, SeedStep


class SeedError(RuntimeError):
    """The dataset could not be built as described."""


def import_object(path: str) -> Any:
    """
    Import a dotted path, written either ``module:Attr`` or ``module.Attr``.

    The colon form is unambiguous and preferred; the dotted form is accepted
    because it is what people type.
    """
    module_path, separator, attribute = path.partition(":")
    if not separator:
        module_path, _, attribute = path.rpartition(".")
    if not module_path or not attribute:
        msg = f"{path!r} is not a dotted path to an importable object"
        raise SeedError(msg)
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        msg = f"{path!r}: cannot import {module_path!r} — {exc}"
        raise SeedError(msg) from exc
    try:
        return getattr(module, attribute)
    except AttributeError as exc:
        msg = f"{path!r}: {module_path!r} has no attribute {attribute!r}"
        raise SeedError(msg) from exc


@dataclass
class SeedContext:
    """
    What a ``hook`` step is handed.

    A hook exists for fan-out a declarative format cannot express — a
    distribution, a conditional attachment, a graph. It gets the knobs, every
    object built so far, the shared deterministic RNG, and the same resolver
    the declarative steps use, so a hook and a step agree on what ``$cycle``
    means.
    """

    config: BenchmarkConfig
    knobs: Mapping[str, Any]
    objects: dict[str, list[Any]]
    rng: Random
    step: SeedStep

    def resolve(self, value: Any, index: int = 0) -> Any:
        """Resolve ``$token`` references the same way a declarative step does."""
        return resolve(value, self._resolution_context(index))

    def _resolution_context(self, index: int) -> ResolutionContext:
        return ResolutionContext(
            knobs=self.knobs, index=index, objects=self.objects, rng=self.rng
        )


@dataclass
class SeedOutcome:
    """The shape that was actually built."""

    counts: dict[str, int] = field(default_factory=dict)
    m2m_pairs: dict[str, int] = field(default_factory=dict)
    export: dict[str, Any] = field(default_factory=dict)
    knobs: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    analyzed: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return the outcome as the ``SEED_SHAPE`` payload."""
        return {
            "counts": self.counts,
            "m2m_pairs": self.m2m_pairs,
            "export": self.export,
            "knobs": self.knobs,
            "warnings": self.warnings,
            "analyzed": self.analyzed,
        }


class _Seeder:
    """Builds one benchmark's dataset, step by step."""

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.knobs = dict(config.knobs)
        self.rng = Random(config.seed.random_seed)  # noqa: S311
        self.objects: dict[str, list[Any]] = {}
        self.outcome = SeedOutcome(knobs=dict(self.knobs))

    # -- resolution ------------------------------------------------------

    def context(self, index: int = 0) -> ResolutionContext:
        """Return a resolution context positioned at ``index``."""
        return ResolutionContext(
            knobs=self.knobs, index=index, objects=self.objects, rng=self.rng
        )

    def _kwargs_at(self, step: SeedStep, index: int) -> dict[str, Any]:
        try:
            return resolve(dict(step.kwargs), self.context(index))
        except ResolutionError as exc:
            msg = f"seed step {step.name!r}, item {index}: {exc}"
            raise SeedError(msg) from exc

    # -- many-to-many ----------------------------------------------------

    def _m2m_values(self, step: SeedStep, spec: Any, index: int) -> list[Any]:
        if isinstance(spec, str):
            value = resolve(spec, self.context(index))
            return list(value) if isinstance(value, list) else [value]
        if not isinstance(spec, dict) or "source" not in spec:
            msg = (
                f"seed step {step.name!r}: an m2m entry must be a $token or a "
                f"table with a 'source' key, got {spec!r}"
            )
            raise SeedError(msg)
        pool = self.objects.get(spec["source"])
        if not pool:
            msg = (
                f"seed step {step.name!r}: m2m source {spec['source']!r} has no "
                f"objects; declare that step before this one"
            )
            raise SeedError(msg)
        strategy = spec.get("strategy", "cycle")
        per_spec = spec.get("per", "all")
        if per_spec == "all" or strategy == "all":
            return list(pool)
        per = min(_resolve_count(per_spec, self.context(index)), len(pool))
        if strategy == "random":
            return self.rng.sample(pool, per)
        if strategy != "cycle":
            msg = (
                f"seed step {step.name!r}: unknown m2m strategy {strategy!r} "
                f"(known: cycle, random, all)"
            )
            raise SeedError(msg)
        start = (index * per) % len(pool)
        return [pool[(start + offset) % len(pool)] for offset in range(per)]

    def _apply_m2m(self, step: SeedStep, instances: Sequence[Any]) -> None:
        for field_name, spec in step.m2m.items():
            pairs = 0
            for index, instance in enumerate(instances):
                values = self._m2m_values(step, spec, index)
                getattr(instance, field_name).set(values)
                pairs += len(values)
            self.outcome.m2m_pairs[f"{step.name}.{field_name}"] = pairs

    # -- step kinds ------------------------------------------------------

    def _run_factory(self, step: SeedStep) -> list[Any]:
        factory_class = import_object(step.factory)
        count = _resolve_count(step.count, self.context())
        if step.bulk:
            built = [
                factory_class.build(**self._kwargs_at(step, index))
                for index in range(count)
            ]
            return list(factory_class._meta.model.objects.bulk_create(built))  # noqa: SLF001
        return [
            factory_class.create(**self._kwargs_at(step, index))
            for index in range(count)
        ]

    def _run_model(self, step: SeedStep) -> list[Any]:
        model = import_object(step.model)
        count = _resolve_count(step.count, self.context())
        instances = [model(**self._kwargs_at(step, index)) for index in range(count)]
        if step.bulk:
            return list(model.objects.bulk_create(instances))
        for instance in instances:
            instance.save()
        return instances

    def _run_fixture(self, step: SeedStep) -> list[Any]:
        from django.core.management import call_command  # noqa: PLC0415

        call_command("loaddata", *step.fixtures, verbosity=0)
        return []

    def _run_sql(self, step: SeedStep) -> list[Any]:
        from django.db import connection  # noqa: PLC0415

        with connection.cursor() as cursor:
            for statement in step.statements:
                cursor.execute(statement)
        return []

    def _run_hook(self, step: SeedStep) -> list[Any]:
        hook = import_object(step.hook)
        context = SeedContext(
            config=self.config,
            knobs=self.knobs,
            objects=self.objects,
            rng=self.rng,
            step=step,
        )
        produced = hook(context)
        return list(produced) if produced is not None else []

    # -- driving ---------------------------------------------------------

    def run_step(self, step: SeedStep) -> None:
        """Execute one step and record what it produced."""
        runner = {
            "factory": self._run_factory,
            "model": self._run_model,
            "fixture": self._run_fixture,
            "sql": self._run_sql,
            "hook": self._run_hook,
        }[step.kind]
        instances = runner(step)
        self.objects[step.name] = instances
        self.outcome.counts[step.name] = len(instances)
        if step.m2m:
            self._apply_m2m(step, instances)

    def collect_exports(self) -> None:
        """Resolve ``[seed.export]`` into the scalars later steps can use."""
        for key, path in self.config.seed.export.items():
            step_name, _, attribute_path = path.partition(".")
            objects = self.objects.get(step_name)
            if not objects:
                msg = (
                    f"[seed.export].{key} refers to step {step_name!r}, which "
                    f"produced no objects"
                )
                raise SeedError(msg)
            value = objects[0]
            for attribute in filter(None, attribute_path.split(".")):
                value = getattr(value, attribute)
            if not isinstance(value, (str, int, float, bool, type(None))):
                msg = (
                    f"[seed.export].{key} resolved to {type(value).__name__}; "
                    f"exports must be scalars, because they travel to another "
                    f"process as JSON"
                )
                raise SeedError(msg)
            self.outcome.export[key] = value

    def check_floors(self) -> None:
        """Warn where the seed falls short of a production row-count floor."""
        for step_name, floor in self.config.calibration.floors.items():
            built = self.outcome.counts.get(step_name, 0)
            if built < floor:
                self.outcome.warnings.append(
                    f"step {step_name!r} built {built} rows, below the "
                    f"production floor of {floor}; the seed understates "
                    f"production fan-out"
                )

    def analyze(self) -> None:
        """Refresh planner statistics, which a freshly loaded table lacks."""
        from django.db import connection  # noqa: PLC0415

        if not self.config.database.analyze or connection.vendor != "postgresql":
            return
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE")
        self.outcome.analyzed = True


def run_seed(config: BenchmarkConfig) -> SeedOutcome:
    """
    Build the dataset described by ``config`` and return the shape it produced.

    The whole seed runs in one transaction, so a step that fails half way
    leaves no partial dataset behind to be measured by mistake.
    """
    from django.db import transaction  # noqa: PLC0415

    seeder = _Seeder(config)
    with transaction.atomic():
        for step in config.seed.steps:
            seeder.run_step(step)
        seeder.collect_exports()
    seeder.check_floors()
    seeder.analyze()
    return seeder.outcome


def exports_of(shape: Mapping[str, Any]) -> Mapping[str, Any]:
    """
    Return the scalars a seed exported, given its ``SEED_SHAPE`` payload.

    Accepts a bare export mapping too, so a hand-run step can be given just
    the ids it needs.
    """
    exported = shape.get("export")
    return exported if isinstance(exported, Mapping) else shape
