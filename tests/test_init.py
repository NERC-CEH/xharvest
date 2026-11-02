import pytest

from conduit_data import greet


def test_greet_default():
    assert greet() == "Hello, world!"


@pytest.mark.parametrize("name", ["reader", "conduit_data", ""])
def test_greet_name(name):
    assert greet(name) == f"Hello, {name}!"
