"""减排模拟器的测试。"""

from __future__ import annotations

import unittest
from datetime import datetime

from mccarbon.carbon import compute_carbon
from mccarbon.factors import CATEGORY_SERVING_KG
from mccarbon.models import Order, OrderItem
from mccarbon.reduce import combined_ceiling, simulate, top_reductions


def _make(channel: str, items: tuple[OrderItem, ...]) -> Order:
    return Order(
        order_id="R1",
        ts=datetime(2026, 5, 1, 12, 0),
        channel=channel,
        store="测试店",
        city="深圳",
        items=items,
        paid=40.0,
        listed=40.0,
    )


class ReduceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.order = _make("delivery", (OrderItem("巨无霸", "汉堡", 1, 25.0, 550.0),))
        self.report = compute_carbon([self.order], {"name": "测试"})

    def test_sorted_descending(self) -> None:
        options = simulate(self.report, [self.order])
        savings = [option.kg_saved for option in options]
        self.assertEqual(savings, sorted(savings, reverse=True))

    def test_only_positive_savings(self) -> None:
        for option in simulate(self.report, [self.order]):
            self.assertGreater(option.kg_saved, 0)

    def test_beef_swap_value(self) -> None:
        options = {option.key: option for option in simulate(self.report, [self.order])}
        self.assertIn("swap_beef", options)
        expected = 2.35 - CATEGORY_SERVING_KG["chicken"]
        self.assertAlmostEqual(options["swap_beef"].kg_saved, expected, places=4)

    def test_pickup_value(self) -> None:
        options = {option.key: option for option in simulate(self.report, [self.order])}
        self.assertIn("pickup", options)
        # 1 件餐品：外送包装 73 + 90 = 163g，到店 10 + 4 = 14g，再叠加配送段 15.6g
        expected = (163 - 14) / 1000.0 + 0.0156
        self.assertAlmostEqual(options["pickup"].kg_saved, expected, places=4)

    def test_dine_in_has_no_pickup(self) -> None:
        order = _make("dine_in", (OrderItem("巨无霸", "汉堡", 1, 25.0, 550.0),))
        report = compute_carbon([order], {"name": "测试"})
        keys = {option.key for option in simulate(report, [order])}
        self.assertNotIn("pickup", keys)

    def test_top_reductions_limit(self) -> None:
        self.assertLessEqual(len(top_reductions(self.report, [self.order], n=2)), 2)

    def test_combined_ceiling_within_total(self) -> None:
        ceiling = combined_ceiling(self.report, [self.order])
        self.assertLessEqual(ceiling, self.report.total_kg + 1e-9)


if __name__ == "__main__":
    unittest.main()
