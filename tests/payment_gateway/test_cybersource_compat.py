"""Tests for the CyberSource REST SDK urllib3 compatibility shim"""

import json
from importlib.metadata import version

import pytest
import urllib3
from CyberSource import rest
from mitol.payment_gateway.api import CyberSourcePaymentGateway
from mitol.payment_gateway.cybersource_compat import (
    CompatUrllib3,
    apply_cybersource_urllib3_compat,
)
from urllib3.connectionpool import HTTPConnectionPool
from urllib3.response import HTTPResponse

SEARCH_URL = "https://apitest.cybersource.com/tss/v2/searches"


@pytest.fixture(autouse=True)
def _isolate_sdk_globals():
    """
    Undo the global state CyberSource.rest keeps between tests.

    `_urllib3_poolmanagers` is a class-level cache that outlives every client, and
    `rest.urllib3` is the module global the shim rebinds.
    """
    original_urllib3 = rest.urllib3
    rest.RESTClientObject._urllib3_poolmanagers.clear()  # noqa: SLF001
    yield
    rest.urllib3 = original_urllib3
    rest.RESTClientObject._urllib3_poolmanagers.clear()  # noqa: SLF001


def test_genuine_urllib3_is_loaded():
    """The urllib3-future stand-in must keep the real package from replacing urllib3"""
    assert urllib3.__version__ == version("urllib3")


def test_shim_is_installed_at_startup():
    """PaymentGatewayApp.ready() swaps CyberSource.rest's urllib3 for the shim"""
    assert isinstance(rest.urllib3, CompatUrllib3)


def test_pool_manager_tolerates_urllib3_future_kwargs():
    """The SDK's keepalive kwargs must not reach the genuine urllib3's PoolKey"""
    manager = rest.urllib3.PoolManager(
        num_pools=4, maxsize=4, keepalive_delay=300, keepalive_idle_window=30
    )

    assert manager.connection_from_url(SEARCH_URL) is not None


def test_proxy_manager_tolerates_urllib3_future_kwargs():
    """The proxy branch of get_pool_manager passes the same kwargs"""
    manager = rest.urllib3.ProxyManager(
        num_pools=4,
        maxsize=4,
        proxy_url="http://proxy.example.com:8080",
        proxy_headers=None,
        keepalive_delay=300,
        keepalive_idle_window=30,
    )

    assert manager.connection_from_url(SEARCH_URL) is not None


def test_shim_delegates_unknown_attributes_to_urllib3():
    """CyberSource.rest also uses urllib3 helpers the shim does not wrap"""
    assert rest.urllib3.make_headers(proxy_basic_auth="user:pass") == {
        "proxy-authorization": "Basic dXNlcjpwYXNz"
    }


def test_apply_is_idempotent():
    """ready() can run more than once in a process; re-patching must not nest"""
    patched = rest.urllib3

    apply_cybersource_urllib3_compat()

    assert rest.urllib3 is patched


def test_find_transactions_reaches_the_wire(mocker):
    """
    Drive the real SDK with only urlopen mocked.

    urlopen sits below PoolManager.connection_from_host, so the pool key construction
    that raised on the urllib3-future kwargs still runs. The other CyberSource tests
    mock the SDK's API classes and never build a pool.
    """
    urlopen = mocker.patch.object(
        HTTPConnectionPool,
        "urlopen",
        return_value=HTTPResponse(
            body=json.dumps({"totalCount": 0}).encode(),
            status=201,
            headers={"Content-Type": "application/json"},
            preload_content=True,
        ),
    )

    assert CyberSourcePaymentGateway().find_transactions(["ref-1"]) == []
    assert urlopen.call_args.args[:2] == ("POST", "/tss/v2/searches")
