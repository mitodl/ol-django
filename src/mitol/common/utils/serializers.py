"""Model Serialization utils"""
import json

from django.core.serializers import serialize


def serialize_model_object(obj):
    """
    Serialize model into a dict representable as JSON
    Args:
        obj (django.db.models.Model): An instantiated Django model
    Returns:
        dict:
            A representation of the model
    """
    # serialize works on iterables so we need to wrap object in a list, then unwrap it
    if obj:
        data = json.loads(serialize("json", [obj]))[0]
        serialized = data["fields"]
        serialized["id"] = data["pk"]
        return serialized
