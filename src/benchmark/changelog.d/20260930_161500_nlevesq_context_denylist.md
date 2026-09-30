### Changed

- The `k8s` backend's default deployed-context denylist now also refuses a `kubectl` context whose name contains `residential`, `data` or `operations`. Override it with `[backend].context_denylist` if one is a false positive on a local cluster.
