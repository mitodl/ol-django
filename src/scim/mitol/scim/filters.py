import operator
from collections.abc import Callable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Model, Q
from mitol.scim.parser import Filters, TermType
from pyparsing import ParseResults


class FilterQuery:
    """Filters for users"""

    model_cls: type[Model]

    attr_map: dict[tuple[str, str | None], tuple[str, ...]]

    related_selects: list[str] = []

    dj_op_mapping = {
        "eq": "exact",
        "ne": "exact",
        "gt": "gt",
        "ge": "gte",
        "lt": "lt",
        "le": "lte",
        "pr": "isnull",
        "co": "contains",
        "sw": "startswith",
        "ew": "endswith",
    }

    dj_negated_ops = ("ne", "pr")

    #: Lookups for an alias path; aliases compare case-insensitively
    dj_alias_op_mapping = {
        "eq": "iexact",
        "ne": "iexact",
        "co": "icontains",
        "sw": "istartswith",
        "ew": "iendswith",
    }

    dj_op_mapping_per_field_overrides: dict[tuple[str, str | None], dict[str, str]] = {}

    @classmethod
    def _filter_expr(cls, parsed: ParseResults) -> Q:
        if parsed is None:
            msg = "Expected a filter, got: None"
            raise ValueError(msg)

        if parsed.term_type == TermType.attr_expr:
            return cls._attr_expr(parsed)

        msg = f"Unsupported term type: {parsed.term_type}"
        raise ValueError(msg)

    @classmethod
    def get_attr_aliases(
        cls,
        scim_keys: tuple[str, str | None],  # noqa: ARG003
    ) -> tuple[tuple[str, ...], ...]:
        """
        Return extra model paths a SCIM attribute also matches.

        A comparison matches if the attribute's ``attr_map`` path or any alias
        matches.

        :param scim_keys: the (attribute, sub-attribute) pair being compared
        :returns: the alias paths, each a tuple of model field names
        :rtype: tuple[tuple[str, ...], ...]
        """
        return ()

    @classmethod
    def _lookup(cls, fields: tuple[str | None, ...], dj_op: str, value) -> Q:
        path = "__".join(part for part in (*fields, dj_op) if part is not None)
        return Q(**{path: value})

    @classmethod
    def _attr_expr(cls, parsed: ParseResults) -> Q:
        scim_keys = (parsed.attr_name, parsed.sub_attr)

        field_op_overrides = cls.dj_op_mapping_per_field_overrides.get(scim_keys, {})

        op_name = parsed.comparison_operator.lower()
        dj_op = field_op_overrides.get(op_name, cls.dj_op_mapping[op_name])

        q = cls._lookup(cls.attr_map.get(scim_keys, scim_keys), dj_op, parsed.value)

        alias_dj_op = cls.dj_alias_op_mapping.get(op_name, cls.dj_op_mapping[op_name])
        for alias in cls.get_attr_aliases(scim_keys):
            q |= cls._lookup(alias, alias_dj_op, parsed.value)

        if parsed.comparison_operator in cls.dj_negated_ops:
            q = ~q

        return q

    @classmethod
    def _filters(cls, parsed: ParseResults) -> Q:
        parsed_iter = iter(parsed)
        q = cls._filter_expr(next(parsed_iter))

        try:
            while operator := cls._logical_op(next(parsed_iter)):
                filter_q = cls._filter_expr(next(parsed_iter))

                # combine the previous and next Q() objects using the bitwise operator
                q = operator(q, filter_q)
        except StopIteration:
            pass

        return q

    @classmethod
    def _logical_op(cls, parsed: ParseResults) -> Callable[[Q, Q], Q] | None:
        """Convert a defined operator to the corresponding bitwise operator"""
        if parsed is None:
            return None

        if parsed.logical_operator.lower() == "and":
            return operator.and_
        elif parsed.logical_operator.lower() == "or":
            return operator.or_
        else:
            msg = f"Unexpected operator: {parsed.operator}"
            raise ValueError(msg)

    @classmethod
    def search(cls, filter_query, request=None):  # noqa: ARG003
        """Create a search query"""
        parsed = Filters.parse_string(filter_query, parse_all=True)

        return cls.model_cls.objects.select_related(*cls.related_selects).filter(
            cls._filters(parsed)
        )


class UserFilterQuery(FilterQuery):
    """FilterQuery for User"""

    attr_map: dict[tuple[str, str | None], tuple[str, ...]] = {
        ("userName", None): ("username",),
        ("emails", "value"): ("email",),
        ("active", None): ("is_active",),
        ("name", "givenName"): ("first_name",),
        ("name", "familyName"): ("last_name",),
    }

    related_selects = []

    dj_op_mapping_per_field_overrides = {
        ("emails", "value"): {
            "eq": "iexact",
            "ne": "iexact",
            "co": "contains",
            "sw": "startswith",
            "ew": "endswith",
        },
        ("emails", None): {
            "eq": "iexact",
            "ne": "iexact",
            "co": "contains",
            "sw": "startswith",
            "ew": "endswith",
        },
    }

    model_cls = get_user_model()

    @classmethod
    def get_attr_aliases(
        cls, scim_keys: tuple[str, str | None]
    ) -> tuple[tuple[str, ...], ...]:
        """
        Match userName against MITOL_SCIM_USERNAME_FILTER_FIELDS too.

        A SCIM client looks a user up by its own username. When the app's
        username is a different value (e.g. a handle chosen before the client
        managed the account), comparing against username alone finds nobody,
        and the client then POSTs a duplicate that fails on uniqueness.

        :param scim_keys: the (attribute, sub-attribute) pair being compared
        :returns: the alias paths, each a tuple of model field names
        :rtype: tuple[tuple[str, ...], ...]
        """
        if scim_keys == ("userName", None):
            return tuple(
                (field,)
                for field in settings.MITOL_SCIM_USERNAME_FILTER_FIELDS
                if field
            )
        return super().get_attr_aliases(scim_keys)
