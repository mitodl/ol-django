from drf_spectacular.extensions import OpenApiSerializerFieldExtension


class GenericObjectFieldExtension(OpenApiSerializerFieldExtension):
    target_class = "main.serializers.GenericObjectField"
    match_subclasses = True

    def map_serializer_field(self, auto_schema, direction):
        return {
            "oneOf": [
                auto_schema._map_serializer(serializer, direction)  # noqa: SLF001
                for serializer in self.target.serializer_mapping.values()
            ]
        }
