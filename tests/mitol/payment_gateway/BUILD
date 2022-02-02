resources(name="files", sources=["**/*.json"])

python_tests(
    name="test-payment_gateway",
    sources=["**/test_*.py"],
    dependencies=[
      "tests:pytest-tests",
      "tests:testapp-lib",
      ":files"
    ],
)
