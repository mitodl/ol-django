"""
Tests for the ol-benchmark command line.

These assert on **exit codes**, not on a return value, because the exit code
is the actual contract: the backends run every step as a subprocess and
``run_process(check=True)`` turns any non-zero exit into a ``BackendError``.
"""

import json
from pathlib import Path

import pytest
import tomllib
from click.testing import CliRunner
from mitol.benchmark import config as cfg
from mitol.benchmark.cli import cli

USAGE_ERROR = 2
CONFIG_ERROR = 2


@pytest.fixture
def run():
    """Return a function invoking the CLI and returning click's Result."""
    # catch_exceptions=False so an unexpected failure surfaces as a traceback
    # rather than as an indistinguishable exit_code of 1.
    runner = CliRunner()

    def _run(*args, expect_failure=False):
        return runner.invoke(cli, list(args), catch_exceptions=expect_failure)

    return _run


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Return an empty directory that is also the working directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestInit:
    """Each layer gets a scaffold that is itself a valid file of that layer."""

    @pytest.mark.parametrize(
        ("args", "expected"),
        [
            (["init", "--project"], cfg.PROJECT_CONFIG_NAME),
            (["init", "--local"], cfg.LOCAL_CONFIG_NAME),
            (["init", "--benchmark", "Library List"], "library_list.toml"),
        ],
    )
    def test_writes_the_expected_file(self, workdir, run, args, expected):
        """The default path follows the conventional benchmarks/ directory."""
        assert run(*args).exit_code == 0
        written = workdir / "benchmarks" / expected
        assert written.is_file()
        assert tomllib.loads(written.read_text())

    def test_the_scaffolded_pair_loads(self, workdir, run):
        """A fresh project + benchmark scaffold is a working configuration."""
        assert run("init", "--project").exit_code == 0
        assert run("init", "--benchmark", "demo").exit_code == 0
        config = cfg.load(workdir / "benchmarks" / "demo.toml")
        assert config.name == "demo"
        assert config.database.name == "bench_demo"
        assert [step.name for step in config.seed.steps] == [
            "user",
            "parents",
            "children",
        ]

    @pytest.mark.usefixtures("workdir")
    def test_an_existing_file_is_not_clobbered(self, run):
        """--force is required to overwrite someone's real configuration."""
        assert run("init", "--project").exit_code == 0
        refused = run("init", "--project")
        assert refused.exit_code == 1
        assert "already exists" in refused.stderr
        assert run("init", "--project", "--force").exit_code == 0

    @pytest.mark.usefixtures("workdir")
    def test_a_layer_must_be_chosen(self, run):
        """There is no default layer; the three are not interchangeable."""
        result = run("init")
        assert result.exit_code == USAGE_ERROR
        assert "exactly 1" in result.stderr

    def test_two_layers_are_refused(self, workdir, run):
        """Nor are they combinable: one invocation writes one file."""
        result = run("init", "--project", "--local")
        assert result.exit_code == USAGE_ERROR
        assert not (workdir / "benchmarks").exists()

    @pytest.mark.usefixtures("workdir")
    def test_the_local_layer_warns_it_must_be_gitignored(self, run):
        """It holds the developer's own connection strings."""
        assert ".gitignore" in run("init", "--local").stdout


class TestValidateAndShow:
    """Checking a configuration without touching a database."""

    @pytest.fixture
    def scaffolded(self, workdir, run):
        """Return the path of a scaffolded project and benchmark pair."""
        run("init", "--project")
        run("init", "--benchmark", "demo")
        return str(workdir / "benchmarks" / "demo.toml")

    def test_validate_succeeds(self, scaffolded, run):
        """A valid configuration reports what it resolved to."""
        result = run("validate", scaffolded)
        assert result.exit_code == 0
        assert "configuration is valid" in result.stdout

    def test_validate_reports_a_configuration_error_distinctly(self, scaffolded, run):
        """Exit code 2 separates 'you wrote it wrong' from 'it went wrong'."""
        result = run("validate", scaffolded, "--knob", "nope=1")
        assert result.exit_code == CONFIG_ERROR
        assert "unknown knob" in result.stderr

    def test_a_malformed_knob_is_a_configuration_error(self, scaffolded, run):
        """--knob takes name=value; anything else is not a silent no-op."""
        result = run("validate", scaffolded, "--knob", "rows")
        assert result.exit_code == CONFIG_ERROR
        assert "name=value" in result.stderr

    def test_knobs_are_repeatable(self, scaffolded, run):
        """A shape sweep varies more than one dimension at a time."""
        result = run(
            "validate", scaffolded, "--knob", "rows=7", "--knob", "blob_bytes=11"
        )
        assert result.exit_code == 0
        assert '"rows": 7' in result.stdout
        assert '"blob_bytes": 11' in result.stdout

    def test_show_prints_redacted_json(self, scaffolded, run):
        """The merged configuration is inspectable, without its passwords."""
        result = run("show", scaffolded)
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["config"]["benchmark"]["name"] == "demo"
        assert "***:***@" in payload["config"]["database"]["admin_url"]

    @pytest.mark.usefixtures("workdir")
    def test_a_missing_file_is_a_configuration_error(self, run):
        """A path typo gets the domain error, not a generic usage one."""
        result = run("validate", "nope.toml")
        assert result.exit_code == CONFIG_ERROR
        assert "no such benchmark configuration file" in result.stderr


