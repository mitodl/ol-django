"""Common exceptions"""


class RequiredPrefetchesNotDefinedError(Exception):
    def __init__(self, serializer_class):
        self.serializer_class = serializer_class
        super().__init__()

    def __str__(self):
        return (
            f"Serializer '{self.serializer_class}' "
            "does not define 'required_prefetches'"
        )


class RequiredPrefetchMissingError(Exception):
    """Exception for when a prefetch hasn't been made"""

    def __init__(self, prefetch_name: str):
        self.prefetch_name = prefetch_name
        self.message = "Required prefetch is missing"
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"{self.message}: '{self.prefetch_name}'"
