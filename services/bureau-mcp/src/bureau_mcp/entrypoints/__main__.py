"""``python -m bureau_mcp`` entrypoint: run the bureau-mcp MCP server over a selected transport.

Transport selection is explicit and fails fast: an unrecognized ``BUREAU_MCP_TRANSPORT`` value
raises ``SystemExit`` at startup rather than silently defaulting to ``stdio``.
"""

import logging
import os

from mcp.server.fastmcp import FastMCP

from bureau_mcp.entrypoints.server import build_server

_TRANSPORT_ENV_VAR = "BUREAU_MCP_TRANSPORT"
_DEFAULT_TRANSPORT = "stdio"
_SUPPORTED_TRANSPORTS = frozenset({"stdio", "sse", "streamable-http"})

logger = logging.getLogger(__name__)


def main() -> None:
    """Configure logging, validate the requested transport, and run the MCP server.

    Raises:
        SystemExit: If ``BUREAU_MCP_TRANSPORT`` is set to an unrecognized value.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    transport = os.environ.get(_TRANSPORT_ENV_VAR, _DEFAULT_TRANSPORT)
    if transport not in _SUPPORTED_TRANSPORTS:
        logger.error(
            "bureau_mcp.startup.invalid_transport",
            extra={"transport": transport, "supported": sorted(_SUPPORTED_TRANSPORTS)},
        )
        raise SystemExit(
            f"Unsupported {_TRANSPORT_ENV_VAR}={transport!r}; "
            f"expected one of {sorted(_SUPPORTED_TRANSPORTS)}."
        )

    server = build_server()
    _run(server, transport)


def _run(server: FastMCP, transport: str) -> None:
    """Run the server on the validated transport, satisfying the SDK's ``Literal`` type.

    Args:
        server: The built MCP server to run.
        transport: The already-validated transport name (one of ``_SUPPORTED_TRANSPORTS``).
    """
    match transport:
        case "stdio":
            server.run(transport="stdio")
        case "sse":  # pragma: no cover - not exercised by this package's tests
            server.run(transport="sse")
        case "streamable-http":  # pragma: no cover - not exercised by this package's tests
            server.run(transport="streamable-http")
        case _:  # pragma: no cover - unreachable, transport is validated in main()
            raise AssertionError(f"unreachable: unsupported transport {transport!r}")


if __name__ == "__main__":
    main()
