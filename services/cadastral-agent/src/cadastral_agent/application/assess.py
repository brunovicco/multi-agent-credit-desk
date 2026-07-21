"""cadastral-agent's KYC assessment use case: screen one company against bureau-mcp's report."""

from cadastral_agent.application.ports import BureauReportPort
from cadastral_agent.domain import kyc_policy
from cadastral_agent.domain.assessment import KycAssessment


class AssessCadastralApplicationUseCase:
    """Screens one company's KYC standing using bureau-mcp's report."""

    def __init__(self, bureau_report_port: BureauReportPort) -> None:
        """Initialize the use case with its bureau report port.

        Args:
            bureau_report_port: The bureau-mcp port to fetch the company's finding from.
        """
        self._bureau_report_port = bureau_report_port

    async def execute(self, cnpj: str) -> KycAssessment:
        """Screen one company's KYC standing.

        Args:
            cnpj: The company's CNPJ, punctuated or digits-only.

        Returns:
            The structured, reproducible KYC assessment outcome.

        Raises:
            InvalidCnpjError: If ``cnpj`` is not a validly formatted identifier.
            CnpjNotFoundError: If bureau-mcp has no report on file for ``cnpj``.
            BureauReportUnavailableError: If bureau-mcp cannot be reached or returns an
                unexpected response.
        """
        finding = await self._bureau_report_port.get_report(cnpj)
        return kyc_policy.assess(finding)
