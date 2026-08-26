"""Close the call graph over "performs a query".

A member counts if its own body runs a query, or if it reaches one through any
chain of calls and property accesses.  The closure is a reverse breadth-first
search from the members that query directly, which visits every node once and
handles recursion and mutual recursion without a depth cap: a member already
marked is never re-enqueued.
"""

from __future__ import annotations

from collections import deque

from mitol.drf_lint.index.model import Member, MemberId, ProjectIndex, QueryHit
from mitol.drf_lint.index.resolve import resolve_ref


def _all_members(index: ProjectIndex) -> dict[MemberId, Member]:
    """Every member in the index, keyed by id."""
    members: dict[MemberId, Member] = {}
    for module in index.modules.values():
        for name, function in module.functions.items():
            members[module.dotted, "", name] = function
        for class_name, info in module.classes.items():
            for name, member in info.members.items():
                members[module.dotted, class_name, name] = member
    return members


def _forward_edges(
    index: ProjectIndex,
    members: dict[MemberId, Member],
    *,
    fallback: str,
) -> dict[MemberId, frozenset[MemberId]]:
    """Resolve every member's outgoing references into concrete member ids."""
    edges: dict[MemberId, frozenset[MemberId]] = {}
    for member_id, member in members.items():
        module, cls_name, _ = member_id
        targets = {
            target
            for target in (
                resolve_ref(index, module, cls_name, ref, fallback=fallback)
                for ref in member.refs
            )
            if target is not None and target != member_id and target in members
        }
        if targets:
            edges[member_id] = frozenset(targets)
    return edges


def propagate(index: ProjectIndex, *, fallback: str = "unique") -> None:
    """Mark every member that transitively performs a query."""
    members = _all_members(index)
    forward = _forward_edges(index, members, fallback=fallback)
    index.edges = forward
    index._hit_cache = {}  # noqa: SLF001

    reverse: dict[MemberId, set[MemberId]] = {}
    for caller, callees in forward.items():
        for callee in callees:
            reverse.setdefault(callee, set()).add(caller)

    querying = {
        member_id
        for member_id, member in members.items()
        if member.forced == "query" or (member.hits and member.forced != "no-query")
    }
    work = deque(querying)
    while work:
        target = work.popleft()
        for caller in reverse.get(target, ()):
            if caller in querying or members[caller].forced == "no-query":
                continue
            querying.add(caller)
            members[caller].via = target
            work.append(caller)

    for member_id in querying:
        members[member_id].queries = True


def transitive_hits(index: ProjectIndex, member_id: MemberId) -> tuple[QueryHit, ...]:
    """Every query reachable from *member_id*, its own included.

    Computed on demand: the checker only ever asks about the handful of
    members a serializer actually touches, so closing this over the whole
    project up front would be wasted work.
    """
    cached = index._hit_cache.get(member_id)  # noqa: SLF001
    if cached is not None:
        return cached

    collected: list[QueryHit] = []
    seen: set[MemberId] = set()
    stack = [member_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        member = index.member(*current)
        if member is None:
            continue
        collected.extend(member.hits)
        stack.extend(index.edges.get(current, ()))

    result = tuple(collected)
    index._hit_cache[member_id] = result  # noqa: SLF001
    return result


def explain(index: ProjectIndex, member_id: MemberId) -> str:
    """Human-readable chain from *member_id* to the query it reaches."""
    parts: list[str] = []
    seen: set[MemberId] = set()
    current: MemberId | None = member_id
    while current is not None and current not in seen:
        seen.add(current)
        _, cls_name, name = current
        parts.append(f"{cls_name}.{name}" if cls_name else name)
        member = index.member(*current)
        current = member.via if member is not None else None
    return " → ".join(parts)
