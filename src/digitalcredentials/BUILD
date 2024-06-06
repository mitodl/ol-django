resources(
    name="files",
    sources=[
        "CHANGELOG.md",
        "README.md",
        "py.typed",
    ],
)

python_sources(
    name="digitalcredentials",
    sources=["**/*.py"],
    dependencies=[
        ":files",
    ],
)

python_distribution(
    name="mitol-django-digital-credentials",
    dependencies=[":digitalcredentials"],
    provides=setup_py(
        name="mitol-django-digital-credentials",
        description="Django application to support digital credentials",
    ),
)
