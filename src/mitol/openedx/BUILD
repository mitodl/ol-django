resources(name="files", sources=[
    "CHANGELOG.md",
    "README.md",
    "py.typed",
])

python_library(
    name="openedx",
    sources=[
      "**/*.py",
    ],
    dependencies=[":files", "//:setuptools"]
)

python_distribution(
    name="mitol-django-openedx",
    dependencies=[":openedx"],
    provides=setup_py(
        name="mitol-django-openedx",
        description="MIT Open Learning django app extensions for edx related utilities",
    ),
    setup_py_commands=["sdist", "bdist_wheel"]
)
