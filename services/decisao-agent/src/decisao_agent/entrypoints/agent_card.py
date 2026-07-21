"""Builds decisao-agent's A2A Agent Card.

The card declares exactly one skill, matching what is actually implemented today: the
deterministic ``credit_core`` evaluation, cross-checked against policy-mcp's catalog (see
``docs/adr/0012-decisao-agent-sources-credit-core-evaluation-directly.md``). The
``opinion_drafting``/``json_repair`` LLM workloads from ``docs/architecture-blueprint.md``
section 2.2 are not implemented yet and are deliberately not declared as skills here - a future
milestone adds them once they exist, per ``docs/adr/0013-decisao-agent-adopts-a2a-sdk.md``.
"""

from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill

_AGENT_VERSION = "0.1.0"
_JSON_MEDIA_TYPE = "application/json"

_EVALUATE_CREDIT_APPLICATION_SKILL = AgentSkill(
    id="evaluate_credit_application",
    name="Evaluate Credit Application",
    description=(
        "Executes the deterministic credit_core evaluation for one application snapshot, "
        "cross-checked against policy-mcp's catalog of critical flags and policy versions."
    ),
    tags=["credit", "deterministic", "evaluation"],
    examples=[],
    input_modes=[_JSON_MEDIA_TYPE],
    output_modes=[_JSON_MEDIA_TYPE],
)


def build_agent_card(base_url: str) -> AgentCard:
    """Build decisao-agent's Agent Card, advertised at ``base_url``.

    Args:
        base_url: The externally reachable base URL this A2A server is served from, e.g.
            ``"http://127.0.0.1:9999"``.

    Returns:
        The Agent Card describing decisao-agent's single implemented skill.
    """
    return AgentCard(
        name="decisao-agent",
        description=(
            "Executes the deterministic credit_core evaluation and cross-checks it against "
            "policy-mcp's catalog. No LLM-drafted parecer yet - see "
            "docs/adr/0012-decisao-agent-sources-credit-core-evaluation-directly.md."
        ),
        version=_AGENT_VERSION,
        default_input_modes=[_JSON_MEDIA_TYPE],
        default_output_modes=[_JSON_MEDIA_TYPE],
        capabilities=AgentCapabilities(streaming=False, extended_agent_card=False),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                url=base_url,
                protocol_version="1.0",
            )
        ],
        skills=[_EVALUATE_CREDIT_APPLICATION_SKILL],
    )
