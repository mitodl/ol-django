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
  wins the MRO - a class that gets the base order wrong, or that declares a
  `cached_property_sources` key naming no cached property, raises `TypeError`
  at the `class` statement rather than silently never clearing.
- A refresh narrowed with `fields` clears only the cached properties that
  declare one of those fields in the optional `cached_property_sources` map.
  `DeferredAttribute.__get__` refreshes with `fields=[<deferred field>]` on
  every deferred-field access, so an unconditional clear there would add
  queries to the paths most likely to have been tuned.
