mitol-django-common
---

This is the Open Learning Django Common app. It provides common functionality used across all our applications.

### Getting started

`pip install mitol-django-common`


### Configuration

- `MITOL_COMMON_USER_FACTORY` - (optional) set to the fully qualified path for a user model factory, otherwise a default based on `django.contrib.auth.models.User` is used

### `CachedPropertiesMixin`

`Model.refresh_from_db()` clears `_prefetched_objects_cache`, cached foreign keys, cached reverse one-to-ones and cached generic foreign keys. It cannot clear a `functools.cached_property` or a `django.utils.functional.cached_property`, because it has no way to know they exist. A cached property derived from a relation therefore goes stale the moment that relation changes, and nothing in Django puts it right.

`CachedPropertiesMixin` makes those caches invalidatable and teaches `refresh_from_db()` to drop them.

**It must precede `Model` in the bases**, or its `refresh_from_db()` loses the MRO and every eviction it promised silently stops happening. Getting the order wrong raises `TypeError` at the `class` statement - it is a mistake in the class definition rather than in any deployment's settings, and it is not specific to Django, since the same shape breaks any class that relies on evicting a `cached_property`:

```python
from mitol.common.models import CachedPropertiesMixin, TimestampedModel


class Enrollment(CachedPropertiesMixin, TimestampedModel):
    @cached_property
    def openedx_user(self):
        return OpenEdxUser.objects.filter(user=self.user).first()
```

```python
enrollment.clear_cached_properties()                  # drop all of them
enrollment.clear_cached_properties("openedx_user")    # drop one
enrollment.refresh_from_db()                          # reload fields, drop all of them
```

Both `cached_property` flavors are discovered, as are ones inherited from a base class. `clear_cached_properties()` raises `AttributeError` on a name that is not a cached property on the model: a silent no-op is how a renamed property becomes a reintroduced staleness bug. Clearing a property that was never read is fine.

#### Narrowed refreshes

Every refresh clears every cached property, including one narrowed with `fields`:

```python
enrollment.refresh_from_db(fields=["user"])   # drops all of them
```

The one exception is a refresh whose named fields were *all* still deferred, which clears nothing. Reading a deferred field is what loads it, so a field still absent from the instance cannot have been read by any cached property on it:

```python
enrollment = Enrollment.objects.only("id", "user").get(pk=pk)
enrollment.openedx_user                       # cached
enrollment.title                              # loads the deferred field, drops nothing
```

That carve-out is what keeps `.only()`/`.defer()` usable: `DeferredAttribute.__get__` calls `refresh_from_db(fields=[attname])` on every deferred-field access, and clearing there would add recomputation to the paths most likely to have been tuned. It is a subset test rather than an intersection - one already-loaded name among the deferred ones is enough to clear - and relation names never qualify, because `get_deferred_fields()` returns concrete attnames only.

So a narrowed `refresh_from_db` is never a way to preserve a specific cached property. If recomputing one is expensive enough to matter, read it back after the refresh rather than trying to keep it.
