"""Tests for the A/B orchestration, with the backend faked."""

import json
import subprocess
from pathlib import Path

import pytest
from mitol.benchmark import config as cfg
from mitol.benchmark.backends import Backend
from mitol.benchmark.runner import BENCH_PREFIX, ArmResult, Runner, RunnerError


class FakeBackend(Backend):
    """Record what the runner asks for, and answer from a script."""

    name = "fake"

    def __init__(self, config):
        """Start with an empty log and no scripted responses."""
        super().__init__(config)
        self.commands = []
        self.sql = []
        self.stdout_for = {}
        self.files = {}
        self.settled = 0

    def describe(self):
        """Name this fake, for the run log."""
        return "a fake backend"

    def exec(self, argv, env=None, *, check=True):  # noqa: ARG002
        """Record the call and reply with whatever was scripted for the step."""
        self.commands.append({"argv": list(argv), "env": dict(env or {})})
        return subprocess.CompletedProcess(
            argv, 0, stdout=self.stdout_for.get(argv[-1], ""), stderr=""
        )

    def admin_sql(self, statements):
        """Record administrative SQL instead of running it."""
        self.sql.extend(statements)

    def read_file(self, path):
        """Return whatever this fake environment claims the file holds."""
        return self.files.get(path, b"")

    def wait_settled(self):
        """Count how often the runner waited for the environment."""
        self.settled += 1


@pytest.fixture
def config():
    """Return a configuration with no seed, aimed at a fake backend."""
    return cfg.from_merged(
        {
            "benchmark": {"name": "runner test"},
            "django": {"settings_module": "main.settings.bench"},
            "database": {"name": "bench_runner"},
            "target": {"path": "/x/"},
            "knobs": {"rows": 3},
        }
    )


@pytest.fixture
def runner(config, tmp_path, monkeypatch):
    """Return a runner using the fake backend and a temp output directory."""
    made = Runner(config, base_ref="main", out_dir=tmp_path / "out")
    monkeypatch.setattr(made, "backend", FakeBackend(config))
    made.log = lambda _message: None
    return made


class TestStepProtocol:
    """Results travel as prefixed JSON lines, never through a shared disk."""

    def test_a_step_receives_the_whole_configuration(self, runner):
        """A container has no access to the files the host merged."""
        runner.backend.stdout_for["bench"] = BENCH_PREFIX + '{"total_ms_min": 1}'
        runner.run_step("bench", BENCH_PREFIX, {"export": {}}, "branch")

        env = runner.backend.commands[0]["env"]
        rebuilt = cfg.from_dict(json.loads(env[cfg.CONFIG_ENV_VAR]))
        assert rebuilt.name == "runner test"
        assert rebuilt.knobs == {"rows": 3}
        assert env[cfg.LABEL_ENV_VAR] == "branch"
        assert env["DATABASE_URL"] == runner.config.database.url
        assert env["DEBUG"] == "False"

    def test_the_payload_is_parsed_out_of_noisy_output(self, runner):
        """Applications log on stdout; the line protocol survives that."""
        runner.backend.stdout_for["bench"] = (
            "INFO some application chatter\n"
            + BENCH_PREFIX
            + '{"total_ms_min": 4}\n'
            + "INFO more chatter\n"
        )
        assert runner.run_step("bench", BENCH_PREFIX)["total_ms_min"] == 4  # noqa: PLR2004

    def test_a_missing_payload_reports_what_the_step_printed(self, runner):
        """A step that died needs its output surfaced, not swallowed."""
        runner.backend.stdout_for["bench"] = "Traceback: everything went wrong"
        with pytest.raises(RunnerError, match="everything went wrong"):
            runner.run_step("bench", BENCH_PREFIX)


