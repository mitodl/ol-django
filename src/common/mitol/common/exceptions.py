"""Common exceptions"""

SerializerTreePath = list[tuple[str, str | None]]


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

    def __init__(self, prefetch_name: str, serializer_path: SerializerTreePath):
        self.prefetch_name = prefetch_name
        self.serializer_tree_path = serializer_path
        self.message = "Required prefetch is missing"
        super().__init__(self.message)

    @property
    def tree_path(self) -> str:
        parts = []
        for serializer_name, field_name in self.serializer_tree_path:
            parts.append(
                serializer_name if not field_name else f"{serializer_name}.{field_name}"
            )

        return " -> ".join(parts)

    def __str__(self) -> str:
        return (
            f"{self.message}: prefetch='{self.prefetch_name}' path='{self.tree_path}'"
        )


class GenericObjectSerializerMissingError(Exception):
    """Exception for when a serializer isn't defined for a generic object type"""
