# Agent Instructions — mitol-django-benchmark

This package turns "this should be faster" into a measurement. You are here
because someone asked whether a change actually sped an endpoint up.

**You edit exactly one file: `benchmarks/<name>.toml`.** `benchmark.toml` is a
project-wide decision and `benchmark.local.toml` belongs to the developer
whose machine this is. If you think one of those needs changing, say so and
ask; do not edit them.

Read `README.md` in this package for the schema. This file is about how to
arrive at a number that is worth quoting.

## Step 1 — Ask for the evidence, in one batched question

Do not start writing a seed. Ask for all of it at once, and say what each
artifact is for — people usually have more than they volunteer:

| Ask for | Why you need it |
| --- | --- |
| The **endpoint and exact query string**, including filter params | Filters drive join fan-out; the wrong params benchmark a different code path |
| The **two git refs** to compare (usually the branch and its merge base) | The A/B arms |
| A **production OTel trace** of a real slow request (JSON export) | The only source of per-query timings and row-count floors |
| **Sample production API responses**, 2-3 from different tenants/filters | The only ground truth for the output shape |
| Whether they can run **read-only queries against a production replica** | Collapses the biggest guesses into facts |
| Anything they already know is slow | Their intuition is usually a good prior |

Without a trace the benchmark still runs, but say plainly that you lose
per-query attribution and the calibration target.

## Step 2 — Derive the shape, and label every guess

Each artifact answers different questions. Anything neither can answer is a
**guess you must label as one**.

- **Sample responses** give the output shape exactly: rows per page, nested
  collection sizes per row, field payload sizes. Compare these against what the
  app's factories actually produce — the gap is usually large in both
  directions.
- **The OTel trace** gives the query timeline, and — because a span wraps
  `cursor.execute` only — the **gaps between spans** are where row fetch, model
  instantiation and serialization live. It also gives **row-count floors** from
  `IN (%s, %s, ...)` placeholder counts, and per-query timings to calibrate
  against.
- **Neither** shows hidden fan-out: rows loaded and discarded, join
  multiplicity, or columns selected but never serialized.

Write the distinction into the file, above each knob:

```toml
[knobs]
# OBSERVED (sample response): 100 rows per page, 13 nested per row.
rows = 100
nested_per_row = 13
# OBSERVED (trace IN-list): at least 388 child rows are loaded.
children = 400
# GUESS: nothing in a response or trace shows column widths. Identical in
# both arms, so it moves the baseline, not the delta.
blob_bytes = 2048
```

Record trace-derived floors so the harness warns when a re-run at another
shape falls below them:

```toml
[calibration.floors]
children = 388
```

## Step 3 — Get the structure right before the sizes

**Structure matters more than sizing.** How rows fan out across joins dominates
how wide they are. The classic error is putting everything under one tenant:
the filter then matches everything, and an unchanged query becomes
pathological.

- Create **many** tenants/orgs so filters stay selective.
- Spread children across parents with `$cycle`, not all onto one.
- Add **noise rows** the page does not return, so the main query is not
  scanning a toy table.
- Seed whatever membership the endpoint's permission check needs — filters
  often return an empty queryset without it, and you will benchmark a 404.
- Where the real distribution is skewed, use a `hook` step. `$cycle` spreads
  uniformly, and uniform fan-out hides the prefetch cost a skewed one exposes.
  See `testapp/libraries/bench_hooks.py` in this repository for a worked hook.

Check `m2m_pairs` in `seed.json` afterwards. Join multiplicity is invisible in
an API response, so that number is the only place the report can state it.

## Step 4 — Calibrate on what the change does not touch

Tune the seed until the **independent observables** match production.
Independent means "not affected by the change under test" — those are
legitimate targets precisely because they are identical in both arms.

```toml
[[calibration.observable]]
name = "rows per page"
source = "sample response"
production = 100

[[calibration.observable]]
name = "cost of the unchanged tenant lookup"
source = "production trace"
production = "4.2 ms"
```

**A seed parameter that makes an *unchanged* query wildly slower than
production is falsified — discard it, however good the story was.**

Never tune against the query you changed. That is circular, and it is the
single easiest way to produce a large, confident, wrong number.

## Step 5 — Run it, then check the benchmark before the result

```bash
ol-benchmark validate benchmarks/<name>.toml
ol-benchmark run benchmarks/<name>.toml --base-ref <merge-base>
```

Before quoting any delta, read `comparison.json` and confirm:

1. **`verdict` is not `void`.** Void means the arms returned different
   responses — check `equivalence_mismatches`. They did not do the same work;
   find out why before doing anything else.
2. **`verdict` is not `inconclusive`.** That is a real answer. Report it as
   one; do not re-run until you get a number you like.
3. **`classifier_collisions` is empty.** A non-empty list means a
   `[[trace.classify]]` label is mixing two different queries and its median is
   meaningless. Tighten the pattern — they are tried in declaration order, so
   put specific ones first.
4. **`per_query` shows the saving where the change aims**, and nothing else
   regressed to pay for it.
5. **`preconditions` is what you expect** in both arms.
6. **`refs` differ.** Two identical refs means the switch did not take effect.
7. **Re-run at a second shape** (`--knob rows=200`). A delta stable across
   shapes is the strongest evidence you can produce locally.

## Step 6 — Report a floor, not an estimate

Local Postgres has no network round-trip, a warm cache and no contention.
Production has all three, and they penalise larger result sets
disproportionately. Say so every time — `comparison.json` carries the sentence
in `caveat`; do not drop it.

State in the write-up:

- The seed shape, next to the numbers. Never quote a headline without it.
- Which inputs were **guesses**, and that they are identical across arms, so
  they move the baseline rather than the delta.
- The execution environment, and what it contributes to the spread.
- Any production signal the harness **failed** to reproduce, and what you
  ruled out.
- Per-query attribution, so a reviewer can check the saving is where you say.

## Pitfalls

| Pitfall | Why it ruins the result |
| --- | --- |
| Benchmarking under pytest or against test settings | Profilers and coverage scale with the work under test, inflating whichever arm loads more and **overstating the win**. The harness refuses, so do not work around it |
| `DEBUG = True` | Django records every query; the cost grows with statement size. The harness forces it off and says so |
| Reseeding between arms | Different rows, so it is not an A/B |
| One traced request | Per-query gaps are far too noisy; the default is a median of seven |
| Quoting a traced total as the result | Instrumentation is not free. The trace is for attribution; the uninstrumented pass is for the number |
| Factory defaults as "realistic" | Blank rich-text fields, one related row where production has dozens |
| Tuning the seed against the query you changed | Circular |
| Extrapolating local ms to production ms | Different hardware, cache state and network |
| Editing `benchmark.local.toml` | It is someone's machine, and it is not committed |

## Working on this package

Standard repository conventions apply: `uv run pytest tests/benchmark`,
`uv run ruff check --fix .`, and a changelog fragment via
`uv run scripts/changelog.py create --app benchmark` before any PR.

The tests run against the `libraries` app in `testapp/`, which exists to give
this tooling something realistically shaped to work on. `benchmarks/` in the
repository root holds this repository's own project config and a worked
example; `benchmarks/testapp_libraries.toml` is the reference for how a
benchmark file should read.

A useful self-check: run the example with `--base-ref HEAD`, so both arms are
the same commit. The verdict must come out `inconclusive` — if the harness
reports a confident delta between a commit and itself, the harness is what is
being measured.
