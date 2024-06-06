resources(
    name="files",
    sources=[
        "CHANGELOG.md",
        "README.md",
        "py.typed",
    ],
)

python_sources(
    name="authentication",
    sources=[
        "**/*.py",
    ],
    dependencies=[
        ":files",
    ],
)

python_distribution(
    name="mitol-django-authentication",
    dependencies=[":authentication"],
    provides=setup_py(
        name="mitol-django-authentication",
        description="MIT Open Learning django app extensions for oauth toolkit",
    ),
)
