#!/usr/bin/env python3
"""Enforce the project's inward dependency direction using Python's AST."""

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

LAYERS = {"domain", "application", "adapters", "entrypoints"}
FORBIDDEN_LOCAL: dict[str, set[str]] = {
    "domain": {"application", "adapters", "entrypoints"},
    "application": {"adapters", "entrypoints"},
}
FORBIDDEN_EXTERNAL: dict[str, tuple[str, ...]] = {
    "domain": (
        "boto3",
        "botocore",
        "celery",
        "django",
        "fastapi",
        "flask",
        "httpx",
        "kafka",
        "pydantic",
        "redis",
        "requests",
        "sqlalchemy",
    ),
    "application": (
        "boto3",
        "botocore",
        "celery",
        "django",
        "fastapi",
        "flask",
        "httpx",
        "kafka",
        "redis",
        "requests",
        "sqlalchemy",
    ),
}


@dataclass(frozen=True, slots=True)
class Violation:
    """Represent one architecture dependency violation."""

    path: Path
    line: int
    message: str


def layer_for(path: Path) -> str | None:
    """Return the architectural layer represented in a source path."""
    if len(path.parts) < 2:
        return None
    layer = path.parts[1]
    return layer if layer in LAYERS else None


def imported_modules(tree: ast.AST, current_module: tuple[str, ...]) -> list[tuple[int, str]]:
    """Collect absolute module names from import statements."""
    imports: list[tuple[int, str]] = []
    current_package = current_module[:-1]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue

        module_parts = tuple((node.module or "").split(".")) if node.module else ()
        if node.level:
            retained = max(0, len(current_package) - (node.level - 1))
            target_parts = current_package[:retained] + module_parts
        else:
            target_parts = module_parts
        base = ".".join(part for part in target_parts if part)
        for alias in node.names:
            imported = ".".join(part for part in (base, alias.name) if part)
            imports.append((node.lineno, imported))

    return imports


def validate_file(path: Path, src_root: Path) -> list[Violation]:
    """Validate imports for one Python source file."""
    relative = path.relative_to(src_root)
    layer = layer_for(relative)
    if layer not in FORBIDDEN_LOCAL:
        return []

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [Violation(relative, getattr(exc, "lineno", 1) or 1, f"cannot parse file: {exc}")]

    module = relative.with_suffix("").parts
    package = module[0]
    violations: list[Violation] = []

    for line, imported in imported_modules(tree, module):
        parts = imported.split(".") if imported else []
        if len(parts) > 1 and parts[0] == package and parts[1] in FORBIDDEN_LOCAL[layer]:
            violations.append(
                Violation(
                    relative,
                    line,
                    f"{layer} must not depend on local layer {parts[1]!r}: {imported}",
                )
            )
            continue

        prefix = imported.split(".", maxsplit=1)[0]
        if prefix in FORBIDDEN_EXTERNAL[layer]:
            violations.append(
                Violation(
                    relative,
                    line,
                    f"{layer} must not import infrastructure package {prefix!r}",
                )
            )

    return violations


def main() -> int:
    """Validate all source modules and return a process status."""
    root = Path(__file__).resolve().parents[1]
    src_root = root / "src"
    violations = [
        violation
        for path in sorted(src_root.rglob("*.py"))
        for violation in validate_file(path, src_root)
    ]

    if not violations:
        print("Architecture dependency check passed.")
        return 0

    print("Architecture dependency violations:", file=sys.stderr)
    for violation in violations:
        print(
            f"- {violation.path}:{violation.line}: {violation.message}",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
