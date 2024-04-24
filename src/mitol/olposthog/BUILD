resources(
    name="files",
    sources=[
        "CHANGELOG.md",
        "README.md",
        "py.typed",
    ],
)

python_sources(
    name="olposthog",
    sources=[
        "**/*.py",
    ],
    dependencies=[
        ":files",
    ],
)

python_distribution(
    name="mitol-django-olposthog",
    dependencies=[":olposthog"],
    provides=setup_py(
        name="mitol-django-olposthog",
        description="MIT Open Learning django app extensions for Posthog.",
    ),
)
