"""Django system checks for the api_versioning app.

Validates that every registered transform's ``serializer`` attribute
points at a real serializer class and uses a version that appears in
``REST_FRAMEWORK["ALLOWED_VERSIONS"]``. Catches typos and rename-drift
that would otherwise silently no-op at request time.

Run via ``./manage.py check`` (also runs as part of Django startup).
"""

from django.core.checks import Error, register
from django.core.checks import Warning as DjangoWarning
from django.utils.module_loading import import_string
from mitol.api_versioning.versions import (
    _transform_registry,
    get_allowed_versions,
)


@register()
def check_transform_serializer_paths(app_configs, **kwargs):  # noqa: ARG001
    """Validate every registered transform.

    Emits:
        - api_versioning.E001 — ``serializer`` dotted path does not resolve.
        - api_versioning.W001 — resolved class's canonical path differs from
          the declared one (re-export drift; lookup may still work).
        - api_versioning.E002 — ``version`` is not in ``ALLOWED_VERSIONS``.
    """
    issues = []
    allowed_versions = set(get_allowed_versions())

    for transforms in _transform_registry.values():
        for transform_cls in transforms:
            issues.extend(_check_one(transform_cls, allowed_versions))

    return issues


def _check_one(transform_cls, allowed_versions):
    issues = []
    serializer_ref = transform_cls.serializer

    if isinstance(serializer_ref, str):
        try:
            resolved = import_string(serializer_ref)
        except (ImportError, AttributeError) as exc:
            issues.append(
                Error(
                    (
                        f"Transform {transform_cls.__qualname__!r} references "
                        f"unresolvable serializer {serializer_ref!r}: {exc}"
                    ),
                    hint=(
                        "Check the dotted path or rename the transform's "
                        "`serializer` attribute to match the actual class."
                    ),
                    obj=transform_cls,
                    id="api_versioning.E001",
                )
            )
            resolved = None

        if resolved is not None:
            canonical = f"{resolved.__module__}.{resolved.__qualname__}"
            if canonical != serializer_ref:
                issues.append(
                    DjangoWarning(
                        (
                            f"Transform {transform_cls.__qualname__!r} declares "
                            f"serializer={serializer_ref!r} but the resolved "
                            f"class's canonical path is {canonical!r}. "
                            f"Runtime lookup uses the canonical path; the "
                            f"transform may not fire."
                        ),
                        hint=(
                            f"Update the transform's `serializer` attribute to "
                            f"{canonical!r}."
                        ),
                        obj=transform_cls,
                        id="api_versioning.W001",
                    )
                )

    if allowed_versions and transform_cls.version not in allowed_versions:
        issues.append(
            Error(
                (
                    f"Transform {transform_cls.__qualname__!r} has "
                    f"version={transform_cls.version!r} which is not in "
                    f"REST_FRAMEWORK['ALLOWED_VERSIONS'] "
                    f"({sorted(allowed_versions)!r})."
                ),
                hint=(
                    "Add the version to ALLOWED_VERSIONS or fix the "
                    "transform's `version` attribute."
                ),
                obj=transform_cls,
                id="api_versioning.E002",
            )
        )

    return issues
