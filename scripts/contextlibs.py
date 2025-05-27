from contextlib import contextmanager
from os import PathLike
from os import chdir as _chdir
from pathlib import Path


@contextmanager
def chdir(path: str | bytes | PathLike[str]):
    original = Path.cwd()

    try:
        _chdir(path)
        yield
    finally:
        _chdir(original)
