# mitol-django-api_versioning

Transform-based API versioning for Django REST Framework.

When an API needs a breaking change, this library lets you keep one canonical
serializer (the latest version's shape) and describe the breaking change as a
small `Transform` class. Older clients keep working because the library
applies the transforms backwards on response and forwards on request; new
clients get the latest shape unmodified. The same approach also rewrites the
generated OpenAPI schema per version so generated TypeScript clients have
correct types.

The design is modelled on [Stripe's API versioning approach](https://stripe.com/blog/api-versioning).
The advantage over per-version view/serializer modules is that bug fixes,
permissions, query plans, and serializer logic live in one place; the
disadvantage is that very behavioural divergence between versions (different
auth flows, different endpoints) is out of scope and should still use
per-version views.

## Prerequisites

- Django ≥ 3.0
- Django REST Framework ≥ 3.14
- drf-spectacular (only required if you want per-version OpenAPI schemas)

DRF must be configured to use namespace-based versioning so each request
arrives with `request.version` set.

## Installation

```bash
pip install mitol-django-api_versioning
```

Add the app to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    "mitol.api_versioning.apps.ApiVersioningApp",
]
```

The app's `ready()` hook auto-discovers a `transforms` submodule in every
installed app, so transforms registered in `<your_app>/transforms.py` (or
`<your_app>/transforms/__init__.py`) load at startup.

## Configuration

### DRF settings

```python
REST_FRAMEWORK = {
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "ALLOWED_VERSIONS": ["v0", "v1", "v2"],
    ...
}
```

`ALLOWED_VERSIONS` is the source of truth. The last entry is the **latest
version**: serializers always produce that shape, and transforms run only when
the request version differs.

### URL conf

The same views serve every version; namespace-based versioning sets
`request.version` from the URL prefix:

```python
v2_urls = v1_urls  # same view callables, same routes

urlpatterns = [
    re_path(r"^api/v2/", include((v2_urls, "v2"))),
    re_path(r"^api/v1/", include((v1_urls, "v1"))),
]
```

### drf-spectacular settings (optional)

If you want per-version OpenAPI schemas, register the postprocess hook:

```python
SPECTACULAR_SETTINGS = {
    ...
    "POSTPROCESSING_HOOKS": [
        "mitol.api_versioning.schema_hooks.postprocess_versioned_schema",
    ],
}
```

See [Per-version OpenAPI schemas](#per-version-openapi-schemas) below for the
URL conf that activates it.

## Usage

### Applying the mixin

Put `VersionedSerializerMixin` first in the bases of any serializer that has
versioned transforms. The serializer always produces the latest version's
shape; the mixin intercepts `to_representation` / `to_internal_value` and
applies transforms when `request.version` is older.

```python
from mitol.api_versioning.mixins import VersionedSerializerMixin
from rest_framework import serializers

class CourseSerializer(VersionedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "title", "enrollment_url"]
```

The mixin's `__init_subclass__` raises `TypeError` at class-definition time if
it appears after the Serializer base class in the MRO, so misordered bases
fail loudly at import time.

### Defining a transform

Each breaking change is one `Transform` subclass. Implement only the methods
relevant to the change — `to_representation` for response data,
`to_internal_value` for request data, `transform_schema` for OpenAPI.

```python
# learning_resources/transforms/v2.py

from mitol.api_versioning.transforms import Transform


class RunAddEnrollmentUrl(Transform):
    """v2 added enrollment_url to LearningResourceRunSerializer."""

    version = "v2"
    description = "Add enrollment_url field to Run"
    serializer = "learning_resources.serializers.LearningResourceRunSerializer"

    def to_representation(self, data, request, instance):
        # v1 clients didn't have enrollment_url
        data.pop("enrollment_url", None)
        return data

    def transform_schema(self, schema):
        schema.get("properties", {}).pop("enrollment_url", None)
        required = schema.get("required", [])
        if "enrollment_url" in required:
            required.remove("enrollment_url")
        return schema
```

`version` is the version that **introduced** the breaking change. The
metaclass auto-registers the class with the registry, so simply defining it
is enough — no manual registration call.

### `component_name` override

`transform_schema` finds the OpenAPI component to mutate by stripping
`Serializer` from the class name (`MySerializer` → `My`). When a serializer
uses `@extend_schema(component_name=...)` or shares a component name with
another serializer, set `component_name` explicitly:

```python
class CaptionUrlAddWordCount(Transform):
    version = "v2"
    description = "Add word_count to caption URL entries"
    serializer = "learning_resources.serializers.VideoSerializer"
    component_name = "CaptionUrl"  # not "Video"

    def transform_schema(self, schema):
        schema.get("properties", {}).pop("word_count", None)
        ...
```

### Inherited serializers

Registry lookup is **exact-class match** — a transform attached to a base
serializer does not automatically apply to subclasses. If both
`LearningResourceBaseDepartmentSerializer` and a derived
`LearningResourceDepartmentSerializer` rename the same field, declare two
transforms (or share the body via a no-`version` abstract base class so the
logic lives once):

```python
class _DepartmentRenameBase(Transform):
    # No `version` → not registered. Just shared logic.
    description = "Rename channel_url to url"

    def to_representation(self, data, request, instance):
        if "url" in data:
            data["channel_url"] = data.pop("url")
        return data


class DepartmentRenameChannelUrlToUrl(_DepartmentRenameBase):
    version = "v2"
    serializer = "learning_resources.serializers.LearningResourceBaseDepartmentSerializer"


class FullDepartmentRenameChannelUrlToUrl(_DepartmentRenameBase):
    version = "v2"
    serializer = "learning_resources.serializers.LearningResourceDepartmentSerializer"
```

### Non-DRF data (OpenSearch, raw dicts)

For data that bypasses DRF serialization but should match a serializer's
output shape (e.g. OpenSearch hits), use `transform_dict_backwards`:

```python
from mitol.api_versioning.mixins import transform_dict_backwards

results = [
    transform_dict_backwards(
        hit["_source"],
        LearningResourceSerializer,
        request,
        recursive=True,  # also walk nested serializer fields
    )
    for hit in hits
]
```

## Per-version OpenAPI schemas

drf-spectacular's `SpectacularAPIView` accepts an `api_version` kwarg that it
threads onto the generator. The postprocessing hook reads that and rewrites
the schema per version:

```python
# openapi/urls.py
from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    path("api/v1/schema/",
         SpectacularAPIView.as_view(api_version="v1"),
         name="v1_schema"),
    path("api/v1/schema/swagger-ui/",
         SpectacularSwaggerView.as_view(url_name="v1_schema"),
         name="v1_swagger_ui"),
    path("api/v2/schema/",
         SpectacularAPIView.as_view(api_version="v2"),
         name="v2_schema"),
    ...
]
```

Each version's schema URL serves a fully transformed OpenAPI document; point
your client generator at it.

## Debugging

When a transform doesn't fire, three things will tell you why:

1. **`./manage.py check`** runs three system checks at startup
   (`api_versioning.E001` / `W001` / `E002`). They flag misconfigured
   `serializer` paths (typos, drift) and versions outside `ALLOWED_VERSIONS`.
2. **`list_transforms_for_serializer(SerializerClass)`** returns every
   registered transform for that serializer, ordered oldest-first. Useful in
   a Python shell to confirm registration.
3. **`log.debug` output** from the mixin: enable `DEBUG` logging on
   `mitol.api_versioning.mixins` to see the chain of transforms applied to
   each request, with version transitions.

## Limitations

This library is scoped to **field-level shape evolution** — renames, additions,
removals, type coercions. Out of scope:

- Different business logic per version (different auth, different ORM access)
- Endpoints that exist in some versions but not others
- Pre-serialization queryset planning (`select_related` / `prefetch_related`)
  — see below.

### Pre-serialization queryset planning

Transforms run *after* DRF has already serialized the instance, so they can't
add ORM hints to the queryset. If an older version exposes nested data the
latest version no longer includes (or no longer prefetches), the older
version's response can degrade into N+1 queries.

The fix lives in the view, not the transform: branch on `request.version` in
`get_queryset()` and only add the extra prefetches for versions that still
need them. The latest version pays nothing.

```python
class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CourseSerializer

    def get_queryset(self):
        queryset = Course.objects.all()
        if getattr(self.request, "version", None) == "v1":
            # v1 still embeds nested runs; v2 returns runs_url instead
            queryset = queryset.prefetch_related("runs__instructors")
        return queryset
```

When an older version needs dramatically different loading behaviour, that's
a sign the change has crossed from shape-evolution into behavioural divergence
and a separate versioned view is probably cleaner.

### Transform-chain growth

The transform chain grows over time. Each new version adds transforms, and a
v1 request against a v5-latest serializer applies four sets of transforms in
sequence. Test every supported version against every endpoint with transforms
to catch regressions where transforms interact badly.
