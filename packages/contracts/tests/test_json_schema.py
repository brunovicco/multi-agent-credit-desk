"""Cross-cutting JSON Schema generation tests for every public contract."""

import pydantic
import pytest

import credit_desk_contracts.artifacts
import credit_desk_contracts.events
import credit_desk_contracts.routing

_PUBLIC_CONTRACTS = (
    credit_desk_contracts.artifacts.ArtifactEnvelope,
    credit_desk_contracts.events.EventEnvelope,
    credit_desk_contracts.routing.ModelRouteRequest,
    credit_desk_contracts.routing.ModelRouteDecision,
    credit_desk_contracts.routing.RejectedCandidate,
)


@pytest.mark.parametrize("contract", _PUBLIC_CONTRACTS)
def test_json_schema_declares_closed_object_with_pinned_version(
    contract: type[pydantic.BaseModel],
) -> None:
    schema = contract.model_json_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    if "schema_version" in schema["properties"]:
        assert schema["properties"]["schema_version"]["const"] == "1.0"
