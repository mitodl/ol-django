
<a id='changelog-2026.9.30'></a>
## [2026.9.30] - 2026-09-30

### Added

- `ol-benchmark memory <config>`: a retention pass for the case the A/B cannot
  answer. When a latency run exonerates an endpoint and production still
  disagrees, the question is usually not what the request costs but what it
  leaves behind — a worker that grows every request ends up living at whatever
  ceiling bounds it, where stop-the-world collections are longest. Single-arm,
  because retention is a property of the code rather than a difference between
  two commits, so it needs no checkout and runs on a dirty tree. The dirty-tree
  refusal is the only one single-arm excuses: a committed `benchmark.local.toml`
  is still refused, being one developer's connection strings in the repository
  however many refs are measured. And because it does run on a dirty tree, the
  result records whether it did: `ref` is reported `git describe --dirty` style
  and `dirty_tree` carries the boolean, because a number measured against
  uncommitted changes belongs to the tree rather than to the commit the A/B
  would have been able to name.

  It reports three series, because none can be read alone: RSS, which a memory
  ceiling sees but which cannot tell retention from a high-water mark; live
  object count after a forced collection, which can; and retained objects by
  type, which usually names the culprit without further work. The verdict is
  `retaining`, `high-water` or `stable`, by thresholds the config states — and
  `stable` means those thresholds were not crossed rather than that nothing is
  held, because growth below them and retention the collector cannot enumerate
  read the same way.

  The figures it reports are the endpoint's own, which takes some doing. The
  measurement's own instrument retains more per request than the threshold
  allows: Django's test client re-connects three signals on every request, and
  `Signal.connect` registers a `weakref.finalize` against the owner of each
  receiver — two of which, a module-level function and the client itself, have
  process lifetime. Twelve objects a request, before the endpoint does
  anything, which on its own is enough for a view returning a fixed string to
  read `retaining`. Each of those finalizers is detached as it appears,
  matched both on its callback and on being held against something only a test
  client can own, so that an application re-connecting its own receiver every
  request — which leaks the same way in production — stays visible.

  An empty response is refused before the requests run, as the A/B refuses it
  before the timed loop: an endpoint serving nothing has an admirably flat
  heap, and would otherwise be reported as clean rather than as never really
  called.

  Where the type is not enough, `[memory].holders` walks the reference graph
  up to the module or class that holds the objects, and every `lru_cache` in
  the process is measured for growth — an empty result there is informative
  too, since it narrows the category and points at a hand-rolled cache. It
  does not close the category: the comparison is on `cache_info().currsize`,
  so a cache that gains no entries while the values already in it accumulate
  references looks flat. The walk is breadth-first under a hard `scan_budget`:
  each `gc.get_referrers` call scans the whole heap, so a depth-first search
  with any branching runs for hours instead of failing.

### Changed

- The `k8s` backend's default deployed-context denylist now also refuses a `kubectl` context whose name contains `residential`, `data` or `operations`. Override it with `[backend].context_denylist` if one is a false positive on a local cluster.

<a id='changelog-2026.9.29'></a>
## [2026.9.29] - 2026-09-29

### Added

- Initial release of `mitol-django-benchmark`: an A/B benchmarking harness that
  seeds a production-shaped throwaway database, runs one endpoint against two
  git refs on identical rows, and attributes the difference query by query from
  OpenTelemetry spans.
- Benchmarks are declared as data across three layers — a committed project
  config, a committed per-benchmark config, and a gitignored per-developer
  config — with `${VAR}` / `${VAR:-default}` expansion in connection strings.
- A declarative seed engine with `factory`, `model`, `fixture`, `sql` and
  `hook` steps, cross-step references (`$cycle`, `$sample`, `$ref`) and
  environment-overridable shape knobs.
- Execution backends for local subprocesses, `docker compose` and Kubernetes
  local-dev clusters, with ref-sync verification for push-based environments.
  The Kubernetes backend requires an explicit `kubectl` context and refuses one
  whose name marks it as a deployed cluster.
- Comparison against production: `ol-benchmark baseline <config> <trace>...`
  distils any number of exported OTel traces into a committable
  `<name>.baseline.json` of per-query medians, keyed by the labels declared in
  `[[trace.classify]]` and carrying no statement text, attribute values or
  absolute timestamps. The report then shows a production column per query and
  flags any query not marked `targeted` that is more than
  `[calibration].drift_factor` away from production — the seed is what that
  calls into question, never the verdict.
- An `ol-benchmark` console script built on `click` (`init`,
  `validate`, `show`, `run`, `report`, `baseline`, `step`) and an
  `ol_benchmark` management command fallback. `init --project` also adds the
  package's artifacts to the project's `.gitignore` — including `traces/` and
  `*.trace.json`, because a raw OTel export carries statement literals and
  user identifiers and the first request for one comes a few steps later.
- Three refusals for measurements that would otherwise look healthy. An empty
  collection is refused before the timed loop, because two arms that each
  serialize an empty page agree perfectly and the equivalence check passes —
  the usual cause is authorization failing open, which renders as a 200 with
  no rows rather than a 403. A remote default file storage is refused before
  seeding, since a developer environment commonly holds working credentials
  for the production bucket and a seed creating file-bearing rows would upload
  to it. Both have opt-outs: `[target].allow_empty` and
  `[measure].allow_remote_storage`.
- Calibration observables can now name where to read themselves back out of
  the response (`response = "response_bytes"`, `"count"`, `"results"`,
  `"nested.<key>"`) and how far from production they may sit (`tolerance`,
  default 25%). Seed row counts prove what was created; only the response
  proves what the endpoint did with it. Like seed drift, a mismatch questions
  the seed and never the verdict.
