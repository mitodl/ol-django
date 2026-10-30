"""Tests for `scripts/release.py weekly`

The command is exercised against a synthetic `src/` tree rather than the real
one, so a test cannot be invalidated by whatever the repository happens to have
waiting in `changelog.d` that day. `prepare` itself is stubbed: it is covered by
being the command a person already runs, and calling it for real would bump
versions in the checkout the tests run from.
"""

import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from scripts import apps, release
from scripts.project import Project

DATE_PATTERN = "YYYY.MM.DD[.INC0]"
SEMVER_PATTERN = "MAJOR.MINOR.PATCH"

SCRIV_MARKER = "<!-- scriv-insert-here -->"

CHANGELOG_HEADER = """\
# Changelog
All notable changes to this project will be documented in this file.

<!-- scriv-insert-here -->
"""


def _write_app(  # noqa: PLR0913
    source_dir: Path,
    module_name: str,
    *,
    package_name: str,
    version: str,
    version_pattern: str = DATE_PATTERN,
    fragments: int = 0,
) -> Path:
    """Create the parts of an app that `weekly` reads"""
    app_dir = source_dir / module_name
    (app_dir / "changelog.d").mkdir(parents=True)
    (app_dir / "mitol" / module_name).mkdir(parents=True)

    (app_dir / "pyproject.toml").write_text(
        textwrap.dedent(f"""\
        [project]
        name = "{package_name}"
        version = "{version}"

        [tool.bumpver]
        current_version = "{version}"
        version_pattern = "{version_pattern}"

        [tool.bumpver.file_patterns]
        "pyproject.toml" = ['version = "{{version}}"']
        "mitol/{module_name}/__init__.py" = ['__version__ = "{{version}}"']
        """)
    )
    (app_dir / "mitol" / module_name / "__init__.py").write_text(
        f'__version__ = "{version}"\n'
    )
    (app_dir / "CHANGELOG.md").write_text(CHANGELOG_HEADER)

    # scriv ignores its own config; `_fragment_paths` has to agree, so one is
    # always present whether or not the app has anything waiting.
    (app_dir / "changelog.d" / "scriv.ini").write_text("[scriv]\nformat = md\n")
    for index in range(fragments):
        (app_dir / "changelog.d" / f"2026010{index}_000000_change.md").write_text(
            f"### Changed\n\n- change {index}\n"
        )

    return app_dir


@pytest.fixture
def project(tmp_path, monkeypatch) -> Project:
    """Build a Project whose `src/` is a synthetic tree under tmp_path"""
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    monkeypatch.setattr(apps, "get_source_dir", lambda: source_dir)

    project = Project()
    project.path = tmp_path
    return project


@pytest.fixture
def prepared(monkeypatch) -> list[str]:
    """Record which apps `weekly` prepared, and fake what `prepare` does to them

    The real `prepare` bumps the version everywhere it is declared, folds the
    fragments into CHANGELOG.md, and deletes them. The stub does the same to
    the synthetic tree, because what `weekly` writes afterwards is read back
    out of those files.
    """
    calls: list[str] = []

    def _fake_prepare(_project, app):
        calls.append(app.module_name)
        new_version = "2026.10.30"

        pyproject = app.absolute_path / "pyproject.toml"
        pyproject.write_text(
            pyproject.read_text().replace(f'"{app.version}"', f'"{new_version}"')
        )

        entries = "\n".join(
            sorted(
                path.read_text().strip()
                for path in release._fragment_paths(app)  # noqa: SLF001
            )
        )
        # scriv inserts at its marker, so the newest entry is first and any
        # older one follows it. The command has to stop at that next anchor.
        changelog = app.absolute_path / "CHANGELOG.md"
        changelog.write_text(
            changelog.read_text().replace(
                SCRIV_MARKER,
                f"{SCRIV_MARKER}\n\n"
                f"<a id='changelog-{new_version}'></a>\n"
                f"## [{new_version}] - 2026-10-30\n\n{entries}",
            )
        )

        for path in release._fragment_paths(app):  # noqa: SLF001
            path.unlink()

    monkeypatch.setattr(release, "_prepare_in_subprocess", _fake_prepare)
    return calls


def _run(project, tmp_path):
    """Invoke `weekly`, returning the result and the two files it may write"""
    body_file = tmp_path / "pr_body.md"
    title_file = tmp_path / "pr_title.txt"
    result = CliRunner().invoke(
        release.weekly,
        ["--body-file", str(body_file), "--title-file", str(title_file)],
        obj=project,
    )
    return result, title_file, body_file


