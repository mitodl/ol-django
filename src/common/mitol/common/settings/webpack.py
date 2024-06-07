"""Boilerplate webpack settings parsing"""
# pragma: no cover
from mitol.common.envs import get_bool, get_int, get_string

WEBPACK_DEV_SERVER_HOST = get_string(
    name="WEBPACK_DEV_SERVER_HOST",
    default="",
    dev_only=True,
    description="The webpack dev server hostname, development only",
)
WEBPACK_DEV_SERVER_PORT = get_int(
    name="WEBPACK_DEV_SERVER_PORT",
    default=None,
    dev_only=True,
    description="The webpack dev server port, development only",
)
WEBPACK_DISABLE_LOADER_STATS = get_bool(
    name="WEBPACK_DISABLE_LOADER_STATS",
    default=False,
    dev_only=True,
    description="Disables the webpack loader, development environment only.",
)
WEBPACK_USE_DEV_SERVER = get_bool(
    name="WEBPACK_USE_DEV_SERVER",
    default=False,
    dev_only=True,
    description="Enables the webpack devserver, development only",
)
