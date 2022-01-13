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
    dependencies=[":files", "//:setuptools"],
)

python_distribution(
    name="mitol-django-common",
    dependencies=[":common"],
    provides=setup_py(
        name="mitol-django-common",
        description="MIT Open Learning django app extensions for common utilities",
    ),
)
