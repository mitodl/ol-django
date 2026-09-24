mitol-django-benchmark
======================

Prove a Django or DRF performance change actually made an endpoint faster.

A performance PR that says "this should be faster" is a guess. This package
turns it into a measurement: seed a **production-shaped** throwaway database,
run the same request on two git refs against **identical rows**, and attribute
the difference query by query.

Two failure modes make a benchmark worse than none, and most of this package
exists to avoid them:

1. **Measuring the harness.** Instrumentation that scales with the thing you
   changed will manufacture a result. An N+1 profiler hooks every ORM fetch, so
   it costs more in whichever arm hydrates more objects — which is the arm you
   are trying to show is slower. The harness refuses to run with one active.
2. **Measuring the wrong shape.** Factory defaults are nothing like production:
   blank rich-text columns, one related row where production has dozens. A seed
   that is off structurally produces a number with no bearing on the endpoint
   you care about.

Related: `mitol-drf-lint` and the `drf-api-performance` skill are about
*writing* fast endpoints. This is about *proving* one got faster.

Installation
------------

```bash
uv add --dev "mitol-django-benchmark[drf,factories,django,postgres]"
```

`click` and `cloup` come with it rather than as an extra: the runner drives
every step by invoking `python -m mitol.benchmark step <name>` inside the
application environment, so the CLI has to work wherever the package is
installed.

| Extra       | Gives you |
| ----------- | --------- |
| `drf`       | DRF's `APIClient`, so authentication does not cost a login round-trip per call |
| `factories` | `factory-boy`, for seed steps of kind `factory` |
| `django`    | OpenTelemetry Django instrumentation — request spans |
| `postgres`  | OpenTelemetry psycopg instrumentation — **query spans, which is where attribution comes from** |
| `postgres2` | the psycopg2 equivalent, for a project still on it |

Registering the app in `INSTALLED_APPS` is optional. The `ol-benchmark` console
script starts Django itself; add `mitol.benchmark.apps.BenchmarkApp` only if you
want the `manage.py ol_benchmark` fallback for a project whose bootstrap the
console script cannot reproduce.

The three configuration layers
------------------------------

Three files, because they have three different owners and lifetimes. Nothing is
repeated between them, and a file that declares a section belonging to another
layer is rejected rather than quietly ignored.

| File | Committed? | Owner | Holds |
| --- | --- | --- | --- |
| `benchmarks/benchmark.toml` | yes | the project | `[django]`, `[database]`, `[defaults.measure]` |
| `benchmarks/<name>.toml` | yes | the benchmark author | `[benchmark]`, `[knobs]`, `[seed]`, `[target]`, `[auth]`, `[trace]`, `[calibration]` |
| `benchmarks/benchmark.local.toml` | **no — gitignore it** | the developer | `[backend]`, and any connection strings their machine needs |

The project and local layers are discovered by searching at and above the
benchmark file's directory. The local layer is genuinely optional: the defaults
are the `local` backend against localhost Postgres, so a fresh clone runs
without one.

Precedence, lowest to highest: **project → benchmark → local → environment →
CLI flags.**

Every string in `[django]`, `[database]` and `[backend]` is expanded with
`${VAR}` and `${VAR:-default}`. That is what lets a committed file work on
every machine — and what a k3d/Tilt cluster needs, where the DSN is assigned by
the cluster rather than known to the repository. An unset variable with no
default is an error naming the variable, not an empty string.

Getting started
---------------

```bash
ol-benchmark init --project                      # benchmarks/benchmark.toml
ol-benchmark init --local                        # benchmarks/benchmark.local.toml
ol-benchmark init --benchmark library-list       # benchmarks/library_list.toml
ol-benchmark validate benchmarks/library_list.toml
ol-benchmark run benchmarks/library_list.toml --base-ref main
```

`ol-benchmark -h` lists the subcommands; each takes `-h` of its own. Exit
codes are part of the contract, because the backends run these as
subprocesses: `2` is a configuration problem, `1` is everything else that is
known to go wrong — including a `void` comparison.

Writing the seed
----------------

Every shape dimension is a knob, so the same benchmark can be re-run at another
shape without editing anything, and the report can state the exact shape the
number was measured at:

```toml
[knobs]
rows = 25
nested_per_row = 10
blob_bytes = 2048
```

