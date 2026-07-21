"""Proves `python -m decisao_agent` works end to end as a real subprocess, including its own
real `python -m policy_mcp` subprocess call.

Spawns the packaged CLI entrypoint (not an in-process fake), feeds it one real
``ApplicationSnapshotInput`` JSON document on stdin, and asserts the ``CreditOpinion`` JSON on
stdout - proving the console entrypoint, the credit_core adapter, and the real policy-mcp MCP
client all work together, not just the composition root in isolation. Matches the existing
pattern in `services/policy-mcp/tests/integration/test_server_stdio_roundtrip.py`.
"""

import json
import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration

_TIMEOUT_SECONDS = 30.0

_HEALTHY_INPUT = {
    "annual_revenue": "1000000",
    "total_debt": "300000",
    "monthly_debt_service": "10000",
    "monthly_operating_cash_flow": "25000",
    "bureau_score": "850",
    "years_in_operation": 12,
    "requested_amount": "30000",
    "critical_flags": [],
}


def test_cli_evaluates_a_healthy_application_end_to_end() -> None:
    process = subprocess.run(
        [sys.executable, "-m", "decisao_agent"],
        input=json.dumps(_HEALTHY_INPUT),
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    body = json.loads(process.stdout)
    assert body["decision"] == "APPROVAL_RECOMMENDED"
    assert body["policy_version"] == "credit-core-demo-policy-v1"


def test_cli_reports_a_stable_error_for_malformed_input() -> None:
    process = subprocess.run(
        [sys.executable, "-m", "decisao_agent"],
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


def test_cli_reports_a_stable_error_for_an_unknown_critical_flag() -> None:
    process = subprocess.run(
        [sys.executable, "-m", "decisao_agent"],
        input=json.dumps({**_HEALTHY_INPUT, "critical_flags": ["NOT_A_REAL_FLAG"]}),
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
    )

    assert process.returncode == 1
    body = json.loads(process.stdout)
    assert body["code"] == "UNKNOWN_CRITICAL_FLAG"


def test_cli_reports_a_stable_error_when_policy_mcp_is_unreachable() -> None:
    process = subprocess.run(
        [sys.executable, "-m", "decisao_agent"],
        input=json.dumps(_HEALTHY_INPUT),
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
        env={
            **os.environ,
            "DECISAO_AGENT_POLICY_MCP_COMMAND": "/no/such/executable-decisao-agent-test",
        },
    )

    assert process.returncode == 1
    body = json.loads(process.stdout)
    assert body["code"] == "POLICY_CATALOG_UNAVAILABLE"
    assert "Traceback" not in process.stdout
    assert "Traceback" not in process.stderr
