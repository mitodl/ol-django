"""
Common model classes
"""
import copy
from typing import Dict, Iterable, List, Type, TypeVar, Union

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DateTimeField, Model, prefetch_related_objects
from django.db.models.query import QuerySet

from mitol.common.utils.datetime import now_in_utc


class TimestampedModelQuerySet(QuerySet):
    """
    Subclassed QuerySet for TimestampedModel
    """

    def update(self, **kwargs):
        """
        Automatically update updated_on timestamp when .update(). This is because .update()
        does not go through .save(), thus will not auto_now, because it happens on the
        database level without loading objects into memory.
        """
        if "updated_on" not in kwargs:
            kwargs["updated_on"] = now_in_utc()
        return super().update(**kwargs)


class TimestampedModel(Model):
    """Base model for created_on/updated_on timestamp fields"""

    objects = TimestampedModelQuerySet.as_manager()
    created_on = DateTimeField(auto_now_add=True)  # UTC
    updated_on = DateTimeField(auto_now=True)  # UTC

    class Meta:
        abstract = True


class AuditableModel(Model):
    """An abstract base class for auditable models"""

    class Meta:
        abstract = True

    def to_dict(self):
        """
        Returns:
            dict:
                A serialized representation of the model object
        """
        raise NotImplementedError

    @classmethod
    def objects_for_audit(cls):
        """
        Returns the correct model manager for the auditable model. This defaults to `objects`, but if
        a different manager is needed for any reason (for example, if `objects` is changed to a manager
        that applies some default filters), it can be overridden.

        Returns:
             django.db.models.manager.Manager: The correct model manager for the auditable model
        """
        return cls.objects

    @classmethod
    def get_audit_class(cls):
        """
        Returns:
            class of Model:
                A class of a Django model used as the audit table
        """
        raise NotImplementedError

    @transaction.atomic
    def save_and_log(self, acting_user, *args, **kwargs):
        """
        Saves the object and creates an audit object.

        Args:
            acting_user (User):
                The user who made the change to the model. May be None if inapplicable.
        """
        before_obj = self.objects_for_audit().filter(id=self.id).first()
        self.save(*args, **kwargs)
        self.refresh_from_db()
        before_dict = None
        if before_obj is not None:
            before_dict = before_obj.to_dict()

        audit_kwargs = dict(
            acting_user=acting_user, data_before=before_dict, data_after=self.to_dict()
        )
        audit_class = self.get_audit_class()
        audit_kwargs[audit_class.get_related_field_name()] = self
        audit_class.objects.create(**audit_kwargs)


class SingletonModel(Model):
    """Model class for models representing tables that should only have a single record"""

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if force_insert and self._meta.model.objects.count() > 0:
            raise ValidationError(
                "Only one {} object should exist. Update the existing object instead "
                "of creating a new one.".format(self.__class__.__name__)
            )
        return super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    class Meta:
        abstract = True


_ModelClass = TypeVar("_ModelClass", bound=Model)
_PrefetchGenericQuerySet = TypeVar(
    "_PrefetchGenericQuerySet", bound="PrefetchGenericQuerySet"
)


def _items_for_class(
    content_type_field: str, items: Iterable[_ModelClass], model_cls: Type[_ModelClass]
) -> Iterable[_ModelClass]:
    """Returns a list of items that matches a class by content_type"""
    return [
        item
        for item in items
        if getattr(item, content_type_field).model_class() == model_cls
    ]


class PrefetchGenericQuerySet(QuerySet):
    """QuerySet supporting for prefetching over generic relationships"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._prefetch_generic_related_lookups = {}
        self._prefetch_generic_done = False

    def prefetch_generic_related(
        self,
        content_type_field: str,
        model_lookups: Dict[
            Union[List[Type[_ModelClass]], Type[_ModelClass]], List[str]
        ],
    ) -> _PrefetchGenericQuerySet:
        """
        Configure prefetch_related over generic relations

        Args:
            content_type_field(str): the field name for the ContentType
            model_lookups(dict of (list of class or class, list of str)):
                a mapping of model classes to lookups

        Returns:
            QuerySet: the new queryset with prefetching configured

        """
        qs = self._chain()  # type: ignore

        for model_classes, lookups in model_lookups.items():
            model_classes = (
                model_classes
                if isinstance(model_classes, Iterable)
                else [model_classes]
            )
            for model_cls in model_classes:
                key = (content_type_field, model_cls)

                qs._prefetch_generic_related_lookups[key] = [
                    *qs._prefetch_generic_related_lookups.get(key, []),
                    *lookups,
                ]

        return qs

    def _prefetch_generic_related_objects(self):
        """Prefetch related objects on a per-model basis"""
        for (
            (content_type_field, model_cls),
            lookups,
        ) in self._prefetch_generic_related_lookups.items():
            items = _items_for_class(content_type_field, self._result_cache, model_cls)
            prefetch_related_objects(items, *lookups)
        self._prefetch_generic_done = True

    def _fetch_all(self):
        """Called when a query is evaluated"""
        # first fetch non-generic data, this avoid N+1 issues on the generic items themselves
        super()._fetch_all()

        if self._prefetch_generic_related_lookups and not self._prefetch_generic_done:
            self._prefetch_generic_related_objects()

    def _clone(self):
        """Clone the queryset"""

        c = super()._clone()
        c._prefetch_generic_related_lookups = copy.deepcopy(
            self._prefetch_generic_related_lookups
        )
        return c
