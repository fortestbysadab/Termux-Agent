"""LLM Planner: communicates with OpenAI-compatible / Gemini / Groq endpoints."""

import copy
import json
import logging
import urllib.request
import urllib.error
from typing import Any, Optional
from config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

# Keywords rejected by Google Gemini's OpenAPI 3.0 schema parser
GEMINI_REJECTED_KEYWORDS = frozenset({
    "additionalProperties", "patternProperties", "propertyNames", "const",
    "$schema", "$id", "$ref", "$defs", "definitions", "exclusiveMinimum",
    "exclusiveMaximum", "allOf", "oneOf", "not", "if", "then", "else",
    "examples", "default", "multipleOf", "uniqueItems", "readOnly", "writeOnly"
})

UNSIGNED_PLACEHOLDER = "skip_thought_signature_validator"

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

def adapt_tools_for_gemini(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    adapted = []
    for tool in tools:
        entry = copy.deepcopy(tool)
        fn = entry.get("function", {})
        params = fn.get("parameters")
        if isinstance(params, dict):
            if params.get("properties"):
                fn["parameters"] = clean_schema_for_gemini(params)
            else:
                # Gemini rejects `{"type": "object", "properties": {}}`
                fn.pop("parameters", None)
        entry["function"] = fn
        adapted.append(entry)
    return adapted

def adapt_messages_for_gemini(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    adapted = []
    for msg in messages:
        entry = copy.deepcopy(msg)
        role = entry.get("role")

        if role == "assistant":
            tool_calls = entry.get("tool_calls")
            if tool_calls and isinstance(tool_calls, list):
                # Gemini requires omitting content when tool_calls are present
                entry.pop("content", None)
                
                head = tool_calls[0] if tool_calls else {}
                msg_extra = entry.get("extra_content")
                if isinstance(msg_extra, dict) and not head.get("extra_content"):
                    head["extra_content"] = copy.deepcopy(msg_extra)

                has_sig = bool((head.get("extra_content") or {}).get("google", {}).get("thought_signature"))
                
                # If unsigned, add escape hatch placeholder to prevent HTTP 400
                if not has_sig and tool_calls:
                    if not isinstance(head.get("extra_content"), dict):
                        head["extra_content"] = {}
                    head["extra_content"].setdefault("google", {})["thought_signature"] = UNSIGNED_PLACEHOLDER
            elif entry.get("content") is None:
                entry["content"] = ""

        elif role == "tool":
            # Gemini OpenAI compatibility rejects custom `name` field on tool replies
            entry.pop("name", None)

        adapted.append(entry)
    return adapted

def parse_provider_error(status_code: int, raw_body: str) -> dict[str, str]:
    title = f"Provider Error (HTTP {status_code})"
    remedy = ""
    message = raw_body[:500]

    try:
        data = json.loads(raw_body)
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            data = data[0]
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                message = err.get("message") or str(err)
            elif err:
                message = str(err)
    except Exception:
        pass

    if status_code in (401, 403):
        title = "Authentication Failed"
        remedy = "Verify LLM_API_KEY in your .env file."
    elif status_code == 404:
        title = "Model or Endpoint Not Found"
        remedy = "Verify LLM_BASE_URL and LLM_MODEL in .env. For Gemini, use: https://generativelanguage.googleapis.com/v1beta/openai"
    elif status_code == 429:
        title = "Quota / Rate Limit Exceeded"
        remedy = "Your API quota is exceeded. Wait a few moments or check your API billing tier."
    elif status_code == 400:
        if "thought_signature" in message.lower():
            title = "Missing Thought Signature"
            remedy = "Gemini thinking models require thought_signature on tool call replay."
        else:
            title = "Invalid Request Schema (HTTP 400)"
            remedy = "The model rejected the parameter schema or function call format."

    return {
        "title": title,
        "message": message,
        "remedy": remedy,
        "raw": raw_body[:1000]
    }

class LLMPlanner:
    def __init__(
        self,
        base_url: str = LLM_BASE_URL,
        api_key: str = LLM_API_KEY,
        model: str = LLM_MODEL,
        timeout: float = 60.0,
    ):
        raw_url = base_url.rstrip("/")
        # Repair common Gemini URL paths
        if "generativelanguage.googleapis.com" in raw_url:
            if not raw_url.endswith("/v1beta/openai"):
                if raw_url.endswith("/v1beta") or raw_url.endswith("/v1"):
                    raw_url = raw_url.rsplit("/", 1)[0] + "/v1beta/openai"
                else:
                    raw_url = raw_url + "/v1beta/openai"
        self.base_url = raw_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.is_gemini = "generativelanguage.googleapis.com" in self.base_url or "gemini" in self.model.lower()

    def complete(self, messages: list[dict], tools: list[dict] = None) -> dict[str, Any]:
        """Send chat completion request to the provider."""
        if not self.api_key:
            return {
                "content": None,
                "error": {
                    "title": "LLM API Key Missing",
                    "message": "No API key was provided.",
                    "remedy": "Please set LLM_API_KEY in your .env file or environment.",
                    "raw": "LLM_API_KEY is empty."
                },
                "tool_calls": []
            }

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Termux-Agent/2.0",
        }

        # Prepare messages
        if self.is_gemini:
            payload_messages = adapt_messages_for_gemini(messages)
        else:
            payload_messages = copy.deepcopy(messages)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "temperature": 0.2,
        }

        if tools:
            if self.is_gemini:
                payload["tools"] = adapt_tools_for_gemini(tools)
            else:
                payload["tools"] = copy.deepcopy(tools)
            payload["tool_choice"] = "auto"

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", "replace")
            err_parsed = parse_provider_error(e.code, err_body)
            logger.error(f"LLM API Error (HTTP {e.code}): {err_body}")
            return {
                "content": None,
                "error": err_parsed,
                "tool_calls": []
            }
        except Exception as e:
            logger.error(f"LLM Network/Connection Error: {e}")
            err_parsed = {
                "title": "Connection Failed",
                "message": str(e),
                "remedy": "Check your phone's network connection and the LLM endpoint URL.",
                "raw": str(e)
            }
            return {
                "content": None,
                "error": err_parsed,
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
            
            # Preserve extra_content (such as thought_signature from Gemini 3/2.5)
            extra = tc.get("extra_content")
            parsed_tool_calls.append({
                "id": str(tc.get("id") or "call_default"),
                "name": str(fn.get("name") or ""),
                "arguments": args,
                "extra_content": dict(extra) if isinstance(extra, dict) else {},
            })

        return {
            "content": content,
            "tool_calls": parsed_tool_calls
        }
