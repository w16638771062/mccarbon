"""碳核算引擎的测试。"""

from __future__ import annotations

import unittest
from datetime import datetime

from mccarbon import mock_data
from mccarbon.carbon import compute_carbon, order_layers
from mccarbon.models import Order, OrderItem


def _order(channel: str, items: tuple[OrderItem, ...], when: datetime | None = None) -> Order:
    return Order(
        order_id="T1",
        ts=when or datetime(2026, 3, 15, 12, 0),
        channel=channel,
        store="测试店",
        city="深圳",
        items=items,
        paid=30.0,
        listed=30.0,
    )


class OrderLayersTest(unittest.TestCase):
    def test_layers_sum(self) -> None:
        order = _order("delivery", (OrderItem("巨无霸", "汉堡", 1, 25.0, 550.0),))
        food, pack, delivery = order_layers(order)
        self.assertAlmostEqual(food, 2.35, places=4)
        self.assertGreater(pack, 0)
        self.assertAlmostEqual(delivery, 0.0156, places=4)

    def test_dine_in_has_no_delivery(self) -> None:
        order = _order("dine_in", (OrderItem("巨无霸", "汉堡", 1, 25.0, 550.0),))
        _, _, delivery = order_layers(order)
        self.assertEqual(delivery, 0.0)

    def test_qty_multiplies(self) -> None:
        order = _order("dine_in", (OrderItem("巨无霸", "汉堡", 2, 25.0, 550.0),))
        food, _, _ = order_layers(order)
        self.assertAlmostEqual(food, 4.70, places=4)

    def test_delivery_packaging_heavier_than_dine_in(self) -> None:
        items = (OrderItem("巨无霸", "汉堡", 1, 25.0, 550.0),)
        _, pack_delivery, _ = order_layers(_order("delivery", items))
        _, pack_dine_in, _ = order_layers(_order("dine_in", items))
        self.assertGreater(pack_delivery, pack_dine_in)


class ComputeCarbonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.orders = mock_data.generate_orders()
        cls.report = compute_carbon(cls.orders, dict(mock_data.MOCK_USER))

    def test_totals_are_consistent(self) -> None:
        report = self.report
        self.assertAlmostEqual(
            report.total_kg, report.food_kg + report.packaging_kg + report.delivery_kg, places=6
        )
        self.assertGreater(report.total_kg, 0)

    def test_food_is_dominant(self) -> None:
        # 餐品层应占九成左右
        self.assertGreater(self.report.food_kg / self.report.total_kg, 0.85)

    def test_monthly_axis_is_continuous(self) -> None:
        months = self.report.monthly
        self.assertTrue(months)
        for earlier, later in zip(months, months[1:]):
            ey, em = map(int, earlier.label.split("-"))
            ly, lm = map(int, later.label.split("-"))
            step = (ly * 12 + lm) - (ey * 12 + em)
            self.assertEqual(step, 1)

    def test_category_shares_cover_food_layer(self) -> None:
        # 类别占比是相对「总排放」计算的，因此其总和等于餐品层占总量的比例
        total = sum(category.share for category in self.report.categories)
        expected = self.report.food_kg / self.report.total_kg * 100
        self.assertAlmostEqual(total, expected, places=4)

    def test_grade_valid(self) -> None:
        self.assertIn(self.report.grade, ("A", "B", "C", "D", "E"))

    def test_order_count(self) -> None:
        self.assertEqual(self.report.order_count, len(self.orders))

    def test_conversions_positive(self) -> None:
        self.assertGreater(self.report.trees, 0)
        self.assertGreater(self.report.car_km, 0)

    def test_heaviest_is_max(self) -> None:
        order, kg = self.report.heaviest
        best = max(
            sum(order_layers(candidate)) for candidate in self.orders
        )
        self.assertAlmostEqual(kg, best, places=6)

    def test_empty_orders_raise(self) -> None:
        with self.assertRaises(ValueError):
            compute_carbon([])


class GradeBandTest(unittest.TestCase):
    def test_grade_bands_monotonic(self) -> None:
        from mccarbon.carbon import _grade_for

        self.assertEqual(_grade_for(5)[0], "A")
        self.assertEqual(_grade_for(50)[0], "B")
        self.assertEqual(_grade_for(100)[0], "C")
        self.assertEqual(_grade_for(200)[0], "D")
        self.assertEqual(_grade_for(1000)[0], "E")


if __name__ == "__main__":
    unittest.main()
