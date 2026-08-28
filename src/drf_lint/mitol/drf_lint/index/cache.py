"""On-disk cache of the per-file scan results.

Only the *pre-propagation* facts are cached.  The closure over the call graph
is global -- a new querying property in one file can change the answer for a
member in another -- so it is always recomputed, which is cheap.

Every failure path here is silent: a corrupt or unreadable cache means a
rebuild, never a failed commit.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from mitol.drf_lint import __version__
from mitol.drf_lint.index.model import (
    ClassInfo,
    ImportedName,
    Member,
    MemberRef,
    ModuleInfo,
    QueryHit,
)
from mitol.drf_lint.rules import patterns

FORMAT_VERSION = 1
DEFAULT_CACHE_NAME = ".drf_lint_cache.json"


def config_hash() -> str:
    """Fingerprint of the detection vocabulary, so an upgrade self-invalidates.

    Derived by reflection rather than a hand-maintained list, because a
    vocabulary added to :mod:`~mitol.drf_lint.rules.patterns` and forgotten here
    would serve stale results silently.  Naming each group also keeps two
    different vocabularies from hashing alike.  Over-invalidating costs a
    rebuild; under-invalidating is the bug.
    """
    parts = [__version__]
    parts.extend(
        f"{name}={','.join(sorted(value))}"
        for name in sorted(vars(patterns))
        if name.isupper() and isinstance(value := getattr(patterns, name), frozenset)
    )
    return "|".join(parts)


def _encode_member(member: Member) -> dict:
    return {
        "n": member.name,
        "k": member.kind,
        "l": member.line,
        "c": member.col,
        "h": [
            [hit.line, hit.relation_root, hit.method, hit.prefetch_safe]
            for hit in member.hits
        ],
        "r": [[list(r.path), r.is_call, r.line] for r in member.refs],
        "f": member.forced,
    }


def _decode_member(data: dict) -> Member:
    return Member(
        name=data["n"],
        kind=data["k"],
        line=data["l"],
        col=data["c"],
        hits=tuple(
            QueryHit(line=h[0], relation_root=h[1], method=h[2], prefetch_safe=h[3])
            for h in data["h"]
        ),
        refs=tuple(
            MemberRef(path=tuple(r[0]), is_call=r[1], line=r[2]) for r in data["r"]
        ),
        forced=data["f"],
    )


def _encode_module(module: ModuleInfo) -> dict:
    return {
        "d": module.dotted,
        "p": module.path,
        "pkg": module.is_package,
        "mt": module.mtime_ns,
        "sz": module.size,
        "i": {
            alias: [imp.module, imp.name, imp.level]
            for alias, imp in module.imports.items()
        },
        "f": {name: _encode_member(m) for name, m in module.functions.items()},
        "c": {
            name: {
                "n": info.name,
                "l": info.line,
                "co": info.col,
                "b": [list(base) for base in info.bases],
                "m": {mn: _encode_member(mv) for mn, mv in info.members.items()},
                "rel": info.relations,
                "mrel": info.many_relations,
                "rp": list(info.required_prefetches)
                if info.required_prefetches is not None
                else None,
                "pe": [list(entry) for entry in info.prefetch_entries],
                "pl": info.prefetch_line,
            }
            for name, info in module.classes.items()
        },
    }


def _decode_module(data: dict) -> ModuleInfo:
    module = ModuleInfo(
        dotted=data["d"],
        path=data["p"],
        is_package=data["pkg"],
        mtime_ns=data["mt"],
        size=data["sz"],
        imports={
            alias: ImportedName(module=value[0], name=value[1], level=value[2])
            for alias, value in data["i"].items()
        },
        functions={name: _decode_member(m) for name, m in data["f"].items()},
    )
    for name, raw in data["c"].items():
        module.classes[name] = ClassInfo(
            name=raw["n"],
            module=module.dotted,
            line=raw["l"],
            col=raw["co"],
            bases=tuple(tuple(base) for base in raw["b"]),
            members={mn: _decode_member(mv) for mn, mv in raw["m"].items()},
            relations=dict(raw["rel"]),
            many_relations=dict(raw.get("mrel", {})),
            required_prefetches=tuple(raw["rp"]) if raw["rp"] is not None else None,
            prefetch_entries=tuple(
                (entry[0], entry[1], entry[2]) for entry in raw["pe"]
            ),
            prefetch_line=raw["pl"],
        )
    return module


def load(path: Path) -> dict[str, ModuleInfo]:
    """Read cached module facts, or return empty on any problem."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    if data.get("format") != FORMAT_VERSION or data.get("config") != config_hash():
        return {}
    try:
        return {
            file_path: _decode_module(raw)
            for file_path, raw in data.get("modules", {}).items()
        }
    except (KeyError, TypeError, IndexError):
        return {}


def save(path: Path, modules: dict[str, ModuleInfo]) -> None:
    """Write the cache atomically.  Failures are ignored."""
    payload = {
        "format": FORMAT_VERSION,
        "config": config_hash(),
        "modules": {
            file_path: _encode_module(module) for file_path, module in modules.items()
        },
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
        ) as handle:
            json.dump(payload, handle)
            temporary = Path(handle.name)
        os.replace(temporary, path)  # noqa: PTH105
    except (OSError, TypeError, ValueError):
        return
