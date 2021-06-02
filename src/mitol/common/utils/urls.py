"""URL utilities"""
from urllib.parse import ParseResult, urlparse, urlunparse


def ensure_trailing_slash(url: str) -> str:
    """ensure a url has a trailing slash"""
    return url if url.endswith("/") else url + "/"


def remove_password_from_url(url: str) -> str:
    """
    Remove a password from a URL

    Args:
        url (str): A URL

    Returns:
        str: A URL without a password
    """
    pieces = urlparse(url)
    netloc = pieces.netloc
    userinfo, delimiter, hostinfo = netloc.rpartition("@")
    if delimiter:
        username, _, _ = userinfo.partition(":")
        rejoined_netloc = f"{username}{delimiter}{hostinfo}"
    else:
        rejoined_netloc = netloc

    return urlunparse(
        ParseResult(
            scheme=pieces.scheme,
            netloc=rejoined_netloc,
            path=pieces.path,
            params=pieces.params,
            query=pieces.query,
            fragment=pieces.fragment,
        )
    )
