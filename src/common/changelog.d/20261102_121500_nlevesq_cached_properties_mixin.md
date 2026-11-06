### Added

- `CachedPropertiesMixin` gives a model one documented way to invalidate its
  `cached_property` values, and a `refresh_from_db` that drops them.
  `Model.refresh_from_db` clears prefetch caches, cached foreign keys, cached
  reverse one-to-ones and cached generic foreign keys, but it cannot know
  about a `functools` or `django.utils.functional` cache, so a property
  derived from a relation stayed stale after the relation changed and every
  call site invented its own eviction. Both `cached_property` flavors are
  discovered, including ones inherited from a base class, and
  `clear_cached_properties()` raises on a name that is not one rather than
  quietly doing nothing. Mix it in before `Model` so its `refresh_from_db`
  wins the MRO - a class that gets the base order wrong raises `TypeError`
  at the `class` statement rather than silently never clearing.
- Every refresh clears every cached property, including one narrowed with
  `fields`, except where the named fields were all still deferred. Reading a
  deferred field is what loads it, so nothing on the instance can derive from
  one that is still absent - which keeps `DeferredAttribute.__get__`, firing
  on every deferred-field access, from recomputing the caches on
  `.only()`/`.defer()` instances.
