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
  `retaining`, `high-water` or `stable`, by thresholds the config states.

  Where the type is not enough, `[memory].holders` walks the reference graph
  up to the module or class that holds the objects, and every `lru_cache` in
  the process is measured for growth — an empty result there is informative
  too, since it rules out the whole category and points at a hand-rolled
  cache. The walk is breadth-first under a hard `scan_budget`: each
  `gc.get_referrers` call scans the whole heap, so a depth-first search with
  any branching runs for hours instead of failing.
