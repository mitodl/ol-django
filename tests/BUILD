resources(
    name="testapp-files",
    sources=["testapp/templates/**/*"],
)

python_sources(
    name="testapp-lib",
    sources=[
        "manage.py",
    ],
    dependencies=[
        "//src:mitol-sources",
        "//tests/testapp",
        ":testapp-files",
        "//:reqs#psycopg2-binary",
        "//:reqs#python3-saml",
        "//:reqs#hubspot-api-client",
    ],
)

resources(
    name="test-data",
    sources=["data/**/*"],
)

python_test_utils(
    name="pytest-utils",
    sources=[
        "conftest.py",
    ],
    dependencies=["//:reqs-testing#pytest-django"],
)

python_tests(
    name="pytest-tests",
    sources=["mitol/**/test_*.py"],
    dependencies=[
        ":testapp-lib",
        ":test-data",
    ],
)

pex_binary(
    name="manage",
    entry_point="manage.py",
    dependencies=[":testapp-lib"],
    restartable=True,
)
