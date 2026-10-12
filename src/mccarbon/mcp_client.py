"""麦当劳 MCP Server 客户端（Streamable HTTP + JSON-RPC 2.0）。

仅依赖 Python 标准库 ``urllib``，无需 pip 安装任何第三方包。

协议要点（对照官方集成指南 https://github.com/M-China/mcd-mcp-server）：
- 接入地址：https://mcp.mcd.cn
- 传输协议：Streamable HTTP
- 鉴权：请求头 ``Authorization: Bearer <MCP_TOKEN>``
- 响应可能是 ``application/json``，也可能是 ``text/event-stream``（SSE），本类两种都兼容。
- 限流：每个 Token 每分钟最多 600 次请求，超限返回 429。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_ENDPOINT = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-06-18"

# 与本项目相关的核心 Tool（麦当劳 MCP Server v1.0.9）
TOOL_ORDER_LIST = "order-list"
TOOL_ORDER_DETAIL = "query-order"
TOOL_MALL_ORDER_LIST = "mall-order-list"
TOOL_MALL_ORDER_DETAIL = "mall-order-detail"
TOOL_MY_ACCOUNT = "query-my-account"
TOOL_NUTRITION = "list-nutrition-foods"
TOOL_NOW_TIME = "now-time-info"


class MCPError(RuntimeError):
    """MCP 调用过程中的错误。"""


@dataclass
class ToolResult:
    """对 tools/call 返回结果的轻量封装。"""

    raw: dict
    is_error: bool = False

    def texts(self) -> list[str]:
        """提取 content 中的全部文本块。"""
        out: list[str] = []
        for block in self.raw.get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                out.append(str(block.get("text", "")))
        if not out and isinstance(self.raw.get("structuredContent"), (dict, list)):
            out.append(json.dumps(self.raw["structuredContent"], ensure_ascii=False))
        return out

    def json(self) -> Any:
        """尽力把返回内容解析为 JSON。

        优先取 ``structuredContent``：麦当劳 MCP 的 ``content[].text`` 前半段是给模型看的
        人类可读说明 + Markdown 表格，真正可解析的数据在 ``structuredContent`` 里。
        只有在没有 ``structuredContent`` 时，才退回去从文本块里抠 JSON。
        """
        structured = self.raw.get("structuredContent")
        if isinstance(structured, (dict, list)) and structured:
            return structured

        for text in self.texts():
            text = text.strip()
            if not text:
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
            embedded = _extract_embedded_json(text)
            if embedded is not None:
                return embedded
        return self.texts()


def _extract_embedded_json(text: str) -> Any:
    """从「说明文字 + JSON」混排的文本里抠出 JSON（``## Original Response`` 之后的段落）。"""
    marker = "Original Response"
    index = text.find(marker)
    candidate = text[index + len(marker):] if index >= 0 else text
    start = candidate.find("{")
    while start >= 0:
        depth = 0
        in_string = False
        escaped = False
        for position in range(start, len(candidate)):
            char = candidate[position]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(candidate[start:position + 1])
                    except json.JSONDecodeError:
                        break
        start = candidate.find("{", start + 1)
    return None


class MCPClient:
    """最小可用的 MCP 客户端。"""

    def __init__(
        self,
        endpoint: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self.endpoint = (endpoint or os.environ.get("MCD_MCP_ENDPOINT") or DEFAULT_ENDPOINT).rstrip("/")
        self.token = token or os.environ.get("MCD_MCP_TOKEN", "")
        self.timeout = timeout
        self.max_retries = max_retries
        self._session_id: str | None = None
        self._next_id = 0
        self._tools_cache: list[dict] | None = None

    # ------------------------------------------------------------------ 基础
    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
            "User-Agent": "mccarbon/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _request(self, method: str, params: dict | None = None) -> Any:
        if not self.token:
            raise MCPError("缺少 MCP Token：请设置环境变量 MCD_MCP_TOKEN，或改用 --mock 离线模式。")

        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        self._next_id += 1
        if params is not None:
            payload["params"] = params

        data = json.dumps(payload).encode("utf-8")
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            request = urllib.request.Request(
                self.endpoint, data=data, headers=self._headers(), method="POST"
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    session_id = response.headers.get("Mcp-Session-Id")
                    if session_id:
                        self._session_id = session_id
                    body = response.read().decode("utf-8", errors="replace")
                return self._parse_body(body)
            except urllib.error.HTTPError as exc:  # noqa: PERF203
                detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
                if exc.code == 401:
                    raise MCPError(f"401：MCP Token 无效或已过期。{detail}") from exc
                if exc.code == 429:
                    wait = 1.5 * (attempt + 1)
                    last_error = MCPError("429：触发限流（600 次/分钟），已自动退避重试。")
                    time.sleep(wait)
                    continue
                raise MCPError(f"HTTP {exc.code}：{detail or exc.reason}") from exc
            except urllib.error.URLError as exc:
                last_error = MCPError(f"网络错误：{exc.reason}")
                time.sleep(1.0 * (attempt + 1))
                continue

        raise last_error or MCPError("未知错误")

    @staticmethod
    def _parse_body(body: str) -> Any:
        text = body.strip()
        if not text:
            return {}
        if text.startswith("{"):
            return MCPClient._unwrap(json.loads(text))
        # SSE：逐行取 data: 后面的 JSON
        result: Any = None
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                chunk = line[len("data:"):].strip()
                if chunk:
                    result = MCPClient._unwrap(json.loads(chunk))
        if result is None:
            raise MCPError(f"无法解析响应：{text[:200]}")
        return result

    @staticmethod
    def _unwrap(message: dict) -> Any:
        if "error" in message:
            error = message["error"]
            raise MCPError(f"MCP 错误 {error.get('code', '')}: {error.get('message', error)}")
        return message.get("result", message)

    # ------------------------------------------------------------ MCP 生命周期
    def initialize(self) -> Any:
        return self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mccarbon", "version": "1.0.0"},
            },
        )

    def list_tools(self, refresh: bool = False) -> list[dict]:
        if self._tools_cache is None or refresh:
            result = self._request("tools/list")
            self._tools_cache = list(result.get("tools", []) if isinstance(result, dict) else [])
        return self._tools_cache

    def call_tool(self, name: str, arguments: dict | None = None) -> ToolResult:
        result = self._request("tools/call", {"name": name, "arguments": arguments or {}})
        if not isinstance(result, dict):
            return ToolResult(raw={"content": [{"type": "text", "text": str(result)}]})
        return ToolResult(raw=result, is_error=bool(result.get("isError")))

    def close(self) -> None:
        """释放会话（服务端通常自动回收，这里仅做尽力而为的清理）。"""
        if not self._session_id:
            return
        request = urllib.request.Request(
            self.endpoint, headers=self._headers(), method="DELETE"
        )
        try:
            urllib.request.urlopen(request, timeout=5)
        except Exception:  # noqa: BLE001 - 清理失败不应影响主流程
            pass
        finally:
            self._session_id = None
