resources(name="files", sources=[
    "CHANGELOG.md",
    "README.md",
    "py.typed",
])

python_sources(
    name="payment_gateway",
    sources=[
      "**/*.py"
    ],
    dependencies=[":files", "//:setuptools"],
)

python_distribution(
    name="mitol-django-payment-gateway",
    dependencies=[":payment_gateway"],
    provides=setup_py(
        name="mitol-django-payment-gateway",
        description="Django application to handle payment processing",
    ),
)
