import functools
import json
import logging
import warnings
from typing import Union

from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from django_scim import exceptions
from django_scim.adapters import SCIMUser
from mitol.scim.constants import SchemaURI
from scim2_filter_parser.attr_paths import AttrPath

User = get_user_model()


logger = logging.getLogger(__name__)


def get_user_model_for_scim():
    """
    Get function for the django_scim library configuration (USER_MODEL_GETTER).

    Returns:
        model: User model.
    """
    return User


@functools.cache
def lock_free_adapter(adapter_cls: type) -> type:
    """
    Build a variant of `adapter_cls` that does not take a row lock.

    `UserAdapter` takes a `SELECT ... FOR UPDATE` when it is constructed, which
    is what a read-modify-write needs but is pure cost on a read -- `to_dict()`
    only reads, and `django_scim` builds one adapter per serialized object.

    Returns a subclass rather than a `functools.partial` so the class-level
    attributes the views read off the adapter -- `url_name`, `id_field`,
    `resource_type_dict` -- keep resolving. Cached so there is one such class
    per adapter rather than one per request, which keeps `isinstance` checks
    and identity comparisons stable.

    Args:
        adapter_cls (type): the adapter class to derive from

    Returns:
        type: a subclass of `adapter_cls` that never locks
    """

    class LockFreeAdapter(adapter_cls):
        def __init__(self, obj, request=None, **kwargs):
            kwargs["lock_user"] = False
            super().__init__(obj, request=request, **kwargs)

    LockFreeAdapter.__name__ = f"LockFree{adapter_cls.__name__}"
    LockFreeAdapter.__qualname__ = LockFreeAdapter.__name__
    return LockFreeAdapter


