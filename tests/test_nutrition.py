"""营养表解析与餐品归类测试。"""

from __future__ import annotations

import unittest

from mccarbon.nutrition import (
    Nutrition,
    classify_category,
    lookup,
    parse_nutrition,
)

_OFFICIAL_TABLE = """\
[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
  猪柳麦满分,null,1288,308,16,16,24,781,213
  中薯条,null,1210,289,4,12,38,165,18
  麦辣鸡腿汉堡,null,2029,485,24,24,42,1208,154
  可乐大杯,null,936,224,0,0,55,0,15
  草莓新地,null,1027,245,4,6,43,84,158
  菠萝派,null,925,221,2,11,27,147,5
  优品豆浆小杯,null,63,15,1,0,3,2,6
"""


class NutritionParseTest(unittest.TestCase):
    def test_parse_official_text_table(self) -> None:
        table = parse_nutrition({"data": _OFFICIAL_TABLE})
        self.assertEqual(len(table), 7)
        self.assertEqual(table["中薯条"].kcal, 289)
        self.assertEqual(table["麦辣鸡腿汉堡"].protein, 24)
        self.assertEqual(table["可乐大杯"].carbohydrate, 55)

    def test_direct_string_input(self) -> None:
        table = parse_nutrition(_OFFICIAL_TABLE)
        self.assertIn("草莓新地", table)
        self.assertEqual(table["草莓新地"].kcal, 245)

    def test_lookup_with_normalization(self) -> None:
        table = parse_nutrition({"data": _OFFICIAL_TABLE})
        self.assertEqual(lookup(table, "优品豆浆小杯").kcal, 15)
        self.assertEqual(lookup(table, "中薯条").kcal, 289)
        self.assertIsNone(lookup(table, "不存在的商品"))


class ClassifyCategoryTest(unittest.TestCase):
    def test_breakfast(self) -> None:
        self.assertEqual(classify_category("猪柳蛋麦满分"), "早餐")
        self.assertEqual(classify_category("脆薯饼"), "早餐")

    def test_burger(self) -> None:
        self.assertEqual(classify_category("麦辣鸡腿汉堡"), "汉堡")
        self.assertEqual(classify_category("巨无霸"), "汉堡")
        self.assertEqual(classify_category("芝芝火腿扒堡"), "汉堡")

    def test_snack(self) -> None:
        self.assertEqual(classify_category("中薯条"), "小食")
        self.assertEqual(classify_category("麦乐鸡5块"), "小食")

    def test_drink(self) -> None:
        self.assertEqual(classify_category("可乐大杯"), "饮料")
        self.assertEqual(classify_category("优品豆浆小杯"), "饮料")

    def test_dessert(self) -> None:
        self.assertEqual(classify_category("草莓新地"), "甜品")
        self.assertEqual(classify_category("菠萝派"), "甜品")

    def test_coffee(self) -> None:
        self.assertEqual(classify_category("冰奶铁中杯"), "咖啡")
        self.assertEqual(classify_category("川宁伯爵红茶"), "咖啡")

    def test_combo(self) -> None:
        self.assertEqual(classify_category("随心配1+1"), "套餐")
        self.assertEqual(classify_category("买薯送薯"), "套餐")

    def test_other(self) -> None:
        self.assertEqual(classify_category("某神秘新品"), "其他")


if __name__ == "__main__":
    unittest.main()
