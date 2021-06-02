import os
from datetime import date

SECTION_MARKER = "##"
UNRELEASED_HEADER = f"{SECTION_MARKER} [Unreleased]\n"
COMPARE_URL = "https://github.com/mitodl/ol-django/compare/{from_ref}...{to_ref}"
TAG_DELIMITER = "/v"


def update_changelog(
    app_dir: str, new_version: str, next_ref: str, base_ref: str
) -> str:
    print("Updating changelog")

    changelog_path = os.path.join(app_dir, "CHANGELOG.md")

    with open(changelog_path, "r") as f:
        lines = f.readlines()

    with open(changelog_path, "w") as f:
        for line in lines:
            if line == UNRELEASED_HEADER:
                # prepend the current set of unreleased changes with the current release
                # effectively moving them down and clearing out unreleased for the next set of changes
                f.writelines(
                    [
                        line,
                        "\n",
                        f"{SECTION_MARKER} [{new_version}] - {date.today().isoformat()}\n",
                    ]
                )
            elif line.startswith("[Unreleased]"):
                # rewrite the unreleased line and add a line for this version
                f.writelines(
                    [
                        f"[Unreleased]: {COMPARE_URL.format(from_ref=next_ref, to_ref='HEAD')}\n",
                        f"[{new_version}]: {COMPARE_URL.format(from_ref=base_ref, to_ref=next_ref)}\n",
                    ]
                )
            else:
                f.writelines([line])

    return changelog_path
