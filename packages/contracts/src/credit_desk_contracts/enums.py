"""Closed vocabularies shared across credit desk contracts.

Values are drawn from ``docs/architecture-blueprint.md`` sections 2.2 (agent workloads), 2.3
(model groups), and 2.5 (log/event taxonomy).
"""

from enum import StrEnum


class DataClassification(StrEnum):
    """LGPD/LC 105-oriented sensitivity tier for a piece of data or an artifact."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class EventOutcome(StrEnum):
    """Terminal outcome of a structured event in the audit trail."""

    SUCCESS = "success"
    FAILURE = "failure"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class ArtifactType(StrEnum):
    """Kind of artifact produced during a credit review workflow."""

    CADASTRAL_FINDINGS = "cadastral_findings"
    FINANCIAL_ANALYSIS = "financial_analysis"
    RISK_ASSESSMENT = "risk_assessment"
    CREDIT_OPINION = "credit_opinion"
    EVIDENCE_BUNDLE = "evidence_bundle"


class RiskLevel(StrEnum):
    """Assessed risk level of a credit application or a routing request."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Workload(StrEnum):
    """LLM workload kind, used as the routing key from workload to model group."""

    DOCUMENT_EXTRACTION = "document_extraction"
    CASHFLOW_ANALYSIS = "cashflow_analysis"
    FINDINGS_CORRELATION = "findings_correlation"
    OPINION_DRAFTING = "opinion_drafting"
    JSON_REPAIR = "json_repair"


class ModelGroup(StrEnum):
    """Model group selectable by the model router, independent of provider or deployment."""

    FAST_SMALL = "fast-small"
    REASONING_MEDIUM = "reasoning-medium"
    REASONING_STRONG = "reasoning-strong"
    FAST_STRUCTURED_OUTPUT = "fast-structured-output"
