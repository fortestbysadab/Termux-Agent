"""LLM Planner: communicates with OpenAI-compatible / Gemini / Groq endpoints."""

import copy
import json
import logging
import urllib.request
import urllib.error
from typing import Any, Optional
from config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

# Keywords rejected by Google Gemini's schema parser
GEMINI_REJECTED_KEYWORDS = {
    "additionalProperties", "patternProperties", "$schema", "$id", "$ref",
    "exclusiveMinimum", "exclusiveMaximum", "allOf", "not"
}

def clean_schema_for_gemini(node: Any) -> Any:
    if isinstance(node, dict):
        cleaned = {}
        for k, v in node.items():
            if k in GEMINI_REJECTED_KEYWORDS:
                continue
            cleaned[k] = clean_schema_for_gemini(v)
        return cleaned
    if isinstance(node, list):
        return [clean_schema_for_gemini(item) for item in node]
    return node

class LLMPlanner:
    def __init__(
        self,
        base_url: str = LLM_BASE_URL,
        api_key: str = LLM_API_KEY,
        model: str = LLM_MODEL,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.is_gemini = "generativelanguage.googleapis.com" in self.base_url or "gemini" in self.model.lower()

    def complete(self, messages: list[dict], tools: list[dict] = None) -> dict[str, Any]:
        """Send chat completion request to the provider."""
        if not self.api_key:
            # Helpful mock fallback if key is not configured yet
            last_msg = messages[-1]["content"] if messages else ""
            if "run" in last_msg.lower() or "list" in last_msg.lower() or "create" in last_msg.lower():
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_default_term",
                            "name": "run_terminal_command",
                            "arguments": {"command": "ls -la"}
                        }
                    ]
                }
            return {
                "content": (
                    "⚠️ **LLM API Key Not Configured**\n\n"
                    "Please set `LLM_API_KEY` in `.env` or in `config.py`.\n"
                    "Supported providers: Google Gemini, OpenAI, Groq, Ollama, OpenRouter."
                ),
                "tool_calls": []
            }

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Termux-Agent/1.0",
        }

        # Prepare payload
        payload_messages = copy.deepcopy(messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "temperature": 0.2,
        }

        if tools:
            formatted_tools = copy.deepcopy(tools)
            if self.is_gemini:
                formatted_tools = [clean_schema_for_gemini(t) for t in formatted_tools]
            payload["tools"] = formatted_tools
            payload["tool_choice"] = "auto"

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", "replace")
            logger.error(f"LLM API Error (HTTP {e.code}): {err_body}")
            return {
                "content": f"⚠️ **LLM Error (HTTP {e.code})**: {err_body}",
                "tool_calls": []
            }
        except Exception as e:
            logger.error(f"LLM Network/Connection Error: {e}")
            return {
                "content": f"⚠️ **Connection Failed**: {str(e)}",
                "tool_calls": []
            }

        choices = result.get("choices", [])
        if not choices:
            return {"content": "Empty response from LLM.", "tool_calls": []}

        msg = choices[0].get("message", {})
        content = msg.get("content")
        raw_tool_calls = msg.get("tool_calls", [])

        parsed_tool_calls = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except Exception:
                args = {}
            parsed_tool_calls.append({
                "id": tc.get("id", "call_default"),
                "name": fn.get("name"),
                "arguments": args,
            })

        return {
            "content": content,
            "tool_calls": parsed_tool_calls
        }
