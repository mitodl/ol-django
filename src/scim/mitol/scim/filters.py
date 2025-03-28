import operator
from collections.abc import Callable
from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Model, Q
from pyparsing import ParseResults

from mitol.scim.parser import Filters, TermType


class FilterQuery:
    """Filters for users"""

    model_cls: type[Model]

    attr_map: dict[tuple[str, Optional[str]], tuple[str, ...]]

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
    def _attr_expr(cls, parsed: ParseResults) -> Q:
        dj_op = cls.dj_op_mapping[parsed.comparison_operator.lower()]

        scim_keys = (parsed.attr_name, parsed.sub_attr)

        path_parts = list(
            filter(
                lambda part: part is not None,
                (
                    *cls.attr_map.get(scim_keys, scim_keys),
                    dj_op,
                ),
            )
        )
        path = "__".join(path_parts)

        q = Q(**{path: parsed.value})

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

    attr_map: dict[tuple[str, Optional[str]], tuple[str, ...]] = {
        ("userName", None): ("username",),
        ("emails", "value"): ("email",),
        ("active", None): ("is_active",),
        ("name", "givenName"): ("first_name",),
        ("name", "familyName"): ("last_name",),
    }

    related_selects = []

    model_cls = get_user_model()
