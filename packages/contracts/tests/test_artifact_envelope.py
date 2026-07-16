"""Behavior tests for `ArtifactEnvelope`."""

import datetime
import typing

import pydantic
import pytest

import credit_desk_contracts.artifacts
import credit_desk_contracts.enums

_NOW = datetime.datetime.now(datetime.UTC)
_VALID_HASH = "sha256:" + "a" * 64


def _payload(**overrides: typing.Any) -> dict[str, typing.Any]:
    payload: dict[str, typing.Any] = {
        "schema_version": "1.0",
        "artifact_id": "artifact-1",
        "artifact_type": credit_desk_contracts.enums.ArtifactType.FINANCIAL_ANALYSIS,
        "workflow_id": "workflow-1",
        "data_classification": credit_desk_contracts.enums.DataClassification.CONFIDENTIAL,
        "produced_at": _NOW,
        "content_hash": _VALID_HASH,
        "size_bytes": 2048,
        "storage_uri": "s3://evidence-bundle/workflow-1/financial-analysis.json",
    }
    payload.update(overrides)
    return payload


def test_round_trips_through_json() -> None:
    envelope = credit_desk_contracts.artifacts.ArtifactEnvelope.model_validate(_payload())

    restored = credit_desk_contracts.artifacts.ArtifactEnvelope.model_validate_json(
        envelope.model_dump_json()
    )

    assert restored == envelope


def test_rejects_unknown_field() -> None:
    with pytest.raises(pydantic.ValidationError):
        credit_desk_contracts.artifacts.ArtifactEnvelope.model_validate(
            _payload(unexpected_field="not allowed")
        )


def test_rejects_invalid_artifact_type() -> None:
    with pytest.raises(pydantic.ValidationError):
        credit_desk_contracts.artifacts.ArtifactEnvelope.model_validate(
            _payload(artifact_type="not_a_known_artifact_type")
        )


def test_requires_schema_version() -> None:
    payload = _payload()
    del payload["schema_version"]

    with pytest.raises(pydantic.ValidationError):
        credit_desk_contracts.artifacts.ArtifactEnvelope.model_validate(payload)


def test_rejects_content_hash_not_shaped_like_sha256() -> None:
    with pytest.raises(pydantic.ValidationError):
        credit_desk_contracts.artifacts.ArtifactEnvelope.model_validate(
            _payload(content_hash="md5:not-a-sha256-digest")
        )


def test_is_immutable_after_construction() -> None:
    envelope = credit_desk_contracts.artifacts.ArtifactEnvelope.model_validate(_payload())

    with pytest.raises(pydantic.ValidationError):
        envelope.size_bytes = 4096


def test_generates_json_schema_with_required_fields() -> None:
    schema = credit_desk_contracts.artifacts.ArtifactEnvelope.model_json_schema()

    assert set(schema["required"]) >= {
        "schema_version",
        "artifact_id",
        "artifact_type",
        "workflow_id",
        "content_hash",
    }
    assert schema["properties"]["schema_version"]["const"] == "1.0"
