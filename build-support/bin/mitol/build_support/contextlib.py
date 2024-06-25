from contextlib import contextmanager  # noqa: D100
from os import chdir as _chdir
from pathlib import Path


@contextmanager
def chdir(path):  # noqa: D103
    original = Path.cwd()

    try:
        _chdir(path)
        yield
    finally:
        _chdir(original)
