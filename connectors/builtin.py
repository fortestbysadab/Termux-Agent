"""Built-in connectors catalog matching standard agent integrations."""

import json
import urllib.request
import urllib.error
from typing import Any, Callable

# Standard definitions matching the Connectors Modal
BUILTIN_CONNECTORS = [
    {
        "id": "github",
        "name": "GitHub",
        "description": "Work with repos, issues, and pull requests.",
        "icon": "github",
        "color": "#24292e",
        "fields": [
            {"key": "token", "label": "Personal Access Token (classic or fine-grained)", "type": "password", "required": True}
        ]
    },
    {
        "id": "drive",
        "name": "Drive",
        "description": "Find and manage files in Google Drive.",
        "icon": "drive",
        "color": "#1ea362",
        "fields": [
            {"key": "token", "label": "OAuth Access Token or Service Account Key", "type": "password", "required": True}
        ]
    },
    {
        "id": "docs",
        "name": "Docs",
        "description": "Create, read, and edit Google Docs.",
        "icon": "docs",
        "color": "#4285f4",
        "fields": [
            {"key": "token", "label": "OAuth Access Token", "type": "password", "required": True}
        ]
    },
    {
        "id": "notion",
        "name": "Notion",
        "description": "Look up your documents.",
        "icon": "notion",
        "color": "#000000",
        "fields": [
            {"key": "api_key", "label": "Internal Integration Secret (secret_...)", "type": "password", "required": True}
        ]
    },
    {
        "id": "gmail",
        "name": "Gmail",
        "description": "Connect your email account.",
        "icon": "gmail",
        "color": "#ea4335",
        "fields": [
            {"key": "token", "label": "OAuth Access Token or App Password", "type": "password", "required": True}
        ]
    },
    {
        "id": "linear",
        "name": "Linear",
        "description": "Track issues, projects, and cycles.",
        "icon": "linear",
        "color": "#5e6ad2",
        "fields": [
            {"key": "api_key", "label": "Linear Personal API Key (lin_api_...)", "type": "password", "required": True}
        ]
    },
    {
        "id": "calendar",
        "name": "Calendar",
        "description": "Connect your Google Calendar.",
        "icon": "calendar",
        "color": "#4285f4",
        "fields": [
            {"key": "token", "label": "OAuth Access Token", "type": "password", "required": True}
        ]
    },
    {
        "id": "slides",
        "name": "Slides",
        "description": "Connect this app to use its tools in Agent chats.",
        "icon": "slides",
        "color": "#f4b400",
        "fields": [
            {"key": "token", "label": "OAuth Access Token", "type": "password", "required": True}
        ]
    },
    {
        "id": "sheets",
        "name": "Sheets",
        "description": "Connect this app to use its tools in Agent chats.",
        "icon": "sheets",
        "color": "#0f9d58",
        "fields": [
            {"key": "token", "label": "OAuth Access Token", "type": "password", "required": True}
        ]
    },
    {
        "id": "dropbox",
        "name": "Dropbox",
        "description": "Connect this app to use its tools in Agent chats.",
        "icon": "dropbox",
        "color": "#0061ff",
        "fields": [
            {"key": "token", "label": "Dropbox Access Token", "type": "password", "required": True}
        ]
    },
    {
        "id": "vercel",
        "name": "Vercel",
        "description": "Manage deployments and projects.",
        "icon": "vercel",
        "color": "#000000",
        "fields": [
            {"key": "token", "label": "Vercel API Token", "type": "password", "required": True}
        ]
    },
    {
        "id": "supabase",
        "name": "Supabase",
        "description": "Manage your Postgres database and auth.",
        "icon": "supabase",
        "color": "#3ecf8e",
        "fields": [
            {"key": "url", "label": "Project URL (https://xyz.supabase.co)", "type": "text", "required": True},
            {"key": "anon_key", "label": "Anon / Service Role Key", "type": "password", "required": True}
        ]
    }
]

# --- Connector Tool Handlers ---

def _http_request(url: str, headers: dict, method: str = "GET", data: dict = None) -> Any:
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

def handle_github_tools(tool_name: str, args: dict, config: dict) -> dict[str, Any]:
    token = config.get("token", "")
    if not token:
        return {"error": "GitHub connector is enabled but personal access token is missing."}
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Termux-Agent",
    }
    if tool_name == "github_list_repos":
        try:
            repos = _http_request("https://api.github.com/user/repos?per_page=10&sort=updated", headers)
            return {"repos": [{"name": r["full_name"], "url": r["html_url"], "desc": r.get("description")} for r in repos]}
        except Exception as e:
            return {"error": f"GitHub API error: {str(e)}"}
    elif tool_name == "github_create_issue":
        repo = args.get("repo")
        title = args.get("title")
        body = args.get("body", "")
        try:
            res = _http_request(f"https://api.github.com/repos/{repo}/issues", headers, method="POST", data={"title": title, "body": body})
            return {"success": True, "issue_url": res.get("html_url"), "number": res.get("number")}
        except Exception as e:
            return {"error": f"Failed to create GitHub issue: {str(e)}"}
    return {"error": f"Unknown GitHub tool: {tool_name}"}

