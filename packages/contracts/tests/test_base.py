"""Behavior tests for the shared UTC timestamp contract used across every envelope."""

import datetime
import typing

import pydantic
import pytest

import credit_desk_contracts.artifacts
import credit_desk_contracts.enums

_VALID_HASH = "sha256:" + "a" * 64


def _envelope(
    produced_at: datetime.datetime,
) -> credit_desk_contracts.artifacts.ArtifactEnvelope:
    payload: dict[str, typing.Any] = {
        "schema_version": "1.0",
        "artifact_id": "artifact-1",
        "artifact_type": credit_desk_contracts.enums.ArtifactType.CADASTRAL_FINDINGS,
        "workflow_id": "workflow-1",
        "data_classification": credit_desk_contracts.enums.DataClassification.INTERNAL,
        "produced_at": produced_at,
        "content_hash": _VALID_HASH,
        "size_bytes": 1,
        "storage_uri": "s3://bucket/key",
    }
    return credit_desk_contracts.artifacts.ArtifactEnvelope.model_validate(payload)


def test_accepts_timezone_aware_utc_timestamp() -> None:
    envelope = _envelope(datetime.datetime.now(datetime.UTC))

    assert envelope.produced_at.tzinfo is not None


def test_rejects_naive_timestamp() -> None:
    with pytest.raises(pydantic.ValidationError):
        _envelope(datetime.datetime.now())


def test_rejects_non_utc_aware_timestamp() -> None:
    non_utc = datetime.datetime.now(datetime.UTC).astimezone(
        datetime.timezone(datetime.timedelta(hours=-3))
    )

    with pytest.raises(pydantic.ValidationError):
        _envelope(non_utc)
