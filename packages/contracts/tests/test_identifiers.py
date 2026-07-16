"""Behavior tests for the non-empty identifier constraint shared by every correlation ID."""

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
        "artifact_type": credit_desk_contracts.enums.ArtifactType.CADASTRAL_FINDINGS,
        "workflow_id": "workflow-1",
        "data_classification": credit_desk_contracts.enums.DataClassification.INTERNAL,
        "produced_at": _NOW,
        "content_hash": _VALID_HASH,
        "size_bytes": 0,
        "storage_uri": "s3://bucket/key",
    }
    payload.update(overrides)
    return payload


def test_rejects_empty_workflow_id() -> None:
    with pytest.raises(pydantic.ValidationError):
        credit_desk_contracts.artifacts.ArtifactEnvelope.model_validate(_payload(workflow_id=""))


def test_rejects_whitespace_only_artifact_id() -> None:
    with pytest.raises(pydantic.ValidationError):
        credit_desk_contracts.artifacts.ArtifactEnvelope.model_validate(_payload(artifact_id="   "))
