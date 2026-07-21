"""Consumer-defined ports for decisao-agent's evaluation application layer.

Defined on the consumer side (``application``), near the use case that needs them, per
``.claude/rules/architecture.md``. ``CreditEvaluationPort`` is the seam that keeps this layer
independent of ``credit_core``; ``PolicyCatalogPort`` is the seam that keeps it independent of
how policy-mcp is actually reached (MCP over stdio today).
"""

from dataclasses import dataclass
from typing import Protocol

from decisao_agent.domain.opinion import CreditOpinion
from decisao_agent.domain.snapshot import ApplicationSnapshot


class CreditEvaluationPort(Protocol):
    """Synchronous access to the deterministic credit evaluation core.

    The only implementation shipped today, ``CreditCoreEvaluationAdapter``, calls
    ``credit_core.evaluation.evaluate_credit_application`` directly. It is synchronous because
    ``credit_core`` is a pure, in-process computation with no I/O.
    """

    def evaluate(self, snapshot: ApplicationSnapshot) -> CreditOpinion:
        """Evaluate one application snapshot and return the resulting credit opinion.

        Args:
            snapshot: The applicant financial and bureau snapshot to evaluate.

        Returns:
            The structured, reproducible evaluation outcome.

        Raises:
            InvalidApplicationSnapshotError: If ``snapshot`` violates an input invariant.
        """
        ...


@dataclass(frozen=True, slots=True)
class PolicyCatalogSnapshot:
    """The subset of policy-mcp's catalog the evaluation use case cross-checks against.

    Attributes:
        known_critical_flag_names: Every critical flag name policy-mcp's catalog recognizes.
        known_policy_versions: Every policy version policy-mcp's catalog recognizes.
    """

    known_critical_flag_names: frozenset[str]
    known_policy_versions: frozenset[str]


class PolicyCatalogPort(Protocol):
    """Read-only access to policy-mcp's catalog, for cross-checking an evaluation.

    The only implementation shipped today, ``PolicyMcpClient``, speaks the MCP protocol to a
    ``policy-mcp`` server process over stdio.
    """

    async def snapshot(self) -> PolicyCatalogSnapshot:
        """Fetch the current known critical flag names and policy versions.

        Returns:
            A ``PolicyCatalogSnapshot`` covering policy-mcp's current catalog.
        """
        ...
