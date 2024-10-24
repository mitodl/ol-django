"""Tests for the uvtestapp app."""

import pytest

from mitol.uvtestapp.api import hello_world


def test_hello_world():
    """Test the hello_world API."""

    assert hello_world() == "Hello world!"
