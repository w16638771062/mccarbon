"""数据源层：把「从麦当劳 MCP 拉历史订单」和「离线示例数据」统一成同一个出口。

真实接入时调用的是官方 ``order-list`` / ``query-order`` / ``mall-order-list`` / ``query-my-account``。
由于官方工具返回的字段命名未固化在公开文档里，这里的解析器写得比较宽容：
同时兼容多种常见字段名，任何解析不了的订单会被跳过并计数，而不是整批失败。
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime
from typing import Any, Iterable

from . import mock_data, nutrition as nutrition_mod
from .mcp_client import MCPClient, MCPError, ToolResult
from .models import Order, OrderItem, mask_account

# 与本研究相关的官方 Tool
TOOL_ORDER_LIST = "order-list"
TOOL_ORDER_DETAIL = "query-order"
TOOL_MY_ACCOUNT = "query-my-account"
TOOL_NUTRITION = "list-nutrition-foods"
TOOL_NOW_TIME = "now-time-info"

# 官方 orderStatus 里代表「未完成 / 已失效」的关键字，这些单不计入画像
_VOID_STATUS_KEYWORDS = ("取消", "退款", "关闭", "失效")

# order-list 不返回城市，但门店名里通常带城市（如「麦当劳深圳观荟里餐厅」）。
# 这里用一份常见城市名做「最长优先」匹配，仅用于补全展示信息，猜不出就留空。
_CITY_NAMES: tuple[str, ...] = (
    "香港", "澳门", "台北",
    "北京", "上海", "天津", "重庆",
    "广州", "深圳", "珠海", "汕头", "佛山", "韶关", "湛江", "肇庆", "江门", "茂名",
    "惠州", "梅州", "汕尾", "河源", "阳江", "清远", "东莞", "中山", "潮州", "揭阳", "云浮",
    "南京", "苏州", "无锡", "常州", "徐州", "南通", "扬州", "盐城", "镇江", "泰州",
    "杭州", "宁波", "温州", "嘉兴", "绍兴", "金华", "台州", "湖州", "丽水",
    "合肥", "芜湖", "蚌埠", "福州", "厦门", "泉州", "漳州", "莆田",
    "南昌", "赣州", "济南", "青岛", "烟台", "潍坊", "临沂", "淄博", "济宁",
    "郑州", "洛阳", "武汉", "宜昌", "襄阳", "长沙", "株洲", "湘潭", "衡阳",
    "成都", "绵阳", "西安", "咸阳", "昆明", "贵阳", "南宁", "桂林", "海口", "三亚",
    "沈阳", "大连", "鞍山", "长春", "吉林", "哈尔滨", "石家庄", "唐山", "保定",
    "太原", "兰州", "银川", "西宁", "乌鲁木齐", "呼和浩特",
)


def infer_city(store_name: str) -> str:
    """从门店名里猜城市；猜不出返回空串。"""
    text = store_name or ""
    # 长名字优先，避免「海南」之类的短串误匹配
    for city in sorted(_CITY_NAMES, key=len, reverse=True):
        if city in text:
            return city
    return ""

_TIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)


def _first(mapping: dict, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # 兼容秒 / 毫秒时间戳
        seconds = value / 1000 if value > 1e11 else value
        try:
            return datetime.fromtimestamp(seconds)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip().replace("Z", "")
        for fmt in _TIME_FORMATS:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def _combo_components(raw_item: dict) -> list[tuple[str, int]]:
    """取出套餐/组合里的子项 ``[(名称, 数量)]``。

    官方在列表接口用 ``name`` / ``quantity``，在详情接口用 ``itemName`` / ``itemQuantity``，
    两种都兼容。
    """
    out: list[tuple[str, int]] = []
    for entry in raw_item.get("comboItemList") or []:
        if not isinstance(entry, dict):
            continue
        name = _first(entry, "name", "itemName", "productName")
        if not name:
            continue
        qty = int(_as_float(_first(entry, "quantity", "itemQuantity", "qty", "num"), 1))
        out.append((str(name), max(qty, 1)))
    return out


def _expand_items(
    raw_items: list, table: dict[str, nutrition_mod.Nutrition]
) -> tuple[list[OrderItem], int, int]:
    """把 ``orderProductList`` 展开成可统计的餐品行。

    真实订单里买的往往是**套餐**（随心配、买薯送薯、两件套……），这些名字不在官方营养表里。
    因此：有 ``comboItemList`` 的套餐会被展开成子项（中薯条、可乐大杯……），
    这样口味画像、类目占比和热量统计才有实际内容。

    返回 ``(餐品行, 热量已知的行数, 总行数)``。
    """
    items: list[OrderItem] = []
    known = 0
    total = 0

    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        top_name = _first(entry, "productName", "name", "mealName", "itemName", "skuName")
        if not top_name:
            continue
        top_qty = int(_as_float(_first(entry, "quantity", "qty", "num", "count"), 1))
        top_qty = max(top_qty, 1)
        price = _as_float(_first(entry, "price", "unitPrice", "salePrice", "amount"), 0.0)

        components = _combo_components(entry)
        if components:
            for name, qty in components:
                found = nutrition_mod.lookup(table, name)
                items.append(
                    OrderItem(
                        name=name,
                        category=nutrition_mod.classify_category(name),
                        qty=top_qty * qty,
                        unit_price=0.0,  # 套餐只给了整包价，无法拆到子项
                        kcal_per_unit=found.kcal if found else 0.0,
                    )
                )
                total += 1
                known += 1 if found and found.known else 0
        else:
            found = nutrition_mod.lookup(table, str(top_name))
            items.append(
                OrderItem(
                    name=str(top_name),
                    category=nutrition_mod.classify_category(str(top_name)),
                    qty=top_qty,
                    unit_price=price,
                    kcal_per_unit=found.kcal if found else 0.0,
                )
            )
            total += 1
            known += 1 if found and found.known else 0

    return items, known, total


def parse_order(
    raw: dict,
    city: str = "",
    table: dict[str, nutrition_mod.Nutrition] | None = None,
    detail: dict | None = None,
) -> Order | None:
    """尽力把一条 MCP 订单记录解析成 ``Order``；解析失败返回 ``None``。

    ``detail`` 为可选的 ``query-order`` 详情（补充 ``takeWay`` / 优惠等列表接口没有的字段）。
    """
    if not isinstance(raw, dict):
        return None

    status = str(_first(raw, "orderStatus", "statusText", default=""))
    if any(keyword in status for keyword in _VOID_STATUS_KEYWORDS):
        return None

    ts = _parse_time(_first(raw, "createTime", "orderTime", "orderDate", "time", "createdAt"))
    if ts is None:
        return None

    raw_items = _first(
        raw, "orderProductList", "items", "products", "orderItems", "mealList", "details", default=[]
    ) or []
    items, _, _ = _expand_items(raw_items, table or {})
    if not items:
        return None

    merged = {**raw, **(detail or {})}

    paid = _as_float(
        _first(merged, "realTotalAmount", "payAmount", "actualAmount", "totalAmount", "paid", "amount"), 0.0
    )
    discount = _as_float(
        _first(merged, "totalDiscountAmount", "discountAmount", "discount", "couponAmount"), 0.0
    )
    listed = _as_float(
        _first(merged, "totalAmount", "productPrice", "originAmount", "totalPrice", "listAmount"),
        paid + discount,
    )

    # 渠道：详情接口的 takeWay（外带/堂食）最准，其次是配送费，最后才看 orderType
    take_way = str(_first(merged, "takeWay", "takeaway", "orderWay", default=""))
    delivery_price = _as_float(_first(merged, "realDeliveryPrice", "deliveryPrice"), 0.0)
    channel_raw = str(_first(merged, "channel", "orderType", "deliveryType", default="")).lower()
    is_delivery = bool(take_way and any(k in take_way for k in ("外送", "配送", "麦乐送"))) or delivery_price > 0
    if not is_delivery:
        is_delivery = any(k in channel_raw for k in ("delivery", "外送", "外卖", "配送"))
    channel = "delivery" if is_delivery else "dine_in"

    store = str(_first(merged, "storeName", "store", "restaurantName", default="未知门店"))
    resolved_city = city or str(_first(merged, "city", "cityName", default="")) or infer_city(store)

    return Order(
        order_id=str(_first(merged, "orderId", "orderNo", "id", default=f"UNKNOWN-{ts:%Y%m%d%H%M%S}")),
        ts=ts,
        channel=channel,
        store=store,
        city=resolved_city,
        items=tuple(items),
        paid=round(paid, 2),
        listed=round(max(listed, paid), 2),
        points_earned=int(_as_float(_first(merged, "pointsEarned", "earnPoints", "points"), 0)),
        points_used=int(_as_float(_first(merged, "pointsUsed", "usePoints"), 0)),
    )


def _extract_records(payload: Any) -> list[dict]:
    """从各种可能的返回结构里取出订单数组。"""
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    if isinstance(payload, dict):
        for key in ("orders", "orderList", "list", "records", "data", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return [entry for entry in value if isinstance(entry, dict)]
            if isinstance(value, dict):
                nested = _extract_records(value)
                if nested:
                    return nested
    return []


def fetch_orders(
    client: MCPClient,
    city: str = "",
    table: dict[str, nutrition_mod.Nutrition] | None = None,
    max_pages: int = 20,
    with_detail: bool = False,
    max_detail: int = 300,
) -> tuple[list[Order], int]:
    """通过 MCP 拉取历史订单。

    ``with_detail`` 为真时，会再对每单调用 ``query-order`` 补充「外带/堂食」「优惠明细」
    等列表接口没有的字段；``max_detail`` 用于兜底限制请求数（避免订单特别多时耗时过久）。

    返回 ``(订单列表, 被跳过的记录数)``。
    """
    orders: list[Order] = []
    skipped = 0
    seen: set[str] = set()
    table = table or {}

    for page in range(max_pages):
        arguments: dict[str, Any] = {"pageNum": page + 1, "pageSize": 50}
        try:
            result: ToolResult = client.call_tool(TOOL_ORDER_LIST, arguments)
        except MCPError:
            # 首页就失败，多半是 Token 缺失 / 无效 / 网络不可达——
            # 直接抛出真实原因，避免被下游误报成「你没下过单」。
            if page == 0:
                raise
            break

        records = _extract_records(result.json())
        if not records:
            break

        fresh = 0
        for record in records:
            order_id = str(record.get("orderId") or record.get("orderNo") or "")
            if order_id and order_id in seen:
                continue

            detail: dict | None = None
            if with_detail and order_id and len(orders) < max_detail:
                try:
                    detail_result = client.call_tool(TOOL_ORDER_DETAIL, {"orderId": order_id})
                    parsed_detail = detail_result.json()
                    if isinstance(parsed_detail, dict):
                        detail = _extract_detail(parsed_detail)
                except MCPError:
                    detail = None  # 详情只是锦上添花，失败就退回列表字段

            order = parse_order(record, city=city, table=table, detail=detail)
            if order_id:
                seen.add(order_id)
            if order is None:
                skipped += 1
                continue
            orders.append(order)
            fresh += 1
        if fresh == 0:
            break

    orders.sort(key=lambda order: order.ts)
    return orders, skipped


def _extract_detail(payload: dict) -> dict:
    """从 ``query-order`` 返回里取出订单详情对象（数据在 ``data`` 里）。"""
    nested = payload.get("data")
    if isinstance(nested, dict):
        return nested
    for key in ("order", "detail", "result"):
        candidate = payload.get(key)
        if isinstance(candidate, dict):
            return candidate
    return payload


def fetch_nutrition(client: MCPClient) -> dict[str, nutrition_mod.Nutrition]:
    """拉取官方营养表（失败时返回空表，热量相关板块会自动降级）。"""
    try:
        payload = client.call_tool(TOOL_NUTRITION, {"pageNum": 1, "pageSize": 500}).json()
    except MCPError:
        return {}
    return nutrition_mod.parse_nutrition(payload)


# query-my-account 返回字段在不同版本里命名不一，这里做宽容匹配。
# 注：官方线上实际返回的是 availablePoint / accumulativePoint / currentMouthExpirePoint
# （"Mouth" 是官方字段里的既有拼写），这里两种拼写都收。
_ACC_NAME_KEYS = ("nickName", "nickname", "userName", "username", "memberName",
                  "displayName", "accountName", "custName", "customerName", "name")
_ACC_ID_KEYS = ("accountId", "memberId", "memberNo", "memberCode", "cardNo", "unionId", "userId")
_ACC_LEVEL_KEYS = ("levelName", "memberLevel", "cardLevel", "vipLevel", "gradeName",
                   "level", "grade")
_ACC_AVAIL_KEYS = ("points_available", "availablePoint", "availablePoints",
                   "currentPoints", "usablePoints", "points", "balance")
_ACC_TOTAL_KEYS = ("points_total", "accumulativePoint", "accumulatePoint", "accumulatePoints",
                   "totalPoints", "totalPoint", "historyPoints", "allPoints")
_ACC_EXPIRE_KEYS = ("points_expiring", "currentMouthExpirePoint", "currentMonthExpirePoint",
                    "nextMouthExpirePoint", "nextMonthExpirePoint", "expiringPoints",
                    "expirePoints", "expiring")


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", "").replace(" ", "")
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


_ACC_WRAPPERS = ("data", "account", "accountInfo", "member", "memberInfo", "memberCard",
                 "user", "userInfo", "result", "detail")


def _flatten_account(payload: dict, depth: int = 5) -> dict[str, Any]:
    """递归展开 data/account/member 之类的包装层，内层字段优先。"""
    merged: dict[str, Any] = dict(payload)
    if depth <= 0:
        return merged
    for key in _ACC_WRAPPERS:
        nested = merged.get(key)
        if isinstance(nested, dict):
            merged = {**merged, **_flatten_account(nested, depth - 1)}
    return merged


def parse_account(payload: Any) -> dict[str, Any]:
    """把 ``query-my-account`` 的返回归一到统一字段。

    返回形如 ``{"name", "member_id", "level", "points_available", "points_total",
    "points_expiring", "points_used", "points_label", "raw"}``；解析不出的字段为 ``None``。
    兼容数据被包在 ``data`` / ``account`` / ``member`` / ``memberInfo`` 等多层包装里的情况。
    """
    if not isinstance(payload, dict):
        return {}
    merged = _flatten_account(payload)
    return {
        "name": _as_str(_first(merged, *_ACC_NAME_KEYS)),
        "member_id": _as_str(_first(merged, *_ACC_ID_KEYS)),
        "level": _as_str(_first(merged, *_ACC_LEVEL_KEYS)),
        "points_available": _as_int(_first(merged, *_ACC_AVAIL_KEYS)),
        "points_total": _as_int(_first(merged, *_ACC_TOTAL_KEYS)),
        "points_expiring": _as_int(_first(merged, *_ACC_EXPIRE_KEYS)),
        "points_used": _as_int(_first(merged, "usedPoint", "pointsUsed", "usedPoints")),
        "points_label": _as_str(_first(merged, "currency", "pointsName", "pointName")),
        "raw": payload,
    }


def fetch_account(client: MCPClient) -> dict[str, Any]:
    """读取并归一化积分 / 会员账户信息（失败时返回空字典，不影响年报主体）。

    返回的 ``member_id`` 已打码（年报是要分享的），原始值保留在 ``raw`` 里。
    """
    try:
        payload = client.call_tool(TOOL_MY_ACCOUNT).json()
    except MCPError:
        return {}
    account = parse_account(payload)
    if account.get("member_id"):
        account["member_id"] = mask_account(account["member_id"])
    return account


def load_orders(
    mock: bool = True,
    client: MCPClient | None = None,
    start: date | None = None,
    end: date | None = None,
    city: str = "",
    detail: bool = False,
) -> tuple[list[Order], dict[str, Any], str, dict[str, Any]]:
    """统一入口：返回 ``(订单, 用户档案, 数据来源说明, 账号信息)``。"""
    if mock:
        orders = mock_data.generate_orders(start=start, end=end)
        return orders, dict(mock_data.MOCK_USER), "离线示例数据（--mock）", dict(mock_data.MOCK_ACCOUNT)

    if client is None:
        raise MCPError("未提供 MCP 客户端，无法拉取真实订单；可改用 --mock 离线模式。")

    # 先取账号信息：真实的积分 / 会员卡号都在这里（昵称、等级官方接口不一定返回）
    account = fetch_account(client)
    # 再取官方营养表，用来给订单里的餐品补上热量
    table = fetch_nutrition(client)

    orders, skipped = fetch_orders(client, city=city, table=table, with_detail=detail)
    if start or end:
        orders = [
            order
            for order in orders
            if (start is None or order.ts.date() >= start) and (end is None or order.ts.date() <= end)
        ]
    if not orders:
        raise MCPError(
            "未从麦当劳 MCP 取到任何历史订单。若账号本身正常，"
            "可能是该账号在统计区间内确实没有订单记录。"
        )

    member_id = account.get("member_id")
    if not member_id:
        member_id = "—"
    # 城市：优先显式指定，否则用订单里出现最多的城市（从门店名推断）
    if not city:
        cities = [order.city for order in orders if order.city]
        city = Counter(cities).most_common(1)[0][0] if cities else ""
    user = {
        # 官方账号接口不返回昵称，拿不到时不要伪造，用中性的称呼
        "name": account.get("name") or "麦当劳会员",
        "city": city,
        "member_id": mask_account(member_id) or "—",
        "level": account.get("level") or "",
    }
    note = f"麦当劳 MCP 实时数据（order-list，已解析 {len(orders)} 单"
    if table:
        note += f"，营养表 {len(table)} 款餐品"
    note += f"，跳过 {skipped} 条无法识别记录）" if skipped else "）"
    return orders, user, note, account


def dumps(orders: Iterable[Order]) -> str:
    """把订单导出为 JSON（便于调试与二次分析）。"""
    payload = [
        {
            "orderId": order.order_id,
            "time": order.ts.isoformat(sep=" "),
            "channel": order.channel,
            "store": order.store,
            "paid": order.paid,
            "listed": order.listed,
            "items": [
                {"name": item.name, "category": item.category, "qty": item.qty, "unitPrice": item.unit_price}
                for item in order.items
            ],
        }
        for order in orders
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)
