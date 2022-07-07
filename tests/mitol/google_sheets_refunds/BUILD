resources(name="files", sources=["**/*.csv"])

python_tests(
    name="test-google-sheets-refunds",
    sources=["**/test_*.py"],
    dependencies=[
        "tests:pytest-tests",
        "tests:testapp-lib",
        ":files"
    ],
)