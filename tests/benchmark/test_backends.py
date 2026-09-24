"""Tests for the execution backends, with the subprocess layer faked."""

import subprocess

import pytest
from mitol.benchmark import config as cfg
from mitol.benchmark.backends import BackendError, get_backend


@pytest.fixture
def calls(monkeypatch):
    """Return a log of every argv the backends run, answering with success."""
    recorded = []

    def fake_run(argv, **kwargs):
        recorded.append(
            {"argv": list(argv), "env": kwargs.get("env"), "cwd": kwargs.get("cwd")}
        )
        return subprocess.CompletedProcess(argv, 0, stdout="pod-1", stderr="")

    monkeypatch.setattr("mitol.benchmark.backends.subprocess.run", fake_run)
    return recorded


def make_config(backend):
    """Return a configuration using the given backend options."""
    return cfg.from_merged(
        {
            "benchmark": {"name": "backend test"},
            "django": {"settings_module": "x"},
            "database": {"name": "bench_backend"},
            "target": {"path": "/x/"},
            "backend": backend,
        }
    )


def test_unknown_backend_kind_is_refused():
    """A typo in the local config fails before anything is dropped."""
    with pytest.raises(BackendError, match=r"unknown \[backend\].kind"):
        get_backend(make_config({"kind": "kubernetes"}))


class TestLocal:
    """Subprocesses of the harness's own environment."""

    def test_step_command_uses_this_interpreter(self):
        """The interpreter running the harness can already import the steps."""
        backend = get_backend(make_config({"kind": "local"}))
        command = backend.step_command("seed")
        assert command[1:] == ["-m", "mitol.benchmark", "step", "seed"]
        assert command[0].endswith("python") or "python" in command[0]

    def test_exec_passes_the_environment_and_working_directory(self, calls):
        """A step needs both to find the application."""
        backend = get_backend(make_config({"kind": "local"}))
        backend.exec(["echo", "hi"], {"OL_BENCHMARK_LABEL": "branch"})
        assert calls[0]["argv"] == ["echo", "hi"]
        assert calls[0]["env"]["OL_BENCHMARK_LABEL"] == "branch"
        assert calls[0]["cwd"]


class TestCompose:
    """A fresh container per step, against an already-up stack."""

    def test_exec_builds_a_throwaway_run(self, calls):
        """--rm --no-deps -T: nothing else running, nothing left behind."""
        backend = get_backend(make_config({"kind": "compose", "service": "web"}))
        backend.exec(["python", "-V"], {"DEBUG": "False"})
        argv = calls[0]["argv"]
        assert argv[:6] == ["docker", "compose", "run", "--rm", "--no-deps", "-T"]
        assert "-e" in argv
        assert "DEBUG=False" in argv
        assert argv[-2:] == ["python", "-V"]
        assert "web" in argv

    def test_admin_sql_runs_in_the_database_service(self, calls):
        """Administrative SQL does not need a client on the host."""
        backend = get_backend(make_config({"kind": "compose", "db_service": "pg"}))
        backend.admin_sql(["DROP DATABASE IF EXISTS x"])
        argv = calls[0]["argv"]
        assert argv[:4] == ["docker", "compose", "exec", "-T"]
        assert "pg" in argv
        assert "DROP DATABASE IF EXISTS x" in argv

    def test_default_python_is_the_container_s(self):
        """The host's interpreter path means nothing inside an image."""
        backend = get_backend(make_config({"kind": "compose"}))
        assert backend.step_command("bench")[0] == "python"


class TestKubernetes:
    """kubectl exec, with the context pinned."""

    def options(self, **extra):
        """Return valid k8s backend options."""
        return {
            "kind": "k8s",
            "context": "k3d-localdev",
            "namespace": "myapp",
            "selector": "app=myapp-web",
            **extra,
        }

    def test_context_is_required(self):
        """This harness runs DROP DATABASE; it will not guess a cluster."""
        backend = get_backend(make_config({"kind": "k8s", "selector": "app=x"}))
        with pytest.raises(BackendError, match="will not inherit"):
            backend.describe()

    def test_every_command_pins_the_context_and_namespace(self, calls):
        """Never the developer's ambient kubectl context."""
        backend = get_backend(make_config(self.options()))
        backend.exec(["python", "-V"])
        for call in calls:
            argv = call["argv"]
            assert argv[0] == "kubectl"
            assert argv[1:3] == ["--context", "k3d-localdev"]
            assert argv[3:5] == ["--namespace", "myapp"]

    def test_the_pod_is_resolved_from_the_selector(self, calls):
        """A running pod is looked up rather than named in the config."""
        backend = get_backend(make_config(self.options(container="web")))
        backend.exec(["python", "-V"], {"DEBUG": "False"})
        lookup, execute = calls
        assert "--selector" in lookup["argv"]
        assert "app=myapp-web" in lookup["argv"]
        assert "pod-1" in execute["argv"]
        assert execute["argv"][-4:] == ["env", "DEBUG=False", "python", "-V"]

    def test_admin_sql_can_target_a_separate_database_pod(self, calls):
        """The scratch DSN is often routable only from inside the cluster."""
        backend = get_backend(make_config(self.options(db_selector="app=postgres")))
        backend.admin_sql(["CREATE DATABASE bench_x"])
        lookup, execute = calls
        assert "app=postgres" in lookup["argv"]
        assert "psql" in execute["argv"]
        assert "CREATE DATABASE bench_x" in execute["argv"]

    def test_wait_settled_is_configurable(self, monkeypatch):
        """Tilt's push-sync needs a moment; a bind mount needs none."""
        slept = []
        monkeypatch.setattr("mitol.benchmark.backends.k8s.time.sleep", slept.append)
        get_backend(make_config(self.options(settle_seconds=2))).wait_settled()
        assert slept == [2.0]
