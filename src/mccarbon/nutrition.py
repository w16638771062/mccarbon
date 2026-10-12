"""营养数据：解析官方 ``list-nutrition-foods`` 返回表，并把餐品名归类到类目。

官方该 Tool 的 ``data`` 字段是一段**紧凑文本表**，形如::

    [160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
      猪柳麦满分,null,1288,308,16,16,24,781,213

第一行是 ``[行数]{列名}``，之后每行是一条记录，字段用逗号分隔。
这里把它解析成 ``{餐品名: Nutrition}``，并对餐品名做类目归类，供统计层使用。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

# 类目规则：**顺序敏感**，越具体的写在越前面。
# 真实订单里的套餐（随心配 / 两件套）会被展开成子项，因此主要命中这里的是单品名。
_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("早餐", ("麦满分", "炒双蛋堡", "早安营养卷", "叠叠卷", "薯饼", "油条", "粥", "图林根香肠")),
    ("甜品", ("冰淇淋", "新地", "麦旋风", "拉明顿", "阿芙佳朵", "派", "yeyeyeye", "奶冻", "爆珠")),
    ("咖啡", ("咖啡", "奶铁", "美式", "玛奇朵", "卡布奇诺", "燕麦奶", "抹茶", "黑巧", "雪冰", "红茶")),
    ("饮料", ("可乐", "雪碧", "柠檬红茶", "苹果汁", "纯悦", "阳光橙", "橙橙",
             "牛奶", "豆浆", "朱古力", "怡泉")),
    ("小食", ("薯条", "麦乐鸡", "鸡翅", "鸡排", "脆汁鸡", "鸡球", "笋卷", "V翅", "双翅",
             "玉米杯", "苹果片", "果然多肉")),
    ("汉堡", ("汉堡", "扒堡", "牛堡", "麦香鸡", "麦香鱼", "板烧鸡腿堡", "巨无霸", "鳕鱼堡",
             "鱼排堡", "双层吉士")),
    ("套餐", ("随心配", "件套", "选1", "买薯送薯", "蜜汁快乐", "牛气满满", "苹板", "薯鱼",
             "超值", "组合")),
)


@dataclass(frozen=True)
class Nutrition:
    """一份餐品的营养信息（单位与官方一致：kcal / g / mg）。"""

    kcal: float = 0.0
    protein: float = 0.0
    fat: float = 0.0
    carbohydrate: float = 0.0
    sodium: float = 0.0
    calcium: float = 0.0

    @property
    def known(self) -> bool:
        """能量与三大营养素全为 0 时视为「未知」（如无糖可乐确实是 0 kcal，但它有碳水）。"""
        return any((self.kcal, self.protein, self.fat, self.carbohydrate, self.sodium, self.calcium))


def classify_category(name: str) -> str:
    """按关键字把餐品名归类到 早餐/汉堡/小食/饮料/咖啡/甜品/套餐/其他。"""
    text = (name or "").strip()
    if not text:
        return "其他"
    for category, keywords in _CATEGORY_RULES:
        if any(keyword in text for keyword in keywords):
            return category
    return "其他"


def _as_float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _parse_table(text: str) -> dict[str, Nutrition]:
    """解析 ``[N]{列名}:`` + ``名称,...,数值`` 形式的紧凑表。"""
    table: dict[str, Nutrition] = {}
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        return table

    header = lines[0]
    if "{" not in header or "}" not in header:
        return table
    columns = [part.strip() for part in header[header.index("{") + 1:header.index("}")].split(",")]
    if len(columns) < 2:
        return table
    # 首列是名称，其余列与行尾字段一一对应
    tail_size = len(columns) - 1
    metric_columns = columns[1:]

    for line in lines[1:]:
        parts = [part.strip() for part in line.strip().split(",")]
        if len(parts) <= tail_size:
            continue
        name = ",".join(parts[:len(parts) - tail_size]).strip()
        tail = parts[len(parts) - tail_size:]
        record = dict(zip(metric_columns, tail))
        if not name:
            continue
        table.setdefault(
            name,
            Nutrition(
                kcal=_as_float(record.get("energyKcal")),
                protein=_as_float(record.get("protein")),
                fat=_as_float(record.get("fat")),
                carbohydrate=_as_float(record.get("carbohydrate")),
                sodium=_as_float(record.get("sodium")),
                calcium=_as_float(record.get("calcium")),
            ),
        )
    return table


def _parse_records(records: list[Any]) -> dict[str, Nutrition]:
    """解析「结构化对象数组」形态（不同版本的服务端可能直接返回 JSON 数组）。"""
    table: dict[str, Nutrition] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        name = record.get("productName") or record.get("name")
        if not name:
            continue
        table.setdefault(
            str(name),
            Nutrition(
                kcal=_as_float(record.get("energyKcal")),
                protein=_as_float(record.get("protein")),
                fat=_as_float(record.get("fat")),
                carbohydrate=_as_float(record.get("carbohydrate")),
                sodium=_as_float(record.get("sodium")),
                calcium=_as_float(record.get("calcium")),
            ),
        )
    return table


def parse_nutrition(payload: Any) -> dict[str, Nutrition]:
    """把 ``list-nutrition-foods`` 的各种返回形态统一成 ``{餐品名: Nutrition}``。

    兼容：``structuredContent`` 里的 ``data`` 为文本表 / 数组 / JSON 字符串，
    以及直接把文本或数组传进来的情况。
    """
    if payload is None:
        return {}
    if isinstance(payload, str):
        text = payload.strip()
        if text.startswith("[") or text.startswith("{"):
            try:
                return parse_nutrition(json.loads(text))
            except json.JSONDecodeError:
                pass
        return _parse_table(payload)
    if isinstance(payload, list):
        return _parse_records(payload)
    if isinstance(payload, dict):
        for key in ("data", "list", "records", "result", "foods"):
            nested = payload.get(key)
            if nested is not None and nested is not payload:
                table = parse_nutrition(nested)
                if table:
                    return table
    return {}


def lookup(table: dict[str, Nutrition], name: str) -> Nutrition | None:
    """按餐品名查营养；先精确匹配，再退化到「去掉空格/全角括号」后的匹配。"""
    if not name:
        return None
    if name in table:
        return table[name]
    normalized = {_normalize(key): value for key, value in table.items()}
    return normalized.get(_normalize(name))


def _normalize(name: str) -> str:
    return (
        name.replace(" ", "")
        .replace("（", "(")
        .replace("）", ")")
        .replace("－", "-")
        .replace("-", "")
        .upper()
    )
