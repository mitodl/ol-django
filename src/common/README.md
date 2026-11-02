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

**It must precede `Model` in the bases**, or its `refresh_from_db()` loses the MRO and silently does nothing:

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

A refresh narrowed with `fields` clears only the cached properties that declare one of those fields in the optional `cached_property_sources` map, and clears nothing when the map is empty:

```python
class Enrollment(CachedPropertiesMixin, TimestampedModel):
    cached_property_sources = {"openedx_user": {"user"}}


enrollment.refresh_from_db(fields=["user"])   # drops openedx_user
enrollment.refresh_from_db(fields=["title"])  # drops nothing
```

This is deliberate rather than conservative-by-accident. `DeferredAttribute.__get__` calls `refresh_from_db(fields=[field_name])` for every deferred-field access on a `.only()`/`.defer()` instance, so an unconditional clear would add queries to the paths most likely to have been tuned. From Django 5.1 it also mirrors what Django itself does with `fields`: drop only the prefetch entries named in `fields`, clear only the relations where `rel.name in fields`. Django 4.2 and 5.0 clear every cached relation on any refresh, narrowed or not, so on those versions the narrowing is this mixin's alone.

The names in `cached_property_sources` are matched against the strings a caller passes to `fields` - there is no resolution against the model's fields. So declare whichever spelling your callers use: `refresh_from_db(fields=["user"])` and `refresh_from_db(fields=["user_id"])` are both legal for the same foreign key, and only the declared one matches. A source name that is never passed is silently never matched; a key that is not a cached property on the model raises `ImproperlyConfigured`, for the same reason an unknown name does.
