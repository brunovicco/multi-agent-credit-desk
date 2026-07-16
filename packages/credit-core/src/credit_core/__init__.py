"""Deterministic, policy-driven credit evaluation core. No LLM, A2A, MCP, or HTTP imports.

The only policy shipped today, ``DEMO_POLICY_V1``, is a synthetic demonstration policy: see
``packages/credit-core/README.md`` before treating any threshold, weight, or authority boundary
here as a production credit policy.
"""

from credit_core.domain import (
    ApprovalAuthority,
    ComponentScore,
    CreditApplicationSnapshot,
    CreditEvaluationResult,
    CriticalFlag,
    Decision,
    ReasonCode,
    ScoreComponent,
)
from credit_core.errors import (
    CreditCoreError,
    InvalidCreditApplicationError,
    InvalidCreditPolicyError,
)
from credit_core.evaluation import evaluate_credit_application, validate_snapshot
from credit_core.policy import (
    DEMO_POLICY_V1,
    CreditPolicy,
    ScoreBand,
    ScoreComponentPolicy,
    ScoreDirection,
    validate_policy,
)

__all__ = [
    "DEMO_POLICY_V1",
    "ApprovalAuthority",
    "ComponentScore",
    "CreditApplicationSnapshot",
    "CreditCoreError",
    "CreditEvaluationResult",
    "CreditPolicy",
    "CriticalFlag",
    "Decision",
    "InvalidCreditApplicationError",
    "InvalidCreditPolicyError",
    "ReasonCode",
    "ScoreBand",
    "ScoreComponent",
    "ScoreComponentPolicy",
    "ScoreDirection",
    "evaluate_credit_application",
    "validate_policy",
    "validate_snapshot",
]
