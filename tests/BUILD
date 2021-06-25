resources(name="testapp-files", sources=[
    "testapp/templates/**/*"
])

python_library(name="testapp-lib", sources=[
    "testapp/**/*.py"
], dependencies=[
    "src/mitol/authentication",
    "src/mitol/common",
    "src/mitol/digitalcredentials",
    "src/mitol/mail",
    "src/mitol/oauth_toolkit_extensions",
    ":testapp-files",
    "//:psycopg2-binary",
    "//:python3-saml"
])

python_library(name="pytest-tests", sources=[
    "conftest.py"
], dependencies=[
    "//:pytest-django"
])

pex_binary(
    name="manage",
    entry_point="manage",
    dependencies=[":testapp-lib", ":testapp-files"],
)