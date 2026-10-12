"""数据模型：把麦当劳 MCP 返回的订单归一化成便于统计的结构。

设计原则：模型层只负责"表达事实"，任何统计口径都放在 ``stats`` 模块里，
这样新增一个统计维度时不需要改动模型，也不会出现口径散落各处的隐患。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# 时段划分（闭区间，左闭右开），用于作息画像
DAYPARTS: tuple[tuple[str, int, int], ...] = (
    ("早餐", 5, 10),
    ("午餐", 10, 14),
    ("下午茶", 14, 17),
    ("晚餐", 17, 21),
    ("夜宵", 21, 29),  # 21:00 - 次日 04:59，用 24+ 表示跨天
)


def classify_daypart(ts: datetime) -> str:
    """把下单时刻映射到作息时段。

    夜宵跨天，所以把 0-5 点也算进夜宵（小时 +24 后落在 24-29 区间）。
    """
    hour = ts.hour if ts.hour >= 5 else ts.hour + 24
    for name, start, end in DAYPARTS:
        if start <= hour < end:
            return name
    return "其他"


def mask_account(member_id: object) -> str:
    """会员卡号 / 账号 ID 打码：保留前 8 位与后 4 位。

    年报是要截图分享的东西，默认不把完整账号打出来。
    """
    text = str(member_id or "")
    if not text:
        return ""
    if len(text) <= 12:
        return text
    return f"{text[:8]}…{text[-4:]}"


@dataclass(frozen=True)
class OrderItem:
    """订单里的一个餐品行。"""

    name: str
    category: str
    qty: int = 1
    unit_price: float = 0.0
    kcal_per_unit: float = 0.0

    @property
    def subtotal(self) -> float:
        return round(self.unit_price * self.qty, 2)

    @property
    def kcal(self) -> float:
        return round(self.kcal_per_unit * self.qty, 1)


@dataclass(frozen=True)
class Order:
    """一个历史订单。"""

    order_id: str
    ts: datetime
    channel: str  # dine_in / delivery
    store: str
    city: str
    items: tuple[OrderItem, ...]
    paid: float
    listed: float
    points_earned: int = 0
    points_used: int = 0

    @property
    def discount(self) -> float:
        """这一单省下的钱（原价 - 实付），负数按 0 处理。"""
        return round(max(self.listed - self.paid, 0.0), 2)

    @property
    def item_count(self) -> int:
        return sum(item.qty for item in self.items)

    @property
    def item_names(self) -> tuple[str, ...]:
        """本次点过的餐品名（去重、保持出现顺序），用于展示摘要。"""
        return tuple(dict.fromkeys(item.name for item in self.items))

    @property
    def kcal(self) -> float:
        return round(sum(item.kcal for item in self.items), 1)

    @property
    def daypart(self) -> str:
        return classify_daypart(self.ts)

    @property
    def is_delivery(self) -> bool:
        return self.channel == "delivery"
