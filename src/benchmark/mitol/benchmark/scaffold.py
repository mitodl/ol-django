"""
Commented starting points for each configuration layer.

These are Python string constants rather than data files on purpose: the
package's wheel ships ``*.py`` only, and a template that is missing from an
installed package is worse than no template at all.
"""

from __future__ import annotations

PROJECT_TEMPLATE = """\
# Project-wide benchmark configuration. Committed.
#
# Everything here is the same for every benchmark in this repository: how a
# step process starts Django, and where the scratch database lives. Nothing
# about a particular benchmark belongs in this file, and nothing about a
# particular developer's machine does either — that is benchmark.local.toml,
# which is not committed.
#
# Any string below may use ${VAR} or ${VAR:-default} to read the environment.

[django]
# The settings module the application really runs, not the test settings.
# Test settings commonly enable profilers and coverage that scale with the
# work under test, which is the fastest way to manufacture a result.
settings_module = "main.settings.prod"
# Prepended to sys.path in the step process, relative to chdir.
pythonpath = []
chdir = "."
# Applied to every step. Most commonly used to turn off remote object storage,
# without which seed factories try to upload files.
env = {}

[database]
# The scratch database is DROPPED and recreated on every run. Its name is
# derived as <name_prefix><benchmark name> and must start with "bench".
name_prefix = "bench_"
# The DSN as the application process sees it; {name} is filled in per
# benchmark. In a cluster this differs from what the host can reach, which is
# why it comes from the environment.
url_template = "${BENCH_DATABASE_URL_TEMPLATE:-postgres://postgres:postgres@localhost:5432/{name}}"
# Where DROP/CREATE DATABASE is issued from. Must not be the scratch database.
admin_url = "${BENCH_ADMIN_DATABASE_URL:-postgres://postgres:postgres@localhost:5432/postgres}"
# Refresh planner statistics after seeding. A freshly loaded table has none,
# and the plans it produces are not the plans production runs.
analyze = true

[defaults.measure]
warmup = 3
iterations = 15
trace_repeats = 7
"""

LOCAL_TEMPLATE = """\
# Per-developer benchmark configuration. NOT committed — add it to .gitignore.
#
# Which execution backend to use is a property of your machine, not of the
# project, so it lives here rather than in benchmark.toml.

[backend]
# local   — steps run as subprocesses of the harness (a virtualenv, uv, a
#           devcontainer shell). Nothing to wait for after a git switch.
# compose — steps run in a fresh container of an already-up compose stack.
# k8s     — steps run with kubectl exec against a local-dev cluster.
kind = "local"

# compose:
# service = "web"
# db_service = "db"

# k8s: the context is required and never inherited, because this harness runs
# DROP DATABASE and your current context is routinely a deployed environment.
# context = "k3d-localdev"
# namespace = "myapp"
# selector = "app=myapp-web"
# container = "web"
# settle_seconds = 5

# Connection strings your machine needs, overriding the project defaults.
# [database]
# url_template = "postgres://app:app@postgres.myapp.svc:5432/{name}"
# admin_url = "postgres://app:app@postgres.myapp.svc:5432/postgres"
"""

BENCHMARK_TEMPLATE = """\
# One benchmark. Committed — this is the file an agent edits.
#
# Record, next to each knob, whether it is OBSERVED (from a production trace or
# a sample API response) or a GUESS. Guesses are identical in both arms, so
# they move the baseline rather than the delta — but the write-up has to say
# which is which.

[benchmark]
name = "{name}"
description = ""

[knobs]
# Every shape dimension gets a knob, so the same benchmark can be re-run at
# another shape without editing anything. Override at run time with
# --knob rows=100 or BENCH_ROWS=100.
rows = 25
# OBSERVED from sample responses: nested collection size per row.
nested_per_row = 10
# GUESS: nothing in a response or a trace shows column widths.
blob_bytes = 2048

# Steps run in order. Later steps reference earlier ones by name.
#   $knob:NAME   $index   $blob:NAME_OR_N   $env:VAR
#   $ref:STEP    $ref:STEP[2]   $cycle:STEP   $sample:STEP:5   $all:STEP
[[seed.step]]
name = "user"
factory = "myapp.factories:UserFactory"
count = 1

[[seed.step]]
name = "parents"
factory = "myapp.factories:ParentFactory"
count = "$knob:rows"
kwargs = {{ title = "Parent {{index}}", body = "$blob:blob_bytes" }}

[[seed.step]]
name = "children"
factory = "myapp.factories:ChildFactory"
count = "$knob:rows"
kwargs = {{ parent = "$cycle:parents" }}

# Scalars the request needs. Everything else stays in the database.
[seed.export]
user_id = "user.pk"
parent_id = "parents.pk"

[target]
# Exactly one of reverse or path.
path = "/api/v1/parents/"
params = {{ page_size = 100 }}
expect_status = 200
# Nested collections whose serialized length is compared between arms: a
# serializer change can keep the row count identical while dropping what is
# inside each row.
nested_keys = []

[auth]
user_id = "$ids:user_id"

# Patterns are tried in order, most specific first: a broad pattern placed
# early will swallow the ones after it. The per_req column in the output is
# the check on that.
[[trace.classify]]
label = "COUNT(*) paginator"
pattern = "COUNT\\\\(\\\\*\\\\)"

# Production evidence, echoed into the report next to the numbers. Calibrate
# only against observables the change under test does not affect.
[[calibration.observable]]
name = "rows per page"
source = "sample response"
production = 100

# Row-count floors from IN-list placeholder counts in a production trace.
# Falling short is a warning: a truncated export makes these lower bounds.
[calibration.floors]
# children = 388
"""


def benchmark_template(name: str) -> str:
    """Return the per-benchmark scaffold, named for this benchmark."""
    return BENCHMARK_TEMPLATE.format(name=name)
