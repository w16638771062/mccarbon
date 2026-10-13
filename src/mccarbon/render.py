"""终端渲染：把碳账本直接打印在命令行里，方便快速查看与 CI 断言。

中文在等宽字体里占两个字符宽，所以这里自己做宽度计算，否则排版会歪。
"""

from __future__ import annotations

from . import reduce
from .carbon import CarbonReport
from .factors import FACTOR_NOTES
from .models import Order


def _w(text: str) -> int:
    """估算字符串在等宽终端里的显示宽度（CJK 记 2）。"""
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(width - _w(text), 0)


def _bar(value: float, peak: float, width: int = 26) -> str:
    if peak <= 0:
        return " " * width
    filled = int(round(value / peak * width))
    return "█" * filled + " " * (width - filled)


def _kg(value: float) -> str:
    if value >= 100:
        return f"{value:,.0f}"
    if value >= 10:
        return f"{value:,.1f}"
    return f"{value:,.2f}"


def account_summary(account: dict | None) -> list[str]:
    """把归一化后的账号信息渲染成几行文本；没有有效字段时返回空列表。"""
    if not account:
        return []
    unit = str(account.get("points_label") or "积分")
    rows: list[tuple[str, str]] = []
    if account.get("name"):
        rows.append(("会员昵称", str(account["name"])))
    if account.get("member_id"):
        rows.append(("会员卡号", str(account["member_id"])))
    if account.get("level"):
        rows.append(("会员等级", str(account["level"])))
    if account.get("points_available") is not None:
        rows.append(("当前可用积分", f"{account['points_available']:,}"))
    if account.get("points_total") is not None:
        rows.append(("历史累计积分", f"{account['points_total']:,}"))
    if account.get("points_expiring") is not None:
        rows.append(("即将过期积分", f"{account['points_expiring']:,}"))
    if unit != "积分":
        rows.append(("积分类型", unit))
    return [f"  {_pad(name, 16)}{value}" for name, value in rows]


def account_card(account: dict) -> str:
    """`account` 子命令的输出：直接把真实账号信息打出来。"""
    rows = account_summary(account)
    rule = "=" * 58
    out = [rule, "  麦当劳 MCP · 账号信息", rule, ""]
    out.extend(rows or ["  （未取到任何账号字段，请确认 Token 与授权状态）"])
    out.append("")
    out.append("  注：会员卡号默认打码展示，避免分享时泄露账号。")
    out.append("基于麦当劳 MCP 构建 · 非麦当劳官方产品")
    out.append(rule)
    return "\n".join(out)


def summarize(
    report: CarbonReport,
    orders: list[Order],
    source_note: str = "",
    account: dict | None = None,
) -> str:
    lines: list[str] = []
    rule = "=" * 58

    identity_parts = [report.user_name, report.city, report.member_id]
    level = (account or {}).get("level")
    if level:
        identity_parts.append(level)
    identity = "  " + " · ".join(part for part in identity_parts if part)

    lines.append(rule)
    lines.append(f"  麦麦碳账本 · {report.year_label}")
    lines.append(identity)
    lines.append(f"  {report.start:%Y-%m-%d} ~ {report.end:%Y-%m-%d}")
    lines.append(rule)
    lines.append("")

    lines.append(f"【年度碳足迹】{_kg(report.total_kg)} kg CO2e")
    lines.append(f"  碳等级 {report.grade} · {report.grade_label}——{report.grade_hint}")
    lines.append("")

    lines.append("【三层结构】")
    peak_layer = max((value for _, value, _ in report.layers), default=1.0)
    for name, value, pct in report.layers:
        lines.append(f"  {_pad(name + '层', 8)}{_bar(value, peak_layer, 22)}  {_kg(value):>7} kg  {pct:>5.1f}%")
    lines.append("")

    lines.append("【年度总览】")
    overview = [
        ("订单笔数", f"{report.order_count} 单"),
        ("餐品件数", f"{report.item_count} 件"),
        ("单均排放", f"{_kg(report.avg_per_order_kg)} kg CO2e"),
        ("具名因子覆盖率", f"{report.rated_share:.0f}%（其余按碳类别中值兜底）"),
    ]
    for label, value in overview:
        lines.append(f"  {_pad(label, 14)}{value}")
    lines.append("")

    lines.append("【换算成更直观的单位】")
    lines.append(f"  · 约等于 {report.trees:,.1f} 棵树一年的固碳量")
    lines.append(f"  · 约等于汽油车行驶 {report.car_km:,.0f} 公里")
    lines.append(f"  · 够给手机充电 {report.phone_charges:,.0f} 次")
    lines.append("")

    lines.append("【每月碳足迹】")
    peak_month = max((point.kg for point in report.monthly), default=0.0)
    for point in report.monthly:
        tail = f"{_kg(point.kg)} kg（{point.orders} 单）" if point.orders else "—"
        lines.append(f"  {_pad(point.label, 10)}{_bar(point.kg, peak_month)}  {tail}")
    lines.append("")

    lines.append("【碳重集中类别】")
    peak_cat = max((category.kg for category in report.categories), default=1.0)
    for category in report.categories[:6]:
        lines.append(
            f"  {_pad(category.label, 12)}{_bar(category.kg, peak_cat, 18)}  "
            f"{_kg(category.kg):>7} kg  {category.share:>5.1f}%  {category.qty:>3} 件"
        )
    lines.append("")

    lines.append("【最碳重单品 Top 5】")
    for index, dish in enumerate(report.top_dishes[:5], start=1):
        tag = {"measured": "实测", "est": "具名", "class": "类别兜底"}.get(dish.basis, "")
        lines.append(
            f"  {index}. {_pad(dish.name, 18)}{dish.qty:>3} 份   {_kg(dish.total_kg):>7} kg   [{tag}]"
        )
    lines.append("")

    if report.heaviest is not None:
        order, kg = report.heaviest
        names = "、".join(order.item_names[:4])
        lines.append("【最碳重的一单】")
        lines.append(f"  {order.ts:%Y-%m-%d %H:%M} @ {order.store}")
        lines.append(f"  {names}——估算 {_kg(kg)} kg CO2e")
        lines.append("")

    lines.append("【减排模拟器 · 换一下能少多少】")
    options = reduce.simulate(report, orders)
    if options:
        for index, option in enumerate(options, start=1):
            lines.append(
                f"  {index}. {_pad(option.label, 16)}-{_kg(option.kg_saved):>6} kg  "
                f"({option.pct:>4.1f}%)  {option.effort}"
            )
            lines.append(f"     {option.detail}")
    else:
        lines.append("  （统计区间内没有可量化的减排场景）")
    lines.append("")

    lines.append("【因子来源】")
    for note in FACTOR_NOTES[:5]:
        lines.append(f"  · {_pad(note.label, 12)}{_pad(note.value, 22)}{note.source}")
    lines.append("")

    if source_note:
        lines.append(f"数据来源：{source_note}")
    lines.append("估算值，非官方披露 · 基于麦当劳 MCP 构建 · 非麦当劳官方产品")
    lines.append(rule)
    return "\n".join(lines)
