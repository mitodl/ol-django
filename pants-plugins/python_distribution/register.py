"""Plugin for python distributions"""

from python_distribution import setup_py


def rules():
    return [
        *setup_py.rules(),
    ]
