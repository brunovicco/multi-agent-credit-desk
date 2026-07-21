"""Executable form of cadastral-agent's core architectural decision.

Only ``cadastral_agent.adapters.bureau_mcp_client`` may import ``mcp`` - see
``docs/adr/0016-cadastral-agent-kyc-screening-policy.md``. This test AST-walks ``domain/``,
``application/``, and ``entrypoints/`` and fails the build if any of them import ``mcp``, directly
or via ``from mcp... import ...``, so the boundary is enforced by a check rather than only
documented. Mirrors
``decisao_agent.tests.unit.test_decisao_agent_architecture_boundary``.
"""

import ast
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "cadastral_agent"
_FORBIDDEN_LAYERS = ("domain", "application", "entrypoints")


def _source_files(layer: str) -> list[Path]:
    return sorted((_SRC_ROOT / layer).rglob("*.py"))


def _root_module_names(node: ast.AST) -> list[str]:
    """Return the top-level module name(s) referenced by one import statement node."""
    if isinstance(node, ast.Import):
        return [alias.name.split(".")[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        return [node.module.split(".")[0]]
    return []


def _imports_module(path: Path, module_name: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(
        module_name in _root_module_names(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
    )


def test_domain_application_and_entrypoints_never_import_mcp() -> None:
    offenders = [
        path
        for layer in _FORBIDDEN_LAYERS
        for path in _source_files(layer)
        if _imports_module(path, "mcp")
    ]

    assert offenders == [], (
        f"the following files must not import mcp, only "
        f"cadastral_agent.adapters.bureau_mcp_client may: {offenders}"
    )


def test_the_adapter_module_itself_does_import_mcp() -> None:
    """Guard against a false negative: prove the AST check actually detects the import."""
    adapter_path = _SRC_ROOT / "adapters" / "bureau_mcp_client.py"

    assert adapter_path.is_file()
    assert _imports_module(adapter_path, "mcp")


def test_forbidden_layers_are_not_accidentally_empty() -> None:
    """Guard against a false pass: every checked layer must actually contain source files."""
    for layer in _FORBIDDEN_LAYERS:
        assert _source_files(layer), f"expected at least one source file under {layer}/"


def test_detects_a_synthetic_violation(tmp_path: Path) -> None:
    """Prove _imports_module flags both import styles, using a throwaway file."""
    plain_import = tmp_path / "plain_import.py"
    plain_import.write_text("import mcp\n", encoding="utf-8")
    from_import = tmp_path / "from_import.py"
    from_import.write_text("from mcp.types import CallToolResult\n", encoding="utf-8")
    clean = tmp_path / "clean.py"
    clean.write_text("from decimal import Decimal\n", encoding="utf-8")

    assert _imports_module(plain_import, "mcp")
    assert _imports_module(from_import, "mcp")
    assert not _imports_module(clean, "mcp")
