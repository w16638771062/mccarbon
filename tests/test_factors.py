"""排放因子与食材归类的测试。"""

from __future__ import annotations

import unittest

from mccarbon import factors


class ClassifyFoodTest(unittest.TestCase):
    def test_common_items(self) -> None:
        cases = {
            "巨无霸": "beef",
            "双层吉士汉堡": "beef",
            "麦辣鸡腿堡": "chicken",
            "麦乐鸡（5块）": "chicken",
            "麦香鱼": "fish",
            "植物基汉堡": "plant",
            "薯条（中）": "side",
            "可乐（中）": "drink",
            "鲜煮咖啡": "coffee",
            "麦旋风": "dessert",
            "猪柳蛋麦满分": "breakfast",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(factors.classify_food(name), expected)

    def test_empty(self) -> None:
        self.assertEqual(factors.classify_food(""), "other")


class MatchDishTest(unittest.TestCase):
    def test_longest_keyword_wins(self) -> None:
        # 「双层巨无霸」应优先命中同名长键，而不是被「巨无霸」抢走
        self.assertEqual(factors.match_dish("双层巨无霸")[0], 4.46)
        self.assertEqual(factors.match_dish("巨无霸")[0], 2.35)
        self.assertEqual(factors.match_dish("双层吉士汉堡")[0], 2.80)

    def test_no_match(self) -> None:
        self.assertIsNone(factors.match_dish("完全未知的餐品"))


class ServingFactorTest(unittest.TestCase):
    def test_measured_anchor(self) -> None:
        value, basis, category = factors.serving_factor("巨无霸")
        self.assertEqual(value, 2.35)
        self.assertEqual(basis, "measured")
        self.assertEqual(category, "beef")

    def test_named_estimate(self) -> None:
        value, basis, category = factors.serving_factor("双层吉士汉堡")
        self.assertEqual(value, 2.80)
        self.assertEqual(basis, "est")
        self.assertEqual(category, "beef")

    def test_class_fallback(self) -> None:
        # 未知的牛肉命名应落到 beef 类别中值
        value, basis, category = factors.serving_factor("神秘牛肉特餐")
        self.assertEqual(basis, "class")
        self.assertEqual(category, "beef")
        self.assertEqual(value, factors.CATEGORY_SERVING_KG["beef"])

    def test_total_fallback(self) -> None:
        value, basis, category = factors.serving_factor("完全未知")
        self.assertEqual(basis, "class")
        self.assertEqual(category, "other")
        self.assertEqual(value, factors.CATEGORY_SERVING_KG["other"])


class PlantIsLowestTest(unittest.TestCase):
    def test_plant_cheaper_than_beef(self) -> None:
        beef, _, _ = factors.serving_factor("巨无霸")
        plant, _, _ = factors.serving_factor("植物基汉堡")
        self.assertLess(plant, beef)


class FactorTableTest(unittest.TestCase):
    def test_table_non_empty_and_measured_first(self) -> None:
        rows = factors.factor_table()
        self.assertTrue(rows)
        self.assertEqual(rows[0][2], "measured")

    def test_all_categories_have_factor(self) -> None:
        for key in ("beef", "chicken", "fish", "plant", "side", "drink",
                    "coffee", "dessert", "breakfast", "combo", "other"):
            self.assertIn(key, factors.CATEGORY_SERVING_KG)


if __name__ == "__main__":
    unittest.main()
