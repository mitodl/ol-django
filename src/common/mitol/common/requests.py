from requests import Session


class SessionWithBaseUrl(Session):
    """Requests Session the auto prefixes requests with a base url"""

    base_url: str

    def __init__(self, *args, base_url=None, **kwargs):
        super().__init__(*args, **kwargs)

        if base_url is None:
            msg = "`base_url` passed as None"
            raise ValueError(msg)

        self.base_url = base_url.rstrip("/")

    def request(self, method, url, *args, **kwargs):
        """Perform a request by prefixing the url with the base url"""
        full_url = self.base_url + url

        return super().request(method, full_url, *args, **kwargs)
