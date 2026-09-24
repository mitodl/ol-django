"""Tests for the ol-benchmark command line."""

import json
from pathlib import Path

import pytest
import tomllib
from mitol.benchmark import config as cfg
from mitol.benchmark.cli import main


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Return an empty directory that is also the working directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestInit:
    """Each layer gets a scaffold that is itself a valid file of that layer."""

    @pytest.mark.parametrize(
        ("argv", "expected"),
        [
            (["init", "--project"], cfg.PROJECT_CONFIG_NAME),
            (["init", "--local"], cfg.LOCAL_CONFIG_NAME),
            (["init", "--benchmark", "Library List"], "library_list.toml"),
        ],
    )
    def test_writes_the_expected_file(self, workdir, argv, expected):
        """The default path follows the conventional benchmarks/ directory."""
        assert main(argv) == 0
        written = workdir / "benchmarks" / expected
        assert written.is_file()
        assert tomllib.loads(written.read_text())

    def test_the_scaffolded_pair_loads(self, workdir):
        """A fresh project + benchmark scaffold is a working configuration."""
        assert main(["init", "--project"]) == 0
        assert main(["init", "--benchmark", "demo"]) == 0
        config = cfg.load(workdir / "benchmarks" / "demo.toml")
        assert config.name == "demo"
        assert config.database.name == "bench_demo"
        assert [step.name for step in config.seed.steps] == [
            "user",
            "parents",
            "children",
        ]

    def test_an_existing_file_is_not_clobbered(self, workdir):  # noqa: ARG002
        """--force is required to overwrite someone's real configuration."""
        assert main(["init", "--project"]) == 0
        assert main(["init", "--project"]) == 1
        assert main(["init", "--project", "--force"]) == 0

    def test_a_layer_must_be_chosen(self, workdir):  # noqa: ARG002
        """There is no default layer; the three are not interchangeable."""
        with pytest.raises(SystemExit):
            main(["init"])


class TestValidateAndShow:
    """Checking a configuration without touching a database."""

    @pytest.fixture
    def scaffolded(self, workdir):
        """Return the path of a scaffolded project and benchmark pair."""
        main(["init", "--project"])
        main(["init", "--benchmark", "demo"])
        return workdir / "benchmarks" / "demo.toml"

    def test_validate_succeeds(self, scaffolded, capsys):
        """A valid configuration reports what it resolved to."""
        assert main(["validate", str(scaffolded)]) == 0
        assert "configuration is valid" in capsys.readouterr().out

    def test_validate_reports_a_configuration_error_distinctly(
        self, scaffolded, capsys
    ):
        """Exit code 2 separates 'you wrote it wrong' from 'it went wrong'."""
        assert main(["validate", str(scaffolded), "--knob", "nope=1"]) == 2  # noqa: PLR2004
        assert "unknown knob" in capsys.readouterr().err

    def test_show_prints_redacted_json(self, scaffolded, capsys):
        """The merged configuration is inspectable, without its passwords."""
        assert main(["show", str(scaffolded)]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["config"]["benchmark"]["name"] == "demo"
        assert "***:***@" in payload["config"]["database"]["admin_url"]

    def test_a_missing_file_is_a_configuration_error(self, workdir, capsys):  # noqa: ARG002
        """A path typo does not look like a harness failure."""
        assert main(["validate", "nope.toml"]) == 2  # noqa: PLR2004
        assert "no such benchmark configuration file" in capsys.readouterr().err


def test_the_repository_s_own_example_is_valid(capsys):
    """The committed worked example stays loadable as the schema evolves."""
    root = Path(__file__).resolve().parents[2]
    assert main(["validate", str(root / "benchmarks" / "testapp_libraries.toml")]) == 0
    assert "testapp-libraries" in capsys.readouterr().out