Override at run time with `--knob rows=100` or `BENCH_ROWS=100`.

Steps run in order and can refer to each other:

```toml
[[seed.step]]
name = "authors"
factory = "libraries.factories:AuthorFactory"
count = 50

[[seed.step]]
name = "books"
factory = "libraries.factories:BookFactory"
count = "$knob:rows"
kwargs = { author = "$cycle:authors", title = "Book {index}" }
m2m = { topics = { source = "topics", per = "$knob:nested_per_row", strategy = "cycle" } }
```

| Step kind | Needs | Does |
| --- | --- | --- |
| `factory` | `factory` | `factory-boy`, one `create()` per row (or one `bulk_create` with `bulk = true`) |
| `model` | `model` | plain model instances, no factory-boy needed |
| `fixture` | `fixtures` | `loaddata` of committed JSON |
| `sql` | `statements` | raw SQL |
| `hook` | `hook` | calls `pkg.mod:fn(context)` — the escape hatch for fan-out a declarative format cannot express |

Tokens, resolved anywhere in `kwargs`, `m2m`, `count`, target params and auth:

| Token | Means |
| --- | --- |
| `$knob:NAME` | a shape knob |
| `$index` | the 0-based index of the row being built |
| `$blob:N` \| `$blob:KNOB` | filler text of roughly N bytes |
| `$ref:STEP`, `$ref:STEP[2]` | one object from an earlier step |
| `$cycle:STEP` | that step's objects, cycled by `$index` |
| `$sample:STEP:5` | 5 of them, from the seeded RNG (deterministic) |
| `$all:STEP` | all of them |
| `$ids:KEY` | a scalar from `[seed.export]` — how the *request* reaches seeded rows |
| `$env:VAR` | an environment variable |
| `$$` | a literal `$` |

Plain strings are also run through `str.format` with `index` and every knob, so
`"Book {index}"` works without a token.

**Structure matters more than sizing.** How rows fan out across joins dominates
how wide they are. Putting everything under one tenant is the classic error: it
makes the filter match everything and turns an unchanged query pathological.
The seed result reports many-to-many pair totals for exactly this reason — join
multiplicity is invisible in an API response.

Backends
--------

| `kind` | Runs steps with | Use when |
| --- | --- | --- |
| `local` | subprocesses of the harness | the application runs in the environment you are typing in |
| `compose` | `docker compose run --rm --no-deps -T <service>` | the repository has its own compose stack, already up |
| `k8s` | `kubectl exec` | a local-dev cluster (k3d + Tilt or similar) |

The `k8s` backend **requires** `context` and never inherits your current
`kubectl` context: a developer's current context is routinely a deployed
environment, and this harness runs `DROP DATABASE`. It also **refuses a
context whose name contains `ci`, `qa`, `prod` or `applications`**, because
being made to name the cluster does not help if the name you type is
`applications-qa`. Override the markers with `[backend].context_denylist` in
your own local config if one of them is a false positive on a cluster you
really do benchmark against. It also waits for a push-based sync to finish
after a ref switch, and the runner separately verifies the switched-to files
actually arrived before measuring.

Comparing against production
----------------------------

A/B-ing two refs tells you whether a change helped. It does not tell you
whether your seed is shaped like reality — and a delta measured on the wrong
shape is a number about your seed. For that you need production.

**Exported OTel traces are never committed.** They carry statement literals,
query strings, user and tenant identifiers and absolute timestamps. What gets
committed is the *aggregate*:

```bash
ol-benchmark baseline benchmarks/library_list.toml traces/*.json
```

Pass as many exported traces as you have — the medians improve with the
sample, exactly as `trace_repeats` does locally. Files may mix the two OTLP
export layouts, a trace split across files is one request, and a trace present
in two files is counted once.

That writes `benchmarks/library_list.baseline.json`: per-query medians keyed
by the labels **you** wrote in `[[trace.classify]]`, plus row-count floors and
the sampled trace IDs. Nothing else. The safety property is structural rather
than a scrubbing pass —

> the only free-text field in the baseline is drawn from a closed set that is
> already committed in the same repository.

A production query matching none of your classifiers is labelled
`"unclassified"` rather than by its SQL, so there is no code path — and no
flag — that can put statement text into the file. The command warns when that
happens so you can add a rule. Use `--stdout` to look before anything is
written, and read the file before you commit it.

