"""Tests for the three-layer configuration loader."""

import pytest
from mitol.benchmark import config as cfg


def test_layers_merge_with_local_winning(layers, write_config):
    """The local layer overrides the project layer; benchmark data survives."""
    write_config(
        layers,
        cfg.LOCAL_CONFIG_NAME,
        """
        [backend]
        kind = "compose"
        service = "web"

        [database]
        admin_url = "postgres://u:p@elsewhere:5432/postgres"
        """,
    )
    config = cfg.load(layers / "example.toml")

    assert config.backend.kind == "compose"
    assert config.backend.options["service"] == "web"
    assert config.database.admin_url == "postgres://u:p@elsewhere:5432/postgres"
    assert config.django.settings_module == "main.settings.bench"
    assert config.name == "example bench"


def test_defaults_underlie_the_benchmark_section(layers, example_config, write_config):
    """[defaults.measure] is a floor that a benchmark's [measure] overrides."""
    assert example_config.measure.iterations == 4  # noqa: PLR2004

    write_config(
        layers,
        "example.toml",
        (layers / "example.toml").read_text() + "\n[measure]\niterations = 9\n",
    )
    assert cfg.load(layers / "example.toml").measure.iterations == 9  # noqa: PLR2004


@pytest.mark.parametrize(
    ("section", "expected_hint"),
    [
        ("[django]\nsettings_module = 'x'", cfg.PROJECT_CONFIG_NAME),
        ("[backend]\nkind = 'local'", cfg.LOCAL_CONFIG_NAME),
    ],
)
def test_benchmark_file_rejects_another_layers_section(
    layers, write_config, section, expected_hint
):
    """A misplaced section is refused, with a pointer to the right layer."""
    write_config(
        layers, "example.toml", (layers / "example.toml").read_text() + "\n" + section
    )
    with pytest.raises(cfg.ConfigError) as caught:
        cfg.load(layers / "example.toml")
    assert expected_hint in str(caught.value)


def test_project_file_rejects_benchmark_specific_sections(layers, write_config):
    """A project-wide file cannot describe one particular benchmark."""
    write_config(
        layers,
        "benchmark.toml",
        (layers / "benchmark.toml").read_text() + "\n[target]\npath = '/x/'\n",
    )
    with pytest.raises(cfg.ConfigError, match=r"\[target\] does not belong"):
        cfg.load(layers / "example.toml")


def test_local_layer_is_optional(example_config):
    """With no local file the defaults apply, so a fresh clone still runs."""
    assert example_config.backend.kind == "local"


class TestEnvironmentInterpolation:
    """``${VAR}`` and ``${VAR:-default}`` in connection strings."""

    def test_default_is_used_when_unset(self, example_config):
        """An unset variable falls back to its declared default."""
        assert example_config.database.url.endswith("/bench_example_bench")
        assert "localhost:5432" in example_config.database.url

    def test_environment_wins(self, layers):
        """A set variable replaces the default."""
        config = cfg.load(
            layers / "example.toml",
            environ={"BENCH_TEST_URL": "postgres://u:p@db:6000/{name}"},
        )
        assert config.database.url == "postgres://u:p@db:6000/bench_example_bench"

    def test_default_may_contain_braces(self, example_config):
        """The {name} placeholder inside a default survives expansion."""
        # A regex-based expander gets this wrong in both directions; the
        # loader counts braces instead.
        assert "{name}" not in example_config.database.url

    def test_unset_without_default_names_the_variable(self, layers, write_config):
        """A missing variable is an error, not an empty string."""
        write_config(
            layers,
            "benchmark.toml",
            """
            [django]
            settings_module = "x"
            [database]
            admin_url = "${BENCH_NOT_SET_ANYWHERE}"
            """,
        )
        with pytest.raises(cfg.ConfigError, match="BENCH_NOT_SET_ANYWHERE"):
            cfg.load(layers / "example.toml", environ={})


