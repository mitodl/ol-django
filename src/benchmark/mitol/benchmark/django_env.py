"""
Bootstrap Django for a benchmark step, and refuse to measure a rigged process.

Two failure modes make a benchmark worse than no benchmark, and both are
environmental rather than anything the benchmark author does wrong:

*Instrumentation that scales with the thing under test.* An N+1 profiler hooks
every ORM fetch, and coverage traces every line. Both cost more in whichever
arm loads more rows, which inflates the apparent saving of a change that loads
fewer. These are refused outright.

*Debug bookkeeping.* With ``DEBUG`` on, Django records every statement it runs
and that cost grows with statement size. Dev settings modules routinely hardcode
``DEBUG = True``, so refusing would make the harness unusable against the
settings people actually have; it is forced off instead, and the fact that it
was forced is recorded in every result.

Everything this module decides is reported back in a ``preconditions`` block so
the write-up can cite the conditions the number was measured under.
"""

from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlparse

if TYPE_CHECKING:  # pragma: no cover
    from mitol.benchmark.config import BenchmarkConfig

# Middleware whose cost scales with the number of objects a request hydrates.
PROFILER_MARKERS = ("zeal", "nplusone", "silk", "debug_toolbar")

_ENGINES = {
    "postgres": "django.db.backends.postgresql",
    "postgresql": "django.db.backends.postgresql",
    "postgis": "django.contrib.gis.db.backends.postgis",
    "sqlite": "django.db.backends.sqlite3",
    "mysql": "django.db.backends.mysql",
}


class PreconditionError(RuntimeError):
    """The process is not in a state where a measurement would mean anything."""


@dataclass
class Preconditions:
    """What the harness found, and what it changed, before measuring."""

    debug_forced_off: bool = False
    profilers_active: list[str] = field(default_factory=list)
    middleware_stripped: list[str] = field(default_factory=list)
    trace_function: str | None = None
    under_pytest: bool = False
    database: str = ""

    def blockers(self) -> list[str]:
        """Return the reasons this process cannot produce a usable number."""
        reasons = []
        if self.profilers_active:
            reasons.append(
                f"profiler middleware is active ({', '.join(self.profilers_active)}); "
                f"its cost scales with the objects a request hydrates, so it "
                f"inflates whichever arm loads more rows. Strip it with "
                f"[measure].middleware_exclude, or set allow_profilers = true to "
                f"measure anyway and have the result say so."
            )
        if self.trace_function:
            reasons.append(
                f"a trace function is installed ({self.trace_function}); line "
                f"tracing (coverage, a profiler, a debugger) dwarfs the effect "
                f"being measured"
            )
        if self.under_pytest:
            reasons.append(
                "running under pytest; test settings commonly enable profilers "
                "and coverage that scale with the work under test"
            )
        return reasons

    def as_dict(self) -> dict[str, Any]:
        """Return the preconditions as a plain mapping, for the result JSON."""
        return asdict(self)


def parse_database_url(url: str) -> dict[str, Any]:
    """
    Turn a database URL into Django ``DATABASES`` entries.

    ``dj_database_url`` is used when it is installed, because every consuming
    project already depends on it and its edge cases are better tested than
    anything worth writing here. The fallback covers the common DSN shapes so
    the harness does not acquire a dependency for one function.
    """
    try:
        import dj_database_url  # noqa: PLC0415
    except ImportError:
        pass
    else:
        return dj_database_url.parse(url)

    parsed = urlparse(url)
    scheme = parsed.scheme.split("+")[0]
    if scheme not in _ENGINES:
        msg = (
            f"cannot parse database URL with scheme {scheme!r} without "
            f"dj_database_url installed"
        )
        raise PreconditionError(msg)
    if scheme == "sqlite":
        return {"ENGINE": _ENGINES[scheme], "NAME": parsed.path or ":memory:"}
    return {
        "ENGINE": _ENGINES[scheme],
        "NAME": parsed.path.lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
    }


def _prepare_environment(config: BenchmarkConfig) -> None:
    """Apply chdir, sys.path and the environment the settings module reads."""
    if config.django.chdir:
        os.chdir(config.django.chdir)
    for entry in reversed(config.django.pythonpath):
        resolved = str(Path(entry).resolve())
        if resolved not in sys.path:
            sys.path.insert(0, resolved)
    os.environ["DJANGO_SETTINGS_MODULE"] = config.django.settings_module
    # Set before django.setup(): most settings modules build DATABASES from
    # this, and getting there first avoids a connection to the wrong database
    # if an AppConfig.ready() queries.
    os.environ["DATABASE_URL"] = config.database.url
    for key, value in config.django.env.items():
        os.environ[key] = value


def _point_at_bench_database(config: BenchmarkConfig) -> None:
    """
    Override ``DATABASES['default']`` rather than trusting the settings module.

    A settings module that ignores ``DATABASE_URL`` would otherwise point the
    whole run at a developer's real database — which the next step drops.
    """
    from django.conf import settings  # noqa: PLC0415
    from django.db import connections  # noqa: PLC0415

    settings.DATABASES["default"] = {
        **settings.DATABASES.get("default", {}),
        **parse_database_url(config.database.url),
    }
    # Forget anything opened while the apps were loading, so the next query
    # connects with the settings above. Private access is the only way to drop
    # an already-initialised alias.
    for connection in connections.all(initialized_only=True):
        connection.close()
        delattr(connections._connections, connection.alias)  # noqa: SLF001
    connections.__dict__.pop("settings", None)


def enforce_preconditions(
    config: BenchmarkConfig, *, strict: bool = True
) -> Preconditions:
    """
    Inspect the configured Django process, fix what is safe to fix, and report.

    With ``strict`` set, anything that would make the measurement meaningless
    raises instead of being recorded. The non-strict form is for callers that
    are already running inside someone else's process (a test suite, a
    management command) and only want the state described.
    """
    from django.conf import settings  # noqa: PLC0415

    found = Preconditions(
        trace_function=getattr(sys.gettrace(), "__qualname__", None)
        if sys.gettrace()
        else None,
        under_pytest="pytest" in sys.modules,
        database=settings.DATABASES.get("default", {}).get("NAME", ""),
    )

    if config.measure.middleware_exclude:
        keep, dropped = [], []
        for entry in settings.MIDDLEWARE:
            if any(marker in entry for marker in config.measure.middleware_exclude):
                dropped.append(entry)
            else:
                keep.append(entry)
        settings.MIDDLEWARE = keep
        found.middleware_stripped = dropped

    found.profilers_active = [
        entry
        for entry in settings.MIDDLEWARE
        if any(marker in entry for marker in PROFILER_MARKERS)
    ]
    if config.measure.allow_profilers:
        found.profilers_active = []

    if settings.DEBUG:
        settings.DEBUG = False
        found.debug_forced_off = True

    if strict and (reasons := found.blockers()):
        msg = "refusing to measure:\n  - " + "\n  - ".join(reasons)
        raise PreconditionError(msg)
    return found


def bootstrap(config: BenchmarkConfig) -> Preconditions:
    """
    Start Django against the scratch database and enforce the preconditions.

    This is the entry point for every step that runs in-process: it is what
    makes ``ol-benchmark step seed`` and ``ol-benchmark step bench`` run against
    the same Django the application runs, rather than a test harness.
    """
    import django  # noqa: PLC0415

    _prepare_environment(config)
    django.setup()
    _point_at_bench_database(config)
    return enforce_preconditions(config)
