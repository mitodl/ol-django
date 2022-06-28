resources(name="testapp-files", sources=["testapp/templates/**/*"])

python_sources(
    name="testapp-lib",
    sources=["testapp/**/*.py"],
    dependencies=[
        "src/mitol/authentication",
        "src/mitol/common",
        "src/mitol/digitalcredentials",
        "src/mitol/google_sheets",
        "src/mitol/google_sheets_refunds",
        "src/mitol/mail",
        "src/mitol/oauth_toolkit_extensions",
        "src/mitol/openedx",
        "src/mitol/payment_gateway",
        ":testapp-files",
        "//:psycopg2-binary",
        "//:python3-saml",
    ],
)

python_sources(
    name="pytest-tests", sources=["conftest.py"], dependencies=["//:pytest-django"]
)

pex_binary(
    name="manage",
    entry_point="manage",
    dependencies=[":testapp-lib", ":testapp-files"],
)
