"""The single use case of decisao-agent's first milestone: evaluate one credit application.

Composes two ports: the synchronous deterministic evaluation (``CreditEvaluationPort``) and an
asynchronous cross-check against policy-mcp's catalog (``PolicyCatalogPort``), so credit_core's
decision can never be trusted against a critical flag or policy version policy-mcp does not
itself recognize. This module never imports ``credit_core`` or a transport/serialization
library.
"""

from decisao_agent.application.ports import CreditEvaluationPort, PolicyCatalogPort
from decisao_agent.domain.errors import PolicyVersionMismatchError, UnknownCriticalFlagError
from decisao_agent.domain.opinion import CreditOpinion
from decisao_agent.domain.snapshot import ApplicationSnapshot


class EvaluateCreditApplicationUseCase:
    """Evaluates a credit application snapshot, cross-checked against policy-mcp's catalog."""

    def __init__(
        self, evaluation_port: CreditEvaluationPort, policy_catalog_port: PolicyCatalogPort
    ) -> None:
        """Initialize the use case with its evaluation and policy catalog ports.

        Args:
            evaluation_port: The deterministic credit evaluation port to use.
            policy_catalog_port: The policy-mcp catalog port to cross-check against.
        """
        self._evaluation_port = evaluation_port
        self._policy_catalog_port = policy_catalog_port

    async def execute(self, snapshot: ApplicationSnapshot) -> CreditOpinion:
        """Evaluate one application snapshot, validated against policy-mcp's catalog.

        Args:
            snapshot: The applicant financial and bureau snapshot to evaluate.

        Returns:
            The structured, reproducible evaluation outcome.

        Raises:
            UnknownCriticalFlagError: If ``snapshot.critical_flags`` names a flag policy-mcp
                does not recognize.
            InvalidApplicationSnapshotError: If ``snapshot`` violates an input invariant.
            PolicyVersionMismatchError: If credit_core applies a policy version policy-mcp does
                not recognize.
        """
        catalog = await self._policy_catalog_port.snapshot()

        unknown_flag_names = snapshot.critical_flags - catalog.known_critical_flag_names
        if unknown_flag_names:
            raise UnknownCriticalFlagError(unknown_flag_names)

        opinion = self._evaluation_port.evaluate(snapshot)

        if opinion.policy_version not in catalog.known_policy_versions:
            raise PolicyVersionMismatchError(opinion.policy_version)

        return opinion
