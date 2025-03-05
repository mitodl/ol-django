import json
import logging
from typing import Optional, Union

from django.contrib.auth import get_user_model
from django.db import transaction
from django_scim import constants
from django_scim.adapters import SCIMUser
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
        return [{"value": self.obj.email, "primary": True}]

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
            "schemas": [constants.SchemaURI.USER],
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

        self.obj.is_active = d.get("active", True)
        self.obj.username = d.get("userName")
        self.obj.first_name = d.get("name", {}).get("givenName", "")
        self.obj.last_name = d.get("name", {}).get("familyName", "")
        self.obj.scim_username = d.get("userName")
        self.obj.scim_external_id = d.get("externalId")

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
            logger.info("User saved. User id %i", self.obj.id)

    def delete(self):
        """
        Update User's is_active to False.
        """
        self.obj.is_active = False
        self.obj.save()
        logger.info("Deactivated user id %i", self.obj.id)

    def handle_add(
        self,
        path: Optional[AttrPath],
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
        self, path: Optional[str], value: Union[str, list, dict]
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

    def _handle_resplace_nested_path(self, nested_path, nested_value):
        """Handle processing a nested path"""
        if nested_path.first_path in self.ATTR_MAP:
            setattr(self.obj, self.ATTR_MAP[nested_path.first_path], nested_value)
        elif nested_path.first_path == ("emails", None, None):
            self.parse_emails(nested_value)
        else:
            return False
        return True

    def handle_replace(
        self,
        path: Optional[AttrPath],
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
                not self._handle_resplace_nested_path(nested_path, nested_value)
                and nested_path.first_path not in self.IGNORED_PATHS
            ):
                logger.debug(
                    "Ignoring SCIM update for path: %s", nested_path.first_path
                )

        self.save()
