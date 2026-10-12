"""麦麦碳账本 · mccarbon

基于麦当劳 MCP 的个人餐饮碳足迹估算与减排模拟器。
零第三方依赖，评审 clone 下来即可运行。
"""

from __future__ import annotations

from .carbon import CarbonReport, CategoryCarbon, DishCarbon, MonthCarbon, compute_carbon
from .factors import CATEGORY_SERVING_KG, DISH_FACTORS, classify_food, serving_factor
from .models import Order, OrderItem, classify_daypart
from .reduce import ReductionOption, simulate, top_reductions
from .report import build_html, write_html

__version__ = "1.0.0"
__all__ = [
    "Order",
    "OrderItem",
    "CarbonReport",
    "CategoryCarbon",
    "DishCarbon",
    "MonthCarbon",
    "ReductionOption",
    "compute_carbon",
    "classify_food",
    "serving_factor",
    "simulate",
    "top_reductions",
    "build_html",
    "write_html",
    "classify_daypart",
    "CATEGORY_SERVING_KG",
    "DISH_FACTORS",
    "__version__",
]
