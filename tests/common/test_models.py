"""Tests for common models"""

from datetime import datetime, timedelta
from functools import cached_property
from random import choice, randint, sample

import pytest
import pytz
from django.contrib.auth import get_user_model
from django.db import IntegrityError, models, transaction
from freezegun import freeze_time
from libraries.models import Author, Book, Media
from main.models import (
    AuditableTestModel,
    AuditableTestModelAudit,
    CachedPropertyChild,
    CachedPropertyModel,
    CachedPropertyOwner,
    Root,
    Updateable,
)
from mitol.common.factories import UserFactory
from mitol.common.models import CachedPropertiesMixin, TimestampedModel
from mitol.common.utils.serializers import serialize_model_object

pytestmark = pytest.mark.django_db


def test_prefetch_generic_related(django_assert_num_queries):
    """Test prefetch over a many-to-one relation"""
    authors = [Author.objects.create(name=f"A{i}") for i in range(5)]
    books = [
        Book.objects.create(title=f"B{i}", author=choice(authors))  # noqa: S311
        for i in range(10)
    ]

    author_pool = [Author.objects.create(name=f"MA{i}") for i in range(5)]
    medias = []
    for i in range(10):
        m = Media.objects.create(title=f"M{i}")
        m.authors.set(sample(author_pool, randint(1, 3)))  # noqa: S311
        medias.append(m)

    roots = [
        Root.objects.create(content_object=choice(books))  # noqa: S311
        for _ in range(5)
    ] + [Root.objects.create(content_object=choice(medias)) for _ in range(5)]  # noqa: S311

    with django_assert_num_queries(0):
        # verify the prefetch is lazy
        query = Root.objects.prefetch_related(
            "content_type"  # need this to avoid N+1 on this relation
        ).prefetch_generic_related(
            "content_type",
            {
                Book: ["content_object__author"],
                Media: ["content_object__authors"],
            },
        )

    # 1 query each for Root, ContentType, Book, Author (book.author FK),
    # Media, and Author (media.authors M2M)
    with django_assert_num_queries(6):
        assert len(query) == len(roots)
        for item in query:
            if isinstance(item.content_object, Book):
                assert item.content_object.author is not None
            else:
                # .all() shouldn't cause a re-evaluation
                assert len(item.content_object.authors.all()) > 0


@pytest.mark.parametrize("pass_updated_on", [True, False])
def test_timestamped_model(pass_updated_on):
    """Verify that TimestampedModel handles update() calls correctly"""
    initial_frozen_datetime = datetime(2020, 6, 9, 12, 14, 56, tzinfo=pytz.utc)
    second_frozen_datetime = initial_frozen_datetime + timedelta(minutes=5)
    passed_updated_on = initial_frozen_datetime + timedelta(minutes=10)
    expected_updated_on = (
        passed_updated_on if pass_updated_on else second_frozen_datetime
    )

    with freeze_time(initial_frozen_datetime):
        obj = Updateable.objects.create()
    assert obj.updated_on == initial_frozen_datetime
    assert obj.created_on == initial_frozen_datetime

    with freeze_time(second_frozen_datetime):
        Updateable.objects.update(
            **(dict(updated_on=passed_updated_on) if pass_updated_on else {})  # noqa: C408
        )

    obj.refresh_from_db()

    assert obj.updated_on == expected_updated_on
    assert obj.created_on == initial_frozen_datetime


def test_auditable_model():
    """Verify that AuditableModel to_dict works correctly"""
    auditable_instance = AuditableTestModel.objects.create()
    user = UserFactory.create()
    data = auditable_instance.to_dict()
    assert serialize_model_object(auditable_instance) == data

    # Make sure audit object is created
    assert AuditableTestModelAudit.objects.count() == 0
    # auditable_instance.status = FinancialAidStatus.AUTO_APPROVED  # noqa: ERA001
    auditable_instance.save_and_log(user)
    assert AuditableTestModelAudit.objects.count() == 1


