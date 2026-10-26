"""Connector Manager: registers built-ins and manages active MCP clients."""

import json
import logging
from typing import Any, Optional
from db import list_connectors, get_connector, upsert_connector, toggle_connector
from connectors.builtin import (
    BUILTIN_CONNECTORS,
    execute_builtin_tool,
    get_builtin_tools_for_connector,
)
from connectors.mcp_client import (
    MCPStdioClient,
    MCPHttpClient,
    mcp_tool_to_openai_schema,
)

logger = logging.getLogger(__name__)

class ConnectorManager:
    def __init__(self):
        self._mcp_clients: dict[str, Any] = {}
        self.init_builtin_connectors()

    def init_builtin_connectors(self) -> None:
        """Seed the database with default connectors if not present."""
        existing = {c["id"]: c for c in list_connectors()}
        for item in BUILTIN_CONNECTORS:
            if item["id"] not in existing:
                upsert_connector(
                    connector_id=item["id"],
                    name=item["name"],
                    kind="builtin",
                    description=item["description"],
                    config={},
                    enabled=0,
                )

    def get_all_connectors_summary(self) -> list[dict[str, Any]]:
        db_connectors = {c["id"]: c for c in list_connectors()}
        summary = []

        # Built-ins first
        for b in BUILTIN_CONNECTORS:
            db_item = db_connectors.get(b["id"], {})
            summary.append({
                "id": b["id"],
                "name": b["name"],
                "kind": "builtin",
                "description": b["description"],
                "icon": b.get("icon", "plug"),
                "color": b.get("color", "#4f46e5"),
                "fields": b.get("fields", []),
                "enabled": db_item.get("enabled", False),
                "is_configured": bool(db_item.get("config")),
            })

        # Custom MCP connectors
        for c in db_connectors.values():
            if c["kind"] in ("mcp_stdio", "mcp_sse"):
                summary.append({
                    "id": c["id"],
                    "name": c["name"],
                    "kind": c["kind"],
                    "description": c.get("description", "Custom MCP Server"),
                    "icon": "cpu",
                    "color": "#8b5cf6",
                    "fields": [],
                    "enabled": c.get("enabled", False),
                    "is_configured": True,
                    "config": c.get("config", {}),
                })
        return summary

    def get_active_tools(self) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str]]]:
        """Returns:
        1. list of OpenAI/Gemini tool schemas
        2. mapping: {tool_name: (connector_id, kind)}
        """
        tools = []
        routing = {}

        for c in list_connectors():
            if not c.get("enabled"):
                continue

            cid = c["id"]
            kind = c["kind"]

            if kind == "builtin":
                builtin_tools = get_builtin_tools_for_connector(cid)
                for t in builtin_tools:
                    t_name = t["function"]["name"]
                    tools.append(t)
                    routing[t_name] = (cid, "builtin")

            elif kind in ("mcp_stdio", "mcp_sse"):
                client = self._get_or_create_mcp_client(cid, c)
                if client:
                    try:
                        mcp_tools = client.list_tools()
                        for mt in mcp_tools:
                            schema = mcp_tool_to_openai_schema(mt, prefix=cid)
                            t_name = schema["function"]["name"]
                            tools.append(schema)
                            routing[t_name] = (cid, kind)
                    except Exception as e:
                        logger.warning(f"Could not list tools for MCP connector {cid}: {e}")

        return tools, routing

    def _get_or_create_mcp_client(self, cid: str, connector_row: dict) -> Any:
        if cid in self._mcp_clients:
            return self._mcp_clients[cid]

        config = connector_row.get("config", {})
        kind = connector_row["kind"]
        try:
            if kind == "mcp_stdio":
                cmd = config.get("command", "")
                args = config.get("args", [])
                env = config.get("env", {})
                client = MCPStdioClient(command=cmd, args=args, env=env)
                client.start()
                self._mcp_clients[cid] = client
                return client
            elif kind == "mcp_sse":
                url = config.get("url", "")
                headers = config.get("headers", {})
                client = MCPHttpClient(endpoint_url=url, headers=headers)
                self._mcp_clients[cid] = client
                return client
        except Exception as e:
            logger.error(f"Failed to start MCP client {cid}: {e}")
            return None

    def execute_tool(self, tool_name: str, arguments: dict, routing: dict[str, tuple[str, str]]) -> Any:
        if tool_name not in routing:
            return {"error": f"No active connector provides tool {tool_name}"}

        cid, kind = routing[tool_name]
        connector = get_connector(cid)
        if not connector:
            return {"error": f"Connector {cid} not found"}

        config = connector.get("config", {})

        if kind == "builtin":
            return execute_builtin_tool(cid, tool_name, arguments, config)
        elif kind in ("mcp_stdio", "mcp_sse"):
            client = self._get_or_create_mcp_client(cid, connector)
            if not client:
                return {"error": f"MCP client {cid} is not connected"}
            # Strip connector prefix to call original tool name on server
            orig_name = tool_name.removeprefix(f"{cid}_")
            return client.call_tool(orig_name, arguments)

        return {"error": f"Unsupported connector kind: {kind}"}