class TestKnobs:
    """Shape knobs, and the two ways of overriding them."""

    def test_environment_override_is_coerced(self, layers):
        """BENCH_<KNOB> overrides, keeping the declared type."""
        config = cfg.load(layers / "example.toml", environ={"BENCH_ROWS": "42"})
        assert config.knobs["rows"] == 42  # noqa: PLR2004

    def test_unrelated_bench_variables_are_ignored(self, layers):
        """The BENCH_ namespace is shared with the harness's own variables."""
        config = cfg.load(
            layers / "example.toml", environ={"BENCH_ADMIN_DATABASE_URL": "x"}
        )
        assert set(config.knobs) == {"rows", "blob_bytes"}

    def test_explicit_override_of_an_unknown_knob_is_an_error(self, layers):
        """A mistyped --knob would otherwise silently measure another shape."""
        with pytest.raises(cfg.ConfigError, match="unknown knob 'rowz'"):
            cfg.load(layers / "example.toml", knob_overrides={"rowz": "10"})

    def test_explicit_override_beats_the_environment(self, layers):
        """CLI flags are the highest-precedence layer."""
        config = cfg.load(
            layers / "example.toml",
            knob_overrides={"rows": "7"},
            environ={"BENCH_ROWS": "42"},
        )
        assert config.knobs["rows"] == 7  # noqa: PLR2004


class TestDatabaseGuards:
    """The scratch database is dropped, so its name is checked."""

    def test_name_is_derived_from_the_benchmark(self, example_config):
        """A derived name always carries the required prefix."""
        assert example_config.database.name == "bench_example_bench"

    def test_a_name_without_the_prefix_is_refused(self, layers, write_config):
        """Anything not obviously scratch is rejected before anything runs."""
        write_config(
            layers,
            cfg.LOCAL_CONFIG_NAME,
            """
            [database]
            name = "mitxonline"
            """,
        )
        with pytest.raises(cfg.ConfigError, match="dropped and recreated"):
            cfg.load(layers / "example.toml")

    def test_admin_url_may_not_be_the_scratch_database(self, layers, write_config):
        """DROP DATABASE cannot run from inside the database being dropped."""
        write_config(
            layers,
            cfg.LOCAL_CONFIG_NAME,
            """
            [database]
            url_template = "postgres://u:p@localhost:5432/{name}"
            admin_url = "postgres://u:p@localhost:5432/bench_fixed"
            name = "bench_fixed"
            """,
        )
        with pytest.raises(cfg.ConfigError, match="admin_url points at"):
            cfg.load(layers / "example.toml")


class TestTargetValidation:
    """[target] has to name exactly one thing to request."""

    @pytest.mark.parametrize(
        "target",
        [
            "[target]\nreverse = 'x'\npath = '/y/'",
            "[target]\nmethod = 'get'",
        ],
    )
    def test_exactly_one_of_reverse_or_path(self, layers, write_config, target):
        """Neither both nor neither is a valid request."""
        body = (layers / "example.toml").read_text().split("[target]")[0]
        write_config(layers, "example.toml", body + target)
        with pytest.raises(cfg.ConfigError, match="exactly one of"):
            cfg.load(layers / "example.toml")


def test_seed_step_kinds_are_validated(layers, write_config):
    """A step that declares a kind must supply what that kind needs."""
    write_config(
        layers,
        "example.toml",
        """
        [benchmark]
        name = "x"
        [[seed.step]]
        name = "orphan"
        kind = "hook"
        [target]
        path = "/x/"
        """,
    )
    with pytest.raises(cfg.ConfigError, match="sets no 'hook'"):
        cfg.load(layers / "example.toml")


def test_duplicate_step_names_are_refused(layers, write_config):
    """Step names address objects later, so they have to be unique."""
    write_config(
        layers,
        "example.toml",
        """
        [benchmark]
        name = "x"
        [[seed.step]]
        name = "a"
        model = "libraries.models:Topic"
        [[seed.step]]
        name = "a"
        model = "libraries.models:Author"
        [target]
        path = "/x/"
        """,
    )
    with pytest.raises(cfg.ConfigError, match="declared twice"):
        cfg.load(layers / "example.toml")


def test_round_trips_through_a_dict(example_config):
    """A step process rebuilds the configuration from JSON, not from files."""
    rebuilt = cfg.from_dict(example_config.as_dict())
    assert rebuilt.name == example_config.name
    assert rebuilt.database.url == example_config.database.url
    assert rebuilt.knobs == example_config.knobs
    assert [step.name for step in rebuilt.seed.steps] == ["things"]


def test_redaction_masks_credentials(example_config):
    """Resolved configuration is written to disk, so passwords come out."""
    redacted = example_config.redacted_dict()
    assert "***:***@" in redacted["config"]["database"]["admin_url"]
    assert ":p@" not in redacted["config"]["database"]["admin_url"]
