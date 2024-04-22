resources(
    name="files",
    sources=[
        "CHANGELOG.md",
        "README.md",
        "py.typed",
    ],
)

python_sources(
    name="posthog",
    sources=[
        "**/*.py",
    ],
    dependencies=[
        ":files",
    ],
)

python_distribution(
    name="mitol-django-posthog",
    dependencies=[":posthog"],
    provides=setup_py(
        name="mitol-django-posthog",
        description="MIT Open Learning django app extensions for Posthog",
    ),
)