def test_cuts_only_date_versioned_apps_that_have_fragments(project, prepared, tmp_path):
    """An app is cut when it has fragments waiting, and left alone otherwise"""
    source_dir = tmp_path / "src"
    _write_app(
        source_dir,
        "mail",
        package_name="mitol-django-mail",
        version="2026.4.2",
        fragments=2,
    )
    _write_app(
        source_dir,
        "scim",
        package_name="mitol-django-scim",
        version="2026.10.9",
        fragments=0,
    )

    result, title_file, body_file = _run(project, tmp_path)

    assert result.exit_code == 0, result.output
    assert prepared == ["mail"]
    assert title_file.read_text().strip() == "Release mitol-django-mail/v2026.10.30"
    assert "mitol-django-mail 2026.4.2 -> 2026.10.30" in body_file.read_text()
    assert "mitol-django-scim" not in body_file.read_text()


def test_uvtestapp_is_never_cut(project, prepared, tmp_path):
    """`uvtestapp` carries a pyproject but is not a releasable app"""
    source_dir = tmp_path / "src"
    _write_app(
        source_dir,
        "uvtestapp",
        package_name="mitol-django-uvtestapp",
        version="2024.10.24",
        fragments=3,
    )

    result, title_file, _ = _run(project, tmp_path)

    assert result.exit_code == 0, result.output
    assert prepared == []
    assert not title_file.exists()


def test_semver_app_is_reported_rather_than_cut(project, prepared, tmp_path):
    """A semver app needs a `--bump`, so `weekly` names it instead of cutting"""
    source_dir = tmp_path / "src"
    _write_app(
        source_dir,
        "mail",
        package_name="mitol-django-mail",
        version="2026.4.2",
        fragments=1,
    )
    _write_app(
        source_dir,
        "edx_api_client",
        package_name="edx-api-client",
        version="1.15.0",
        version_pattern=SEMVER_PATTERN,
        fragments=2,
    )

    result, _, body_file = _run(project, tmp_path)

    assert result.exit_code == 0, result.output
    assert prepared == ["mail"]

    body = body_file.read_text()
    assert "## Not released automatically" in body
    assert "`edx-api-client` (1.15.0, 2 waiting)" in body
    assert "--app edx_api_client --bump major|minor|patch" in body


def test_nothing_waiting_writes_no_files(project, prepared, tmp_path):
    """Absence of the files is how a caller learns there was nothing to cut"""
    source_dir = tmp_path / "src"
    _write_app(
        source_dir,
        "mail",
        package_name="mitol-django-mail",
        version="2026.4.2",
        fragments=0,
    )

    result, title_file, body_file = _run(project, tmp_path)

    assert result.exit_code == 0, result.output
    assert prepared == []
    assert not title_file.exists()
    assert not body_file.exists()
    assert "No date-versioned app has changelog fragments waiting." in result.output


def test_a_semver_app_alone_still_writes_no_files(project, prepared, tmp_path):
    """Only semver apps waiting is still nothing for this command to cut"""
    source_dir = tmp_path / "src"
    _write_app(
        source_dir,
        "edx_api_client",
        package_name="edx-api-client",
        version="1.15.0",
        version_pattern=SEMVER_PATTERN,
        fragments=1,
    )

    result, title_file, body_file = _run(project, tmp_path)

    assert result.exit_code == 0, result.output
    assert prepared == []
    assert not title_file.exists()
    assert not body_file.exists()
    assert "edx-api-client" in result.output


def test_several_apps_get_a_counted_title(project, prepared, tmp_path):
    """Spelling out every package produces a title nothing displays in full"""
    source_dir = tmp_path / "src"
    for module_name in ("mail", "scim", "geoip"):
        _write_app(
            source_dir,
            module_name,
            package_name=f"mitol-django-{module_name}",
            version="2026.4.2",
            fragments=1,
        )

    result, title_file, _ = _run(project, tmp_path)

    assert result.exit_code == 0, result.output
    assert sorted(prepared) == ["geoip", "mail", "scim"]
    assert title_file.read_text().strip().startswith("Release 3 packages (")


@pytest.mark.usefixtures("prepared")
def test_changelog_entry_stops_at_the_next_anchor(project, tmp_path):
    """The body carries this release's entry, not the ones before it"""
    source_dir = tmp_path / "src"
    app_dir = _write_app(
        source_dir,
        "mail",
        package_name="mitol-django-mail",
        version="2026.4.2",
        fragments=1,
    )
    (app_dir / "CHANGELOG.md").write_text(
        f"{CHANGELOG_HEADER}\n"
        "<a id='changelog-2026.4.2'></a>\n"
        "## [2026.4.2] - 2026-04-02\n\n"
        "### Changed\n\n- an older release nobody is cutting now\n"
    )

    result, _, body_file = _run(project, tmp_path)

    assert result.exit_code == 0, result.output

    body = body_file.read_text()
    assert "change 0" in body
    assert "an older release nobody is cutting now" not in body
    # scriv's own `## [version] - date` heading is dropped: the section heading
    # above it already names the package and both versions.
    assert "## [2026.10.30]" not in body