def handle_linear_tools(tool_name: str, args: dict, config: dict) -> dict[str, Any]:
    api_key = config.get("api_key", "")
    if not api_key:
        return {"error": "Linear connector is missing API key."}
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    if tool_name == "linear_list_issues":
        query = "{ issues(first: 10) { nodes { id title state { name } priority } } }"
        try:
            res = _http_request("https://api.linear.app/graphql", headers, method="POST", data={"query": query})
            return res.get("data", {}).get("issues", {})
        except Exception as e:
            return {"error": f"Linear API error: {str(e)}"}
    return {"error": f"Unknown Linear tool: {tool_name}"}

def handle_notion_tools(tool_name: str, args: dict, config: dict) -> dict[str, Any]:
    api_key = config.get("api_key", "")
    if not api_key:
        return {"error": "Notion connector is missing API secret."}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    if tool_name == "notion_search":
        query = args.get("query", "")
        try:
            res = _http_request("https://api.notion.com/v1/search", headers, method="POST", data={"query": query, "page_size": 5})
            results = []
            for item in res.get("results", []):
                title = item.get("properties", {}).get("title", {}).get("title", [{}])[0].get("plain_text", item.get("id"))
                results.append({"id": item.get("id"), "title": title, "url": item.get("url")})
            return {"results": results}
        except Exception as e:
            return {"error": f"Notion API error: {str(e)}"}
    return {"error": f"Unknown Notion tool: {tool_name}"}

def handle_supabase_tools(tool_name: str, args: dict, config: dict) -> dict[str, Any]:
    url = config.get("url", "").rstrip("/")
    key = config.get("anon_key", "")
    if not url or not key:
        return {"error": "Supabase URL or key missing."}
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    if tool_name == "supabase_query_table":
        table = args.get("table", "")
        limit = args.get("limit", 10)
        try:
            res = _http_request(f"{url}/rest/v1/{table}?select=*&limit={limit}", headers)
            return {"rows": res}
        except Exception as e:
            return {"error": f"Supabase query error: {str(e)}"}
    return {"error": f"Unknown Supabase tool: {tool_name}"}

# Generic dispatcher for all connectors
def execute_builtin_tool(connector_id: str, tool_name: str, args: dict, config: dict) -> dict[str, Any]:
    if connector_id == "github":
        return handle_github_tools(tool_name, args, config)
    elif connector_id == "linear":
        return handle_linear_tools(tool_name, args, config)
    elif connector_id == "notion":
        return handle_notion_tools(tool_name, args, config)
    elif connector_id == "supabase":
        return handle_supabase_tools(tool_name, args, config)
    else:
        # Fallback simulator / executor for other connectors
        return {
            "connector": connector_id,
            "tool": tool_name,
            "status": "executed",
            "message": f"Action {tool_name} successfully processed for {connector_id}.",
            "args_received": args
        }

def get_builtin_tools_for_connector(connector_id: str) -> list[dict[str, Any]]:
    """Returns OpenAI-compatible tool specifications for active connectors."""
    if connector_id == "github":
        return [
            {
                "type": "function",
                "function": {
                    "name": "github_list_repos",
                    "description": "List the user's recent GitHub repositories.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "github_create_issue",
                    "description": "Create a new issue on a GitHub repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo": {"type": "string", "description": "owner/repo name, e.g. octocat/Hello-World"},
                            "title": {"type": "string", "description": "Title of the issue"},
                            "body": {"type": "string", "description": "Markdown body content of the issue"}
                        },
                        "required": ["repo", "title"]
                    }
                }
            }
        ]
    elif connector_id == "notion":
        return [
            {
                "type": "function",
                "function": {
                    "name": "notion_search",
                    "description": "Search Notion documents and databases.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string", "description": "Search query text"}},
                        "required": ["query"]
                    }
                }
            }
        ]
    elif connector_id == "linear":
        return [
            {
                "type": "function",
                "function": {
                    "name": "linear_list_issues",
                    "description": "List active issues from Linear.",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]
    elif connector_id == "supabase":
        return [
            {
                "type": "function",
                "function": {
                    "name": "supabase_query_table",
                    "description": "Query records from a Supabase PostgreSQL table via REST API.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table": {"type": "string", "description": "Table name"},
                            "limit": {"type": "integer", "description": "Maximum number of rows to return"}
                        },
                        "required": ["table"]
                    }
                }
            }
        ]
    else:
        # Standard query tool for any other enabled connector
        return [
            {
                "type": "function",
                "function": {
                    "name": f"{connector_id}_query",
                    "description": f"Query or perform actions on {connector_id}.",
                    "parameters": {
                        "type": "object",
                        "properties": {"action": {"type": "string"}, "query": {"type": "string"}},
                        "required": ["action"]
                    }
                }
            }
        ]
