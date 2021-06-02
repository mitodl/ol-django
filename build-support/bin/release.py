""" Script to create a release """
import re
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from os import getcwd
from os.path import join

from changelog import update_changelog
from common import list_apps
from git import Repo
from semver import VersionInfo

VAR_RE = re.compile(r"""(.+)\s=\s[\"'](.+)[\"']""")


def create_parser() -> ArgumentParser:
    """Parse arguments"""
    parser = ArgumentParser(description="Prepare the changelog for a release.")
    parser.add_argument(
        "--app",
        required=True,
        type=str,
        choices=list_apps(),
        help="The application to update the changelog for",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--version",
        type=str,
        help="The new version to use",
    )
    group.add_argument(
        "--bump-major",
        action="store_true",
        help="Bump to the next major version",
    )
    group.add_argument(
        "--bump-minor",
        action="store_true",
        help="Bump to the next minor version",
    )
    group.add_argument(
        "--bump-patch",
        action="store_true",
        help="Bump to the next patch version",
    )
    return parser


def update_version(current_version: str, args: Namespace) -> str:
    """Update the version"""
    if args.version:
        return args.version
    version = VersionInfo.parse(current_version)
    print(version)
    print(args)
    if args.bump_major:
        version = version.bump_major()
    elif args.bump_minor:
        version = version.bump_minor()
    elif args.bump_patch:
        version = version.bump_patch()
    return str(version)


@dataclass(frozen=True)
class Metadata:
    app_name: str
    old_version: str
    new_version: str
    base_ref: str
    next_ref: str


def update_init_py(args: Namespace, init_filename: str) -> Metadata:
    """Update __init__.py"""
    print(f"Updating {init_filename}")
    #
    # write out the new version to the corresponding VERSION file

    old_version = None
    new_version = None
    app_name = None
    lines = []
    with open(init_filename, "r") as f:
        for line in f.readlines():
            result = VAR_RE.match(line)
            if result:
                if result.group(1) == "__version__":
                    old_version = result.group(2)
                    new_version = update_version(old_version, args)
                    line = f'__version__ = "{new_version}"\n'
                elif result.group(1) == "__distributionname__":
                    app_name = result.group(2)
            lines.append(line)

    with open(init_filename, "w") as f:
        f.writelines(lines)

    if not all([app_name, old_version, new_version]):
        raise Exception(f"Unable to read {init_filename}")

    return Metadata(
        app_name=app_name,
        old_version=old_version,
        new_version=new_version,
        base_ref=f"{app_name}/{old_version}",
        next_ref=f"{app_name}/{new_version}",
    )


def main() -> None:
    """Generate a release"""
    args = create_parser().parse_args()
    app_dir = join(getcwd(), "src/mitol", args.app)

    # checkout the main branch
    repo = Repo(".")
    # repo.heads.main.checkout()

    version_filename = join(app_dir, "__init__.py")
    metadata = update_init_py(args, version_filename)
    print(f"New version: {metadata.new_version}")

    changelog_filename = update_changelog(
        app_dir, metadata.new_version, metadata.next_ref, metadata.base_ref
    )

    # commit the changes and tag it
    print("Commiting")
    repo.index.add(
        [
            changelog_filename,
            version_filename,
        ]
    )
    repo.index.commit(f"Release {metadata.next_ref}")
    print(f"Tagging {metadata.next_ref}")
    repo.create_tag(metadata.next_ref)


if __name__ == "__main__":
    main()
