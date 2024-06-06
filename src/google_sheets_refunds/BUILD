resources(
    name="files",
    sources=[
        "CHANGELOG.md",
        "README.md",
        "py.typed",
    ],
)

python_sources(
    name="google_sheets_refunds",
    sources=["**/*.py"],
    dependencies=[
        ":files",
        "//:reqs#setuptools",
    ],
)

python_distribution(
    name="mitol-django-google-sheets-refunds",
    dependencies=[":google_sheets_refunds"],
    provides=setup_py(
        name="mitol-django-google-sheets-refunds",
        description="Library to handle Refund requests using Google Sheets integrations in Django",
    ),
)
