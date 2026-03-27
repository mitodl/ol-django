"""Base types for drf_lint rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    """A lint rule violation detected in a source file."""

    rule: str
    message: str
    line: int
    col: int

    def format(self, filename: str) -> str:
        """Format violation as a human-readable string."""
        return f"{filename}:{self.line}:{self.col}: {self.rule} {self.message}"

    def baseline_key(self, filename: str) -> str:
        """Return the unique key used for baseline tracking."""
        return f"{filename}:{self.line}:{self.col}:{self.rule}"
