"""Base utilities"""
import abc


def base_register_subclasses_factory(*mixin_classes):
    class BaseRegisterSubclasses(abc.ABC, *mixin_classes):
        _SUBCLASSES = {}

        def __init_subclass__(cls, *, subclass_type, **kwargs):
            super().__init_subclass__()
            if subclass_type in cls._SUBCLASSES:
                raise TypeError(f"{subclass_type} has already been defined")
            cls._SUBCLASSES[subclass_type] = cls

        @classmethod
        def get_all_subclasses(cls):
            return cls._SUBCLASSES.values()

        @classmethod
        def get_subclass_by_type(cls, subclass_type):
            return cls._SUBCLASSES[subclass_type]

        @classmethod
        def get_all_types(cls):
            return cls._SUBCLASSES.keys()

    return BaseRegisterSubclasses
