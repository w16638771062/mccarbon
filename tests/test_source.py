"""数据源层单元测试。"""

from __future__ import annotations

import json
import unittest

from mccarbon.mcp_client import MCPClient, MCPError
from mccarbon.nutrition import Nutrition, parse_nutrition
from mccarbon.source import (
    fetch_orders,
    infer_city,
    parse_account,
    parse_order,
)


class DummyClient(MCPClient):
    """允许不读环境变量、直接指定测试行为的 MCP 客户端。"""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls = []
        self._session_id = None
        self._next_id = 0

    def call_tool(self, name: str, arguments: dict | None = None):
        self.calls.append((name, arguments))
        if not self._responses:
            raise MCPError("unexpected call")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        from mccarbon.mcp_client import ToolResult

        return ToolResult(raw=response)


class ParseOrderTest(unittest.TestCase):
    def test_expands_combo_items(self) -> None:
        """orderProductList 里含 comboItemList 的套餐应被展开成单品。"""
        table = {"中薯条": Nutrition(kcal=289), "麦香鸡": Nutrition(kcal=369)}
        raw = {
            "orderId": "O1",
            "createTime": "2026-07-19 15:37:56",
            "storeName": "麦当劳深圳某店",
            "orderStatus": "订单已完成",
            "realTotalAmount": "19.8",
            "orderProductList": [
                {
                    "productName": "买薯送薯",
                    "quantity": 2,
                    "comboItemList": [
                        {"name": "中薯条", "quantity": 1},
                        {"name": "中薯条", "quantity": 1},
                    ],
                }
            ],
        }
        order = parse_order(raw, table=table)
        assert order is not None
        self.assertEqual(order.item_count, 4)  # 2 份 × 2 中薯条
        self.assertAlmostEqual(order.kcal, 289 * 4, places=1)
        self.assertEqual(order.items[0].category, "小食")

    def test_skips_void_status_orders(self) -> None:
        raw = {
            "orderId": "O2",
            "createTime": "2026-07-19 15:00:00",
            "storeName": "店",
            "orderStatus": "已取消",
            "orderProductList": [{"productName": "巨无霸", "quantity": 1}],
        }
        self.assertIsNone(parse_order(raw, table={"巨无霸": Nutrition(kcal=500)}))


class InferCityTest(unittest.TestCase):
    def test_city_from_store_name(self) -> None:
        self.assertEqual(infer_city("麦当劳深圳观荟里餐厅"), "深圳")
        self.assertEqual(infer_city("麦当劳茂名电白万达餐厅"), "茂名")
        self.assertEqual(infer_city("麦当劳广州解放北路餐厅"), "广州")
        self.assertEqual(infer_city("麦当劳香港某店"), "香港")
        self.assertEqual(infer_city("某不知名餐厅"), "")


class FetchOrdersTest(unittest.TestCase):
    def test_first_page_mcp_error_propagates(self) -> None:
        """首页调用失败时，必须暴露真实原因（如 Token 缺失/无效），而不是吞掉后变成"没订单"。"""
        client = DummyClient([MCPError("401：MCP Token 无效或已过期。")])
        with self.assertRaises(MCPError) as ctx:
            fetch_orders(client)
        self.assertIn("Token", str(ctx.exception))

    def test_later_page_error_breaks_gracefully(self) -> None:
        """后续页失败时，应保留已拿到的订单并结束翻页。"""
        record = {
            "orderId": "A1",
            "orderTime": "2026-05-01 12:00:00",
            "items": [{"productName": "巨无霸", "quantity": 1, "price": 24.0}],
            "payAmount": 24.0,
        }
        client = DummyClient([
            {"content": [{"type": "text", "text": json.dumps({"orders": [record]}, ensure_ascii=False)}]},
            MCPError("网络错误"),
        ])
        orders, skipped = fetch_orders(client)
        self.assertEqual(len(orders), 1)
        self.assertEqual(skipped, 0)

    def test_prefers_structured_content(self) -> None:
        """新版麦当劳 MCP 把结构化 JSON 放在 structuredContent 里，json() 应优先取它。"""
        record = {
            "orderId": "A2",
            "createTime": "2026-06-01 12:00:00",
            "storeName": "麦当劳上海某店",
            "orderStatus": "订单已完成",
            "orderProductList": [{"productName": "中薯条", "quantity": 1}],
            "realTotalAmount": "13.5",
        }
        client = DummyClient([
            {"structuredContent": {"success": True, "data": {"list": [record]}}},
        ])
        orders, skipped = fetch_orders(client, table={"中薯条": Nutrition(kcal=289)})
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].store, "麦当劳上海某店")
        self.assertEqual(orders[0].item_count, 1)
        self.assertEqual(skipped, 0)


class ParseAccountTest(unittest.TestCase):
    def test_reads_common_fields(self) -> None:
        account = parse_account({
            "nickName": "麦门老张",
            "memberId": "M888666",
            "levelName": "金卡会员",
            "availablePoints": "3,860",
            "totalPoints": 12940,
            "expiringPoints": 420,
        })
        self.assertEqual(account["name"], "麦门老张")
        self.assertEqual(account["member_id"], "M888666")
        self.assertEqual(account["level"], "金卡会员")
        # "3,860" 这类带千分位的字符串也要能解析
        self.assertEqual(account["points_available"], 3860)
        self.assertEqual(account["points_total"], 12940)
        self.assertEqual(account["points_expiring"], 420)

    def test_reads_real_mcd_fields(self) -> None:
        """官方线上接口实际返回 availablePoint / accumulativePoint / currentMouthExpirePoint 等字段。"""
        account = parse_account({
            "code": 200,
            "data": {
                "accountId": "42FBD022-35A7-7E0A-B728-FF1B0ED66000",
                "availablePoint": "162",
                "accumulativePoint": "333.1",
                "currency": "麦享会积分",
                "currentMouthExpirePoint": "0",
                "usedPoint": "0",
            },
        })
        self.assertEqual(account["member_id"], "42FBD022-35A7-7E0A-B728-FF1B0ED66000")
        self.assertEqual(account["points_available"], 162)
        self.assertEqual(account["points_total"], 333)
        self.assertEqual(account["points_used"], 0)
        self.assertEqual(account["points_label"], "麦享会积分")

    def test_reads_nested_payload(self) -> None:
        account = parse_account({
            "code": 0,
            "data": {"member": {"nickname": "小王", "memberNo": "A1", "points": 120}},
        })
        self.assertEqual(account["name"], "小王")
        self.assertEqual(account["member_id"], "A1")
        self.assertEqual(account["points_available"], 120)

    def test_missing_fields_are_none(self) -> None:
        account = parse_account({"foo": "bar"})
        self.assertIsNone(account["name"])
        self.assertIsNone(account["member_id"])
        self.assertIsNone(account["points_available"])

    def test_non_dict_returns_empty(self) -> None:
        self.assertEqual(parse_account(["nope"]), {})
        self.assertEqual(parse_account(None), {})


if __name__ == "__main__":
    unittest.main()
