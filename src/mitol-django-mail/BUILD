python_library(
    name="mail",
    sources=["mitol/**/*.py", "!**/*_test.py", "!testapp/*", "!**/test_*.py"],
    dependencies=["src/mitol-django-common:common"]
)

python_tests(
    name="test-mail",
    sources=["**/*_test.py", "**/test_*.py", "conftest.py"]
)

python_distribution(
    provides=setup_py(
        name="mitol-django-mail",
        version="0.1.6",
        description="MIT Open Learning django app extensions for mail",
        author="MIT Office of Open Learning <mitx-devops@mit.edu>",
        classifiers=[
            "Natural Language :: English",
            "Operating System :: OS Independent",
            "Programming Language :: Python",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8"
        ],
    ),
    setup_py_commands=["sdist", "bdist_wheel"]
)
