"""Tests for the declarative seed engine, against the testapp's own models."""

import pytest
from libraries.models import Author, Book, Topic
from mitol.benchmark import config as cfg
from mitol.benchmark.seeding import SeedError, import_object, run_seed

pytestmark = pytest.mark.django_db


def make_config(**sections):
    """Return a configuration built directly, without going through files."""
    merged = {
        "benchmark": {"name": "seeding test"},
        "django": {"settings_module": "main.settings.test"},
        "database": {"name": "bench_seeding"},
        "target": {"path": "/api/libraries/"},
        **sections,
    }
    return cfg.from_merged(merged)


def test_counts_and_exports():
    """A step's rows are created and its scalars exported."""
    config = make_config(
        knobs={"rows": 4},
        seed={
            "step": [
                {
                    "name": "authors",
                    "factory": "libraries.factories:AuthorFactory",
                    "count": "$knob:rows",
                    "kwargs": {"name": "Author {index}"},
                }
            ],
            "export": {"author_id": "authors.pk"},
        },
    )
    outcome = run_seed(config)

    assert outcome.counts == {"authors": 4}
    assert Author.objects.count() == 4  # noqa: PLR2004
    assert set(Author.objects.values_list("name", flat=True)) == {
        f"Author {index}" for index in range(4)
    }
    assert outcome.export["author_id"] == Author.objects.earliest("id").pk


def test_cycle_spreads_rows_across_an_earlier_step():
    """Structural fan-out: books are distributed over authors, not stacked."""
    config = make_config(
        seed={
            "step": [
                {
                    "name": "authors",
                    "factory": "libraries.factories:AuthorFactory",
                    "count": 3,
                },
                {
                    "name": "books",
                    "factory": "libraries.factories:BookFactory",
                    "count": 9,
                    "kwargs": {"author": "$cycle:authors"},
                },
            ]
        }
    )
    run_seed(config)

    assert sorted(author.book_set.count() for author in Author.objects.all()) == [
        3,
        3,
        3,
    ]


def test_m2m_fan_out_is_applied_and_counted():
    """Join multiplicity is invisible in a response, so the seed reports it."""
    config = make_config(
        knobs={"per_book": 2},
        seed={
            "step": [
                {
                    "name": "topics",
                    "factory": "libraries.factories:TopicFactory",
                    "count": 6,
                },
                {
                    "name": "books",
                    "factory": "libraries.factories:BookFactory",
                    "count": 5,
                    "m2m": {
                        "topics": {
                            "source": "topics",
                            "per": "$knob:per_book",
                            "strategy": "cycle",
                        }
                    },
                },
            ]
        },
    )
    outcome = run_seed(config)

    assert outcome.m2m_pairs == {"books.topics": 10}
    assert all(book.topics.count() == 2 for book in Book.objects.all())  # noqa: PLR2004


def test_m2m_strategy_all_attaches_the_whole_pool():
    """``per = "all"`` is the way to say every row from the source step."""
    config = make_config(
        seed={
            "step": [
                {
                    "name": "topics",
                    "factory": "libraries.factories:TopicFactory",
                    "count": 4,
                },
                {
                    "name": "books",
                    "factory": "libraries.factories:BookFactory",
                    "count": 2,
                    "m2m": {"topics": {"source": "topics", "per": "all"}},
                },
            ]
        }
    )
    assert run_seed(config).m2m_pairs == {"books.topics": 8}


def test_model_step_needs_no_factory_boy():
    """A plain model step is enough where there is no factory."""
    config = make_config(
        seed={
            "step": [
                {
                    "name": "topics",
                    "model": "libraries.models:Topic",
                    "count": 3,
                    "kwargs": {"name": "Plain {index}"},
                }
            ]
        }
    )
    assert run_seed(config).counts == {"topics": 3}