@pytest.mark.django_db
def test_global_id_is_unique_but_allows_many_unset():
    """
    global_id refuses duplicates while leaving out-of-band users unconstrained.

    This is the whole reason unset is NULL rather than "": SQL treats NULLs as
    distinct under a unique constraint and empty strings as equal, so storing
    "" would cap the estate at exactly one user without an SSO account.
    """
    User = get_user_model()

    unset = [
        User.objects.create(username=f"unset-{i}", email=f"unset-{i}@example.com")
        for i in range(3)
    ]
    assert all(user.global_id is None for user in unset)

    User.objects.create(
        username="linked", email="linked@example.com", global_id="a-global-id"
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(
            username="fork", email="fork@example.com", global_id="a-global-id"
        )


# How many children the cached_property_instance fixture starts with.
INITIAL_CHILD_COUNT = 2


@pytest.fixture
def cached_property_instance():
    """Build a CachedPropertyModel with children, read back out of the database"""
    owner = CachedPropertyOwner.objects.create(name="first owner")
    instance = CachedPropertyModel.objects.create(title="T", note="a note", owner=owner)
    CachedPropertyChild.objects.create(parent=instance, name="a")
    CachedPropertyChild.objects.create(parent=instance, name="b")
    return CachedPropertyModel.objects.get(pk=instance.pk)


def test_clear_cached_properties_on_a_cold_cache_is_a_noop(cached_property_instance):
    """Clearing a property that was never read does nothing rather than raising"""
    assert "child_count" not in cached_property_instance.__dict__

    cached_property_instance.clear_cached_properties()
    cached_property_instance.clear_cached_properties("child_count")

    # the guard must not have read the property into existence
    assert "child_count" not in cached_property_instance.__dict__


def test_clear_cached_properties_forces_a_requery(
    cached_property_instance, django_assert_num_queries
):
    """A cleared property is recomputed on the next read"""
    with django_assert_num_queries(1):
        assert cached_property_instance.child_count == INITIAL_CHILD_COUNT
    with django_assert_num_queries(0):
        assert cached_property_instance.child_count == INITIAL_CHILD_COUNT

    CachedPropertyChild.objects.create(parent=cached_property_instance, name="c")
    cached_property_instance.clear_cached_properties("child_count")

    with django_assert_num_queries(1):
        assert cached_property_instance.child_count == INITIAL_CHILD_COUNT + 1


def test_discovery_finds_both_cached_property_flavors():
    """
    Discover cached properties of both flavors.

    `functools.cached_property` and `django.utils.functional.cached_property`
    are distinct classes, and this org uses both.
    """
    names = CachedPropertyModel.get_cached_property_names()

    assert "child_count" in names  # functools
    assert "child_names" in names  # django.utils.functional
    # nothing Django puts on a model class should be picked up as well
    assert names == frozenset(
        {"child_count", "child_names", "owner_name", "inherited_label"}
    )


def test_discovery_finds_cached_properties_from_base_classes():
    """A cached property reachable only through the MRO is discovered"""
    assert "inherited_label" not in vars(CachedPropertyModel)
    assert "inherited_label" in CachedPropertyModel.get_cached_property_names()


def test_clear_cached_properties_rejects_an_unknown_name(cached_property_instance):
    """An unrecognised name raises - a silent miss is how staleness returns"""
    assert cached_property_instance.child_count == INITIAL_CHILD_COUNT

    with pytest.raises(AttributeError, match="child_cont"):
        cached_property_instance.clear_cached_properties("child_cont", "child_count")

    # nothing was cleared: the call failed before touching any cache
    assert cached_property_instance.__dict__["child_count"] == INITIAL_CHILD_COUNT


def test_mixin_must_precede_model_in_the_bases():
    """
    A class that lists `Model` first raises rather than silently not clearing.

    `Model.refresh_from_db` would win the MRO, so every refresh on such a
    model would reload its fields and leave every cached property populated -
    no error, no eviction, exactly the staleness this mixin exists to remove.
    """
    with pytest.raises(TypeError, match="CachedPropertiesMixin"):

        class Backwards(models.Model, CachedPropertiesMixin):
            """Test-only model with the bases the wrong way round"""

            class Meta:
                abstract = True


def test_base_order_is_checked_against_the_whole_mro():
    """
    `Model` reached through an abstract base still counts as preceding.

    This is the likelier spelling of the mistake - nobody inherits `Model`
    directly - and the one a `__bases__` check misses: `Model` is not among
    this class's own bases, so such a check would find nothing to compare and
    wave it through.
    """
    with pytest.raises(TypeError, match="CachedPropertiesMixin"):

        class Backwards(TimestampedModel, CachedPropertiesMixin):
            """Test-only model inheriting Model through an abstract base"""

            class Meta:
                abstract = True


def test_a_subclass_that_names_the_mixin_nowhere_is_accepted():
    """A subclass inherits the order through the MRO and is left alone"""

    class Correct(CachedPropertiesMixin, models.Model):
        """Test-only model with the bases in the documented order"""

        class Meta:
            abstract = True

        @cached_property
        def label(self):
            """Cached on the parent"""
            return "correct"

    class Grandchild(Correct):
        """Test-only subclass that names `CachedPropertiesMixin` nowhere"""

        class Meta:
            abstract = True

    assert CachedPropertiesMixin not in Grandchild.__bases__
    assert Grandchild.get_cached_property_names() == frozenset({"label"})


def test_discovery_honors_a_shadowed_cached_property():
    """
    A name is only reported when the winning definition is a cached property.

    Unioning the whole MRO would keep reporting the parent's cached property,
    so `clear_cached_properties` would accept the name and then do nothing -
    the plain `property` has no deleter, so the `del` raises `AttributeError`
    and the guard swallows it.
    """

    class Base(CachedPropertiesMixin):
        """Test-only parent defining `label` as a cached property"""

        @cached_property
        def label(self):
            """Cached on the parent"""
            return "parent"

    class Shadowed(Base):
        """Test-only child overriding `label` with a plain property"""

        @property
        def label(self):
            """Not cached on the child"""
            return "child"

    assert "label" in Base.get_cached_property_names()
    assert "label" not in Shadowed.get_cached_property_names()
    with pytest.raises(AttributeError, match="label"):
        Shadowed().clear_cached_properties("label")


def test_refresh_from_db_clears_every_cached_property(cached_property_instance):
    """A full refresh drops all of them"""
    assert cached_property_instance.child_count == INITIAL_CHILD_COUNT
    assert cached_property_instance.child_names == ["a", "b"]
    assert cached_property_instance.owner_name == "first owner"
    assert cached_property_instance.inherited_label == "<T>"

    CachedPropertyChild.objects.create(parent=cached_property_instance, name="c")
    cached_property_instance.refresh_from_db()

    assert not (
        set(cached_property_instance.__dict__)
        & CachedPropertyModel.get_cached_property_names()
    )
    assert cached_property_instance.child_count == INITIAL_CHILD_COUNT + 1


def test_refresh_from_db_with_a_loaded_field_clears_every_cached_property(
    cached_property_instance,
):
    """
    Narrowing the reload does not narrow the eviction.

    The named field was loaded, so any cached property could have read it and
    there is nothing on the instance that says which ones did.
    """
    assert cached_property_instance.owner_name == "first owner"
    assert cached_property_instance.child_count == INITIAL_CHILD_COUNT

    other = CachedPropertyOwner.objects.create(name="second owner")
    CachedPropertyModel.objects.filter(pk=cached_property_instance.pk).update(
        owner=other
    )
    CachedPropertyChild.objects.create(parent=cached_property_instance, name="c")

    cached_property_instance.refresh_from_db(fields=["owner"])

    assert cached_property_instance.owner_name == "second owner"
    assert cached_property_instance.child_count == INITIAL_CHILD_COUNT + 1


def test_refresh_from_db_with_one_loaded_field_among_deferred_ones_clears(
    cached_property_instance,
):
    """
    The deferred test is a subset, not an intersection.

    One loaded name among the deferred ones is enough: a cached property
    could have read that one, and the skip has no way to tell.
    """
    instance = CachedPropertyModel.objects.only("id", "title", "owner").get(
        pk=cached_property_instance.pk
    )
    assert instance.get_deferred_fields() == {"note"}
    assert instance.child_count == INITIAL_CHILD_COUNT

    CachedPropertyChild.objects.create(parent=instance, name="c")
    instance.refresh_from_db(fields=["note", "title"])

    assert instance.child_count == INITIAL_CHILD_COUNT + 1


def test_refresh_from_db_clears_a_field_that_is_no_longer_deferred(
    cached_property_instance,
):
    """
    The skip tracks deferredness, not the field name.

    Once the field has been loaded, a cached property could have read it, so
    the second refresh of the same name has to clear.
    """
    instance = CachedPropertyModel.objects.only("id", "title", "owner").get(
        pk=cached_property_instance.pk
    )
    assert instance.note == "a note"  # loads it, so it is no longer deferred
    assert instance.child_count == INITIAL_CHILD_COUNT

    CachedPropertyChild.objects.create(parent=instance, name="c")
    instance.refresh_from_db(fields=["note"])

    assert instance.child_count == INITIAL_CHILD_COUNT + 1


def test_refresh_from_db_with_no_fields_clears_nothing(
    cached_property_instance, django_assert_num_queries
):
    """An empty `fields` is Django's early return, and evicts nothing"""
    assert cached_property_instance.child_count == INITIAL_CHILD_COUNT

    with django_assert_num_queries(0):
        cached_property_instance.refresh_from_db(fields=[])
        assert cached_property_instance.child_count == INITIAL_CHILD_COUNT


def test_refresh_from_db_with_a_prefetch_name_clears_the_cached_properties(
    cached_property_instance,
):
    """
    Django resolves a prefetched name out of `fields` before doing anything
    else, mutating the list it was handed and returning early once nothing is
    left. The eviction still has to happen, so whether to evict is decided
    before delegating.
    """
    instance = CachedPropertyModel.objects.prefetch_related("children").get(
        pk=cached_property_instance.pk
    )
    assert instance.child_count == INITIAL_CHILD_COUNT

    CachedPropertyChild.objects.create(parent=instance, name="c")
    instance.refresh_from_db(fields=["children"])

    assert instance.child_count == INITIAL_CHILD_COUNT + 1


@pytest.mark.parametrize("wrap", [iter, tuple, set, list])
def test_refresh_from_db_accepts_any_iterable_for_fields(
    cached_property_instance, wrap
):
    """
    `fields` is documented as any iterable, and the refresh still has to happen.

    `iter` is the regression guard: reading a one-shot iterable for the
    narrowing and then handing the drained original to Django made the whole
    refresh a silent no-op. The other three are signature coverage and pass
    either way.
    """
    CachedPropertyModel.objects.filter(pk=cached_property_instance.pk).update(
        note="changed"
    )

    cached_property_instance.refresh_from_db(fields=wrap(["note"]))

    assert cached_property_instance.note == "changed"


def test_refresh_from_db_decides_to_evict_from_a_one_shot_iterator(
    cached_property_instance,
):
    """
    The eviction decision has to survive a one-shot `fields` too.

    The test above covers the other half - Django gets the names and the row
    is refreshed. Reading `fields` straight through to decide whether to
    evict would drain it before Django ever saw it, and the row would come
    back unchanged.
    """
    assert cached_property_instance.owner_name == "first owner"

    other = CachedPropertyOwner.objects.create(name="second owner")
    CachedPropertyModel.objects.filter(pk=cached_property_instance.pk).update(
        owner=other
    )

    cached_property_instance.refresh_from_db(fields=iter(["owner"]))

    assert cached_property_instance.owner_name == "second owner"


def test_deferred_field_access_clears_nothing(
    cached_property_instance, django_assert_num_queries
):
    """
    DeferredAttribute.__get__ refreshes with fields=[<deferred field>], so an
    unconditional clear would add queries to every .only()/.defer() instance.
    Skipping is safe because reading a deferred field is what loads it: the
    field is still absent here, so no cached property can derive from it.
    """
    instance = CachedPropertyModel.objects.only("id", "title", "owner").get(
        pk=cached_property_instance.pk
    )
    assert instance.child_count == INITIAL_CHILD_COUNT

    with django_assert_num_queries(1):
        # one query for the deferred field itself, and nothing evicted
        assert instance.note == "a note"
    with django_assert_num_queries(0):
        assert instance.child_count == INITIAL_CHILD_COUNT


def test_discovery_is_memoized_and_issues_no_queries(django_assert_num_queries):
    """Discovery is a class-level walk, so it is free at runtime"""
    with django_assert_num_queries(0):
        names = CachedPropertyModel.get_cached_property_names()
        assert CachedPropertyModel.get_cached_property_names() is names