**The trace IDs are the one deliberate exception.** A trace ID is a pointer,
not data: it resolves only for someone who already has access to your tracing
backend. It is what lets a reviewer open the exact request a number came from.
It does record *that* a request existed, so drop the field if your team is not
comfortable publishing that.

Two things to get right when exporting:

- **Include the server/root span.** A trace filtered down to database spans
  makes the final query's gap read as zero, and that gap is where
  serialization lives. The command warns if it spots this.
- **One endpoint per baseline.** A glob that sweeps in unrelated traces
  averages their queries into nonsense; the command warns when the traces
  cover more than one route.

Then reference it, and say which query the change is meant to move:

```toml
[[trace.classify]]
label = "topics prefetch"
pattern = "book_topics"
targeted = true            # excluded from the drift check; it should differ

[calibration]
baseline = "library_list.baseline.json"
drift_factor = 5
```

The attribution table gains a production column, and any **untargeted** query
more than `drift_factor` away from production is reported under "Seed drift
from production". That is the falsification check: a seed parameter that makes
an unchanged query wildly slower than production is wrong, however good the
story behind it was. Drift is a warning about the seed and never changes the
verdict — the verdict is about whether the two arms are comparable to each
other.

Local faster than production is expected and says so. Local *slower* on a
query the change does not touch is the real alarm.

What you get
------------

Written to `.bench/out/<benchmark>/` by default:

| File | Contents |
| --- | --- |
| `comparison.json` | **the primary artifact** — verdict, deltas, per-query attribution, calibration |
| `report.md` | the same, for a human |
| `config.resolved.json` | every setting in force and which layer it came from, credentials redacted |
| `seed.json` | per-step row counts, m2m pair totals, exports, floor warnings |
| `base.json`, `branch.json` | the wall-clock results, with the conditions they were measured under |
| `trace-base.json`, `trace-branch.json` | every span: duration **and the gap to the next one** |
| `agg-base.json`, `agg-branch.json` | median per logical query across the traced repeats |

`benchmarks/<name>.baseline.json` is the one output that is **committed** — it
is production evidence distilled to numbers, and a colleague needs it to
re-run the drift check from a fresh clone.

### Verdicts

`comparison.json` never reports a bare number. It reports one of:

- **`void`** — the arms returned different responses. They did not do the same
  work, so no delta may be quoted. Find out why.
- **`inconclusive`** — the difference is inside the run-to-run spread, or min
  and median disagree about which arm is faster. This is a real answer.
- **`ok`** — the difference exceeds the spread and both statistics agree.

### Reading the trace

A database span wraps `cursor.execute` and nothing else, so row fetch, model
instantiation and serialization all live in the **gaps between spans**. That is
why every span carries `gap_ms` and the aggregation reports `sql` and `gap`
separately: a trace that shows only span durations will tell you the queries
are fast while the request is slow.

The traced numbers are for attribution, never for the headline. Instrumentation
is not free, and it is normally inert in an application with no OTLP endpoint —
which is what keeps the wall-clock pass clean. Set `[trace].otlp_endpoint` to
additionally ship the spans to a real collector.

What the number means
---------------------

Local Postgres has no network round-trip, a warm cache and no contention.
Production has all three, and they penalise larger result sets
disproportionately. **What you measure here is a floor, not an estimate.** Every
report says so; do not delete it when you quote the number.

Also state, every time:

- the seed shape, next to the numbers;
- which knobs were guesses, and that they are identical in both arms, so they
  move the baseline rather than the delta;
- any production signal the harness failed to reproduce.

Pitfalls the harness cannot see
-------------------------------

| Pitfall | Why it ruins the result |
| --- | --- |
| Tuning the seed against the query you changed | Circular. Calibrate only on observables the change does not touch |
| Factory defaults as "realistic" | Blank rich-text fields, one related row where production has dozens |
| One traced request | Per-query gaps are far too noisy; the default is a median of seven |
| Quoting a traced total as the result | The trace is for attribution; the uninstrumented pass is for the number |
| Extrapolating local ms to production ms | Different hardware, cache state and network |

See `AGENTS.md` in this package for the full calibration procedure.