class UserAdapter(SCIMUser):
    """
    Custom adapter to extend django_scim library.
    """

    password_changed = False
    activity_changed = False

    resource_type = "User"

    id_field = "scim_id"

    ATTR_MAP = {
        ("active", None, None): "is_active",
        ("name", "givenName", None): "first_name",
        ("name", "familyName", None): "last_name",
        ("userName", None, None): "username",
    }

    IGNORED_PATHS = {
        ("schemas", None, None),
    }

    def __init__(self, obj, request=None, *, lock_user: bool = True):
        super().__init__(obj, request=request)
        if lock_user and self.obj.pk is not None:
            self.obj = User.objects.select_for_update().get(pk=self.obj.pk)

    @property
    def is_new_user(self):
        """

        Returns:
            bool: True is the user does not currently exist,
            False if the user already exists.
        """
        return not bool(self.obj.id)

    @property
    def id(self):
        """
        Return the SCIM id
        """
        return self.obj.scim_id

    @property
    def emails(self):
        """
        Return the email of the user per the SCIM spec.
        """
        return [{"value": self.obj.email.lower(), "primary": True}]

    @property
    def display_name(self):
        """
        Return the displayName of the user per the SCIM spec.
        """
        return f"{self.obj.first_name} {self.obj.last_name}"

    @property
    def meta(self):
        """
        Return the meta object of the user per the SCIM spec.
        """
        return {
            "resourceType": self.resource_type,
            "created": self.obj.created_on.isoformat(timespec="milliseconds"),
            "lastModified": self.obj.updated_on.isoformat(timespec="milliseconds"),
            "location": self.location,
        }

    def to_dict(self):
        """
        Return a ``dict`` conforming to the SCIM User Schema,
        ready for conversion to a JSON object.
        """
        return {
            "id": self.id,
            "externalId": self.obj.scim_external_id,
            "schemas": [SchemaURI.USER],
            "userName": self.obj.username,
            "name": {
                "givenName": self.obj.first_name,
                "familyName": self.obj.last_name,
            },
            "displayName": self.display_name,
            "emails": self.emails,
            "active": self.obj.is_active,
            "groups": [],
            "meta": self.meta,
        }

    def is_nullable(self, attname: str) -> bool:
        """
        Return whether a model field accepts NULL.

        Anything that isn't a concrete field is reported as nullable, since
        there is no column constraint to reason about.

        :param attname: name of the field on the model
        :returns: True if the field accepts NULL
        :rtype: bool
        """
        try:
            return self.obj._meta.get_field(attname).null  # noqa: SLF001
        except FieldDoesNotExist:
            return True

    def set_mapped_attr(self, attname: str, value) -> None:
        """
        Assign a value from a SCIM payload to a field on the user.

        A SCIM client can send an explicit ``null`` for an attribute it has no
        value for. Writing that to a NOT NULL column raises an IntegrityError,
        which django_scim turns into a 500, and a client that treats 500 as
        retryable will resend the same payload forever. Leave the existing
        value in place instead.

        :param attname: name of the field on the model
        :param value: value from the SCIM payload
        """
        if value is None and not self.is_nullable(attname):
            logger.debug("Ignoring null SCIM value for %s", attname)
            return

        setattr(self.obj, attname, value)

    def from_dict(self, d):
        """
        Consume a ``dict`` conforming to the SCIM User Schema, updating the
        internal user object with data from the ``dict``.

        Please note, the user object is not saved within this method. To
        persist the changes made by this method, please call ``.save()`` on the
        adapter. Eg::

            scim_user.from_dict(d)
            scim_user.save()
        """
        self.parse_emails(d.get("emails"))

        username = d.get("userName")

        if not username:
            # userName is REQUIRED per RFC 7643 section 4.1.1. Without this the
            # write fails on the NOT NULL column and the client sees a 500,
            # which it retries.
            msg = "userName is required and may not be null"
            raise exceptions.BadRequestError(msg)

        # a null `name` is equivalent to an absent one: both clear the fields
        name = d.get("name") or {}

        self.obj.is_active = d.get("active", True)
        self.obj.username = username
        self.obj.first_name = name.get("givenName") or ""
        self.obj.last_name = name.get("familyName") or ""
        self.obj.scim_username = username
        self.obj.scim_external_id = d.get("externalId")
        # None, not "": global_id is unique, and NULLs are distinct where
        # empty strings are not - two users with no external id would collide.
        self.obj.global_id = self.obj.scim_external_id or None

    def _save_user(self):
        self.obj.save()

    def _save_related(self):
        pass

    def save(self):
        """
        Save instances of the Profile and User models.
        """
        with transaction.atomic():
            # user must be saved first due to FK Profile -> User
            self._save_user()
            self._save_related()
            logger.info(
                "User saved. User id=%i, global_id=%s", self.obj.id, self.obj.global_id
            )

    def delete(self):
        """
        Update User's is_active to False.
        """
        self.obj.is_active = False
        self.obj.save()
        logger.info("Deactivated user id %i", self.obj.id)

    def handle_add(
        self,
        path: AttrPath | None,
        value: Union[str, list, dict],
        operation: dict,  # noqa: ARG002
    ):
        """
        Handle add operations per:
        https://tools.ietf.org/html/rfc7644#section-3.5.2.1

        Args:
            path (AttrPath)
            value (Union[str, list, dict])
        """
        if path is None:
            return

        if path.first_path == ("externalId", None, None):
            self.obj.scim_external_id = value
            self.obj.save()

    def parse_scim_for_keycloak_payload(self, payload: str) -> dict:
        """
        Parse the payload sent from scim-for-keycloak and normalize it
        """
        result = {}

        for key, value in json.loads(payload).items():
            if key == "schema":
                continue

            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    result[self.split_path(f"{key}.{nested_key}")] = nested_value
            else:
                result[key] = value

        return result

    def parse_path_and_values(
        self, path: str | None, value: Union[str, list, dict]
    ) -> list:
        """Parse the incoming value(s)"""
        if isinstance(value, str):
            # scim-for-keycloak sends this as a noncompliant JSON-encoded string
            if path is None:
                val = json.loads(value)
            else:
                msg = "Called with a non-null path and a str value"
                raise ValueError(msg)
        else:
            val = value

        results = []

        for attr_path, attr_value in val.items():
            if isinstance(attr_value, dict):
                # nested object, we want to recursively flatten it to `first.second`
                results.extend(self.parse_path_and_values(attr_path, attr_value))
            else:
                flattened_path = (
                    f"{path}.{attr_path}" if path is not None else attr_path
                )
                new_path = self.split_path(flattened_path)
                new_value = attr_value
                results.append((new_path, new_value))

        return results

    def _default_validate_op(self, path, value, operation):
        """
        Validate an operation before it is handled.

        scim-for-keycloak omits ``path`` and carries the attribute names in
        ``value``. django_scim builds its validation error message from
        ``operation["path"]``, so an invalid value raises a KeyError there and
        the client gets a retryable 500 in place of the intended 400.
        """
        if path is not None and "path" not in operation:
            operation = {
                **operation,
                "path": ".".join(part for part in path.first_path if part),
            }

        super()._default_validate_op(path, value, operation)

    def _handle_replace_nested_path(self, nested_path, nested_value):
        """Handle processing a nested path"""
        if nested_path.first_path in self.ATTR_MAP:
            self.set_mapped_attr(self.ATTR_MAP[nested_path.first_path], nested_value)
        elif nested_path.first_path == ("emails", None, None):
            self.parse_emails(nested_value)
        else:
            return False
        return True

    # Deprecated alias for the historical misspelling, kept so a subclass that
    # overrode that name can still delegate up through super().
    _handle_resplace_nested_path = _handle_replace_nested_path

    def _dispatch_replace_nested_path(self, nested_path, nested_value):
        """Route a nested path to its handler.

        This method used to be named ``_handle_resplace_nested_path`` - note
        the transposed letters. A subclass that spelled its override the way
        the name reads (``_handle_replace_nested_path``) silently never got
        called, which is the bug this rename fixes. Dispatching through here
        keeps any subclass that matched the historical misspelling working,
        so the rename doesn't trade one silent no-op for another.
        """
        legacy = getattr(type(self), "_handle_resplace_nested_path", None)
        if legacy is not None and legacy is not UserAdapter._handle_replace_nested_path:
            warnings.warn(
                f"{type(self).__name__} overrides _handle_resplace_nested_path, "
                "which is deprecated. Rename it to _handle_replace_nested_path.",
                DeprecationWarning,
                stacklevel=2,
            )
            return legacy(self, nested_path, nested_value)
        return self._handle_replace_nested_path(nested_path, nested_value)

    def handle_replace(
        self,
        path: AttrPath | None,
        value: Union[str, list, dict],
        operation: dict,  # noqa: ARG002
    ):
        """
        Handle the replace operations.

        All operations happen within an atomic transaction.
        """

        if not isinstance(value, dict):
            # Restructure for use in loop below.
            value = {path: value}

        for nested_path, nested_value in (value or {}).items():
            if (
                not self._dispatch_replace_nested_path(nested_path, nested_value)
                and nested_path.first_path not in self.IGNORED_PATHS
            ):
                logger.debug(
                    "Ignoring SCIM update for path: %s", nested_path.first_path
                )

        self.save()
