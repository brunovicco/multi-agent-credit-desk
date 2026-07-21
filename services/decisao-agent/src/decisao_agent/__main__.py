"""Top-level ``python -m decisao_agent`` shim.

Python's ``-m`` module runner requires ``__main__.py`` directly under the top-level package
(``decisao_agent/__main__.py``), so this thin shim exists purely to satisfy that runtime
requirement. The actual composition root and CLI logic live in
``decisao_agent.entrypoints.__main__``, next to the rest of the entrypoints layer, per
``.claude/rules/architecture.md``'s "keep the composition root in or near the entrypoint".
"""

from decisao_agent.entrypoints.__main__ import main

if __name__ == "__main__":
    main()