def test_bulk_step_uses_bulk_create():
    """Large steps can skip per-row saves."""
    config = make_config(
        seed={
            "step": [
                {
                    "name": "topics",
                    "model": "libraries.models:Topic",
                    "count": 50,
                    "kwargs": {"name": "Bulk {index}"},
                    "bulk": True,
                }
            ]
        }
    )
    assert run_seed(config).counts == {"topics": 50}
    assert Topic.objects.filter(name__startswith="Bulk").count() == 50  # noqa: PLR2004


def test_hook_step_receives_the_context():
    """The escape hatch gets the knobs and everything built so far."""
    config = make_config(
        knobs={"topics": 3},
        seed={"step": [{"name": "hooked", "hook": "libraries.bench_hooks:topics_for"}]},
    )
    assert run_seed(config).counts == {"hooked": 3}
    assert Topic.objects.filter(name__startswith="hooked").count() == 3  # noqa: PLR2004


def test_hook_step_can_shape_fan_out_the_data_file_cannot():
    """A hook builds a skewed distribution where $cycle would be uniform."""
    config = make_config(
        knobs={"books": 20},
        seed={
            "step": [
                {
                    "name": "authors",
                    "factory": "libraries.factories:AuthorFactory",
                    "count": 5,
                },
                {"name": "books", "hook": "libraries.bench_hooks:skewed_books"},
            ]
        },
    )
    run_seed(config)
    per_author = sorted(
        (author.book_set.count() for author in Author.objects.all()), reverse=True
    )
    assert per_author[0] > per_author[-1], "the hook should skew, not spread"
    assert sum(per_author) == 20  # noqa: PLR2004


def test_sql_step_runs_statements():
    """Raw SQL is available for what the ORM will not express."""
    config = make_config(
        seed={"step": [{"name": "warm", "kind": "sql", "statements": ["SELECT 1"]}]}
    )
    assert run_seed(config).counts == {"warm": 0}


def test_floor_warning_when_the_seed_understates_production():
    """Falling short of a trace-derived floor is a warning, not an error."""
    config = make_config(
        seed={
            "step": [
                {
                    "name": "topics",
                    "factory": "libraries.factories:TopicFactory",
                    "count": 2,
                }
            ]
        },
        calibration={"floors": {"topics": 388}},
    )
    outcome = run_seed(config)
    assert outcome.warnings
    assert "below the production floor of 388" in outcome.warnings[0]


def test_a_failing_step_leaves_no_partial_dataset():
    """The whole seed is one transaction, so nothing half-built is measured."""
    config = make_config(
        seed={
            "step": [
                {
                    "name": "topics",
                    "factory": "libraries.factories:TopicFactory",
                    "count": 3,
                },
                {
                    "name": "broken",
                    "factory": "libraries.factories:BookFactory",
                    "count": 1,
                    "kwargs": {"author": "$ref:nonexistent"},
                },
            ]
        }
    )
    with pytest.raises(SeedError, match="no seed step named"):
        run_seed(config)
    assert Topic.objects.count() == 0


def test_export_must_be_a_scalar():
    """Exports travel to another process as JSON."""
    config = make_config(
        seed={
            "step": [
                {
                    "name": "books",
                    "factory": "libraries.factories:BookFactory",
                    "count": 1,
                }
            ],
            "export": {"author": "books.author"},
        }
    )
    with pytest.raises(SeedError, match="exports must be scalars"):
        run_seed(config)


class TestImportObject:
    """Dotted paths, in both spellings."""

    def test_colon_form(self):
        """``module:Attr`` is the unambiguous spelling."""
        assert import_object("libraries.models:Topic").__name__ == "Topic"

    def test_dotted_form(self):
        """``module.Attr`` is accepted because it is what people type."""
        assert import_object("libraries.models.Topic").__name__ == "Topic"

    @pytest.mark.parametrize(
        ("path", "message"),
        [
            ("nothing", "not a dotted path"),
            ("libraries.models:Nope", "has no attribute"),
            ("no_such_module:Thing", "cannot import"),
        ],
    )
    def test_failures_are_explained(self, path, message):
        """An unresolvable path says which half of it failed."""
        with pytest.raises(SeedError, match=message):
            import_object(path)