class TestGuards:
    """What has to be true before anything is dropped or measured."""

    def test_a_dirty_tree_is_refused(self, runner, monkeypatch):
        """Otherwise the two arms are not the two refs you think."""
        monkeypatch.setattr(
            "mitol.benchmark.runner.git",
            lambda *a, **k: " M some/file.py",  # noqa: ARG005
        )
        with pytest.raises(RunnerError, match="uncommitted changes"):
            runner.check_working_tree()

    def test_a_committed_local_config_is_refused(self, runner, monkeypatch):
        """It holds one developer's cluster and connection strings."""
        runner.config.raw["_layers"] = {"local": "benchmarks/benchmark.local.toml"}
        monkeypatch.setattr(
            "mitol.benchmark.runner.git",
            lambda *a, **k: "benchmarks/benchmark.local.toml",  # noqa: ARG005
        )
        with pytest.raises(RunnerError, match="tracked by git"):
            runner.check_local_config_untracked()

    def test_no_local_config_is_fine(self, runner):
        """The layer is optional, so its absence cannot fail the check."""
        runner.check_local_config_untracked()

    def test_the_scratch_database_is_dropped_then_created(self, runner):
        """Seeding into leftovers from a previous run is not an A/B."""
        runner.recreate_database()
        assert runner.backend.sql == [
            'DROP DATABASE IF EXISTS "bench_runner"',
            'CREATE DATABASE "bench_runner"',
        ]


class TestRefVerification:
    """Trusting a git switch reached the application is how arms get mixed."""

    def test_probes_are_files_the_refs_genuinely_differ_on(self, runner, monkeypatch):
        """A probe that is identical in both refs verifies nothing."""
        monkeypatch.setattr(
            "mitol.benchmark.runner.git",
            lambda *a, **k: "src/benchmark/mitol/benchmark/cli.py\nnot/a/real/file.py",  # noqa: ARG005
        )
        assert runner.probe_files("main", "topic") == [
            "src/benchmark/mitol/benchmark/cli.py"
        ]

    def test_matching_content_settles_immediately(self, runner):
        """Under a bind mount there is nothing to wait for."""
        probe = "src/benchmark/mitol/benchmark/cli.py"
        runner.backend.files[probe] = Path(runner.repo_root, probe).read_bytes()
        runner.sync_ref("main", [probe])
        assert runner.backend.settled == 1

    def test_stale_content_times_out_rather_than_measuring_it(
        self, runner, monkeypatch
    ):
        """Measuring a pod still running the other ref is the worst outcome."""
        monkeypatch.setenv("OL_BENCHMARK_SYNC_TIMEOUT", "0")
        monkeypatch.setattr("mitol.benchmark.runner.time.sleep", lambda _s: None)
        probe = "src/benchmark/mitol/benchmark/cli.py"
        runner.backend.files[probe] = b"not what the host has"
        with pytest.raises(RunnerError, match="timed out waiting"):
            runner.sync_ref("main", [probe])

    def test_no_probe_says_so_out_loud(self, runner):
        """Silently passing an unverifiable check is worse than not checking."""
        said = []
        runner.log = said.append
        runner.sync_ref("main", [])
        assert "cannot verify" in said[0]


def test_outputs_are_all_written(runner, tmp_path):
    """Every artifact a reviewer or an agent might read."""
    base = {
        "total_ms_min": 10.0,
        "total_ms_median": 12.0,
        "total_ms_max": 20.0,
        "queries": 3,
        "response_bytes": 100,
        "count": 5,
        "results": 5,
        "ref": "aaa",
    }
    branch = {**base, "total_ms_min": 4.0, "total_ms_median": 5.0, "ref": "bbb"}
    arms = {
        "base": _arm("base", "aaa", base),
        "branch": _arm("branch", "bbb", branch),
    }
    comparison = runner.write_outputs({"counts": {"x": 1}}, arms)

    written = {path.name for path in (tmp_path / "out").iterdir()}
    assert written == {
        "config.resolved.json",
        "seed.json",
        "base.json",
        "branch.json",
        "trace-base.json",
        "trace-branch.json",
        "agg-base.json",
        "agg-branch.json",
        "comparison.json",
        "report.md",
    }
    assert comparison["verdict"] == "ok"
    assert (tmp_path / "out" / "report.md").read_text().startswith("# Benchmark:")


def _arm(label, ref, bench):
    return ArmResult(
        label=label, ref=ref, bench=bench, trace={"repeats": 1, "runs": []}
    )
