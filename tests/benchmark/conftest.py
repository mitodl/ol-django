"""Fixtures for the mitol-django-benchmark tests."""

import textwrap
from pathlib import Path

import pytest
from mitol.benchmark import config as cfg

PROJECT_TOML = """
[django]
settings_module = "main.settings.bench"
pythonpath = ["testapp"]

[database]
name_prefix = "bench_"
url_template = "${BENCH_TEST_URL:-postgres://u:p@localhost:5432/{name}}"
admin_url = "postgres://u:p@localhost:5432/postgres"

[defaults.measure]
iterations = 4
"""

BENCHMARK_TOML = """
[benchmark]
name = "example bench"

[knobs]
rows = 3
blob_bytes = 64

[[seed.step]]
name = "things"
model = "libraries.models:Topic"
count = "$knob:rows"
kwargs = { name = "Topic {index}" }

[seed.export]
first_id = "things.pk"

[target]
path = "/api/libraries/"
params = { page_size = 5 }
"""


@pytest.fixture
def write_config():
    """Return a function writing a dedented TOML file and returning its path."""

    def _write(directory: Path, name: str, content: str) -> Path:
        path = Path(directory) / name
        path.write_text(textwrap.dedent(content))
        return path

    return _write


@pytest.fixture
def layers(tmp_path, write_config):
    """Return a directory holding a valid project/benchmark configuration pair."""
    write_config(tmp_path, "benchmark.toml", PROJECT_TOML)
    write_config(tmp_path, "example.toml", BENCHMARK_TOML)
    return tmp_path


@pytest.fixture
def example_config(layers):
    """Return the loaded configuration for the fixture benchmark."""
    return cfg.load(layers / "example.toml")
