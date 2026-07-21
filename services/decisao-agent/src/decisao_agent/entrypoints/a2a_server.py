"""``python -m decisao_agent.entrypoints.a2a_server``: run decisao-agent as an A2A server.

This is a separate entrypoint from the batch CLI (``entrypoints.__main__``), not a selectable
transport of the same process: the CLI is a one-shot batch program that reads stdin once and
exits, while this is a long-running daemon serving A2A requests over HTTP - different process
shapes, kept as two composition roots rather than one env-var-selected mode. See
``docs/adr/0013-decisao-agent-adopts-a2a-sdk.md``.
"""

import logging
import os

import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette

from decisao_agent.adapters.credit_core_evaluation_adapter import CreditCoreEvaluationAdapter
from decisao_agent.adapters.litellm_client import LiteLLMClient
from decisao_agent.adapters.model_router_client import ModelRouterClient
from decisao_agent.adapters.policy_mcp_client import PolicyMcpClient
from decisao_agent.application.evaluate import EvaluateCreditApplicationUseCase
from decisao_agent.entrypoints.a2a_executor import DecisaoAgentExecutor
from decisao_agent.entrypoints.agent_card import build_agent_card

logger = logging.getLogger(__name__)

_HOST_ENV_VAR = "DECISAO_AGENT_A2A_HOST"
_PORT_ENV_VAR = "DECISAO_AGENT_A2A_PORT"
_POLICY_MCP_COMMAND_ENV_VAR = "DECISAO_AGENT_POLICY_MCP_COMMAND"
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 9999


def build_app(base_url: str) -> Starlette:
    """Build the A2A Starlette app, wiring the executor into the agent-card and JSON-RPC routes.

    Args:
        base_url: The externally reachable base URL to advertise in the Agent Card, e.g.
            ``"http://127.0.0.1:9999"``.

    Returns:
        The fully configured Starlette app, ready to run under any ASGI server.
    """
    use_case = EvaluateCreditApplicationUseCase(
        evaluation_port=CreditCoreEvaluationAdapter(),
        policy_catalog_port=PolicyMcpClient(command=os.environ.get(_POLICY_MCP_COMMAND_ENV_VAR)),
        model_routing_port=ModelRouterClient(),
        chat_completion_port=LiteLLMClient(),
    )
    agent_card = build_agent_card(base_url)
    request_handler = DefaultRequestHandler(
        agent_executor=DecisaoAgentExecutor(use_case),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    routes = list(create_agent_card_routes(agent_card))
    routes.extend(create_jsonrpc_routes(request_handler, "/"))

    return Starlette(routes=routes)


def main() -> None:
    """Configure logging and run the A2A server, bound per DECISAO_AGENT_A2A_HOST/PORT."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    host = os.environ.get(_HOST_ENV_VAR, _DEFAULT_HOST)
    port = int(os.environ.get(_PORT_ENV_VAR, str(_DEFAULT_PORT)))
    app = build_app(f"http://{host}:{port}")

    logger.info("decisao_agent.a2a_server.starting", extra={"host": host, "port": port})
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
