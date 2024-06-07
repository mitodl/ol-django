resources(
    name="files",
    sources=[
        "CHANGELOG.md",
        "README.md",
        "py.typed",
    ],
)

python_sources(
    name="openedx",
    sources=[
        "**/*.py",
    ],
    dependencies=[
        ":files",
        "//:reqs#setuptools",
    ],
)

python_distribution(
    name="mitol-django-openedx",
    dependencies=[":openedx"],
    provides=setup_py(
        name="mitol-django-openedx",
        description="MIT Open Learning django app extensions for edx related utilities",
    ),
)
