"""Tests for the api_versioning Django system checks."""

import pytest
from mitol.api_versioning import checks as checks_module
from mitol.api_versioning.checks import check_transform_serializer_paths
from mitol.api_versioning.transforms import Transform


# A real serializer-shaped class we can resolve via dotted path.
class _ResolvableSerializer:
    pass


_RESOLVABLE_PATH = f"{__name__}._ResolvableSerializer"


@pytest.mark.usefixtures("_versions")
def test_no_transforms_passes():
    """No registered transforms → no issues."""
    assert check_transform_serializer_paths(app_configs=None) == []


@pytest.mark.usefixtures("_versions")
def test_resolvable_path_passes():
    """A transform whose serializer resolves cleanly → no issues."""

    class GoodTransform(Transform):
        version = "v2"
        description = "ok"
        serializer = _RESOLVABLE_PATH

    assert check_transform_serializer_paths(app_configs=None) == []


@pytest.mark.parametrize(
    ("version", "serializer", "expected_id"),
    [
        ("v2", "myapp.does_not_exist.NopeSerializer", "api_versioning.E001"),
        ("v9", _RESOLVABLE_PATH, "api_versioning.E002"),
    ],
    ids=["unresolvable_path_e001", "version_not_in_allowed_e002"],
)
@pytest.mark.usefixtures("_versions")
def test_check_emits_error(version, serializer, expected_id):
    """Misconfigured transforms surface the appropriate check id."""
    type(
        "BadTransform",
        (Transform,),
        {
            "version": version,
            "description": "bad",
            "serializer": serializer,
        },
    )

    issues = check_transform_serializer_paths(app_configs=None)
    assert expected_id in [i.id for i in issues]


@pytest.mark.usefixtures("_versions")
def test_canonical_mismatch_emits_w001(monkeypatch):
    """Path resolves but canonical name differs → W001 Warning."""
    alias_path = "tests.api_versioning.test_checks.AliasResolvableSerializer"

    class MismatchTransform(Transform):
        version = "v2"
        description = "alias path"
        # Start with a real path so metaclass validation passes, then drift it.
        serializer = _RESOLVABLE_PATH

    MismatchTransform.serializer = alias_path

    real_import_string = checks_module.import_string

    def fake_import_string(path):
        if path == alias_path:
            return _ResolvableSerializer
        return real_import_string(path)

    monkeypatch.setattr(checks_module, "import_string", fake_import_string)

    issues = check_transform_serializer_paths(app_configs=None)
    assert "api_versioning.W001" in [i.id for i in issues]
