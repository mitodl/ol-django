"""Plugin for releases"""
from os.path import join
import re

from pants.backend.python.goals.setup_py import SetupKwargs, SetupKwargsRequest
from pants.engine.rules import Get, collect_rules, rule
from pants.engine.target import Target
from pants.engine.unions import UnionRule
from pants.util.frozendict import FrozenDict
from pants.engine.fs import DigestContents, GlobMatchErrorBehavior, PathGlobs
import toml


VAR_RE = re.compile(r"""(.+)\s=\s[\"'](.+)[\"']""")
STANDARD_CLASSIFIERS = [
    "Natural Language :: English",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8"

]
DEFAULT_SETUP_KWARGS = dict(
    authors=["MIT Office of Open Learning <mitx-devops@mit.edu>"],
    license="BSD 3-Clause License",
    long_description_content_type="text/markdown",
    zip_safe=True,
)

class PantsSetupKwargsRequest(SetupKwargsRequest):
    @classmethod
    def is_applicable(cls, _: Target) -> bool:
        # We always use our custom `setup()` kwargs generator for `python_distribution` targets in
        # this repo.
        return True


@rule
async def pants_setup_kwargs(
    request: PantsSetupKwargsRequest
) -> SetupKwargs:
    kwargs = request.explicit_kwargs.copy()
    path = request.target.address.spec_path

    # read in __init__.py
    pyproject_contents = await Get(
        DigestContents,
        PathGlobs(
            [join(path, "pyproject.toml")],
            description_of_origin="`setup_py()` plugin",
            glob_match_error_behavior=GlobMatchErrorBehavior.error,
        ),
    )
    pyproject = toml.loads(pyproject_contents[0].content.decode())

    # read in the readme
    readme_contents = await Get(
        DigestContents,
        PathGlobs(
            [join(path, "README.md")],
            description_of_origin="`setup_py()` plugin",
            glob_match_error_behavior=GlobMatchErrorBehavior.error,
        ),
    )

    kwargs.update(DEFAULT_SETUP_KWARGS)
    kwargs["version"] = pyproject["project"]["version"]
    # Add classifiers. We preserve any that were already set.
    kwargs["classifiers"] = [*STANDARD_CLASSIFIERS, *kwargs.get("classifiers", [])]
    kwargs["long_description"] = readme_contents[0].content.decode()

    return SetupKwargs(kwargs, address=request.target.address)


def rules():
    return (*collect_rules(), UnionRule(SetupKwargsRequest, PantsSetupKwargsRequest))
