"""Plugin for python distributions"""

from python_distribution import setup_py


def rules():  # noqa: D103
    return [
        *setup_py.rules(),
    ]
