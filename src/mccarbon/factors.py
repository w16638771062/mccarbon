"""排放因子库：把一份餐品、一个包装、一单配送换算成二氧化碳当量（CO2e）。

设计原则（这是碳账本最容易被质疑的地方，所以把「口径」写死在这里）：

1. **能查到实测值的就用实测值**。下表 ``DISH_FACTORS`` 中带 ``measured`` 标注的条目，
   直接取自公开的餐品生命周期评估（LCA）实测数据：
   - Vegan Society「Plate Up For The Planet」对英国麦当劳餐品的实测：
     Double Big Mac 4.46 / Quarter Pounder 2.99 / Big Mac 2.35 / 20 块麦乐鸡 2.13 /
     Filet-O-Fish 0.82 / McPlant 0.29 / McFlurry 0.17 / 大薯条 0.15（单位 kg CO2e / 份）。
   - ADEME Agribalyse 数据库：快餐汉堡品类 LCA 值 18.6 kg CO2e/kg 成品，
     其中**农业环节占 92.5%**，这解释了为什么「换个蛋白质来源」减排效果最好。

2. **查不到的按同类外推到类别中值**。中文菜单里的绝大多数餐品没有公开实测值，
   因此按「碳类别」给出每份中值（``CATEGORY_SERVING_KG``）。这比把英国单品数据
   硬套到中文菜单上更稳，也更好解释。

3. **包装与配送是独立的第二、三层**，因子来自《中国产品全生命周期温室气体排放系数库》
   与国内外卖研究（每单平均 111.80 g CO2e，其中包装占 86%，配送段仅约 15.6 g）。

所有数字都是**估算**，用于横向对比与减排方向判断，不是官方披露值。
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# 第一层 · 餐品层（约占总量 90%）
# ---------------------------------------------------------------------------

# 碳类别 -> 每份排放中值（kg CO2e / 份）。抽出来单独放，便于评审核对与调参。
CATEGORY_SERVING_KG: dict[str, float] = {
    "beef": 2.40,       # 牛肉汉堡：蛋白质来源碳强度最高
    "chicken": 1.00,    # 鸡肉汉堡 / 鸡类小食
    "fish": 0.80,       # 鱼类汉堡
    "plant": 0.30,      # 植物基汉堡（对照实验中的最低值）
    "side": 0.35,       # 薯条 / 小食 / 蔬菜
    "drink": 0.10,      # 碳酸饮料 / 果汁 / 水
    "coffee": 0.22,     # 咖啡（含奶款更高）
    "dessert": 0.15,    # 冰淇淋 / 派 / 甜品
    "breakfast": 0.60,  # 早餐（麦满分 / 卷 / 粥）
    "combo": 1.50,      # 套餐整体（用于未展开的套餐行）
    "other": 0.80,      # 无法归类时的兜底
}

# 单份实测量。key 为餐品名关键词，匹配时「最长关键词优先」，避免「巨无霸」抢走「双层巨无霸」。
DISH_FACTORS: dict[str, tuple[float, str]] = {
    # --- 牛肉类（含实测锚点） ---
    "双层巨无霸": (4.46, "measured"),
    "四盎司牛肉堡": (2.99, "measured"),
    "安格斯": (3.40, "est"),
    "双层吉士汉堡": (2.80, "est"),
    "吉士汉堡": (1.70, "est"),
    "巨无霸": (2.35, "measured"),
    # --- 鱼类（实测） ---
    "麦香鱼": (0.82, "measured"),
    "鳕鱼堡": (0.85, "est"),
    # --- 植物基（实测） ---
    "植物基": (0.29, "measured"),
    "素肉": (0.29, "est"),
    # --- 鸡肉类 ---
    "麦辣鸡腿堡": (1.05, "est"),
    "麦辣鸡腿汉堡": (1.05, "est"),
    "板烧鸡腿堡": (0.95, "est"),
    "原味鸡腿堡": (0.95, "est"),
    "麦香鸡": (0.75, "est"),
    "鸡排堡": (1.00, "est"),
    # --- 小食 ---
    "麦乐鸡（5块）": (0.53, "est"),
    "麦乐鸡（20块）": (2.13, "measured"),
    "麦乐鸡": (0.53, "est"),
    "麦辣鸡翅": (0.50, "est"),
    "脆汁鸡": (0.60, "est"),
    "薯条（大）": (0.15, "measured"),
    "薯条（中）": (0.11, "est"),
    "薯条（小）": (0.08, "est"),
    "大薯条": (0.15, "est"),
    "中薯条": (0.11, "est"),
    "小薯条": (0.08, "est"),
    "薯条": (0.11, "est"),
    "玉米杯": (0.10, "est"),
    "蔬菜沙拉": (0.15, "est"),
    "苹果片": (0.05, "est"),
    # --- 饮品 ---
    "无糖可乐": (0.06, "est"),
    "可乐": (0.09, "est"),
    "雪碧": (0.09, "est"),
    "橙汁": (0.20, "est"),
    "柠檬红茶": (0.08, "est"),
    "纯悦": (0.02, "est"),
    "牛奶": (0.30, "est"),
    "豆浆": (0.15, "est"),
    # --- 甜品 ---
    "麦旋风": (0.17, "measured"),
    "新地": (0.12, "est"),
    "苹果派": (0.15, "est"),
    "圆筒冰淇淋": (0.08, "est"),
    "奶冻": (0.10, "est"),
    # --- 咖啡 ---
    "拿铁": (0.30, "est"),
    "卡布奇诺": (0.28, "est"),
    "奶铁": (0.30, "est"),
    "美式": (0.06, "est"),
    "雪冰": (0.35, "est"),
    "鲜煮咖啡": (0.05, "est"),
    # --- 早餐 ---
    "猪柳蛋麦满分": (0.75, "est"),
    "猪柳麦满分": (0.65, "est"),
    "烟肉蛋麦满分": (0.65, "est"),
    "麦满分": (0.60, "est"),
    "早餐卷": (0.55, "est"),
    "粥": (0.35, "est"),
    "油条": (0.15, "est"),
    "薯饼": (0.10, "est"),
}

# 归类规则：顺序敏感，越具体越靠前。
_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("plant", ("植物", "素肉", "素堡", "plant", "mcplant")),
    ("fish", ("麦香鱼", "鳕鱼", "鱼排", "鱼堡", "鱼")),
    ("beef", ("牛肉", "牛堡", "巨无霸", "安格斯", "四盎司", "吉士", "牛排", "牛气")),
    ("chicken", ("鸡", "麦乐", "板烧", "脆汁", "原味鸡", "麦香鸡")),
    ("dessert", ("冰淇淋", "新地", "麦旋风", "圆筒", "派", "甜品", "奶冻", "拉明顿")),
    ("coffee", ("咖啡", "拿铁", "美式", "玛奇朵", "卡布", "奶铁", "雪冰", "抹茶", "黑巧")),
    ("drink", ("可乐", "雪碧", "橙汁", "柠檬红茶", "纯悦", "水", "牛奶", "豆浆",
               "朱古力", "怡泉", "苹果汁", "阳光橙")),
    ("breakfast", ("麦满分", "早餐", "粥", "油条", "薯饼", "卷", "炒双蛋")),
    ("side", ("薯条", "麦乐鸡", "鸡翅", "鸡排", "鸡球", "沙拉", "玉米", "苹果片", "笋卷")),
    ("combo", ("随心配", "件套", "选1", "买薯送薯", "组合", "套餐", "超值")),
)


def classify_food(name: str) -> str:
    """把中文餐品名归到碳类别（beef / chicken / fish / plant / side / drink / coffee / dessert / breakfast / combo / other）。"""
    text = (name or "").strip().lower()
    if not text:
        return "other"
    for category, keywords in _CATEGORY_RULES:
        if any(keyword.lower() in text for keyword in keywords):
            return category
    return "other"


def match_dish(name: str) -> tuple[float, str] | None:
    """在 ``DISH_FACTORS`` 里找最贴切的单份因子（最长关键词优先）。"""
    text = (name or "").strip()
    if not text:
        return None
    best_key = ""
    for key in DISH_FACTORS:
        if key in text and len(key) > len(best_key):
            best_key = key
    if not best_key:
        return None
    return DISH_FACTORS[best_key]


def serving_factor(name: str) -> tuple[float, str, str]:
    """返回 ``(每份 kg CO2e, 依据类型, 碳类别)``。

    依据类型：``measured``（公开实测锚点）、``est``（同类外推的具名餐品）、
    ``class``（连具名都没有，按碳类别中值兜底）。
    """
    category = classify_food(name)
    hit = match_dish(name)
    if hit is not None:
        value, basis = hit
        return value, basis, category
    return CATEGORY_SERVING_KG.get(category, CATEGORY_SERVING_KG["other"]), "class", category


# ---------------------------------------------------------------------------
# 第二层 · 包装层
# ---------------------------------------------------------------------------
# 依据《中国产品全生命周期温室气体排放系数库》：
#   PP 餐盒（650mL / 23g）≈ 186.18 g CO2e / 个
#   一次性餐具（一套）    ≈ 54 g CO2e
#   塑料袋（6g）          ≈ 19 g CO2e
# 一个餐盒平均盛 2 件餐品，故每件摊销约 93g；取整 90g，便于口算。
PACKAGING_DELIVERY_BASE_G = 73.0        # 外送每单：塑料袋 19 + 餐具套 54
PACKAGING_DELIVERY_PER_ITEM_G = 90.0    # 外送每件餐品摊销的餐盒
PACKAGING_DINEIN_BASE_G = 10.0          # 到店 / 自提每单：纸袋与杯盖
PACKAGING_DINEIN_PER_ITEM_G = 4.0       # 到店 / 自提每件：少量包装

# ---------------------------------------------------------------------------
# 第三层 · 配送层
# ---------------------------------------------------------------------------
# 国内外卖研究：每单平均 111.80 g CO2e，其中 86% 来自包装，
# 配送段本身仅约 15.6 g（电动两轮为主）。因此「到店自提」几乎能抹掉这一层。
DELIVERY_PER_ORDER_G = 15.6

# ---------------------------------------------------------------------------
# 换算常数（把 kg CO2e 变成直观单位）
# ---------------------------------------------------------------------------
TREE_ABSORB_KG_PER_YEAR = 21.0   # 一棵成熟树每年约吸收 21 kg CO2
CAR_G_PER_KM = 170.0             # 汽油乘用车约 170 g CO2 / 公里
SMARTPHONE_CHARGE_G = 8.2        # 给手机充一次电约 8.2 g CO2（趣味换算用）


@dataclass(frozen=True)
class FactorNote:
    """给文档 / 终端输出用的因子来源说明。"""

    label: str
    value: str
    source: str


FACTOR_NOTES: tuple[FactorNote, ...] = (
    FactorNote("牛肉汉堡", "约 2.4 kg CO2e/份", "ADEME Agribalyse：牛肉碳强度是豆类的 20 倍以上"),
    FactorNote("鸡肉汉堡", "约 1.0 kg CO2e/份", "按品类 LCA 外推"),
    FactorNote("植物基汉堡", "0.29 kg CO2e/份", "Vegan Society 实测（McPlant）"),
    FactorNote("巨无霸", "2.35 kg CO2e/份", "Vegan Society 实测"),
    FactorNote("PP 餐盒", "186.18 g CO2e/个", "中国产品全生命周期温室气体排放系数库"),
    FactorNote("配送段", "15.6 g CO2e/单", "国内外卖研究（电动两轮）"),
    FactorNote("一棵树", f"{TREE_ABSORB_KG_PER_YEAR:.0f} kg CO2/年", "常用生态换算值"),
)


def factor_table() -> list[tuple[str, float, str]]:
    """给文档 / 测试用的因子速查表：``[(餐品关键词, 每份 kg, 依据)]``，实测在前。"""
    rows = [(key, value, basis) for key, (value, basis) in DISH_FACTORS.items()]
    order = {"measured": 0, "est": 1}
    rows.sort(key=lambda row: (order.get(row[2], 2), -row[1]))
    return rows
