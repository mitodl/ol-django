"""
SCIM filter parsers
    + _tag_term_type(TermType.attr_name)

This module aims to compliantly parse SCIM filter queries per the spec:
https://datatracker.ietf.org/doc/html/rfc7644#section-3.4.2.2

Note that this implementation defines things slightly differently
because a naive implementation exactly matching the filter grammar will
result in hitting Python's recursion limit because the grammar defines
logical lists (AND/OR chains) as a recursive relationship.

This implementation avoids that by defining separately FilterExpr and
Filter. As a result of this, some definitions are collapsed and removed
(e.g. valFilter => FilterExpr).
"""

from enum import auto

try:
    from enum import StrEnum
except ImportError:
    from strenum import StrEnum

from pyparsing import (
    CaselessKeyword,
    Char,
    Combine,
    DelimitedList,
    FollowedBy,
    Forward,
    Group,
    Literal,
    Suppress,
    Tag,
    alphanums,
    alphas,
    common,
    dbl_quoted_string,
    nested_expr,
    one_of,
    remove_quotes,
    ungroup,
)


class TagName(StrEnum):
    """Tag names"""

    term_type = auto()
    value_type = auto()


class TermType(StrEnum):
    """Tag term type"""

    urn = auto()
    attr_name = auto()
    attr_path = auto()
    attr_expr = auto()
    value_path = auto()
    presence = auto()

    logical_op = auto()
    compare_op = auto()
    negation_op = auto()

    filter_expr = auto()
    filters = auto()


class ValueType(StrEnum):
    """Tag value_type"""

    boolean = auto()
    number = auto()
    string = auto()
    null = auto()


def _tag_term_type(term_type: TermType) -> Tag:
    return Tag(TagName.term_type.name, term_type)


def _tag_value_type(value_type: ValueType) -> Tag:
    return Tag(TagName.value_type.name, value_type)


NameChar = Char(alphanums + "_-")
AttrName = Combine(
    Char(alphas)
    + NameChar[...]
    # ensure we're not somehow parsing an URN
    + ~FollowedBy(":")
).set_results_name("attr_name") + _tag_term_type(TermType.attr_name)

# Example URN-qualifed attr:
# urn:ietf:params:scim:schemas:core:2.0:User:userName
# |--------------- URN --------------------|:| attr |
UrnAttr = Combine(
    Combine(
        Literal("urn:")
        + DelimitedList(
            # characters ONLY if followed by colon
            Char(alphanums + ".-_")[1, ...] + FollowedBy(":"),
            # separator
            Literal(":"),
            # combine everything back into a singular token
            combine=True,
        )[1, ...]
    ).set_results_name("urn")
    # separator between URN and attribute name
    + Literal(":")
    + AttrName
    + _tag_term_type(TermType.urn)
)


SubAttr = ungroup(Combine(Suppress(".") + AttrName)).set_results_name("sub_attr") ^ (
    Tag("sub_attr", None)
)

AttrPath = (
    (
        # match on UrnAttr first
        UrnAttr ^ AttrName
    )
    + SubAttr
    + _tag_term_type(TermType.attr_path)
)

ComparisonOperator = one_of(
    ["eq", "ne", "co", "sw", "ew", "gt", "lt", "ge", "le"],
    caseless=True,
    as_keyword=True,
).set_results_name("comparison_operator") + _tag_term_type(TermType.compare_op)

LogicalOperator = Group(
    one_of(["or", "and"], caseless=True).set_results_name("logical_operator")
    + _tag_term_type(TermType.logical_op)
)

NegationOperator = Group(
    (
        CaselessKeyword("not")
        + _tag_term_type(TermType.negation_op)
        + Tag("negated", True)  # noqa: FBT003
    )[..., 1]
    ^ Tag("negated", False)  # noqa: FBT003
)

ValueTrue = Literal("true").set_parse_action(lambda: True) + _tag_value_type(
    ValueType.boolean
)
ValueFalse = Literal("false").set_parse_action(lambda: False) + _tag_value_type(
    ValueType.boolean
)
ValueNull = Literal("null").set_parse_action(lambda: None) + _tag_value_type(
    ValueType.null
)
ValueNumber = (common.integer | common.fnumber) + _tag_value_type(ValueType.number)
ValueString = dbl_quoted_string.set_parse_action(remove_quotes) + _tag_value_type(
    ValueType.string
)

ComparisonValue = ungroup(
    ValueTrue | ValueFalse | ValueNull | ValueNumber | ValueString
).set_results_name("value")

AttrPresence = Group(
    AttrPath + Literal("pr").set_results_name("presence").set_parse_action(lambda: True)
) + _tag_term_type(TermType.presence)
AttrExpression = AttrPresence | Group(
    AttrPath + ComparisonOperator + ComparisonValue + _tag_term_type(TermType.attr_expr)
)

# these are forward references, so that we can have
# parsers circularly reference themselves
FilterExpr = Forward()
Filters = Forward()

ValuePath = Group(AttrPath + nested_expr("[", "]", Filters)).set_results_name(
    "value_path"
) + _tag_term_type(TermType.value_path)

FilterExpr <<= (
    AttrExpression | ValuePath | (NegationOperator + nested_expr("(", ")", Filters))
) + _tag_term_type(TermType.filter_expr)

Filters <<= (
    # comment to force it to wrap the below for operator precedence
    (FilterExpr + (LogicalOperator + FilterExpr)[...])
    + _tag_term_type(TermType.filters)
)
