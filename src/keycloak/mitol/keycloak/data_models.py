from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class UserAttributes(BaseModel):
    """
    Pydantic model for Keycloak user attributes
    """

    full_name: Annotated[
        str | None,
        Field(serialization_alias="fullName", exclude_if=lambda v: v is None),
    ] = None

    @field_serializer("*", mode="plain")
    def as_array(self, value: Any) -> list[Any]:
        return [value]

    model_config = ConfigDict(serialize_by_alias=True, frozen=True)
