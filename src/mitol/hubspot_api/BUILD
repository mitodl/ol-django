resources(name="files", sources=[
    "CHANGELOG.md",
    "README.md",
    "py.typed",
])

python_sources(
    name="hubspot_api",
    sources=[
      "**/*.py"
    ],
    dependencies=[":files", "//:setuptools"],
)

python_distribution(
    name="mitol-hubspot-api",
    dependencies=[":hubspot_api"],
    provides=setup_py(
        name="mitol-django-hubspot-api",
        description="Django application for Hubspot API integration",
    ),
)
