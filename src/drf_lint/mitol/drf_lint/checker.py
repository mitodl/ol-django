"""LibCST visitor that checks for ORM violations in DRF serializer classes."""

from __future__ import annotations

from pathlib import Path

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from mitol.drf_lint.rules import orm001, orm002
from mitol.drf_lint.rules.base import Violation


class _SerializerORMVisitor(cst.CSTVisitor):
    """Walk a CST looking for ORM calls inside serializer class methods."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self) -> None:
        self._class_stack: list[cst.ClassDef] = []
        self._in_serializer_method: bool = False
        self._method_state_stack: list[bool] = []
        self.violations: list[Violation] = []

    # ------------------------------------------------------------------ #
    # Class tracking
    # ------------------------------------------------------------------ #

    def visit_ClassDef(self, node: cst.ClassDef) -> None:  # noqa: N802
        self._class_stack.append(node)

    def leave_ClassDef(self, node: cst.ClassDef) -> None:  # noqa: ARG002, N802
        if self._class_stack:
            self._class_stack.pop()

    # ------------------------------------------------------------------ #
    # Method tracking
    # ------------------------------------------------------------------ #

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:  # noqa: ARG002, N802
        # Save current state before entering this function.
        self._method_state_stack.append(self._in_serializer_method)
        # A method is "inside a serializer" only when its immediately enclosing
        # class is a serializer.  Nested classes (e.g. Meta) reset this to False.
        self._in_serializer_method = bool(
            self._class_stack and _is_serializer_class(self._class_stack[-1])
        )

    def leave_FunctionDef(self, node: cst.FunctionDef) -> None:  # noqa: ARG002, N802
        if self._method_state_stack:
            self._in_serializer_method = self._method_state_stack.pop()

    # ------------------------------------------------------------------ #
    # Violation detection
    # ------------------------------------------------------------------ #

    def visit_Call(self, node: cst.Call) -> None:  # noqa: N802
        if not self._in_serializer_method:
            return
        pos = self.get_metadata(PositionProvider, node)
        line, col = pos.start.line, pos.start.column

        violation = orm001.check(node, line, col)
        if violation is None:
            violation = orm002.check(node, line, col)
        if violation is not None:
            self.violations.append(violation)


def _is_serializer_class(node: cst.ClassDef) -> bool:
    """Heuristic: class name ends in 'Serializer' or a base contains 'Serializer'."""
    if node.name.value.endswith("Serializer"):
        return True
    return any(_expr_contains_serializer(base.value) for base in node.bases)


def _expr_contains_serializer(expr: cst.BaseExpression) -> bool:
    if isinstance(expr, cst.Name):
        return "Serializer" in expr.value
    if isinstance(expr, cst.Attribute):
        return "Serializer" in expr.attr.value or _expr_contains_serializer(expr.value)
    return False


def check_source(
    source_code: str,
) -> list[Violation]:
    """Parse *source_code* and return ORM violations, respecting ``# noqa`` comments."""
    try:
        module = cst.parse_module(source_code)
    except cst.ParserSyntaxError:
        return []

    visitor = _SerializerORMVisitor()
    wrapper = MetadataWrapper(module)
    wrapper.visit(visitor)

    source_lines = source_code.splitlines()
    return [v for v in visitor.violations if not _is_noqa(source_lines, v)]


def check_file(path: Path) -> list[Violation]:
    """Read *path* and return all ORM violations."""
    return check_source(path.read_text(encoding="utf-8"))


def _is_noqa(source_lines: list[str], violation: Violation) -> bool:
    """Return True if the violation's source line carries a ``# noqa`` suppression."""
    if violation.line < 1 or violation.line > len(source_lines):
        return False
    line = source_lines[violation.line - 1]
    if "# noqa" not in line:
        return False
    # Bare noqa (no codes) suppresses everything on this line.
    if "# noqa:" not in line:
        return True
    # Specific codes, e.g. ``# noqa: ORM001`` or ``# noqa: ORM001,ORM002``
    noqa_part = line[line.index("# noqa:") + 7 :].strip()
    codes = {c.strip() for c in noqa_part.split(",")}
    return violation.rule in codes