class TestGroup:
    """What the group itself owns."""

    def test_version(self, run):
        """The console script reports the package version."""
        from mitol.benchmark import __version__  # noqa: PLC0415

        result = run("--version")
        assert result.exit_code == 0
        assert __version__ in result.stdout

    @pytest.mark.parametrize("args", [["-h"], ["init", "-h"], ["run", "-h"]])
    def test_help_exits_cleanly(self, run, args):
        """The group's error translation must not swallow click's own exits."""
        result = run(*args)
        assert result.exit_code == 0
        assert "Usage:" in result.stdout

    def test_an_unknown_subcommand_is_a_usage_error(self, run):
        """A typo'd command name is not a silent success."""
        assert run("nonsense").exit_code == USAGE_ERROR

    def test_step_rejects_an_unknown_step(self, run):
        """The step names are the harness's own protocol, not free text."""
        result = run("step", "nonsense")
        assert result.exit_code == USAGE_ERROR
        assert "nonsense" in result.stderr


def test_the_repository_s_own_example_is_valid(run):
    """The committed worked example stays loadable as the schema evolves."""
    root = Path(__file__).resolve().parents[2]
    result = run("validate", str(root / "benchmarks" / "testapp_libraries.toml"))
    assert result.exit_code == 0
    assert "testapp-libraries" in result.stdout


class TestBaseline:
    """Distilling production traces through the command line."""

    @pytest.fixture
    def scaffolded(self, workdir, run):
        """Return a benchmark file that declares one classifier."""
        run("init", "--project")
        run("init", "--benchmark", "demo")
        path = workdir / "benchmarks" / "demo.toml"
        path.write_text(
            path.read_text()
            + '\n[[trace.classify]]\nlabel = "users"\npattern = "FROM users"\n'
        )
        return path

    @pytest.fixture
    def traces(self, workdir):
        """Return several exported traces, each a distinct request."""
        directory = workdir / "traces"
        directory.mkdir()
        paths = []
        for index in range(3):
            path = directory / f"{index}.json"
            path.write_text(
                json.dumps(
                    {
                        "resourceSpans": [
                            {
                                "scopeSpans": [
                                    {
                                        "spans": [
                                            {
                                                "name": "SELECT",
                                                "traceId": f"trace{index}",
                                                "startTimeUnixNano": "0",
                                                "endTimeUnixNano": str(
                                                    (index + 1) * 1_000_000
                                                ),
                                                "attributes": [
                                                    {
                                                        "key": "db.statement",
                                                        "value": {
                                                            "stringValue": (
                                                                "SELECT * FROM "
                                                                "users WHERE "
                                                                "email = "
                                                                "'alice@example.com'"
                                                            )
                                                        },
                                                    }
                                                ],
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                )
            )
            paths.append(str(path))
        return paths

    def test_an_arbitrary_number_of_traces_is_accepted(
        self, workdir, run, scaffolded, traces
    ):
        """Traces are variadic so a shell glob is the natural way to pass them."""
        result = run("baseline", str(scaffolded), *traces)
        assert result.exit_code == 0
        written = workdir / "benchmarks" / "demo.baseline.json"
        payload = json.loads(written.read_text())
        assert payload["requests"] == 3  # noqa: PLR2004
        assert payload["trace_ids"] == ["trace0", "trace1", "trace2"]

    def test_the_written_file_carries_no_production_sql(
        self, workdir, run, scaffolded, traces
    ):
        """The point of the whole command."""
        assert run("baseline", str(scaffolded), *traces).exit_code == 0
        written = (workdir / "benchmarks" / "demo.baseline.json").read_text()
        assert "alice@example.com" not in written
        assert "users" in written  # the label survived, so this is not vacuous

    def test_stdout_writes_nothing(self, workdir, run, scaffolded, traces):
        """For when you want to look before letting it near the repo."""
        result = run("baseline", str(scaffolded), "--stdout", *traces)
        assert result.exit_code == 0
        assert json.loads(result.stdout)["requests"] == 3  # noqa: PLR2004
        assert not (workdir / "benchmarks" / "demo.baseline.json").exists()

    def test_out_overrides_the_destination(self, workdir, run, scaffolded, traces):
        """A team may keep baselines somewhere other than beside the config."""
        target = workdir / "elsewhere" / "prod.json"
        assert (
            run("baseline", str(scaffolded), "--out", str(target), *traces).exit_code
            == 0
        )
        assert json.loads(target.read_text())["requests"] == 3  # noqa: PLR2004

    def test_at_least_one_trace_is_required(self, run, scaffolded):
        """There is nothing to distil from no traces."""
        assert run("baseline", str(scaffolded)).exit_code == USAGE_ERROR

    def test_a_benchmark_with_no_classifiers_is_refused(self, workdir, run, traces):
        """Every query would be 'unclassified' and the baseline would be mute."""
        run("init", "--project")
        bare = workdir / "benchmarks" / "bare.toml"
        bare.write_text('[benchmark]\nname = "bare"\n\n[target]\npath = "/x/"\n')
        result = run("baseline", str(bare), *traces)
        assert result.exit_code == CONFIG_ERROR
        assert "no [[trace.classify]] rules" in result.stderr

    def test_unmatched_queries_warn_but_succeed(self, workdir, run, traces):
        """Labelled 'unclassified' rather than failing the command."""
        run("init", "--project")
        run("init", "--benchmark", "other")
        path = workdir / "benchmarks" / "other.toml"
        path.write_text(
            path.read_text()
            + '\n[[trace.classify]]\nlabel = "nope"\npattern = "FROM nothing"\n'
        )
        result = run("baseline", str(path), "--stdout", *traces)
        assert result.exit_code == 0
        assert "unclassified" in result.stderr
        assert "alice@example.com" not in result.stdout
