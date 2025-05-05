"""
Common model classes
"""

import copy
from collections.abc import Iterable
from typing import TypeVar, Union

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import (
    PROTECT,
    CharField,
    DateTimeField,
    ForeignKey,
    JSONField,
    Model,
    prefetch_related_objects,
)
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
        """  # noqa: E501
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


class AuditModel(TimestampedModel):
    """An abstract base class for audit models"""

    acting_user = ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=PROTECT)
    data_before = JSONField(blank=True, null=True)
    data_after = JSONField(blank=True, null=True)

    class Meta:
        abstract = True

    @classmethod
    def get_related_field_name(cls):
        """
        Returns:
            str: A field name which links the Auditable model to this model
        """  # noqa: D401
        raise NotImplementedError


class AuditableModel(Model):
    """An abstract base class for auditable models"""

    class Meta:
        abstract = True

    def to_dict(self):
        """
        Returns:
            dict:
                A serialized representation of the model object
        """  # noqa: D401
        raise NotImplementedError

    @classmethod
    def objects_for_audit(cls):
        """
        Returns the correct model manager for the auditable model. This defaults to `objects`, but if
        a different manager is needed for any reason (for example, if `objects` is changed to a manager
        that applies some default filters), it can be overridden.

        Returns:
             django.db.models.manager.Manager: The correct model manager for the auditable model
        """  # noqa: E501, D401
        return cls.objects

    @classmethod
    def get_audit_class(cls):
        """
        Returns:
            class of Model:
                A class of a Django model used as the audit table
        """  # noqa: D401
        raise NotImplementedError

    @transaction.atomic
    def save_and_log(self, acting_user, *args, **kwargs):
        """
        Saves the object and creates an audit object.

        Args:
            acting_user (User):
                The user who made the change to the model. May be None if inapplicable.
        """  # noqa: D401
        before_obj = self.objects_for_audit().filter(id=self.id).first()
        self.save(*args, **kwargs)
        self.refresh_from_db()
        before_dict = None
        if before_obj is not None:
            before_dict = before_obj.to_dict()

        audit_kwargs = dict(  # noqa: C408
            acting_user=acting_user, data_before=before_dict, data_after=self.to_dict()
        )
        audit_class = self.get_audit_class()
        audit_kwargs[audit_class.get_related_field_name()] = self
        audit_class.objects.create(**audit_kwargs)


class SingletonModel(Model):
    """Model class for models representing tables that should only have a single record"""  # noqa: E501

    def save(
        self,
        force_insert=False,  # noqa: FBT002
        force_update=False,  # noqa: FBT002
        using=None,
        update_fields=None,
    ):
        if force_insert and self._meta.model.objects.count() > 0:
            raise ValidationError(  # noqa: TRY003
                f"Only one {self.__class__.__name__} object should exist. Update the existing object instead "  # noqa: EM102, E501
                "of creating a new one."
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
    content_type_field: str,
    items: Iterable[_ModelClass],
    model_cls: type[_ModelClass],
) -> Iterable[_ModelClass]:
    """Returns a list of items that matches a class by content_type"""  # noqa: D401
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
        model_lookups: dict[
            Union[list[type[_ModelClass]], type[_ModelClass]], list[str]
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
        qs = self._chain()  # type: ignore  # noqa: PGH003

        for model_classes, lookups in model_lookups.items():
            model_classes = (  # noqa: PLW2901
                model_classes
                if isinstance(model_classes, Iterable)
                else [model_classes]
            )
            for model_cls in model_classes:
                key = (content_type_field, model_cls)

                qs._prefetch_generic_related_lookups[key] = [  # noqa: SLF001
                    *qs._prefetch_generic_related_lookups.get(key, []),  # noqa: SLF001
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
        """Called when a query is evaluated"""  # noqa: D401
        # first fetch non-generic data, this avoid N+1 issues on the generic items themselves  # noqa: E501
        super()._fetch_all()

        if self._prefetch_generic_related_lookups and not self._prefetch_generic_done:
            self._prefetch_generic_related_objects()

    def _clone(self):
        """Clone the queryset"""

        c = super()._clone()
        c._prefetch_generic_related_lookups = copy.deepcopy(  # noqa: SLF001
            self._prefetch_generic_related_lookups
        )
        return c


class UserGlobalIdMixin(Model):
    """
    Mixin that adds a standard global_id definition.

    The `global_id` field points to the SSO ID for the user (so, usually the Keycloak
    ID, which is a UUID). We store it as a string in case the SSO source changes.
    We allow a blank value so we can have out-of-band users - we may want a
     Django user that's not connected to an SSO user, for instance.
    """

    global_id = CharField(
        max_length=36,
        blank=True,
        default="",
        help_text="The SSO ID (usually a Keycloak UUID) for the user.",
    )

    class Meta:
        abstract = True
