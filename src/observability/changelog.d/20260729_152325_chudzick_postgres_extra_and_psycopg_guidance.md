### Added

- Added a `postgres` extra providing `opentelemetry-instrumentation-psycopg` and `psycopg[c]`, the instrumentation being auto-discovered via the `opentelemetry_instrumentor` entry-point group.
- Documented in the README why the extra decides the database driver: the instrumentation targets psycopg 3, and Django's Postgres backend prefers psycopg 3 over psycopg2 whenever it is importable, so installing it switches an application's driver with nothing in the dependency diff naming one. Since the extra already makes that decision, it pins the compiled binding rather than leaving a bare `psycopg` to resolve to the pure-Python `ctypes` implementation that upstream documents as "much slower".
- Documented the resulting build prerequisites (C compiler, Python headers, `libpq-dev`, `pg_config` — all present in `ol-python-base`, absent from GitHub's `ubuntu-24.04` runners) and `psycopg[binary]` as the escape hatch for environments that cannot compile.
