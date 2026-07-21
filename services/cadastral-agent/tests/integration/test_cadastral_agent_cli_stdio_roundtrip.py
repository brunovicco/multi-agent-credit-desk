"""Proves `python -m cadastral_agent` works end to end as a real subprocess, including its own
real `python -m bureau_mcp` subprocess call.

Spawns the packaged CLI entrypoint (not an in-process fake), feeds it one real ``CnpjInput`` JSON
document on stdin, and asserts the ``KycAssessmentOutput`` JSON on stdout - proving the console
entrypoint, the use case, and the real bureau-mcp MCP client all work together. Matches the
existing pattern in
`services/decisao-agent/tests/integration/test_decisao_agent_cli_stdio_roundtrip.py`.
"""

import json
import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration

_TIMEOUT_SECONDS = 30.0

_HEALTHY_CNPJ = "11.222.333/0001-81"
_LEVERAGED_CNPJ = "22.333.444/0001-81"
_NEGATIVE_HISTORY_CNPJ = "33.444.555/0001-81"


def _run_cli(cnpj: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "cadastral_agent"],
        input=json.dumps({"cnpj": cnpj}),
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
        env=env,
    )


def test_cli_approves_the_healthy_persona_end_to_end() -> None:
    process = _run_cli(_HEALTHY_CNPJ)

    assert process.returncode == 0, process.stderr
    body = json.loads(process.stdout)
    assert body["decision"] == "APPROVED"
    assert body["reason_codes"] == []


def test_cli_refers_the_leveraged_persona_to_committee() -> None:
    process = _run_cli(_LEVERAGED_CNPJ)

    assert process.returncode == 0, process.stderr
    body = json.loads(process.stdout)
    assert body["decision"] == "COMMITTEE_REFERRAL"
    assert "OVERDUE_DEBT_ON_FILE" in body["reason_codes"]


def test_cli_blocks_the_negative_history_persona() -> None:
    process = _run_cli(_NEGATIVE_HISTORY_CNPJ)

    assert process.returncode == 0, process.stderr
    body = json.loads(process.stdout)
    assert body["decision"] == "BLOCKED"


def test_cli_reports_a_stable_error_for_malformed_input() -> None:
    process = subprocess.run(
        [sys.executable, "-m", "cadastral_agent"],
        input="not valid json",
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
    )

    assert process.returncode == 1
    body = json.loads(process.stdout)
    assert body["code"] == "INVALID_INPUT"
    assert "Traceback" not in process.stdout
    assert "Traceback" not in process.stderr


def test_cli_reports_a_stable_error_for_a_malformed_cnpj() -> None:
    process = _run_cli("not-a-cnpj")

    assert process.returncode == 1
    body = json.loads(process.stdout)
    assert body["code"] == "INVALID_CNPJ"
    assert "not-a-cnpj" not in body["message"]


def test_cli_reports_a_stable_error_for_an_unknown_cnpj() -> None:
    process = _run_cli("99.999.999/0001-91")

    assert process.returncode == 1
    body = json.loads(process.stdout)
    assert body["code"] == "CNPJ_NOT_FOUND"


def test_cli_reports_a_stable_error_when_bureau_mcp_is_unreachable() -> None:
    process = _run_cli(
        _HEALTHY_CNPJ,
        env={
            **os.environ,
            "CADASTRAL_AGENT_BUREAU_MCP_COMMAND": "/no/such/executable-cadastral-agent-test",
        },
    )

    assert process.returncode == 1
    body = json.loads(process.stdout)
    assert body["code"] == "BUREAU_REPORT_UNAVAILABLE"
    assert "Traceback" not in process.stdout
    assert "Traceback" not in process.stderr
