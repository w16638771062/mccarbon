"""离线示例数据：生成一整年可复现的麦当劳历史订单。

用途有两个：
1. 评审 / 用户在没有 MCP Token 的情况下也能一键跑出完整年报；
2. 单元测试有稳定的输入。

所有随机都走固定种子，保证任何机器上生成的数据完全一致。
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from .models import Order, OrderItem

SEED = 20261012

# 用户档案（示例）
MOCK_USER = {"name": "麦门信徒", "city": "深圳", "member_id": "M****1024"}

# (餐品名, 类目, 单价, 每份热量 kcal)
PRODUCTS: tuple[tuple[str, str, float, float], ...] = (
    ("巨无霸", "汉堡", 25.0, 550),
    ("双层吉士汉堡", "汉堡", 22.0, 450),
    ("麦辣鸡腿堡", "汉堡", 23.0, 480),
    ("板烧鸡腿堡", "汉堡", 24.0, 470),
    ("麦香鱼", "汉堡", 18.0, 340),
    ("原味鸡腿堡", "汉堡", 21.0, 430),
    ("麦乐鸡（5块）", "小食", 12.5, 230),
    ("麦辣鸡翅（2块）", "小食", 13.0, 240),
    ("薯条（中）", "小食", 11.0, 340),
    ("薯条（大）", "小食", 13.0, 460),
    ("玉米杯", "小食", 9.0, 90),
    ("蔬菜沙拉", "小食", 12.0, 70),
    ("可乐（中）", "饮料", 10.0, 150),
    ("无糖可乐（中）", "饮料", 10.0, 1),
    ("橙汁", "饮料", 12.0, 120),
    ("雪碧（中）", "饮料", 10.0, 140),
    ("麦旋风", "甜品", 13.0, 300),
    ("新地（巧克力）", "甜品", 8.0, 200),
    ("苹果派", "甜品", 8.0, 230),
    ("圆筒冰淇淋", "甜品", 4.0, 150),
    ("鲜煮咖啡", "咖啡", 12.0, 5),
    ("拿铁咖啡", "咖啡", 17.0, 120),
    ("早餐卷", "早餐", 12.0, 300),
    ("烟肉蛋麦满分", "早餐", 14.0, 310),
    ("猪柳蛋麦满分", "早餐", 15.0, 380),
)

_BY_CATEGORY: dict[str, list[tuple[str, str, float, float]]] = {}
for _p in PRODUCTS:
    _BY_CATEGORY.setdefault(_p[1], []).append(_p)

STORES: tuple[tuple[str, str], ...] = (
    ("科技园店", "深圳"),
    ("深南天虹店", "深圳"),
    ("海岸城店", "深圳"),
    ("万象天地店", "深圳"),
    ("车公庙店", "深圳"),
    ("欢乐颂店", "深圳"),
    ("龙华壹方城店", "深圳"),
    ("机场 T3 店", "深圳"),
)

# 每个时段的下单概率权重（工作日 / 周末）
_DAYPART_WEIGHTS_WEEKDAY = (("早餐", 0.16), ("午餐", 0.44), ("下午茶", 0.18), ("晚餐", 0.16), ("夜宵", 0.06))
_DAYPART_WEIGHTS_WEEKEND = (("早餐", 0.08), ("午餐", 0.34), ("下午茶", 0.22), ("晚餐", 0.24), ("夜宵", 0.12))

_DAYPART_HOURS = {
    "早餐": (7, 9),
    "午餐": (11, 13),
    "下午茶": (14, 16),
    "晚餐": (18, 20),
    "夜宵": (21, 23),
}


def _weighted_pick(rng: random.Random, pairs: tuple[tuple[str, float], ...]) -> str:
    total = sum(w for _, w in pairs)
    needle = rng.random() * total
    acc = 0.0
    for name, weight in pairs:
        acc += weight
        if needle <= acc:
            return name
    return pairs[-1][0]


def _pick_product(rng: random.Random, category: str) -> tuple[str, str, float, float]:
    """按类目挑一个高频餐品：给前几项更高权重，让"爆款"更突出。"""
    pool = _BY_CATEGORY[category]
    weights = [1.0 / (index + 1) for index in range(len(pool))]
    return rng.choices(pool, weights=weights, k=1)[0]


def _build_combo(rng: random.Random, daypart: str) -> list[OrderItem]:
    """按场景拼一单：主食 + 可选小食 + 可选饮品/甜品/咖啡。"""
    items: list[OrderItem] = []

    if daypart == "早餐":
        main = _pick_product(rng, "早餐")
        items.append(OrderItem(main[0], main[1], 1, main[2], main[3]))
        if rng.random() < 0.65:
            drink = rng.choice(_BY_CATEGORY["咖啡"] + _BY_CATEGORY["饮料"])
            items.append(OrderItem(drink[0], drink[1], 1, drink[2], drink[3]))
        return items

    main = _pick_product(rng, "汉堡")
    items.append(OrderItem(main[0], main[1], 1, main[2], main[3]))

    # 套餐感：主食 + 小食 + 饮品；下午茶偏小食 + 甜品 + 咖啡
    if daypart == "下午茶":
        items = []
        snack = _pick_product(rng, "小食")
        items.append(OrderItem(snack[0], snack[1], 1, snack[2], snack[3]))
        if rng.random() < 0.8:
            sweet = _pick_product(rng, "甜品")
            items.append(OrderItem(sweet[0], sweet[1], 1, sweet[2], sweet[3]))
        if rng.random() < 0.7:
            coffee = _pick_product(rng, "咖啡")
            items.append(OrderItem(coffee[0], coffee[1], 1, coffee[2], coffee[3]))
        return items

    if rng.random() < 0.78:
        side = _pick_product(rng, "小食")
        items.append(OrderItem(side[0], side[1], 1, side[2], side[3]))
    if rng.random() < 0.72:
        drink = _pick_product(rng, "饮料")
        items.append(OrderItem(drink[0], drink[1], 1, drink[2], drink[3]))
    if daypart == "夜宵" and rng.random() < 0.45:
        sweet = _pick_product(rng, "甜品")
        items.append(OrderItem(sweet[0], sweet[1], 1, sweet[2], sweet[3]))
    return items


def generate_orders(
    start: date | None = None,
    end: date | None = None,
    seed: int = SEED,
) -> list[Order]:
    """生成 [start, end] 区间内的历史订单，按时间升序返回。"""
    end = end or date(2026, 10, 11)
    start = start or date(2026, 1, 1)
    rng = random.Random(seed)

    orders: list[Order] = []
    serial = 0
    cursor = start
    while cursor <= end:
        is_weekend = cursor.weekday() >= 5
        weights = _DAYPART_WEIGHTS_WEEKEND if is_weekend else _DAYPART_WEIGHTS_WEEKDAY

        # 一天下单几单：多数 0~1 单，偶尔 2~3 单（加班 / 聚会 / 请客）
        roll = rng.random()
        if roll < (0.52 if is_weekend else 0.40):
            count = 0
        elif roll < (0.94 if is_weekend else 0.88):
            count = 1
        elif roll < 0.985:
            count = 2
        else:
            count = 3

        used_dayparts: set[str] = set()
        for _ in range(count):
            daypart = _weighted_pick(rng, weights)
            if daypart in used_dayparts:  # 同一天尽量不重复时段
                continue
            used_dayparts.add(daypart)

            low, high = _DAYPART_HOURS[daypart]
            ts = datetime(
                cursor.year,
                cursor.month,
                cursor.day,
                rng.randint(low, high),
                rng.choice((0, 5, 12, 18, 23, 30, 37, 45, 52)),
            )
            items = tuple(_build_combo(rng, daypart))
            listed = round(sum(item.subtotal for item in items), 2)

            # 约 55% 的订单用了券/满减
            if rng.random() < 0.55:
                discount_ratio = rng.choice((0.08, 0.12, 0.15, 0.2, 0.25, 0.3))
                paid = round(listed * (1 - discount_ratio), 2)
                paid = round(paid - 1 if paid >= 20 else paid, 2)  # 抹个零头，更像真实满减
            else:
                paid = listed
            paid = round(max(paid, 4.0), 2)

            store = rng.choice(STORES)
            channel = "delivery" if (not is_weekend and rng.random() < 0.62) else "dine_in"

            serial += 1
            orders.append(
                Order(
                    order_id=f"MC{cursor.strftime('%Y%m%d')}{serial:04d}",
                    ts=ts,
                    channel=channel,
                    store=store[0],
                    city=store[1],
                    items=items,
                    paid=paid,
                    listed=listed,
                    points_earned=int(paid),
                    points_used=0,
                )
            )
        cursor += timedelta(days=1)

    orders.sort(key=lambda order: order.ts)
    return orders


MOCK_ACCOUNT = {
    "name": "麦门信徒",
    "member_id": "M****1024",
    "level": "金卡会员",
    "points_available": 3860,
    "points_total": 12940,
    "points_expiring": 420,
    "points_used": 3260,
    "points_label": "麦享会积分",
}
