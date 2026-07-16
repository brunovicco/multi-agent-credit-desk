"""Regression test proving credit_core imports only the standard library and itself.

scripts/validate_architecture.py already enforces this against the real repository tree as part
of the quality gate. This test gives the same guarantee directly from the package's own test
suite, and additionally forbids relative imports, which the shared validator tolerates for
credit_core but this package's engineering instructions do not.
"""

import ast
import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "credit_core"
_DYNAMIC_IMPORT_MODULES = frozenset({"importlib"})
_ALLOWED_MODULES = frozenset(sys.stdlib_module_names) - _DYNAMIC_IMPORT_MODULES


def _source_files() -> list[Path]:
    return sorted(_SRC_ROOT.rglob("*.py"))


def test_credit_core_imports_only_stdlib_and_itself() -> None:
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module.split(".")[0]]
            else:
                continue
            for module in modules:
                assert module == "credit_core" or module in _ALLOWED_MODULES, (
                    f"{path}: disallowed import {module!r}"
                )


def test_credit_core_uses_no_relative_imports() -> None:
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level and node.level > 0:
                raise AssertionError(f"{path}: uses a relative import (level={node.level})")


def test_credit_core_does_not_use_future_annotations() -> None:
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "__future__"
                and any(alias.name == "annotations" for alias in node.names)
            ):
                raise AssertionError(f"{path}: uses 'from __future__ import annotations'")
