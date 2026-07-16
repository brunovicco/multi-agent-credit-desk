"""Versioned envelope describing a stored evidence-bundle artifact."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from credit_desk_contracts._base import StrictContract, UtcDatetime
from credit_desk_contracts.enums import ArtifactType, DataClassification
from credit_desk_contracts.identifiers import ArtifactId, WorkflowId


class ArtifactEnvelope(StrictContract):
    """Reference metadata for one artifact stored in the evidence bundle.

    The envelope carries a content hash and a storage pointer rather than the artifact payload
    itself, so the contract layer never carries customer data regardless of artifact size or
    content type. See ``docs/adr/0007-telemetry-without-sensitive-content.md``.
    """

    schema_version: Literal["1.0"]
    artifact_id: ArtifactId
    artifact_type: ArtifactType
    workflow_id: WorkflowId
    data_classification: DataClassification
    produced_at: UtcDatetime
    content_hash: Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
    size_bytes: Annotated[int, Field(ge=0)]
    storage_uri: Annotated[str, StringConstraints(min_length=1)]
