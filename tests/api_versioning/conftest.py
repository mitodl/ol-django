"""Shared fixtures for api_versioning tests."""

import pytest
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


@pytest.fixture
def _versions(request, settings):
    """Configure ``REST_FRAMEWORK['ALLOWED_VERSIONS']``.

    Defaults to ``['v0', 'v1', 'v2']``. Override the version list per test
    with indirect parametrization::

        @pytest.mark.parametrize("_versions", [["v0", "v1"]], indirect=True)
        def test_foo(_versions): ...
    """
    versions = getattr(request, "param", ["v0", "v1", "v2"])
    settings.REST_FRAMEWORK = {
        **getattr(settings, "REST_FRAMEWORK", {}),
        "ALLOWED_VERSIONS": list(versions),
    }
    return versions
