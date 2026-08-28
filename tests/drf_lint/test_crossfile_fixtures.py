"""End-to-end checks over the on-disk ``fixtures/crossfile`` package.

The other cross-file tests build throwaway projects; this one runs against a
committed, readable example so the fixtures stay an accurate illustration of
what each rule catches.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from mitol.drf_lint.checker import ALL_RULES, LOCAL_RULES, CheckContext, check_file
from mitol.drf_lint.index import build_index, module_for_path

ROOT = Path(__file__).parent / "fixtures" / "crossfile"


@pytest.fixture(scope="module")
def index():
    """One index over the fixture package, shared by every test here."""
    return build_index(ROOT, use_cache=False)


def _check(index, relative: str, **kwargs):
    path = ROOT / relative
    module, _ = module_for_path(path, ROOT)
    return check_file(path, CheckContext(index=index, module=module, **kwargs))


def _rules(index, relative: str, **kwargs) -> list[str]:
    return [v.rule for v in _check(index, relative, **kwargs)]


def test_cross_file_fixture_rules(index):
    """Every cross-file rule is represented, in source order."""
    assert _rules(index, "myapp/serializers.py") == [
        "ORM005",  # source="run_count" on a declared field
        "ORM005",  # "run_count" in Meta.fields
        "ORM005",  # "summary" in Meta.fields, reached transitively
        "ORM004",  # compute_stats(instance)
        "ORM003",  # instance.run_count
        "ORM006",  # instance.author.name
        "ORM003",  # inherited instance.revision_count
        "ORM003",  # alias.summary
    ]


def test_prefetch_fixture_rules(index):
    """The required_prefetches rules, plus the re-querying ORM002 message."""
    assert _rules(index, "myapp/prefetch_serializers.py") == [
        "ORM008",  # no required_prefetches at all
        "ORM007",  # "run_list" field needs the runs prefetch
        "ORM007",  # instance.runs.all() needs the runs prefetch
        "ORM009",  # "author__books" can never be satisfied
        "ORM002",  # declared, but .filter() re-queries anyway
    ]


def test_clean_fixture_has_no_violations(index):
    """Every false-positive guard in one file."""
    assert _rules(index, "myapp/clean_serializers.py") == []


def test_no_index_means_no_cross_file_violations():
    """The fixtures owe every violation to the index."""
    assert check_file(ROOT / "myapp" / "serializers.py") == []


def test_local_rules_only_matches_the_pre_index_behaviour(index):
    """`--no-cross-file` leaves exactly the two original rules."""
    rules = _rules(
        index,
        "myapp/prefetch_serializers.py",
        enabled_rules=LOCAL_RULES,
        prefetch_aware=False,
    )
    assert set(rules) <= LOCAL_RULES


def test_every_rule_code_is_exercised_somewhere(index):
    """A guard against adding a code and forgetting to cover it here."""
    seen = set()
    for name in ("serializers.py", "prefetch_serializers.py", "clean_serializers.py"):
        seen.update(_rules(index, f"myapp/{name}"))
    assert ALL_RULES - seen == {"ORM001"}


def test_ambiguous_model_name_is_not_guessed(index):
    """A second app defines a querying member of the same name; strict wins."""
    unrelated = index.modules["otherapp.models"].classes["Unrelated"]
    assert unrelated.members["run_count"].queries
    assert "ORM003" in _rules(index, "myapp/serializers.py")
