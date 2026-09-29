### Added

- `ol-benchmark memory <config>`: a retention pass for the case the A/B cannot
  answer. When a latency run exonerates an endpoint and production still
  disagrees, the question is usually not what the request costs but what it
  leaves behind — a worker that grows every request ends up living at whatever
  ceiling bounds it, where stop-the-world collections are longest. Single-arm,
  because retention is a property of the code rather than a difference between
  two commits, so it needs no checkout and runs on a dirty tree.

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
