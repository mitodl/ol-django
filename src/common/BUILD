resources(
    name="files",
    sources=[
        "CHANGELOG.md",
        "README.md",
        "py.typed",
    ],
)

python_sources(
    name="common",
    sources=[
        "**/*.py",
    ],
    dependencies=[
        ":files",
        "//:reqs#setuptools",
    ],
)

poetry_requirements(name="libs")

python_distribution(
    name="mitol-django-common",
    dependencies=[
        ":libs",
        ":common",
    ],
    provides=setup_py(
        name="mitol-django-common",
        description="MIT Open Learning django app extensions for common utilities",
    ),
)
