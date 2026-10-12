"""减排模拟器：基于碳账本给出「换一下能少多少」的可执行选项。

刻意保持「只算不劝」——输出的是减排量与占比，不替用户做价值判断。
这也是碳题材必须守住的边界：不做洗绿（greenwashing），只做个人台账与可操作选项。
"""

from __future__ import annotations

from dataclasses import dataclass

from . import factors
from .carbon import CarbonReport
from .factors import (
    CATEGORY_SERVING_KG,
    DELIVERY_PER_ORDER_G,
    PACKAGING_DELIVERY_BASE_G,
    PACKAGING_DELIVERY_PER_ITEM_G,
    PACKAGING_DINEIN_BASE_G,
    PACKAGING_DINEIN_PER_ITEM_G,
)
from .models import Order

# 场景难度标签
EFFORT_EASY = "轻松"
EFFORT_MEDIUM = "需要一点取舍"
EFFORT_HARD = "改变习惯"

# 换蛋白质时的目标因子（换到鸡肉类中值）
_CHICKEN_TARGET = CATEGORY_SERVING_KG["chicken"]


@dataclass(frozen=True)
class ReductionOption:
    key: str
    label: str
    kg_saved: float
    pct: float  # 占总排放量的百分比
    detail: str
    effort: str

    @property
    def car_km(self) -> float:
        return self.kg_saved * 1000.0 / factors.CAR_G_PER_KM


def _cat(report: CarbonReport, key: str):
    """取某个碳类别的聚合结果；没有则返回 None。"""
    for category in report.categories:
        if category.key == key:
            return category
    return None


def _beef_to_chicken(report: CarbonReport) -> ReductionOption:
    beef = _cat(report, "beef")
    qty = beef.qty if beef else 0
    beef_kg = beef.kg if beef else 0.0
    saved = max(beef_kg - qty * _CHICKEN_TARGET, 0.0)
    detail = (
        f"把 {qty} 份牛肉汉堡换成鸡肉堡（每份约 {_CHICKEN_TARGET:.2f} kg CO2e）"
        if qty
        else "统计区间内没有牛肉类餐品，无需替换"
    )
    return ReductionOption("swap_beef", "红肉换白肉", saved, _pct(saved, report), detail, EFFORT_MEDIUM)


def _delivery_to_pickup(report: CarbonReport, orders: list[Order]) -> ReductionOption:
    saved = 0.0
    count = 0
    for order in orders:
        if order.channel != "delivery":
            continue
        count += 1
        items = max(order.item_count, 1)
        pack_now = (PACKAGING_DELIVERY_BASE_G + PACKAGING_DELIVERY_PER_ITEM_G * items) / 1000.0
        pack_after = (PACKAGING_DINEIN_BASE_G + PACKAGING_DINEIN_PER_ITEM_G * items) / 1000.0
        saved += max(pack_now - pack_after, 0.0) + DELIVERY_PER_ORDER_G / 1000.0
    detail = (
        f"把 {count} 笔外送改成到店自提，省下一次性包装与配送段排放"
        if count
        else "统计区间内没有外送订单"
    )
    return ReductionOption("pickup", "外送改自提", saved, _pct(saved, report), detail, EFFORT_EASY)


def _trim_side(report: CarbonReport) -> ReductionOption:
    side = _cat(report, "side")
    saved = (side.kg if side else 0.0) * 0.25
    detail = "小食（薯条 / 鸡块 / 沙拉）少点约四分之一，碳强度不高但基数大"
    return ReductionOption("trim_side", "小食减四分之一", saved, _pct(saved, report), detail, EFFORT_EASY)


def _halve_dessert(report: CarbonReport) -> ReductionOption:
    dessert = _cat(report, "dessert")
    saved = (dessert.kg if dessert else 0.0) * 0.5
    detail = "甜品与冰淇淋减半，乳制品是这部分的主要来源"
    return ReductionOption("halve_dessert", "甜品减半", saved, _pct(saved, report), detail, EFFORT_EASY)


def _shrink_combo(report: CarbonReport) -> ReductionOption:
    """把「牛肉主食 + 小食 + 饮品」的全家桶式点法换成主食单点。"""
    combo = _cat(report, "combo")
    saved = (combo.kg if combo else 0.0) * 0.6
    detail = "减少「套餐化」点法（主食 + 小食 + 饮品的组合），按套餐行的六成估算"
    return ReductionOption("shrink_combo", "拆掉部分套餐组合", saved, _pct(saved, report), detail, EFFORT_MEDIUM)


def _pct(saved: float, report: CarbonReport) -> float:
    return saved / report.total_kg * 100 if report.total_kg else 0.0


def simulate(report: CarbonReport, orders: list[Order]) -> list[ReductionOption]:
    """返回全部减排场景，按可减排量从多到少排序。"""
    options = [
        _beef_to_chicken(report),
        _delivery_to_pickup(report, orders),
        _trim_side(report),
        _halve_dessert(report),
        _shrink_combo(report),
    ]
    options = [option for option in options if option.kg_saved > 0.0005]
    options.sort(key=lambda option: -option.kg_saved)
    return options


def top_reductions(report: CarbonReport, orders: list[Order], n: int = 3) -> list[ReductionOption]:
    return simulate(report, orders)[:n]


def combined_ceiling(report: CarbonReport, orders: list[Order]) -> float:
    """把所有场景叠加起来（保守相加，各场景作用于不同餐品，不会重复计算）。"""
    return sum(option.kg_saved for option in simulate(report, orders))
