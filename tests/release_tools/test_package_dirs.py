"""The walk that finds importable directories under a package

Exercised directly because `_version_module` short-circuits on a name match,
so going through it leaves this unreached - which is how a symlink loop got
in unnoticed.
"""

import pytest
from mitol.release_tools.init import _package_dirs

from tests.release_tools.conftest import write


def names(root):
    return sorted(str(path) for path in _package_dirs(root))


def test_finds_the_outermost_importable_directories(tmp_path):
    write(tmp_path / "pkg" / "__init__.py", "")
    write(tmp_path / "pkg" / "inner" / "__init__.py", "")
    write(tmp_path / "src" / "other" / "__init__.py", "")

    # `src` has no __init__.py, so it is descended into rather than returned,
    # and `pkg/inner` is inside a package already.
    assert names(tmp_path) == ["pkg", "src/other"]


@pytest.mark.parametrize(
    "junk", ["__pycache__", "build", "dist", "node_modules", "venv", ".venv", ".tox"]
)
def test_build_and_environment_trees_are_pruned(tmp_path, junk):
    """Pruned while walking, not filtered after: a .venv is enormous"""
    write(tmp_path / "pkg" / "__init__.py", "")
    write(tmp_path / junk / "lib" / "junk" / "__init__.py", "")

    assert names(tmp_path) == ["pkg"]


def test_a_symlink_loop_does_not_hang(tmp_path):
    """A link to an ancestor would otherwise be walked until the path is too long

    `rglob` never followed directory symlinks; the manual walk has to decline
    them explicitly or `init` spins and then reports hundreds of phantom
    candidates.
    """
    write(tmp_path / "pkg" / "__init__.py", "")
    (tmp_path / "plain").mkdir()
    (tmp_path / "plain" / "loop").symlink_to(tmp_path, target_is_directory=True)

    assert names(tmp_path) == ["pkg"]


def test_a_symlinked_package_is_not_followed(tmp_path):
    write(tmp_path / "pkg" / "__init__.py", "")
    (tmp_path / "linked").symlink_to(tmp_path / "pkg", target_is_directory=True)

    assert names(tmp_path) == ["pkg"]


def test_an_unreadable_directory_is_skipped_not_fatal(tmp_path):
    """`rglob` swallowed these; a traceback out of `init` would be a regression"""
    write(tmp_path / "pkg" / "__init__.py", "")
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o000)

    try:
        assert names(tmp_path) == ["pkg"]
    finally:
        locked.chmod(0o755)
