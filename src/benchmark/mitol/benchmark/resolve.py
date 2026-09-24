"""
Resolution of the ``$token`` references used throughout a benchmark config.

Seed steps, target parameters and auth blocks are data, so the only way they
can refer to a knob, to a previously created object, or to a value exported by
the seed is through a textual token. Every token is resolved here, in one
place, so the same spelling means the same thing wherever it appears.

Tokens (a string is a token only if it *starts* with ``$``):

``$knob:NAME``      the value of a shape knob
``$ids:KEY``        a scalar exported by the seed (see ``[seed.export]``)
``$env:VAR``        an environment variable, error if unset
``$index``          the 0-based index of the object being built
``$blob:N``         filler text of roughly N bytes; N may be a knob name
``$ref:STEP``       the first object created by an earlier step
``$ref:STEP[i]``    the i-th object created by an earlier step
``$cycle:STEP``     that step's objects, cycled by ``$index``
``$sample:STEP:N``  N of that step's objects, sampled from the seeded RNG
``$all:STEP``       every object created by an earlier step
``$$``              a literal ``$`` — how you write a string that starts with one

Anything else is returned unchanged, except that a plain string is run through
``str.format`` with ``index`` and every knob available, so ``"Book {index}"``
works without a token.
"""

from __future__ import annotations

import os
import random  # shape sampling, not security
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

_BLOB_PARAGRAPH = (
    "<p>Placeholder body copy standing in for the real rich text this column "
    "holds in production, so that the row width is representative.</p>"
)


class ResolutionError(ValueError):
    """A ``$token`` could not be resolved."""


@dataclass
class ResolutionContext:
    """
    Everything a ``$token`` may refer to at the point it is resolved.

    ``objects`` is empty outside the seed step: ``$ref``/``$cycle``/``$sample``
    only mean something while the dataset is being built. Target parameters
    reach seeded rows through ``$ids`` instead, because they run in a different
    process against a database that is already populated.
    """

    knobs: Mapping[str, Any] = field(default_factory=dict)
    ids: Mapping[str, Any] = field(default_factory=dict)
    index: int = 0
    objects: Mapping[str, Sequence[Any]] = field(default_factory=dict)
    rng: random.Random = field(default_factory=lambda: random.Random(1234))  # noqa: S311

    def at(self, index: int) -> ResolutionContext:
        """Return a copy of this context positioned at ``index``."""
        return ResolutionContext(
            knobs=self.knobs,
            ids=self.ids,
            index=index,
            objects=self.objects,
            rng=self.rng,
        )


def blob_text(nbytes: int) -> str:
    """Return roughly ``nbytes`` of plausible rich text."""
    if nbytes <= 0:
        return ""
    repeats = nbytes // len(_BLOB_PARAGRAPH) + 1
    return (_BLOB_PARAGRAPH * repeats)[:nbytes]


