"""
Common model classes
"""

import copy
import functools
from collections.abc import Iterable
from contextlib import suppress
from typing import ClassVar, TypeVar, Union

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
from django.utils.functional import cached_property as django_cached_property
from mitol.common.utils.datetime import now_in_utc

# functools.cached_property and django.utils.functional.cached_property are
# distinct classes and this org uses both, sometimes in the same codebase, so
# an isinstance check against only one silently no-ops on the other - which is
# the failure mode CachedPropertiesMixin exists to prevent.
_CACHED_PROPERTY_CLASSES = (functools.cached_property, django_cached_property)


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

    It is unique: it is the identity key an API gateway resolves users by, and
    without the constraint a get-then-create under concurrency silently forks
    an account in two.

    Unset is NULL rather than "", so that out-of-band users - a Django user
    with no SSO account behind it - can still exist in any number. SQL treats
    NULLs as distinct under a unique constraint; empty strings it does not,
    which would cap the estate at exactly one unlinked user.
    """

    global_id = CharField(
        max_length=36,
        null=True,
        blank=True,
        default=None,
        unique=True,
        help_text="The SSO ID (usually a Keycloak UUID) for the user.",
    )

    class Meta:
        abstract = True


class CachedPropertiesMixin:
    """
    Makes a model's cached properties invalidatable, and teaches
    `refresh_from_db` to drop them.

    `Model.refresh_from_db` clears `_prefetched_objects_cache`, cached foreign
    keys, cached reverse one-to-ones and cached generic foreign keys, but it
    cannot know about a `functools` or `django.utils.functional` cache, so it
    leaves those populated. A cached property derived from a relation
    therefore stays stale after the relation changes, and every call site
    invents its own eviction instead.

    This is a plain mixin, not an abstract model: it adds no fields and no
    Meta, so it composes onto any model. It must precede `Model` in the bases
    so that this `refresh_from_db` wins the MRO:

        class Enrollment(CachedPropertiesMixin, TimestampedModel):
            ...
    """

    # Optional map of {cached property name: {field/relation names it derives
    # from}}. Consulted only to narrow `refresh_from_db(fields=...)`; a
    # property that is not declared here is never cleared by a narrowed
    # refresh.
    cached_property_sources: ClassVar[dict[str, set[str]]] = {}

    @classmethod
    def get_cached_property_names(cls) -> frozenset[str]:
        """
        Every cached property defined on this class or any of its bases.

        Memoized on the class - read out of `cls.__dict__` rather than by
        attribute lookup, so a subclass computes its own answer instead of
        inheriting its parent's.
        """
        names = cls.__dict__.get("_cached_property_names")
        if names is None:
            names = frozenset(
                name
                for klass in cls.__mro__
                for name, attr in vars(klass).items()
                if isinstance(attr, _CACHED_PROPERTY_CLASSES)
            )
            unmatched = sorted(set(cls.cached_property_sources) - names)
            if unmatched:
                msg = (
                    f"{cls.__name__}.cached_property_sources declares "
                    f"{', '.join(unmatched)}, which is not a cached property "
                    f"on {cls.__name__}. A narrowed refresh_from_db would "
                    f"never clear it."
                )
                raise AttributeError(msg)
            cls._cached_property_names = names
        return names

    def clear_cached_properties(self, *names: str) -> None:
        """
        Drop the named cached properties, or all of them when given none.

        An unrecognised name raises rather than quietly doing nothing: a
        silent no-op is how a renamed property becomes a reintroduced
        staleness bug.
        """
        known = self.get_cached_property_names()
        unknown = sorted(set(names) - known)
        if unknown:
            msg = (
                f"{type(self).__name__} has no cached property named: "
                f"{', '.join(unknown)}"
            )
            raise AttributeError(msg)

        for name in names or known:
            # cached_property defines only __set_name__ and __get__, so `del`
            # falls through to object.__delattr__, which pops the instance
            # __dict__ entry and raises AttributeError on a cold cache.
            # hasattr() is not usable as the guard: it calls __get__ and so
            # populates the very cache being cleared.
            with suppress(AttributeError):
                delattr(self, name)

    @classmethod
    def _cached_properties_deriving_from(cls, fields: Iterable[str]) -> set[str]:
        """Find the cached properties declaring any of `fields` as a source"""
        refreshed = set(fields)
        return {
            name
            for name, sources in cls.cached_property_sources.items()
            if refreshed & set(sources)
        }

    def refresh_from_db(self, using=None, fields=None, **kwargs):
        """
        Reload field values from the database and drop stale cached properties.

        A full refresh clears every cached property. A refresh narrowed with
        `fields` clears only the cached properties that declare one of those
        fields in `cached_property_sources`, which matches Django's own
        contract for `fields` - it drops only the prefetch entries named in
        `fields` and clears only relations where `rel.name in fields`.
        Narrowing matters because `DeferredAttribute.__get__` calls
        `refresh_from_db(fields=[field_name])` for every deferred-field access
        on a `.only()`/`.defer()` instance, where an unconditional clear would
        add queries to the paths most likely to have been tuned.

        `using` and `fields` are named explicitly and the rest passed through
        because `from_queryset` only exists from Django 5.1 and this package
        supports Django 4.2. `arefresh_from_db` delegates to this method via
        `sync_to_async` on every supported version, so the async path needs no
        separate override.
        """
        # Django before 5.1 removes prefetch-cache names from the very list it
        # was handed, so snapshot what was asked for before delegating.
        requested = None if fields is None else list(fields)

        super().refresh_from_db(using=using, fields=fields, **kwargs)

        if requested is None:
            self.clear_cached_properties()
            return
        stale = self._cached_properties_deriving_from(requested)
        # Guarded: clear_cached_properties() with no names clears everything,
        # which is the opposite of what a narrowed refresh should do.
        if stale:
            self.clear_cached_properties(*stale)
