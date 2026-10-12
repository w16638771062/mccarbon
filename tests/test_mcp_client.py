"""MCP 客户端单元测试。"""

from __future__ import annotations

import json
import unittest

from mccarbon.mcp_client import ToolResult


class ToolResultTest(unittest.TestCase):
    def test_json_prefers_structured_content(self) -> None:
        """麦当劳 MCP 的真实返回在 structuredContent 里，text 是 Markdown 说明，必须优先取前者。"""
        result = ToolResult(
            raw={
                "content": [
                    {
                        "type": "text",
                        "text": "# API Response Information\n\n## Original Response\n\n{\"code\":200}",
                    }
                ],
                "structuredContent": {"success": True, "data": {"list": [{"orderId": "A1"}]}},
            }
        )
        self.assertEqual(result.json(), {"success": True, "data": {"list": [{"orderId": "A1"}]}})

    def test_json_falls_back_to_text_json(self) -> None:
        """没有 structuredContent 时，从文本块里抠 JSON。"""
        result = ToolResult(raw={"content": [{"type": "text", "text": json.dumps({"foo": "bar"})}]})
        self.assertEqual(result.json(), {"foo": "bar"})

    def test_json_embedded_in_markdown(self) -> None:
        result = ToolResult(
            raw={
                "content": [
                    {
                        "type": "text",
                        "text": "# Response\n\n## Original Response\n\n{\"code\":200,\"data\":{\"availablePoint\":\"162\"}}",
                    }
                ]
            }
        )
        self.assertEqual(result.json(), {"code": 200, "data": {"availablePoint": "162"}})


if __name__ == "__main__":
    unittest.main()
