"""Tests for the project index: scanning, propagation and inheritance."""

from __future__ import annotations

from mitol.drf_lint.checker import (
    ALL_RULES,
    CROSS_FILE_RULES,
    LOCAL_RULES,
    CheckContext,
    check_source,
)
from mitol.drf_lint.index import explain, overlay_source, transitive_hits
from mitol.drf_lint.index.resolve import class_member

_EXPECTED_HITS = 2


def _member(index, module, cls, name):
    info = index.modules[module].classes[cls]
    found = class_member(index, info, name)
    assert found is not None, f"{cls}.{name} not in the index"
    return found


# ------------------------------------------------------------------ #
# Direct detection
# ------------------------------------------------------------------ #


def test_property_with_queryset_call_is_marked(modelled):
    """`self.runs.count()` in a property marks it as query-performing."""
    index = modelled.index()
    _, member = _member(index, "myapp.models", "Course", "run_count")
    assert member.queries
    assert member.kind == "property"


def test_property_without_query_is_clean(modelled):
    """A property that only touches plain attributes is not marked."""
    index = modelled.index()
    _, member = _member(index, "myapp.models", "Course", "plain_name")
    assert not member.queries


def test_foreign_key_traversal_is_a_query(modelled):
    """`self.author.name` counts, because the related row must be fetched."""
    index = modelled.index()
    _, member = _member(index, "myapp.models", "Course", "author_name")
    assert member.queries


def test_relations_are_recorded_by_kind(modelled):
    """Foreign keys are traversal-sensitive; many-to-many fields are not."""
    course = modelled.index().modules["myapp.models"].classes["Course"]
    assert "author" in course.relations
    assert "topics" in course.many_relations
    assert "topics" not in course.relations


def test_cached_property_still_counts(modelled):
    """`@cached_property` caches per instance, so a list response still N+1s."""
    index = modelled.index()
    _, member = _member(index, "myapp.models", "Course", "cached_runs")
    assert member.queries
    assert member.kind == "cached_property"


def test_module_level_function_is_marked(modelled):
    """A plain function that queries is indexed like any other member."""
    functions = modelled.index().modules["myapp.utils"].functions
    assert functions["compute_stats"].queries
    assert not functions["pure_helper"].queries


# ------------------------------------------------------------------ #
# Propagation
# ------------------------------------------------------------------ #


def test_transitive_call_chain_propagates(modelled):
    """Summary -> get_price -> compute_stats all count as querying."""
    index = modelled.index()
    for name in ("summary", "get_price"):
        _, member = _member(index, "myapp.models", "Course", name)
        assert member.queries, name


def test_explanation_names_the_whole_chain(modelled):
    """The reported chain is what makes a transitive hit diagnosable."""
    index = modelled.index()
    chain = explain(index, ("myapp.models", "Course", "summary"))
    assert chain == "Course.summary → Course.get_price → compute_stats"


def test_mutual_recursion_terminates_and_is_clean(modelled):
    """loop_a and loop_b call each other and reach no query."""
    index = modelled.index()
    for name in ("loop_a", "loop_b"):
        _, member = _member(index, "myapp.models", "Course", name)
        assert not member.queries, name


def test_recursion_reaching_a_query_is_marked(project):
    """A cycle that touches the database still marks every member in it."""
    project.write(
        "myapp/models.py",
        """
        class Thing:
            @property
            def a(self):
                return self.b

            @property
            def b(self):
                return self.a or self.rows.count()
        """,
    )
    index = project.index()
    for name in ("a", "b"):
        _, member = _member(index, "myapp.models", "Thing", name)
        assert member.queries, name


def test_transitive_hits_collect_every_reached_query(project):
    """The hit union spans the whole chain, not just the entry point."""
    project.write(
        "myapp/models.py",
        """
        class Thing:
            @property
            def outer(self):
                return self.tags.all() and self.inner

            @property
            def inner(self):
                return self.rows.count()
        """,
    )
    index = project.index()
    hits = transitive_hits(index, ("myapp.models", "Thing", "outer"))
    assert len(hits) == _EXPECTED_HITS
    assert {hit.method for hit in hits} == {"all", "count"}


# ------------------------------------------------------------------ #
# Inheritance
# ------------------------------------------------------------------ #


def test_property_inherited_from_abstract_base(modelled):
    """A querying property on an abstract base is found on the subclass."""
    index = modelled.index()
    owner, member = _member(index, "myapp.models", "Course", "revision_count")
    assert member.queries
    assert owner.name == "AbstractTimestamped"


def test_subclass_override_shadows_a_querying_base_property(modelled):
    """Track.run_count is clean and must win over Course.run_count."""
    index = modelled.index()
    owner, member = _member(index, "myapp.models", "Track", "run_count")
    assert owner.name == "Track"
    assert not member.queries


