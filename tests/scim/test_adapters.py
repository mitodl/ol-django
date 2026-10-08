"""Tests for the SCIM user adapter"""

import pytest
from main.factories import UserFactory
from mitol.scim.adapters import UserAdapter

pytestmark = [pytest.mark.django_db]


class ReplaceOverrideAdapter(UserAdapter):
    """Overrides the nested-path handler under its correct spelling"""

    def __init__(self, obj, request=None, *, lock_user=True):
        super().__init__(obj, request=request, lock_user=lock_user)
        self.handled = []

    def _handle_replace_nested_path(self, nested_path, nested_value):
        if nested_path.first_path == ("fullName", None, None):
            self.handled.append(nested_value)
            return True
        return super()._handle_replace_nested_path(nested_path, nested_value)


class LegacyOverrideAdapter(UserAdapter):
    """Overrides the historical misspelling, as subclasses in the wild may"""

    def __init__(self, obj, request=None, *, lock_user=True):
        super().__init__(obj, request=request, lock_user=lock_user)
        self.handled = []

    def _handle_resplace_nested_path(self, nested_path, nested_value):
        if nested_path.first_path == ("fullName", None, None):
            self.handled.append(nested_value)
            return True
        # delegating under the old name is what such a subclass would do
        return super()._handle_resplace_nested_path(nested_path, nested_value)


def _replace(adapter, path, value):
    """Run a single replace operation through the adapter"""
    adapter.handle_replace(adapter.split_path(path), value, {"op": "replace"})


def test_subclass_override_of_replace_nested_path_is_called():
    """A subclass handler spelled _handle_replace_nested_path must be invoked.

    It previously was not: handle_replace dispatched to
    _handle_resplace_nested_path, so an override spelled the way the name
    reads silently never ran and the attribute was dropped with a 200.
    """
    adapter = ReplaceOverrideAdapter(UserFactory.create())

    _replace(adapter, "fullName", "Billy Bob")

    assert adapter.handled == ["Billy Bob"]


def test_legacy_misspelled_override_still_dispatches():
    """A subclass still matching the old misspelling keeps working, loudly."""
    adapter = LegacyOverrideAdapter(UserFactory.create())

    with pytest.deprecated_call(match="_handle_resplace_nested_path"):
        _replace(adapter, "fullName", "Billy Bob")

    assert adapter.handled == ["Billy Bob"]


def test_legacy_override_can_delegate_to_super():
    """A legacy subclass delegating up under the old name reaches the base.

    The deprecated alias has to stay resolvable for that `super()` call, and
    must point at the plain handler rather than the dispatcher, or delegating
    up would recurse.
    """
    user = UserFactory.create(first_name="Old")
    adapter = LegacyOverrideAdapter(user)

    with pytest.deprecated_call():
        _replace(adapter, "name.givenName", "New")

    user.refresh_from_db()
    assert adapter.handled == []
    assert user.first_name == "New"


def test_attr_map_paths_still_applied():
    """The base handler keeps writing mapped paths onto the user"""
    user = UserFactory.create(first_name="Old")
    adapter = UserAdapter(user)

    _replace(adapter, "name.givenName", "New")

    user.refresh_from_db()
    assert user.first_name == "New"


def test_unmapped_path_is_ignored_without_error():
    """An unmapped path is dropped rather than raising"""
    user = UserFactory.create()
    adapter = UserAdapter(user)

    _replace(adapter, "fullName", "Billy Bob")

    user.refresh_from_db()
    assert not hasattr(user, "fullName")
