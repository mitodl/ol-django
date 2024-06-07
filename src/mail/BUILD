resources(name="mail-templates", sources=["templates/**/*"])

resources(
    name="files",
    sources=[
        "CHANGELOG.md",
        "README.md",
        "py.typed",
    ],
)

python_sources(
    name="mail",
    sources=[
        "**/*.py",
    ],
    dependencies=[
        ":mail-templates",
        ":files",
        "//:reqs#html5lib",  # pulled in dynamically by bs4
    ],
)

python_distribution(
    name="mitol-django-mail",
    dependencies=[":mail"],
    provides=setup_py(
        name="mitol-django-mail",
        description="MIT Open Learning django app extensions for mail",
    ),
)
