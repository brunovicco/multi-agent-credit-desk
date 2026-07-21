"""Pydantic wire schemas for cadastral-agent's CLI, and explicit domain-to-wire mappings.

Every output schema mirrors ``credit_desk_contracts._base.StrictContract``'s conventions: unknown
fields are rejected (``extra="forbid"``) and instances are immutable once constructed
(``frozen=True``) - matching ``decisao_agent.entrypoints.schemas`` and
``bureau_mcp.entrypoints.schemas``. The convention is reimplemented locally rather than imported,
for the same reason those two do. Mapping is explicit, one field at a time - never automatic
dataclass serialization, so a schema change is always a deliberate, reviewable edit.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from cadastral_agent.domain.assessment import KycAssessment


class CnpjInput(BaseModel):
    """Wire schema for the CLI's JSON input."""

    model_config = ConfigDict(extra="forbid", strict=True)

    cnpj: str


class _CadastralAgentContract(BaseModel):
    """Base model for every cadastral-agent output wire schema: immutable, closed to unknowns."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class KycAssessmentOutput(_CadastralAgentContract):
    """Wire schema for the CLI's JSON output.

    See ``cadastral_agent.domain.assessment.KycAssessment``.
    """

    cnpj: str
    external_score: Decimal
    decision: str
    reason_codes: tuple[str, ...]


def to_kyc_assessment_output(assessment: KycAssessment) -> KycAssessmentOutput:
    """Map a ``KycAssessment`` domain value to its wire schema.

    Args:
        assessment: The domain KYC assessment to map.

    Returns:
        The equivalent wire schema.
    """
    return KycAssessmentOutput(
        cnpj=assessment.cnpj,
        external_score=assessment.external_score,
        decision=assessment.decision.value,
        reason_codes=assessment.reason_codes,
    )
