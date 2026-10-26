"""Model Context Protocol (MCP) client supporting stdio and HTTP/SSE transports."""

import json
import subprocess
import threading
import time
import urllib.request
from typing import Any, Optional

class MCPStdioClient:
    """Manages an MCP server process over standard input/output (stdio JSON-RPC)."""

    def __init__(self, command: str, args: list[str] = None, env: dict = None):
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._lock = threading.Lock()

    def start(self) -> None:
        full_cmd = [self.command] + self.args
        self.process = subprocess.Popen(
            full_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        # Send MCP initialize handshake
        init_res = self._send_rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "TermuxAgent", "version": "1.0.0"}
        })
        # Send initialized notification
        self._send_notification("notifications/initialized", {})

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send_rpc(self, method: str, params: dict, timeout: float = 15.0) -> dict[str, Any]:
        with self._lock:
            if not self.process or self.process.poll() is not None:
                raise RuntimeError("MCP server process is not running.")
            
            req_id = self._next_id()
            payload = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params,
            }
            msg = json.dumps(payload) + "\n"
            self.process.stdin.write(msg)
            self.process.stdin.flush()

            # Read response
            line = self.process.stdout.readline()
            if not line:
                stderr_output = self.process.stderr.read() if self.process.stderr else ""
                raise RuntimeError(f"MCP server closed output stream. Stderr: {stderr_output}")
            
            resp = json.loads(line)
            if "error" in resp:
                raise RuntimeError(f"MCP Error: {resp['error']}")
            return resp.get("result", {})

    def _send_notification(self, method: str, params: dict) -> None:
        if not self.process or self.process.poll() is not None:
            return
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._send_rpc("tools/list", {})
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> Any:
        result = self._send_rpc("tools/call", {"name": name, "arguments": arguments})
        return result.get("content", [])

    def stop(self) -> None:
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2.0)
            except Exception:
                self.process.kill()


class MCPHttpClient:
    """Connects to a remote MCP server via HTTP / Streamable JSON-RPC."""

    def __init__(self, endpoint_url: str, headers: dict = None):
        self.endpoint_url = endpoint_url
        self.headers = headers or {"Content-Type": "application/json"}
        self._request_id = 0

    def _send_rpc(self, method: str, params: dict) -> dict[str, Any]:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        req = urllib.request.Request(
            self.endpoint_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self.headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise RuntimeError(f"MCP HTTP Error: {data['error']}")
            return data.get("result", {})

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._send_rpc("tools/list", {})
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> Any:
        result = self._send_rpc("tools/call", {"name": name, "arguments": arguments})
        return result.get("content", [])


def mcp_tool_to_openai_schema(mcp_tool: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Converts standard MCP tool schema to OpenAI/Gemini function declaration schema."""
    name = f"{prefix}_{mcp_tool['name']}" if prefix else mcp_tool["name"]
    parameters = mcp_tool.get("inputSchema", {"type": "object", "properties": {}})
    
    # Ensure parameter properties exist
    if "properties" not in parameters:
        parameters["properties"] = {}

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": mcp_tool.get("description", f"MCP tool {name}"),
            "parameters": parameters,
        }
    }
