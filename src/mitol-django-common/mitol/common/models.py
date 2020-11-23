"""
Common model classes
"""
import copy
from typing import Iterable

from django.db.models import DateTimeField, Model, prefetch_related_objects
from django.db.models.query import QuerySet

from mitol.common.utils import now_in_utc


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


def _items_for_class(content_type_field, items, model_cls):
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

    def prefetch_generic_related(self, content_type_field, model_lookups):
        """
        Configure prefetch_related over generic relations

        Args:
            content_type_field(str): the field name for the ContentType
            model_lookups(dict of (list of class or class, list of str)):
                a mapping of model classes to lookups

        Returns:
            QuerySet: the new queryset with prefetching configured

        """
        qs = self._chain()

        for model_classes, lookups in model_lookups.items():
            model_classes = (
                model_classes
                if isinstance(model_classes, Iterable)
                else [model_classes]
            )
            for model_cls in model_classes:
                key = (content_type_field, model_cls)
                # pylint: disable=protected-access
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
        # pylint: disable=protected-access
        c = super()._clone()
        c._prefetch_generic_related_lookups = copy.deepcopy(
            self._prefetch_generic_related_lookups
        )
        return c
