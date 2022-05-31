resources(name="files", sources=[
    "CHANGELOG.md",
    "README.md",
    "py.typed",
])

python_sources(
    name="google_sheets",
    sources=[
      "**/*.py"
    ],
    dependencies=[":files", "//:setuptools"],
)

python_distribution(
    name="mitol-django-google-sheets",
    dependencies=[":google_sheets"],
    provides=setup_py(
        name="mitol-django-google-sheets",
        description="Core library to handle Google Sheets integrations in Django",
    ),
)
