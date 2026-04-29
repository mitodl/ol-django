"""Tests for the api_versioning Django system checks."""

import pytest
from mitol.api_versioning import checks as checks_module
from mitol.api_versioning.checks import check_transform_serializer_paths
from mitol.api_versioning.transforms import Transform
from mitol.api_versioning.versions import (
    _registered_transforms,
    _transform_registry,
)


@pytest.fixture(autouse=True)
def _clear_registry():
    """Clear the transform registry before and after each test."""
    saved_registry = dict(_transform_registry)
    saved_registered = set(_registered_transforms)
    _transform_registry.clear()
    _registered_transforms.clear()
    yield
    _transform_registry.clear()
    _registered_transforms.clear()
    _transform_registry.update(saved_registry)
    _registered_transforms.update(saved_registered)


# A real serializer-shaped class we can resolve via dotted path.
class _ResolvableSerializer:
    pass


_RESOLVABLE_PATH = f"{__name__}._ResolvableSerializer"


def test_no_transforms_passes(settings):
    """No registered transforms → no issues."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1"]}
    assert check_transform_serializer_paths(app_configs=None) == []


def test_resolvable_path_passes(settings):
    """A transform whose serializer resolves cleanly → no issues."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1", "v2"]}

    class GoodTransform(Transform):
        version = "v2"
        description = "ok"
        serializer = _RESOLVABLE_PATH

    issues = check_transform_serializer_paths(app_configs=None)
    assert issues == []


def test_unresolvable_path_emits_e001(settings):
    """Bad dotted path → E001 Error."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1", "v2"]}

    class BadTransform(Transform):
        version = "v2"
        description = "broken path"
        serializer = "myapp.does_not_exist.NopeSerializer"

    issues = check_transform_serializer_paths(app_configs=None)
    ids = [i.id for i in issues]
    assert "api_versioning.E001" in ids


def test_canonical_mismatch_emits_w001(settings):
    """Path resolves but canonical name differs → W001 Warning."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1", "v2"]}

    # Re-export the class under a different module path (simulate
    # `from .real import X` in another module). We can't easily set up
    # a real re-export at test time, so simulate by giving the class a
    # __qualname__ that doesn't match the path.
    class MismatchTransform(Transform):
        version = "v2"
        description = "alias path"
        serializer = "tests.api_versioning.test_checks._ResolvableSerializer"

    # The class lives at this module path. Its canonical
    # __module__.__qualname__ should match for this test to pass; flip the
    # declared string to simulate drift.
    MismatchTransform.serializer = (
        "tests.api_versioning.test_checks.AliasResolvableSerializer"
    )

    # Patch import_string to resolve to our class anyway, so we hit the
    # canonical-mismatch branch.
    real_import_string = checks_module.import_string

    def fake_import_string(path):
        if path == "tests.api_versioning.test_checks.AliasResolvableSerializer":
            return _ResolvableSerializer
        return real_import_string(path)

    checks_module.import_string = fake_import_string
    try:
        issues = check_transform_serializer_paths(app_configs=None)
    finally:
        checks_module.import_string = real_import_string

    ids = [i.id for i in issues]
    assert "api_versioning.W001" in ids


def test_version_not_in_allowed_emits_e002(settings):
    """Version outside ALLOWED_VERSIONS → E002 Error."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1"]}

    class WrongVersionTransform(Transform):
        version = "v9"
        description = "future version"
        serializer = _RESOLVABLE_PATH

    issues = check_transform_serializer_paths(app_configs=None)
    ids = [i.id for i in issues]
    assert "api_versioning.E002" in ids
