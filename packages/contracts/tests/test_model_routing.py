"""Behavior tests for the model-routing decision-record contracts."""

import datetime
import decimal
import typing

import pydantic
import pytest

import credit_desk_contracts.enums
import credit_desk_contracts.routing

_NOW = datetime.datetime.now(datetime.UTC)


def _request_payload(**overrides: typing.Any) -> dict[str, typing.Any]:
    payload: dict[str, typing.Any] = {
        "schema_version": "1.0",
        "requested_at": _NOW,
        "workflow_id": "workflow-1",
        "task_id": "task-1",
        "agent_name": "financeiro-agent",
        "workload": credit_desk_contracts.enums.Workload.CASHFLOW_ANALYSIS,
        "risk_level": credit_desk_contracts.enums.RiskLevel.HIGH,
        "data_classification": credit_desk_contracts.enums.DataClassification.CONFIDENTIAL,
        "context_tokens_estimated": 24_000,
        "structured_output_required": True,
        "max_latency_ms": 30_000,
        "max_cost_usd": decimal.Decimal("0.15"),
    }
    payload.update(overrides)
    return payload


def _decision_payload(**overrides: typing.Any) -> dict[str, typing.Any]:
    payload: dict[str, typing.Any] = {
        "schema_version": "1.0",
        "routing_decision_id": "decision-1",
        "decided_at": _NOW,
        "workflow_id": "workflow-1",
        "task_id": "task-1",
        "selected_model_group": credit_desk_contracts.enums.ModelGroup.REASONING_STRONG,
        "reason": "matches workload table for cashflow_analysis",
        "rejected_candidates": (),
    }
    payload.update(overrides)
    return payload


def test_route_request_round_trips_through_json() -> None:
    request = credit_desk_contracts.routing.ModelRouteRequest.model_validate(_request_payload())

    restored = credit_desk_contracts.routing.ModelRouteRequest.model_validate_json(
        request.model_dump_json()
    )

    assert restored == request


def test_route_request_rejects_unknown_field() -> None:
    with pytest.raises(pydantic.ValidationError):
        credit_desk_contracts.routing.ModelRouteRequest.model_validate(
            _request_payload(extra_signal="not allowed")
        )


def test_route_request_rejects_invalid_workload() -> None:
    with pytest.raises(pydantic.ValidationError):
        credit_desk_contracts.routing.ModelRouteRequest.model_validate(
            _request_payload(workload="unknown_workload")
        )


def test_route_request_rejects_non_positive_max_cost() -> None:
    with pytest.raises(pydantic.ValidationError):
        credit_desk_contracts.routing.ModelRouteRequest.model_validate(
            _request_payload(max_cost_usd=decimal.Decimal("0"))
        )


def test_route_decision_carries_every_rejected_candidate_with_its_reason() -> None:
    rejected = (
        credit_desk_contracts.routing.RejectedCandidate.model_validate(
            {
                "model_group": credit_desk_contracts.enums.ModelGroup.FAST_SMALL,
                "reason": "workload requires strong reasoning",
            }
        ),
        credit_desk_contracts.routing.RejectedCandidate.model_validate(
            {
                "model_group": credit_desk_contracts.enums.ModelGroup.REASONING_MEDIUM,
                "reason": "data classification requires a locally hosted deployment",
            }
        ),
    )

    decision = credit_desk_contracts.routing.ModelRouteDecision.model_validate(
        _decision_payload(rejected_candidates=rejected)
    )

    assert decision.rejected_candidates == rejected
    assert all(
        isinstance(candidate, credit_desk_contracts.routing.RejectedCandidate)
        for candidate in decision.rejected_candidates
    )


def test_route_decision_accepts_no_rejected_candidates() -> None:
    decision = credit_desk_contracts.routing.ModelRouteDecision.model_validate(_decision_payload())

    assert decision.rejected_candidates == ()


def test_rejected_candidate_requires_non_empty_reason() -> None:
    with pytest.raises(pydantic.ValidationError):
        credit_desk_contracts.routing.RejectedCandidate.model_validate(
            {"model_group": credit_desk_contracts.enums.ModelGroup.FAST_SMALL, "reason": ""}
        )


def test_route_decision_is_immutable() -> None:
    decision = credit_desk_contracts.routing.ModelRouteDecision.model_validate(_decision_payload())

    with pytest.raises(pydantic.ValidationError):
        decision.selected_model_group = credit_desk_contracts.enums.ModelGroup.REASONING_STRONG


def test_generates_json_schema_for_every_routing_contract() -> None:
    for model in (
        credit_desk_contracts.routing.ModelRouteRequest,
        credit_desk_contracts.routing.ModelRouteDecision,
        credit_desk_contracts.routing.RejectedCandidate,
    ):
        schema = model.model_json_schema()
        assert schema["type"] == "object"
        assert schema.get("additionalProperties") is False
