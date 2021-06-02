resources(name="files", sources=[
    "CHANGELOG.md",
    "README.md",
    "py.typed",
])

python_library(
    name="common",
    sources=[
      "**/*.py",
    ],
    dependencies=[":files", "//:setuptools"]
)

python_distribution(
    name="mitol-django-common",
    dependencies=[":common"],
    provides=setup_py(
        name="mitol-django-common",
        description="MIT Open Learning django app extensions for common utilities",
    ),
    setup_py_commands=["sdist", "bdist_wheel"]
)
