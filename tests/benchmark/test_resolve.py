"""Tests for ``$token`` resolution."""

import random

import pytest
from mitol.benchmark.resolve import (
    ResolutionContext,
    ResolutionError,
    blob_text,
    resolve,
    resolve_count,
)


@pytest.fixture
def context():
    """Return a context with knobs, exports and two steps of objects."""
    return ResolutionContext(
        knobs={"rows": 5, "blob_bytes": 200},
        ids={"user_id": 17},
        objects={"authors": ["a", "b", "c"], "topics": list(range(10))},
        rng=random.Random(1234),  # noqa: S311
    )


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("$knob:rows", 5),
        ("$ids:user_id", 17),
        ("$ref:authors", "a"),
        ("$ref:authors[2]", "c"),
        ("$index", 0),
        ("$all:authors", ["a", "b", "c"]),
        ("$$literal", "$literal"),
        ("plain", "plain"),
    ],
)
def test_tokens(context, token, expected):
    """Each token resolves to the thing it names."""
    assert resolve(token, context) == expected


def test_cycle_follows_the_index(context):
    """$cycle spreads rows across an earlier step instead of reusing one."""
    assert [resolve("$cycle:authors", context.at(i)) for i in range(5)] == [
        "a",
        "b",
        "c",
        "a",
        "b",
    ]


def test_sample_is_deterministic(context):
    """The seeded RNG makes a sampled shape reproducible across arms."""
    first = resolve("$sample:topics:4", context)
    again = resolve(
        "$sample:topics:4",
        ResolutionContext(
            objects=context.objects,
            rng=random.Random(1234),  # noqa: S311
        ),
    )
    assert first == again
    assert len(first) == 4  # noqa: PLR2004


def test_blob_sizes_from_a_knob_or_a_literal(context):
    """$blob accepts a knob name or a byte count."""
    assert len(resolve("$blob:blob_bytes", context)) == 200  # noqa: PLR2004
    assert len(resolve("$blob:32", context)) == 32  # noqa: PLR2004
    assert blob_text(0) == ""


def test_format_interpolation(context):
    """Plain strings still get index and knob interpolation."""
    assert resolve("Book {index}", context.at(3)) == "Book 3"
    assert resolve("{rows} rows", context) == "5 rows"


def test_recursion_into_containers(context):
    """Nested structures are resolved all the way down."""
    resolved = resolve(
        {"a": ["$knob:rows", {"b": "$ids:user_id"}]},
        context,
    )
    assert resolved == {"a": [5, {"b": 17}]}


@pytest.mark.parametrize(
    ("token", "message"),
    [
        ("$knob:missing", "unknown knob"),
        ("$ids:missing", "was not exported by the seed"),
        ("$ref:missing", "no seed step named"),
        ("$ref:authors[9]", "created only 3"),
        ("$nonsense:x", "unknown token type"),
        ("$knob:", "expected"),
    ],
)
def test_errors_name_what_went_wrong(context, token, message):
    """A bad reference says what it was and what was available."""
    with pytest.raises(ResolutionError, match=message):
        resolve(token, context)


def test_resolve_count_rejects_a_negative(context):
    """A count has to be a non-negative integer."""
    with pytest.raises(ResolutionError, match="negative"):
        resolve_count(-1, context)
