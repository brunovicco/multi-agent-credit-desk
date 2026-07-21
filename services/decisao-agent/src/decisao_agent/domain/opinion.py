"""decisao-agent's own vocabulary for the outcome of a credit evaluation.

These are frozen, immutable Value Objects mirroring the shape of
``credit_core.domain.CreditEvaluationResult`` and ``credit_core.domain.ComponentScore`` without
importing those types - the translation happens once, at the adapter boundary in
``decisao_agent.adapters.credit_core_evaluation_adapter``.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ComponentScoreView:
    """One scored component of the applied policy, before and after weighting.

    Attributes:
        component: The scored component's name (e.g. ``"BUREAU_SCORE"``).
        metric_value: The raw input metric value for this component.
        raw_score: The component's raw score, before weighting.
        weight: The component's weight in the total score.
        weighted_score: ``raw_score`` multiplied by ``weight``.
    """

    component: str
    metric_value: Decimal
    raw_score: Decimal
    weight: Decimal
    weighted_score: Decimal


@dataclass(frozen=True, slots=True)
class CreditOpinion:
    """The structured, reproducible outcome of evaluating one credit application.

    Attributes:
        policy_version: Version identifier of the policy credit_core applied.
        total_score: Sum of every component's ``weighted_score``.
        component_scores: Full per-component breakdown, in policy declaration order.
        decision: The final decision (e.g. ``"APPROVAL_RECOMMENDED"``, ``"BLOCKED"``).
        approval_authority: The approval authority required for ``decision``.
        reason_codes: Deterministic reason codes explaining ``decision`` and
            ``approval_authority``. Empty whenever ``decision`` is ``"BLOCKED"``.
        blocking_reasons: Deterministic reason codes for each critical flag that caused a
            block. Empty unless ``decision`` is ``"BLOCKED"``.
    """

    policy_version: str
    total_score: Decimal
    component_scores: tuple[ComponentScoreView, ...]
    decision: str
    approval_authority: str
    reason_codes: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
