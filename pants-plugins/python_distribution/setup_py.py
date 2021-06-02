"""Plugin for releases"""
import re
from pants.backend.python.goals.setup_py import SetupKwargs, SetupKwargsRequest
from pants.engine.rules import Get, collect_rules, rule
from pants.engine.target import Target
from pants.engine.unions import UnionRule
from pants.util.frozendict import FrozenDict
from pants.engine.fs import DigestContents, GlobMatchErrorBehavior, PathGlobs
from os.path import join

class PantsSetupKwargsRequest(SetupKwargsRequest):
    @classmethod
    def is_applicable(cls, _: Target) -> bool:
        # We always use our custom `setup()` kwargs generator for `python_distribution` targets in
        # this repo.
        return True

VAR_RE = re.compile(r"""(.+)\s=\s[\"'](.+)[\"']""")

@rule
async def pants_setup_kwargs(
    request: PantsSetupKwargsRequest
) -> SetupKwargs:
    kwargs = request.explicit_kwargs.copy()
    path = request.target.address.spec_path

    digest_contents = await Get(
        DigestContents,
        PathGlobs(
            [join(path, "__init__.py")],
            description_of_origin="`setup_py()` plugin",
            glob_match_error_behavior=GlobMatchErrorBehavior.error,
        ),
    )
    about = {}

    for line in digest_contents[0].content.decode().split("\n"):
        result = VAR_RE.match(line)
        if result:
            about[result.group(1)] = result.group(2)

    # Add classifiers. We preserve any that were already set.
    standard_classifiers = [
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8"

    ]
    kwargs["classifiers"] = [*standard_classifiers, *kwargs.get("classifiers", [])]

    # Hardcode certain kwargs and validate that they weren't already set.
    hardcoded_kwargs = dict(
        # name=about["__distributionname__"],
        authors=["MIT Office of Open Learning <mitx-devops@mit.edu>"],
        version=about["__version__"],
        license="BSD 3-Clause License",
        zip_safe=True,
    )
    kwargs.update(hardcoded_kwargs)

    return SetupKwargs(kwargs, address=request.target.address)


def rules():
    return (*collect_rules(), UnionRule(SetupKwargsRequest, PantsSetupKwargsRequest))
