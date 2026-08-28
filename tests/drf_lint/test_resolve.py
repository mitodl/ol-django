"""Tests for import, dotted-name and Meta.model resolution."""

from __future__ import annotations

from mitol.drf_lint.index.model import ImportedName
from mitol.drf_lint.index.resolve import (
    absolute_module,
    inherits_from,
    lookup_class,
    resolve_base_qualname,
)

_MODEL_META = """
from rest_framework import serializers
{imports}

class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = {expression}
        fields = ["id"]
"""


def _resolve(project, imports: str, expression: str, **kwargs):
    project.with_models()
    project.write(
        "myapp/serializers.py",
        _MODEL_META.format(imports=imports, expression=expression),
    )
    return lookup_class(
        project.index(), "myapp.serializers", tuple(expression.split(".")), **kwargs
    )


# ------------------------------------------------------------------ #
# Relative imports
# ------------------------------------------------------------------ #


def test_absolute_module_from_relative_import():
    """`from .models import X` inside myapp.serializers means myapp.models."""
    imported = ImportedName(module="models", name="X", level=1)
    assert (
        absolute_module("myapp.serializers", imported, is_package=False)
        == "myapp.models"
    )


def test_absolute_module_from_double_relative_import():
    """A second dot climbs one more package."""
    imported = ImportedName(module="models", name="X", level=2)
    assert (
        absolute_module("myapp.api.serializers", imported, is_package=False)
        == "myapp.models"
    )


def test_absolute_module_inside_a_package_init():
    """Inside ``myapp/__init__.py``, one dot means myapp itself."""
    imported = ImportedName(module="models", name="X", level=1)
    assert absolute_module("myapp", imported, is_package=True) == "myapp.models"


# ------------------------------------------------------------------ #
# Meta.model resolution
# ------------------------------------------------------------------ #


def test_resolves_relative_from_import(project):
    """`from .models import Course`."""
    resolved = _resolve(project, "from .models import Course", "Course")
    assert resolved is not None
    assert resolved.qualname == "myapp.models.Course"


def test_resolves_absolute_from_import(project):
    """`from myapp.models import Course`."""
    resolved = _resolve(project, "from myapp.models import Course", "Course")
    assert resolved is not None
    assert resolved.qualname == "myapp.models.Course"


def test_resolves_aliased_import(project):
    """`from myapp.models import Course as Thing`."""
    resolved = _resolve(project, "from myapp.models import Course as Thing", "Thing")
    assert resolved is not None
    assert resolved.qualname == "myapp.models.Course"


def test_resolves_module_attribute_access(project):
    """`from myapp import models` then `models.Course`."""
    resolved = _resolve(project, "from myapp import models", "models.Course")
    assert resolved is not None
    assert resolved.qualname == "myapp.models.Course"


def test_resolves_dotted_module_import(project):
    """`import myapp.models` then `myapp.models.Course`."""
    resolved = _resolve(project, "import myapp.models", "myapp.models.Course")
    assert resolved is not None
    assert resolved.qualname == "myapp.models.Course"


# ------------------------------------------------------------------ #
# Fallback policy
# ------------------------------------------------------------------ #


def test_unique_fallback_recovers_an_unimported_name(project):
    """A name with exactly one candidate is recovered when imports fail."""
    resolved = _resolve(project, "", "Course", fallback="unique")
    assert resolved is not None
    assert resolved.qualname == "myapp.models.Course"


def test_never_fallback_refuses_to_guess(project):
    """`never` resolves only through imports."""
    assert _resolve(project, "", "Course", fallback="never") is None


def test_unique_fallback_refuses_an_ambiguous_name(project):
    """Two classes share the name, so the fallback declines to pick one."""
    project.write("otherapp/models.py", "class Course:\n    pass\n")
    assert _resolve(project, "", "Course", fallback="unique") is None


def test_any_fallback_picks_one_anyway(project):
    """`any` is the debugging escape hatch and does pick."""
    project.write("otherapp/models.py", "class Course:\n    pass\n")
    assert _resolve(project, "", "Course", fallback="any") is not None


# ------------------------------------------------------------------ #
# Base classes
# ------------------------------------------------------------------ #


def test_base_qualname_resolves_an_unindexed_third_party_class(project):
    """The import statement is enough; the base need not be indexed."""
    project.write(
        "myapp/serializers.py",
        """
        from mitol.common.serializers import BaseSerializer

        class Thing(BaseSerializer):
            pass
        """,
    )
    index = project.index()
    info = index.modules["myapp.serializers"].classes["Thing"]
    assert (
        resolve_base_qualname(index, "myapp.serializers", info.bases[0])
        == "mitol.common.serializers.BaseSerializer"
    )


def test_inherits_from_via_module_attribute(project):
    """`from mitol.common import serializers` then `serializers.BaseSerializer`."""
    project.write(
        "myapp/serializers.py",
        """
        from mitol.common import serializers

        class Thing(serializers.BaseSerializer):
            pass
        """,
    )
    index = project.index()
    info = index.modules["myapp.serializers"].classes["Thing"]
    assert inherits_from(
        index, info, frozenset({"mitol.common.serializers.BaseSerializer"})
    )


def test_inherits_from_through_a_local_intermediate_base(project):
    """A project-local base in between is followed."""
    project.write(
        "myapp/base.py",
        """
        from mitol.common.serializers import BaseSerializer

        class AppSerializer(BaseSerializer):
            pass
        """,
    )
    project.write(
        "myapp/serializers.py",
        """
        from myapp.base import AppSerializer

        class Thing(AppSerializer):
            pass
        """,
    )
    index = project.index()
    info = index.modules["myapp.serializers"].classes["Thing"]
    assert inherits_from(
        index, info, frozenset({"mitol.common.serializers.BaseSerializer"})
    )


def test_unrelated_base_does_not_match(project):
    """An ordinary ModelSerializer carries no prefetch contract."""
    project.write(
        "myapp/serializers.py",
        """
        from rest_framework import serializers

        class Thing(serializers.ModelSerializer):
            pass
        """,
    )
    index = project.index()
    info = index.modules["myapp.serializers"].classes["Thing"]
    assert not inherits_from(
        index, info, frozenset({"mitol.common.serializers.BaseSerializer"})
    )
