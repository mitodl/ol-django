"""Webpack utils tests"""
from mitol.common.utils.webpack import (
    webpack_dev_server_host,
    webpack_dev_server_url,
    webpack_public_path,
)


def test_webpack_public_path(rf, settings, mocker):
    """Test public_path() behaviors"""
    request = rf.get("/")

    mocker.patch(
        "mitol.common.utils.webpack.webpack_dev_server_url", return_value="/dev/server"
    )

    settings.WEBPACK_USE_DEV_SERVER = True
    assert webpack_public_path(request) == "/dev/server/"

    settings.WEBPACK_USE_DEV_SERVER = False
    assert webpack_public_path(request) == "/static/bundles/"


def test_webpack_dev_server_host(settings, rf):
    """Test webpack_dev_server_host()"""
    request = rf.get("/", SERVER_NAME="invalid-dev-server1.local")
    settings.WEBPACK_DEV_SERVER_HOST = "invalid-dev-server2.local"
    assert webpack_dev_server_host(request) == "invalid-dev-server2.local"
    settings.WEBPACK_DEV_SERVER_HOST = None
    assert webpack_dev_server_host(request) == "invalid-dev-server1.local"


def test_webpack_dev_server_url(settings, rf):
    """Test webpack_dev_server_url()"""
    settings.WEBPACK_DEV_SERVER_PORT = 7777
    settings.WEBPACK_DEV_SERVER_HOST = "invalid-dev-server.local"
    request = rf.get("/")
    assert webpack_dev_server_url(request) == "http://invalid-dev-server.local:7777"