def test_attribute_assignment_shadows_a_base_member(project):
    """A class-level assignment shadows an inherited querying property."""
    project.write(
        "myapp/models.py",
        """
        class Base:
            @property
            def value(self):
                return self.rows.count()

        class Child(Base):
            value = 3
        """,
    )
    index = project.index()
    owner, member = _member(index, "myapp.models", "Child", "value")
    assert owner.name == "Child"
    assert not member.queries


def test_unresolvable_base_is_skipped(project):
    """A third-party base terminates the walk instead of raising."""
    project.write(
        "myapp/models.py",
        """
        from somewhere.external import Mixin

        class Thing(Mixin):
            @property
            def value(self):
                return 1
        """,
    )
    index = project.index()
    _, member = _member(index, "myapp.models", "Thing", "value")
    assert not member.queries


# ------------------------------------------------------------------ #
# Markers and robustness
# ------------------------------------------------------------------ #


def test_no_query_marker_clears_a_member(modelled):
    """`# drf-lint: no-query` overrides the detected query."""
    index = modelled.index()
    _, member = _member(index, "myapp.models", "Course", "marked_clean")
    assert not member.queries


def test_no_query_marker_cuts_propagation_to_callers(modelled):
    """A caller of a hand-marked member stays clean too."""
    index = modelled.index()
    _, member = _member(index, "myapp.models", "Course", "calls_marked_clean")
    assert not member.queries


def test_query_marker_forces_a_member(project):
    """`# drf-lint: query` marks a member the scanner cannot see through."""
    project.write(
        "myapp/models.py",
        """
        class Thing:
            @property
            def value(self):  # drf-lint: query
                return self._opaque()
        """,
    )
    index = project.index()
    _, member = _member(index, "myapp.models", "Thing", "value")
    assert member.queries


def test_unparseable_file_is_skipped(project):
    """A syntax error elsewhere must never break the run."""
    project.write("myapp/broken.py", "def oops(:\n")
    project.with_models()
    index = project.index()
    assert "myapp.broken" not in index.modules
    assert "myapp.models" in index.modules


def test_dict_get_is_not_mistaken_for_a_query(project):
    """`.get("k")` with an argument is a mapping lookup, not a queryset call."""
    project.write(
        "myapp/models.py",
        """
        class Thing:
            @property
            def value(self):
                return self.data.get("key")
        """,
    )
    index = project.index()
    _, member = _member(index, "myapp.models", "Thing", "value")
    assert not member.queries


# ------------------------------------------------------------------ #
# Overlaying unsaved source
# ------------------------------------------------------------------ #


def test_overlay_replaces_what_was_read_from_disk(modelled):
    """A programmatic caller can check source that is not on disk yet."""
    path = modelled.root / "myapp" / "serializers.py"
    path.write_text("class CourseSerializer:\n    pass\n")
    index = modelled.index()

    edited = (
        "from myapp.models import Course\n\n\n"
        "class CourseSerializer:\n"
        "    class Meta:\n"
        "        model = Course\n"
        '        fields = ["run_count"]\n'
    )
    module = overlay_source(index, edited, path)
    violations = check_source(edited, CheckContext(index=index, module=module))
    assert [v.rule for v in violations] == ["ORM005"]


def test_overlay_of_unparseable_source_keeps_the_indexed_version(modelled):
    """A half-typed file must not evict what the index already knows."""
    path = modelled.root / "myapp" / "models.py"
    index = modelled.index()
    overlay_source(index, "class Broken(:\n", path)
    assert "Course" in index.modules["myapp.models"].classes


# ------------------------------------------------------------------ #
# Rule groupings
# ------------------------------------------------------------------ #


def test_rule_groups_partition_every_code():
    """Each rule is either single-file or index-backed, never both or neither."""
    assert LOCAL_RULES | CROSS_FILE_RULES == ALL_RULES
    assert not LOCAL_RULES & CROSS_FILE_RULES


def test_cross_file_rules_never_fire_without_an_index(modelled):
    """The whole cross-file group is inert when there is nothing to resolve."""
    source = (modelled.root / "myapp" / "models.py").read_text()
    modelled.write(
        "myapp/serializers.py",
        """
        from rest_framework import serializers

        from myapp.models import Course


        class CourseSerializer(serializers.ModelSerializer):
            class Meta:
                model = Course
                fields = ["run_count"]

            def get_thing(self, instance):
                return instance.author.name
        """,
    )
    source = (modelled.root / "myapp" / "serializers.py").read_text()
    assert {v.rule for v in check_source(source)} & CROSS_FILE_RULES == set()
