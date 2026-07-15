#!/usr/bin/env python3
"""Enforce inward dependency direction and credit-core isolation using Python's AST."""

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

CREDIT_CORE_PACKAGE = "credit_core"
CREDIT_CORE_RELATIVE_ROOT = Path("packages/credit-core/src/credit_core")
CREDIT_CORE_DYNAMIC_IMPORT_MODULES = {"importlib"}
# sys.stdlib_module_names is the authoritative, future-proof allowlist: anything not in it is
# third-party or another workspace member by construction, so nothing needs to be enumerated here.
STDLIB_MODULE_NAMES = frozenset(sys.stdlib_module_names) - CREDIT_CORE_DYNAMIC_IMPORT_MODULES


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


def validate_file(path: Path, src_root: Path, root: Path) -> list[Violation]:
    """Validate imports for one Python source file against Clean Architecture layering.

    Args:
        path: Absolute path to the source file to check.
        src_root: Absolute path to the ``src`` root that ``path`` belongs to, used to derive the
            file's architectural layer.
        root: Absolute path to the repository root. Reported violation paths are relative to this
            root so they stay unambiguous across multiple ``src`` roots (legacy ``src/``,
            ``services/*/src``, and ``packages/*/src``).

    Returns:
        Every layering violation found in the file, with paths relative to ``root``.
    """
    relative = path.relative_to(src_root)
    layer = layer_for(relative)
    if layer not in FORBIDDEN_LOCAL:
        return []

    repo_relative = path.relative_to(root)

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [
            Violation(repo_relative, getattr(exc, "lineno", 1) or 1, f"cannot parse file: {exc}")
        ]

    module = relative.with_suffix("").parts
    package = module[0]
    violations: list[Violation] = []

    for line, imported in imported_modules(tree, module):
        parts = imported.split(".") if imported else []
        if len(parts) > 1 and parts[0] == package and parts[1] in FORBIDDEN_LOCAL[layer]:
            violations.append(
                Violation(
                    repo_relative,
                    line,
                    f"{layer} must not depend on local layer {parts[1]!r}: {imported}",
                )
            )
            continue

        prefix = imported.split(".", maxsplit=1)[0]
        if prefix in FORBIDDEN_EXTERNAL[layer]:
            violations.append(
                Violation(
                    repo_relative,
                    line,
                    f"{layer} must not import infrastructure package {prefix!r}",
                )
            )

    return violations


def discover_layered_roots(root: Path) -> list[Path]:
    """Return every src root that must be checked for Clean Architecture layering.

    Discovers the legacy root ``src/`` layout when present, and every ``services/*/src`` root.
    Neither is hard-coded as the only source of truth: this repository has no application package
    today, but the check stays live for whichever layout is present.
    """
    roots: list[Path] = []
    legacy_src = root / "src"
    if legacy_src.is_dir():
        roots.append(legacy_src)

    services_dir = root / "services"
    if services_dir.is_dir():
        for service_dir in sorted(p for p in services_dir.iterdir() if p.is_dir()):
            service_src = service_dir / "src"
            if service_src.is_dir():
                roots.append(service_src)

    return roots


def _dynamic_import_call_violations(tree: ast.AST, relative: Path) -> list[Violation]:
    """Flag calls to the ``__import__`` builtin, which bypasses static import analysis."""
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
        ):
            violations.append(
                Violation(
                    relative,
                    node.lineno,
                    "credit_core must not use the dynamic import mechanism '__import__'",
                )
            )
    return violations


def validate_credit_core_file(path: Path, package_src_root: Path, root: Path) -> list[Violation]:
    """Validate one credit_core source file against the default-deny import policy.

    Only standard-library modules and imports of ``credit_core`` itself are allowed. Every other
    third-party or workspace import is rejected by default, and ``importlib``/``__import__`` are
    rejected explicitly even though ``importlib`` is part of the standard library, because both
    exist specifically to bypass static import analysis.

    Args:
        path: Absolute path to the source file to check.
        package_src_root: Absolute path to ``packages/credit-core/src``, used to derive the
            module name for import resolution.
        root: Absolute path to the repository root. Reported violation paths are relative to this
            root.

    Returns:
        Every default-deny policy violation found in the file, with paths relative to ``root``.
    """
    relative = path.relative_to(package_src_root)
    repo_relative = path.relative_to(root)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [
            Violation(repo_relative, getattr(exc, "lineno", 1) or 1, f"cannot parse file: {exc}")
        ]

    module = relative.with_suffix("").parts
    violations = _dynamic_import_call_violations(tree, repo_relative)

    for line, imported in imported_modules(tree, module):
        top = imported.split(".", maxsplit=1)[0] if imported else ""
        if top == CREDIT_CORE_PACKAGE:
            continue
        if top in CREDIT_CORE_DYNAMIC_IMPORT_MODULES:
            violations.append(
                Violation(
                    repo_relative,
                    line,
                    f"credit_core must not import {imported!r}: "
                    "dynamic import mechanisms are forbidden",
                )
            )
            continue
        if top in STDLIB_MODULE_NAMES:
            continue
        violations.append(
            Violation(
                repo_relative,
                line,
                f"credit_core must not import {imported!r}: only the standard library and "
                "credit_core itself are allowed",
            )
        )

    return violations


def collect_credit_core_violations(root: Path) -> list[Violation]:
    """Validate every credit_core source file, if the package is present."""
    package_src_root = root / CREDIT_CORE_RELATIVE_ROOT.parent
    package_root = root / CREDIT_CORE_RELATIVE_ROOT
    if not package_root.is_dir():
        return []

    return [
        violation
        for path in sorted(package_root.rglob("*.py"))
        for violation in validate_credit_core_file(path, package_src_root, root)
    ]


def collect_violations(root: Path) -> list[Violation]:
    """Collect every architecture dependency violation under the given repository root."""
    violations = [
        violation
        for src_root in discover_layered_roots(root)
        for path in sorted(src_root.rglob("*.py"))
        for violation in validate_file(path, src_root, root)
    ]
    violations.extend(collect_credit_core_violations(root))
    return violations


def main() -> int:
    """Validate all source modules and return a process status."""
    root = Path(__file__).resolve().parents[1]
    violations = collect_violations(root)

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
