"""Regression tests for scripts/validate_architecture.py.

Loaded via importlib because scripts/ is not a package on mypy_path or sys.path. All fixtures use
tmp_path so these tests do not depend on the real repository tree.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "validate_architecture.py"
CREDIT_CORE_FILE = Path("packages/credit-core/src/credit_core/scoring.py")


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_architecture", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture(scope="module")
def validator() -> ModuleType:
    return _load_validator()


class TestLayeringRegression:
    """Preserve the pre-existing Clean Architecture layering behavior while extending discovery."""

    def test_legacy_domain_importing_application_is_rejected(
        self, tmp_path: Path, validator: ModuleType
    ) -> None:
        _write(tmp_path / "src/mypkg/domain/model.py", "from mypkg.application import service\n")
        violations = validator.collect_violations(tmp_path)
        assert any("must not depend on local layer 'application'" in v.message for v in violations)

    def test_legacy_domain_importing_pydantic_is_rejected(
        self, tmp_path: Path, validator: ModuleType
    ) -> None:
        _write(tmp_path / "src/mypkg/domain/model.py", "import pydantic\n")
        violations = validator.collect_violations(tmp_path)
        assert any("infrastructure package 'pydantic'" in v.message for v in violations)

    def test_clean_legacy_module_passes(self, tmp_path: Path, validator: ModuleType) -> None:
        _write(tmp_path / "src/mypkg/domain/model.py", "from dataclasses import dataclass\n")
        assert validator.collect_violations(tmp_path) == []

    def test_service_domain_importing_service_application_is_rejected(
        self, tmp_path: Path, validator: ModuleType
    ) -> None:
        """A services/*/src root must be discovered and checked, not just the legacy src/ layout."""
        _write(
            tmp_path / "services/orchestrator/src/orchestrator/domain/model.py",
            "from orchestrator.application import workflow\n",
        )
        violations = validator.collect_violations(tmp_path)
        assert any(
            v.path == Path("services/orchestrator/src/orchestrator/domain/model.py")
            and "must not depend on local layer 'application'" in v.message
            for v in violations
        )

    def test_violation_path_is_repository_relative_not_src_root_relative(
        self, tmp_path: Path, validator: ModuleType
    ) -> None:
        """Violation paths must stay unambiguous when several src roots exist in one repository."""
        _write(tmp_path / "src/mypkg/domain/model.py", "import pydantic\n")
        violations = validator.collect_violations(tmp_path)
        assert len(violations) == 1
        assert violations[0].path == Path("src/mypkg/domain/model.py")

    def test_both_legacy_and_service_roots_are_discovered_together(
        self, tmp_path: Path, validator: ModuleType
    ) -> None:
        _write(tmp_path / "src/mypkg/domain/model.py", "import pydantic\n")
        _write(
            tmp_path / "services/orchestrator/src/orchestrator/domain/model.py",
            "from orchestrator.adapters import db\n",
        )
        violations = validator.collect_violations(tmp_path)
        assert len(violations) == 2

    def test_missing_src_and_services_is_a_noop(
        self, tmp_path: Path, validator: ModuleType
    ) -> None:
        assert validator.discover_layered_roots(tmp_path) == []
        assert validator.collect_violations(tmp_path) == []


class TestCreditCoreDefaultDeny:
    """The credit_core policy is default-deny: only stdlib and self-imports are allowed."""

    def test_stdlib_import_allowed(self, tmp_path: Path, validator: ModuleType) -> None:
        _write(tmp_path / CREDIT_CORE_FILE, "from decimal import Decimal\nimport dataclasses\n")
        assert validator.collect_credit_core_violations(tmp_path) == []

    def test_self_import_allowed(self, tmp_path: Path, validator: ModuleType) -> None:
        _write(tmp_path / CREDIT_CORE_FILE, "from credit_core.policy import evaluate\n")
        assert validator.collect_credit_core_violations(tmp_path) == []

    def test_relative_self_import_allowed(self, tmp_path: Path, validator: ModuleType) -> None:
        _write(tmp_path / CREDIT_CORE_FILE, "from .policy import evaluate\n")
        assert validator.collect_credit_core_violations(tmp_path) == []

    def test_unknown_third_party_import_rejected(
        self, tmp_path: Path, validator: ModuleType
    ) -> None:
        """Proves default-deny: a package that appears on no denylist is still rejected."""
        _write(tmp_path / CREDIT_CORE_FILE, "import numpy\n")
        violations = validator.collect_credit_core_violations(tmp_path)
        assert len(violations) == 1
        assert "numpy" in violations[0].message

    @pytest.mark.parametrize(
        "import_statement",
        [
            "import anthropic",
            "import openai",
            "import mcp",
            "import a2a",
            "import httpx",
            "import requests",
            "import sqlalchemy",
            "import boto3",
            "import redis",
        ],
    )
    def test_vendor_and_infrastructure_imports_rejected(
        self, tmp_path: Path, validator: ModuleType, import_statement: str
    ) -> None:
        module_name = import_statement.removeprefix("import ")
        _write(tmp_path / CREDIT_CORE_FILE, import_statement + "\n")
        violations = validator.collect_credit_core_violations(tmp_path)
        assert len(violations) == 1
        assert module_name in violations[0].message

    def test_importlib_import_rejected_despite_being_stdlib(
        self, tmp_path: Path, validator: ModuleType
    ) -> None:
        _write(tmp_path / CREDIT_CORE_FILE, "import importlib\n")
        violations = validator.collect_credit_core_violations(tmp_path)
        assert len(violations) == 1
        assert "dynamic import" in violations[0].message

    def test_importlib_import_module_form_rejected(
        self, tmp_path: Path, validator: ModuleType
    ) -> None:
        _write(tmp_path / CREDIT_CORE_FILE, "from importlib import import_module\n")
        violations = validator.collect_credit_core_violations(tmp_path)
        assert len(violations) == 1
        assert "dynamic import" in violations[0].message

    def test_dunder_import_call_rejected(self, tmp_path: Path, validator: ModuleType) -> None:
        _write(tmp_path / CREDIT_CORE_FILE, "mod = __import__('os')\n")
        violations = validator.collect_credit_core_violations(tmp_path)
        assert len(violations) == 1
        assert "__import__" in violations[0].message

    def test_violation_location_and_message_are_deterministic(
        self, tmp_path: Path, validator: ModuleType
    ) -> None:
        _write(tmp_path / CREDIT_CORE_FILE, "from decimal import Decimal\nimport anthropic\n")
        violations = validator.collect_credit_core_violations(tmp_path)
        assert len(violations) == 1
        violation = violations[0]
        assert violation.path == CREDIT_CORE_FILE
        assert violation.line == 2
        assert "anthropic" in violation.message

    def test_missing_credit_core_package_is_a_noop(
        self, tmp_path: Path, validator: ModuleType
    ) -> None:
        assert validator.collect_credit_core_violations(tmp_path) == []
