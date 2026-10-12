"""碳核算引擎：把历史订单换算成「麦门碳账本」。

三层模型（详见 README 的「方法学」一节）：

- **餐品层**：每个 SKU（套餐已展开成子项）× 单份因子。约占总量九成，是减排的主战场。
- **包装层**：按渠道区分——外送（餐盒 + 餐具 + 袋）远重于到店 / 自提。
- **配送层**：仅外送计入，到店 / 自提为 0。

输出一个 ``CarbonReport``，包含总量、三层结构、月度曲线、食材类别归因、
最碳重一单、碳等级与直观换算（树 / 公里）。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from . import factors
from .factors import (
    CAR_G_PER_KM,
    DELIVERY_PER_ORDER_G,
    PACKAGING_DELIVERY_BASE_G,
    PACKAGING_DELIVERY_PER_ITEM_G,
    PACKAGING_DINEIN_BASE_G,
    PACKAGING_DINEIN_PER_ITEM_G,
    SMARTPHONE_CHARGE_G,
    TREE_ABSORB_KG_PER_YEAR,
)
from .models import Order

CATEGORY_LABELS: dict[str, str] = {
    "beef": "牛肉类",
    "chicken": "鸡肉类",
    "fish": "鱼类",
    "plant": "植物基",
    "side": "小食 / 薯类",
    "drink": "饮品",
    "coffee": "咖啡",
    "dessert": "甜品",
    "breakfast": "早餐",
    "combo": "套餐",
    "other": "其他",
}

# 碳等级分档（按年度总排放 kg CO2e）。阈值是可解释的经验分档，不是官方标准。
_GRADE_BANDS: tuple[tuple[str, float], ...] = (
    ("A", 30.0),
    ("B", 80.0),
    ("C", 160.0),
    ("D", 320.0),
)
_GRADE_HINTS: dict[str, str] = {
    "A": "低碳饮食，继续保持",
    "B": "总体克制，仍有优化空间",
    "C": "中等强度，蛋白质来源是关键变量",
    "D": "偏高，换一换红肉就有明显下降",
    "E": "高碳饮食，减排潜力很大",
}
_GRADE_LABELS: dict[str, str] = {
    "A": "低碳先锋",
    "B": "轻碳选手",
    "C": "中碳常客",
    "D": "高碳重度爱好者",
    "E": "碳排大户",
}


@dataclass(frozen=True)
class DishCarbon:
    """某个餐品在整个统计区间里的碳贡献。"""

    name: str
    category: str
    qty: int
    per_unit_kg: float
    total_kg: float
    basis: str  # measured / est / class

    @property
    def category_label(self) -> str:
        return CATEGORY_LABELS.get(self.category, self.category)


@dataclass(frozen=True)
class CategoryCarbon:
    key: str
    label: str
    kg: float
    share: float  # 占总量的百分比
    qty: int


@dataclass(frozen=True)
class MonthCarbon:
    label: str
    kg: float
    orders: int


@dataclass
class CarbonReport:
    total_kg: float
    food_kg: float
    packaging_kg: float
    delivery_kg: float
    monthly: tuple[MonthCarbon, ...]
    categories: tuple[CategoryCarbon, ...]
    top_dishes: tuple[DishCarbon, ...]
    heaviest: tuple[Order, float] | None
    order_count: int
    item_count: int
    start: date
    end: date
    year_label: str
    user_name: str = ""
    city: str = ""
    member_id: str = ""
    rated_share: float = 0.0  # 命中「具名因子表」的餐品行占比（其余按类别中值估算）
    trees: float = 0.0
    car_km: float = 0.0
    phone_charges: float = 0.0
    grade: str = "A"
    grade_label: str = ""
    grade_hint: str = ""

    # ---- 结构化占比，供输出层直接取用 ----
    @property
    def layers(self) -> tuple[tuple[str, float, float], ...]:
        """``[(层名, kg, 占比%), ...]``。"""
        total = self.total_kg or 1.0
        return (
            ("餐品", self.food_kg, self.food_kg / total * 100),
            ("包装", self.packaging_kg, self.packaging_kg / total * 100),
            ("配送", self.delivery_kg, self.delivery_kg / total * 100),
        )

    @property
    def avg_per_order_kg(self) -> float:
        return self.total_kg / self.order_count if self.order_count else 0.0


def _grade_for(total_kg: float) -> tuple[str, str, str]:
    for grade, upper in _GRADE_BANDS:
        if total_kg < upper:
            return grade, _GRADE_LABELS[grade], _GRADE_HINTS[grade]
    return "E", _GRADE_LABELS["E"], _GRADE_HINTS["E"]


def order_layers(order: Order) -> tuple[float, float, float]:
    """单笔订单的三层排放 ``(餐品, 包装, 配送)``，单位 kg。"""
    food_g = 0.0
    for item in order.items:
        per_unit, _, _ = factors.serving_factor(item.name)
        food_g += per_unit * 1000.0 * item.qty

    items = max(order.item_count, 1)
    if order.channel == "delivery":
        packaging_g = PACKAGING_DELIVERY_BASE_G + PACKAGING_DELIVERY_PER_ITEM_G * items
        delivery_g = DELIVERY_PER_ORDER_G
    else:
        packaging_g = PACKAGING_DINEIN_BASE_G + PACKAGING_DINEIN_PER_ITEM_G * items
        delivery_g = 0.0

    return food_g / 1000.0, packaging_g / 1000.0, delivery_g / 1000.0


def _month_axis(orders: list[Order]) -> list[tuple[int, int]]:
    """生成连续的 (年, 月) 轴，中间不跳月。"""
    if not orders:
        return []
    first = min(order.ts for order in orders)
    last = max(order.ts for order in orders)
    axis: list[tuple[int, int]] = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        axis.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return axis


def compute_carbon(orders: list[Order], user: dict | None = None) -> CarbonReport:
    """把订单列表换算成一份碳账本。"""
    if not orders:
        raise ValueError("没有可用于碳核算的订单。")

    user = user or {}
    food_kg = packaging_kg = delivery_kg = 0.0
    dish_qty: dict[str, int] = defaultdict(int)
    dish_kg: dict[str, float] = defaultdict(float)
    dish_per_unit: dict[str, float] = {}
    dish_basis: dict[str, str] = {}
    dish_category: dict[str, str] = {}
    cat_kg: dict[str, float] = defaultdict(float)
    cat_qty: dict[str, int] = defaultdict(int)
    month_kg: dict[tuple[int, int], float] = defaultdict(float)
    month_orders: dict[tuple[int, int], int] = defaultdict(int)

    rated_lines = 0
    total_lines = 0
    heaviest: tuple[Order, float] | None = None

    for order in orders:
        food, pack, delivery = order_layers(order)
        food_kg += food
        packaging_kg += pack
        delivery_kg += delivery
        total_order = food + pack + delivery
        if heaviest is None or total_order > heaviest[1]:
            heaviest = (order, total_order)

        key = (order.ts.year, order.ts.month)
        month_kg[key] += total_order
        month_orders[key] += 1

        for item in order.items:
            per_unit, basis, category = factors.serving_factor(item.name)
            line_kg = per_unit * item.qty
            dish_qty[item.name] += item.qty
            dish_kg[item.name] += line_kg
            dish_per_unit[item.name] = per_unit
            dish_basis[item.name] = basis
            dish_category[item.name] = category
            cat_kg[category] += line_kg
            cat_qty[category] += item.qty
            total_lines += 1
            if basis in ("measured", "est"):
                rated_lines += 1

    total_kg = food_kg + packaging_kg + delivery_kg
    grade, grade_label, grade_hint = _grade_for(total_kg)

    monthly = tuple(
        MonthCarbon(
            label=f"{year}-{month:02d}",
            kg=month_kg.get((year, month), 0.0),
            orders=month_orders.get((year, month), 0),
        )
        for year, month in _month_axis(orders)
    )

    categories = tuple(
        CategoryCarbon(
            key=key,
            label=CATEGORY_LABELS.get(key, key),
            kg=value,
            share=value / total_kg * 100 if total_kg else 0.0,
            qty=cat_qty[key],
        )
        for key, value in sorted(cat_kg.items(), key=lambda pair: -pair[1])
    )

    top_dishes = tuple(
        DishCarbon(
            name=name,
            category=dish_category[name],
            qty=dish_qty[name],
            per_unit_kg=dish_per_unit[name],
            total_kg=dish_kg[name],
            basis=dish_basis[name],
        )
        for name, _ in sorted(dish_kg.items(), key=lambda pair: -pair[1])[:8]
    )

    first = min(order.ts for order in orders).date()
    last = max(order.ts for order in orders).date()
    years = sorted({order.ts.year for order in orders})
    year_label = f"{years[0]}–{years[-1]}" if len(years) > 1 else str(years[0])

    return CarbonReport(
        total_kg=total_kg,
        food_kg=food_kg,
        packaging_kg=packaging_kg,
        delivery_kg=delivery_kg,
        monthly=monthly,
        categories=categories,
        top_dishes=top_dishes,
        heaviest=heaviest,
        order_count=len(orders),
        item_count=sum(order.item_count for order in orders),
        start=first,
        end=last,
        year_label=year_label,
        user_name=str(user.get("name") or "麦当劳会员"),
        city=str(user.get("city") or ""),
        member_id=str(user.get("member_id") or ""),
        rated_share=(rated_lines / total_lines * 100) if total_lines else 0.0,
        trees=total_kg / TREE_ABSORB_KG_PER_YEAR,
        car_km=total_kg * 1000.0 / CAR_G_PER_KM,
        phone_charges=total_kg * 1000.0 / SMARTPHONE_CHARGE_G,
        grade=grade,
        grade_label=grade_label,
        grade_hint=grade_hint,
    )
