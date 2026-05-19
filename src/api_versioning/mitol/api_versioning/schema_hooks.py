"""drf-spectacular postprocessing hook for API versioning.

When generating OpenAPI specs for older API versions, this hook walks
backwards through registered transforms and applies their schema
modifications. This ensures each version's spec accurately describes
that version's response/request shapes, which is critical for correct
TypeScript client generation.

Register this hook in SPECTACULAR_SETTINGS["POSTPROCESSING_HOOKS"].
"""

import logging
import re
from typing import Any

from mitol.api_versioning.versions import (
    get_latest_version,
    get_transforms_between,
)

log = logging.getLogger(__name__)


def _resolve_schema_name(serializer_ref: Any) -> str:
    """Convert a serializer reference to the drf-spectacular schema name.

    Accepts either a dotted path string or a class object.
    drf-spectacular typically strips the "Serializer" suffix and uses the
    remaining class name. E.g.::

        "myapp.serializers.LearningResourceSerializer"
        -> "LearningResource"
    """
    if isinstance(serializer_ref, str):
        class_name = serializer_ref.rsplit(".", 1)[-1]
    else:
        class_name = serializer_ref.__name__
    return re.sub(r"Serializer$", "", class_name)


# Known suffixes that drf-spectacular appends to schema component names.
# COMPONENT_SPLIT_REQUEST=True generates separate Request variants
# for writable endpoints.
_SCHEMA_SUFFIXES = ("", "Request")
_SCHEMA_PREFIXES = ("", "Patched")


def _get_all_schema_variants(base_name, schemas):
    """Find all schema component names that match a base serializer name.

    drf-spectacular generates variants like:
        - LearningResource (base)
        - LearningResourceRequest (for request bodies)
        - PatchedLearningResource (for PATCH requests)
        - PatchedLearningResourceRequest

    Uses exact matching with known prefixes/suffixes to avoid false
    positives (e.g., "CourseRun" should not match when targeting "Course").
    """
    expected = set()
    for prefix in _SCHEMA_PREFIXES:
        for suffix in _SCHEMA_SUFFIXES:
            expected.add(f"{prefix}{base_name}{suffix}")

    return [name for name in schemas if name in expected]


def postprocess_versioned_schema(
    result: dict[str, Any],
    generator: Any,
    request: Any,  # noqa: ARG001
    public: bool,  # noqa: ARG001, FBT001
) -> dict[str, Any]:
    """Postprocessing hook for drf-spectacular.

    When generating the schema for an older API version, applies all
    transform_schema() methods backwards to produce correct schema shapes
    for that version.

    Args:
        result: The generated OpenAPI schema dict.
        generator: The drf-spectacular SchemaGenerator instance.
        request: The request (may be None during CLI generation).
        public: Whether this is a public schema.

    Returns:
        The (possibly modified) schema dict.
    """
    latest = get_latest_version()
    if not latest:
        return result

    api_version = getattr(generator, "api_version", None) or latest
    if api_version == latest:
        return result

    schemas = result.get("components", {}).get("schemas", {})
    if not schemas:
        return result

    transforms = get_transforms_between(api_version, latest)
    if not transforms:
        return result

    log.info(
        "Applying %d schema transform(s) for API version %s",
        len(transforms),
        api_version,
    )

    # Apply transforms in reverse order (newest first, going backwards)
    for transform_cls in reversed(transforms):
        # Use explicit component_name if set, otherwise derive from serializer
        base_name = transform_cls.component_name or _resolve_schema_name(
            transform_cls.serializer
        )
        variant_names = _get_all_schema_variants(base_name, schemas)

        for schema_name in variant_names:
            schemas[schema_name] = transform_cls().transform_schema(
                schemas[schema_name]
            )

    return result
