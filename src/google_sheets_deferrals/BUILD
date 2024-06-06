resources(
    name="files",
    sources=[
        "CHANGELOG.md",
        "README.md",
        "py.typed",
    ],
)

python_sources(
    name="google_sheets_deferrals",
    sources=["**/*.py"],
    dependencies=[
        ":files",
        "//:reqs#setuptools",
    ],
)

python_distribution(
    name="mitol-django-google-sheets-deferrals",
    dependencies=[":google_sheets_deferrals"],
    provides=setup_py(
        name="mitol-django-google-sheets-deferrals",
        description="Library to handle Deferral requests using Google Sheets integrations in Django",
    ),
)
