"""
Tests for mitol.common.templatetags.render_bundle
"""

from os import path
from textwrap import dedent

import pytest
from django.template import Context, Template

FAKE_COMMON_BUNDLE = [
    {
        "name": "common-1f11431a92820b453513.js",
        "path": "/project/static/bundles/common-1f11431a92820b453513.js",
    },
    {
        "name": "styles-1f123456670b45387513.css",
        "path": "/project/static/bundles/styles-1f123456670b45387513.css",
    },
    {
        "name": "misc-84685678567856785688.txt",
        "path": "/project/static/bundles/misc-84685678567856785688.txt",
    },
]


@pytest.fixture(autouse=True)
def dont_disable_webpack(settings):
    """Re-enable webpack loader stats for these tests."""
    settings.WEBPACK_DISABLE_LOADER_STATS = False


def test_render_bundle_disable_loader_stats(settings, mocker, rf):
    """Verify it renders nothing if WEBPACK_DISABLE_LOADER_STATS = True"""
    settings.WEBPACK_DISABLE_LOADER_STATS = True
    request = rf.get("/")
    get_loader = mocker.patch("mitol.common.templatetags.render_bundle.get_loader")

    context = Context({"request": request})
    template = Template("{% load render_bundle %}{% render_bundle 'bundle_name' %}")
    assert template.render(context) == ""

    get_loader.assert_not_called()


@pytest.mark.parametrize(
    "attrs, expected",
    [
        ("", ""),
        ("added_attrs='defer'", "defer"),
    ],
)
def test_render_bundle(mocker, rf, attrs, expected):
    """Verify render_bundle returns the path to the bundle with the correct base url"""
    request = rf.get("/")
    context = {"request": request}

    # convert to generator
    common_bundle = (chunk for chunk in FAKE_COMMON_BUNDLE)
    get_bundle = mocker.Mock(return_value=common_bundle)
    loader = mocker.Mock(get_bundle=get_bundle)
    bundle_name = "bundle_name"

    get_loader = mocker.patch(
        "mitol.common.templatetags.render_bundle.get_loader", return_value=loader
    )
    mocker.patch(
        "mitol.common.templatetags.render_bundle.webpack_public_path", return_value="/"
    )

    context = Context({"request": request})
    template = Template(
        f"{{% load render_bundle %}}{{% render_bundle '{bundle_name}' {attrs} %}}"
    )

    script_url = path.join("/", FAKE_COMMON_BUNDLE[0]["name"])
    style_url = path.join("/", FAKE_COMMON_BUNDLE[1]["name"])
    assert template.render(context) == dedent(
        f"""\
    <script type="text/javascript" src="{script_url}" {expected} ></script>
    <link type="text/css" href="{style_url}" rel="stylesheet" {expected} />"""
    )

    get_bundle.assert_called_with(bundle_name)
    get_loader.assert_called_with("DEFAULT")


def test_render_bundle_missing_file(mocker, rf):
    """
    If webpack-stats.json is missing, return an empty string
    """
    request = rf.get("/")
    context = {"request": request}

    get_bundle = mocker.Mock(side_effect=OSError)
    loader = mocker.Mock(get_bundle=get_bundle)
    bundle_name = "bundle_name"
    get_loader = mocker.patch(
        "mitol.common.templatetags.render_bundle.get_loader", return_value=loader
    )

    context = Context({"request": request})
    template = Template(
        f"{{% load render_bundle %}}{{% render_bundle '{bundle_name}' %}}"
    )
    assert template.render(context) == ""

    get_bundle.assert_called_with(bundle_name)
    get_loader.assert_called_with("DEFAULT")
