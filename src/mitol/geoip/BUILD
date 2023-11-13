resources(
    name="files",
    sources=[
        "CHANGELOG.md",
        "README.md",
        "py.typed",
    ],
)

python_sources(
    name="geoip",
    sources=["**/*.py"],
    dependencies=[
        ":files",
        "//:reqs#setuptools",
    ],
)

python_distribution(
    name="mitol-django-geoip",
    dependencies=[":geoip"],
    provides=setup_py(
        name="mitol-django-geoip",
        description="Django application to handle IP-based geolocation",
    ),
)
