"""MCP server `realbasket` (Model Context Protocol, target architecture phase 1).

One server process, thin wrappers around the deterministic core (`core/`, `data/`, `knowledge/`), split into
modules per area:

- `data_tools.py`      (area data):      basket, prices, VPI, index calculation, data checks
- `knowledge_tools.py` (area knowledge): method-note search (RAG), document pages as resources, citation prompt
- `analysis_tools.py`  (area analysis):  deviation drivers, drill-down, city rents, state coverage
- `server.py`:         builds the server from the areas, CLI (stdio or Streamable HTTP)

    poetry run real-basket-mcp                                          # stdio
    poetry run real-basket-mcp --transport streamable-http --port 8001
"""

SERVER_MODULE = "real_basket.mcp_servers.server"
