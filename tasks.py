import os
import sys
from collections import namedtuple
from datetime import date

import requests

from invoke import call, task
import semver

AppName = namedtuple("AppName", ["short", "long"])
UNRELEASED_HEADER = "## [Unreleased]\n"


def _parse_app_name(app_name):
    """Parse the app name into a short/long version"""
    return AppName(app_name[len("mitol-django-") :], app_name)


@task
def no_changes(c):
    """Asserts there's no uncommitted changes"""
    c.run("git update-index --refresh")
    if c.run("git diff-index --quiet HEAD --", warn=True).exited != 0:
        print("Uncommitted changes detected")
        sys.exit(1)


@task(pre=[no_changes])
def use_branch(c, branch_name):
    """Switch to a branch"""
    c.run(f"git checkout {branch_name}")
    c.run("git pull")


@task(
    # pre=[call(use_branch, "main")],
    help={
        "app_name": "the app's name",
        "version": "the version rule to use, as designated by https://python-poetry.org/docs/cli/#version",
    },
)
def version(c, app_name, version):
    """Change an app's version and version the changelog"""
    app_name = _parse_app_name(app_name)

    changelog_path = os.path.join(app_name.long, "CHANGELOG.md")
    with open(changelog_path, "r") as f:
        lines = f.readlines()

    if UNRELEASED_HEADER not in lines:
        print(
            "Changelog is missing '[Unreleased]' section, please fix before proceeding"
        )
        sys.exit(2)

    with c.cd(app_name.long):
        new_version = c.run(f"poetry version {version}").stdout.split(" ")[-1].strip()

    # initial repo commit if there's no tags for this app
    initial_ref = c.run(
        "git rev-list --max-parents=0 HEAD"
    ).stdout.strip()
    base_ref = next(
        iter(sorted(
            [
                tag.strip()
                for tag in c.run("git tag -l").stdout.splitlines()
                if tag.startswith(f"{app_name.long}-v")
            ],
            # sort by semantic versions
            key=lambda tag: semver.VersionInfo.parse(tag.split("-v")[1])
        )),
        initial_ref,
    )
    next_ref = f"{app_name.long}-v{new_version}"

    with open(changelog_path, "w") as f:
        for line in lines:
            if line == UNRELEASED_HEADER:
                # prepend the current set of unreleased changes with the current release
                # effectively moving them down and clearing out unreleased for the next set of changes
                f.writelines(
                    [line, "\n", f"## [{new_version}] - {date.today().isoformat()}\n",]
                )
            elif line.startswith("[Unreleased]"):
                # rewrite the unreleased line and add a line for this version
                f.writelines(
                    [
                        f"[Unreleased]: https://github.com/mitodl/ol-django/compare/{new_version}...HEAD",
                        f"[{new_version}]: https://github.com/mitodl/ol-django/compare/{base_ref}...{new_version}",
                    ]
                )
            else:
                f.writelines([line])

    c.run("git add .")
    c.run(f"git commit -m \"Release {next_ref}\"")
    c.run(f"git tag {next_ref}")
    # c.run("git push origin main")