def _as_int(value: Any, token: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        msg = f"{token}: expected an integer, got {value!r}"
        raise ResolutionError(msg) from exc


def _step_objects(name: str, ctx: ResolutionContext, token: str) -> Sequence[Any]:
    if name not in ctx.objects:
        known = ", ".join(sorted(ctx.objects)) or "none yet"
        msg = (
            f"{token}: no seed step named {name!r} has run yet "
            f"(steps available here: {known})"
        )
        raise ResolutionError(msg)
    objects = ctx.objects[name]
    if not objects:
        msg = f"{token}: seed step {name!r} created no objects"
        raise ResolutionError(msg)
    return objects


def _resolve_knob(arg: str, ctx: ResolutionContext, token: str) -> Any:
    if arg not in ctx.knobs:
        known = ", ".join(sorted(ctx.knobs)) or "none declared"
        msg = f"{token}: unknown knob {arg!r} (declared knobs: {known})"
        raise ResolutionError(msg)
    return ctx.knobs[arg]


def _resolve_ids(arg: str, ctx: ResolutionContext, token: str) -> Any:
    if arg not in ctx.ids:
        known = ", ".join(sorted(ctx.ids)) or "nothing exported"
        msg = (
            f"{token}: {arg!r} was not exported by the seed "
            f"(add it to [seed.export]; exported: {known})"
        )
        raise ResolutionError(msg)
    return ctx.ids[arg]


def _resolve_env(arg: str, token: str) -> str:
    value = os.environ.get(arg)
    if value is None:
        msg = f"{token}: environment variable {arg!r} is not set"
        raise ResolutionError(msg)
    return value


def _resolve_blob(arg: str, ctx: ResolutionContext, token: str) -> str:
    size = ctx.knobs.get(arg, arg)
    return blob_text(_as_int(size, token))


def _resolve_ref(arg: str, ctx: ResolutionContext, token: str) -> Any:
    name, _, suffix = arg.partition("[")
    objects = _step_objects(name, ctx, token)
    if not suffix:
        return objects[0]
    position = _as_int(suffix.rstrip("]"), token)
    if position >= len(objects):
        msg = f"{token}: step {name!r} created only {len(objects)} object(s)"
        raise ResolutionError(msg)
    return objects[position]


def _resolve_sample(arg: str, ctx: ResolutionContext, token: str) -> list[Any]:
    name, _, count = arg.partition(":")
    objects = _step_objects(name, ctx, token)
    wanted = min(_as_int(count, token), len(objects))
    return ctx.rng.sample(list(objects), wanted)


def _resolve_cycle(arg: str, ctx: ResolutionContext, token: str) -> Any:
    objects = _step_objects(arg, ctx, token)
    return objects[ctx.index % len(objects)]


# Every handler takes (argument, context, whole-token) so dispatch stays flat.
_HANDLERS = {
    "knob": _resolve_knob,
    "ids": _resolve_ids,
    "env": lambda arg, _ctx, token: _resolve_env(arg, token),
    "blob": _resolve_blob,
    "ref": _resolve_ref,
    "cycle": _resolve_cycle,
    "sample": _resolve_sample,
    "all": lambda arg, ctx, token: list(_step_objects(arg, ctx, token)),
}


def _resolve_token(token: str, ctx: ResolutionContext) -> Any:
    verb, _, arg = token[1:].partition(":")
    if verb == "index":
        return ctx.index
    handler = _HANDLERS.get(verb)
    if handler is None:
        known = ", ".join(sorted([*_HANDLERS, "index"]))
        msg = f"{token}: unknown token type ${verb} (known: {known})"
        raise ResolutionError(msg)
    if not arg:
        msg = f"{token}: expected ${verb}:<argument>"
        raise ResolutionError(msg)
    return handler(arg, ctx, token)


def _resolve_string(value: str, ctx: ResolutionContext) -> Any:
    if value.startswith("$$"):
        return value[1:]
    if value.startswith("$"):
        return _resolve_token(value, ctx)
    if "{" not in value:
        return value
    try:
        return value.format(index=ctx.index, **ctx.knobs)
    except (IndexError, KeyError) as exc:
        msg = f"{value!r}: no such interpolation {exc}"
        raise ResolutionError(msg) from exc


def resolve(value: Any, ctx: ResolutionContext) -> Any:
    """Resolve every ``$token`` in ``value``, recursing into dicts and lists."""
    if isinstance(value, str):
        return _resolve_string(value, ctx)
    if isinstance(value, Mapping):
        return {key: resolve(item, ctx) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [resolve(item, ctx) for item in value]
    return value


def resolve_count(value: Any, ctx: ResolutionContext) -> int:
    """Resolve ``value`` and require the result to be a non-negative integer."""
    resolved = resolve(value, ctx)
    count = _as_int(resolved, f"count {value!r}")
    if count < 0:
        msg = f"count {value!r} resolved to a negative number: {count}"
        raise ResolutionError(msg)
    return count
