resources(
    name="files",
    sources=[
        "CHANGELOG.md",
        "README.md",
        "py.typed",
    ],
)

python_sources(
    name="oauth_toolkit_extensions",
    sources=[
        "**/*.py",
    ],
    dependencies=[
        ":files",
    ],
)

python_distribution(
    name="mitol-django-oauth-toolkit-extensions",
    dependencies=[":oauth_toolkit_extensions"],
    provides=setup_py(
        name="mitol-django-oauth-toolkit-extensions",
        description="MIT Open Learning django app extensions for oauth toolkit",
    ),
)
