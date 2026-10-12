"""碳账本渲染：生成一个**单文件、零外部依赖、离线可看、可截图分享**的 HTML。

为什么坚持不用图表库 / CDN（与「麦门年度账单」一致）：
- 评审 clone 下来双击就能打开，不需要联网、不需要构建；
- 所有图形用内联 SVG 现算，任何环境渲染一致；
- 单文件方便截图、转发——这正是拉 Star 的关键动作。

配色改用「森林绿 + 麦当劳黄」：碳题材用绿色更贴切，同时保留一点品牌关联。
"""

from __future__ import annotations

import html
from datetime import datetime

from . import reduce
from .carbon import CATEGORY_LABELS, CarbonReport
from .models import Order

GREEN = "#0E7A4E"
GREEN_2 = "#1BA35A"
GREEN_SOFT = "#DCFCE7"
YELLOW = "#FFC72C"
INK = "#12211A"
MUTED = "#6E7F76"
LINE = "#DDE9E1"
CREAM = "#F4FAF5"

# 三层配色
LAYER_COLORS = {"餐品": "#0E7A4E", "包装": "#7BC49A", "配送": "#FFC72C"}

# 食材类别配色
CATEGORY_COLORS: dict[str, str] = {
    "beef": "#DC2626",
    "chicken": "#F59E0B",
    "fish": "#3B82F6",
    "plant": "#16A34A",
    "side": "#84CC16",
    "drink": "#06B6D4",
    "coffee": "#8B5CF6",
    "dessert": "#EC4899",
    "breakfast": "#F97316",
    "combo": "#64748B",
    "other": "#94A3B8",
}

GRADE_COLORS = {"A": "#16A34A", "B": "#65A30D", "C": "#EAB308", "D": "#F97316", "E": "#DC2626"}

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #E9F1EB;
  color: #12211A;
  font-family: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  -webkit-font-smoothing: antialiased;
  padding: 28px 16px 48px;
}
.page { max-width: 760px; margin: 0 auto; }
.card { background: #FFFFFF; border-radius: 18px; padding: 26px 26px 24px; margin-bottom: 16px; box-shadow: 0 1px 0 rgba(0,0,0,0.03); }
.hero {
  background: linear-gradient(135deg, #0E7A4E 0%, #16A34A 100%);
  border-radius: 18px; padding: 30px 28px 28px; margin-bottom: 16px;
  color: #FFFFFF; position: relative; overflow: hidden;
}
.hero:after {
  content: ""; position: absolute; right: -50px; bottom: -80px;
  width: 200px; height: 200px; border-radius: 50%; background: #FFC72C; opacity: 0.9;
}
.hero .kicker { font-size: 12px; letter-spacing: 2px; opacity: 0.88; }
.hero h1 { font-size: 28px; font-weight: 500; margin: 10px 0 6px; letter-spacing: 0.5px; }
.hero .sub { font-size: 13px; opacity: 0.92; }
.hero .big { font-size: 46px; font-weight: 600; margin-top: 18px; line-height: 1.05; position: relative; z-index: 1; }
.hero .big span { font-size: 18px; font-weight: 400; margin-left: 8px; opacity: 0.92; }
.hero .grade { position: absolute; right: 28px; top: 30px; z-index: 2; text-align: center; }
.hero .grade .g { font-size: 40px; font-weight: 700; line-height: 1; text-shadow: 0 1px 2px rgba(0,0,0,0.18); }
.hero .grade .t { font-size: 11px; margin-top: 4px; opacity: 0.95; }
.hero .hint { font-size: 13px; margin-top: 12px; position: relative; z-index: 1; opacity: 0.95; }
h2 { font-size: 15px; font-weight: 500; margin-bottom: 4px; }
.hint { font-size: 12px; color: #6E7F76; margin-bottom: 18px; }
.numbers { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.num { background: #F4FAF5; border-radius: 12px; padding: 16px 14px; }
.num .v { font-size: 22px; font-weight: 500; color: #0E7A4E; line-height: 1.15; }
.num .v small { font-size: 12px; font-weight: 400; color: #6E7F76; margin-left: 2px; }
.num .k { font-size: 12px; color: #6E7F76; margin-top: 6px; }
.two { display: grid; grid-template-columns: 260px 1fr; gap: 24px; align-items: center; }
.legend { font-size: 13px; }
.legend .row { display: flex; align-items: center; gap: 8px; padding: 7px 0; }
.legend .dot { width: 10px; height: 10px; border-radius: 3px; flex: none; }
.legend .nm { flex: 1; }
.legend .pc { color: #6E7F76; font-variant-numeric: tabular-nums; }
.cat { padding: 9px 0; }
.cat .top { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px; }
.cat .top .pc { color: #6E7F76; font-variant-numeric: tabular-nums; }
.cat .track { height: 9px; background: #EDF3EE; border-radius: 5px; overflow: hidden; }
.cat .track i { display: block; height: 100%; border-radius: 5px; }
.fun { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.fun .f { background: #F4FAF5; border-radius: 12px; padding: 16px; }
.fun .f .v { font-size: 20px; font-weight: 500; color: #0E7A4E; }
.fun .f .k { font-size: 12px; color: #6E7F76; margin-top: 4px; line-height: 1.5; }
.rec { display: flex; gap: 14px; padding: 13px 0; border-bottom: 1px dashed #DDE9E1; font-size: 13px; align-items: baseline; }
.rec:last-child { border-bottom: none; }
.rec .rank { width: 22px; height: 22px; border-radius: 50%; background: #DCFCE7; color: #0E7A4E; font-size: 12px; font-weight: 600; display: flex; align-items: center; justify-content: center; flex: none; }
.rec .body { flex: 1; }
.rec .body .h { display: flex; justify-content: space-between; gap: 10px; }
.rec .body .h b { font-weight: 500; }
.rec .body .h .save { color: #0E7A4E; font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }
.rec .body .d { color: #6E7F76; font-size: 12px; margin-top: 4px; line-height: 1.55; }
.rec .body .effort { display: inline-block; font-size: 10px; padding: 1px 7px; border-radius: 6px; background: #EDF3EE; color: #6E7F76; margin-top: 6px; }
.heavy { display: flex; gap: 16px; font-size: 13px; line-height: 1.7; }
.heavy .lb { color: #6E7F76; width: 92px; flex: none; }
.heavy .vl { flex: 1; }
.heavy .vl b { color: #0E7A4E; font-weight: 600; }
footer { text-align: center; font-size: 12px; color: #82958A; margin-top: 22px; line-height: 1.8; }
footer .meth { text-align: left; background: #FFFFFF; border-radius: 14px; padding: 18px 20px; color: #6E7F76; margin-bottom: 14px; font-size: 11.5px; line-height: 1.75; }
footer .meth b { color: #12211A; font-weight: 500; }
@media (max-width: 620px) {
  .numbers, .fun { grid-template-columns: 1fr 1fr; }
  .two { grid-template-columns: 1fr; }
  .hero .big { font-size: 36px; }
  .hero .grade { right: 20px; top: 24px; }
}
"""


def _esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def _kg(value: float) -> str:
    if value >= 100:
        return f"{value:,.0f}"
    if value >= 10:
        return f"{value:,.1f}"
    return f"{value:,.2f}"


# ------------------------------------------------------------------ SVG 组件
def _svg_layers(report: CarbonReport) -> str:
    """三层结构环形图（餐品 / 包装 / 配送）。"""
    size, radius, stroke = 220, 76, 26
    center = size / 2
    circumference = 2 * 3.141592653589793 * radius
    total = report.total_kg or 1.0
    layers = [layer for layer in report.layers if layer[1] > 0]

    slices = []
    offset = 0.0
    for name, value, _pct in layers:
        fraction = value / total
        dash = fraction * circumference
        color = LAYER_COLORS.get(name, GREEN)
        slices.append(
            f'<circle cx="{center}" cy="{center}" r="{radius}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-dasharray="{dash:.2f} {circumference - dash:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {center} {center})"/>'
        )
        offset += dash

    food_pct = report.food_kg / total * 100
    center_text = (
        f'<text x="{center}" y="{center - 4}" text-anchor="middle" font-size="26" font-weight="600" '
        f'fill="{INK}">{_kg(report.total_kg)}</text>'
        f'<text x="{center}" y="{center + 18}" text-anchor="middle" font-size="11" fill="{MUTED}">kg CO2e</text>'
    )
    return (
        f'<svg viewBox="0 0 {size} {size}" width="220" height="220" role="img" aria-label="碳排放三层结构">'
        f'{"".join(slices)}{center_text}</svg>'
        f'<div style="text-align:center;font-size:12px;color:{MUTED};margin-top:2px">餐品层占 {food_pct:.0f}%</div>'
    )


def _svg_monthly(report: CarbonReport) -> str:
    """按月碳足迹柱状图（只画覆盖到的月份）。"""
    months = report.monthly
    width, height = 700, 236
    left, right, top, base = 34, 34, 34, 176
    chart_w = width - left - right
    slot = chart_w / max(len(months), 1)
    bar_w = slot * 0.56
    peak = max((point.kg for point in months), default=0.0) or 1.0
    best = max(range(len(months)), key=lambda index: months[index].kg) if months else 0

    bars = []
    for index, point in enumerate(months):
        ratio = point.kg / peak
        bar_h = max(ratio * (base - top), 3 if point.kg > 0 else 0)
        x = left + index * slot + (slot - bar_w) / 2
        y = base - bar_h
        is_peak = index == best and point.kg > 0
        fill = GREEN if is_peak else "#AFDCC0"
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="4" fill="{fill}"/>')
        label_fill = GREEN if is_peak else MUTED
        weight = "600" if is_peak else "400"
        if point.kg > 0:
            bars.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" '
                f'font-size="10.5" fill="{label_fill}" font-weight="{weight}">{point.kg:.1f}</text>'
            )
        label = point.label[2:] if len(months) > 3 else point.label
        bars.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{base + 20:.1f}" text-anchor="middle" '
            f'font-size="10" fill="{MUTED}">{label}</text>'
        )
    axis = f'<line x1="{left}" y1="{base}" x2="{width - right}" y2="{base}" stroke="{LINE}" stroke-width="1"/>'
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" '
        f'aria-label="按月碳足迹柱状图">{"".join(bars)}{axis}</svg>'
    )


def _category_bars(report: CarbonReport) -> str:
    peak = max((category.kg for category in report.categories), default=1.0)
    rows = []
    for category in report.categories:
        color = CATEGORY_COLORS.get(category.key, "#94A3B8")
        width = max(category.kg / peak * 100, 2) if peak else 0
        rows.append(
            f'<div class="cat"><div class="top"><span>{_esc(category.label)}'
            f' <span style="color:{MUTED}">· {category.qty} 件</span></span>'
            f'<span class="pc">{_kg(category.kg)} kg · {category.share:.0f}%</span></div>'
            f'<div class="track"><i style="width:{width:.1f}%;background:{color}"></i></div></div>'
        )
    return "".join(rows)


def _reduce_rows(report: CarbonReport, orders: list[Order]) -> str:
    options = reduce.simulate(report, orders)
    if not options:
        return '<p style="font-size:13px;color:#6E7F76">在统计区间内没有可量化的减排场景。</p>'
    rows = []
    for index, option in enumerate(options[:4], start=1):
        rows.append(
            f'<div class="rec"><div class="rank">{index}</div><div class="body">'
            f'<div class="h"><b>{_esc(option.label)}</b>'
            f'<span class="save">-{_kg(option.kg_saved)} kg（{option.pct:.0f}%）</span></div>'
            f'<div class="d">{_esc(option.detail)}</div>'
            f'<span class="effort">{_esc(option.effort)}</span></div></div>'
        )
    return "".join(rows)


def _heavy_card(report: CarbonReport) -> str:
    if report.heaviest is None:
        return ""
    order, kg = report.heaviest
    names = "、".join(order.item_names[:5])
    rows = [
        ("最碳重一单", f"{order.ts:%Y-%m-%d %H:%M}"),
        ("门店", order.store or "未知门店"),
        ("餐品", names or "—"),
        ("估算排放", f"<b>{_kg(kg)} kg CO2e</b>（含包装与配送）"),
    ]
    body = "".join(f'<div class="lb">{_esc(label)}</div><div class="vl">{value}</div>' for label, value in rows)
    return f'<div class="heavy">{body}</div>'


def build_html(
    report: CarbonReport,
    orders: list[Order],
    source_note: str = "",
    account: dict | None = None,
) -> str:
    """生成完整的单文件 HTML 碳账本。"""
    account = account or {}
    identity = " · ".join(part for part in (report.user_name, report.city, report.member_id) if part)
    grade_color = GRADE_COLORS.get(report.grade, GREEN)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    layer_rows = "".join(
        f'<div class="row"><span class="dot" style="background:{LAYER_COLORS.get(name, GREEN)}"></span>'
        f'<span class="nm">{_esc(name)}层</span><span class="pc">{_kg(value)} kg · {pct:.0f}%</span></div>'
        for name, value, pct in report.layers
    )

    totals = [
        (f"{report.order_count}", "笔订单"),
        (f"{report.item_count}", "件餐品"),
        (f"{_kg(report.avg_per_order_kg)}", "kg / 单"),
    ]
    totals_html = "".join(
        f'<div class="num"><div class="v">{value}</div><div class="k">{label}</div></div>'
        for value, label in totals
    )

    fun = [
        (f"{report.trees:,.1f}", "棵", "相当于这些树一年的固碳量"),
        (f"{report.car_km:,.0f}", "公里", "约等于汽油车行驶的排放"),
        (f"{report.phone_charges:,.0f}", "次", "够给手机充电的次数"),
    ]
    fun_html = "".join(
        f'<div class="f"><div class="v">{value} <small style="font-size:12px">{unit}</small></div>'
        f'<div class="k">{label}</div></div>'
        for value, unit, label in fun
    )

    source_line = f"数据来源：{_esc(source_note)}" if source_note else ""
    member_line = f" · {_esc(account.get('level'))}" if account.get("level") else ""

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>麦麦碳账本 · {_esc(report.user_name)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="page">

  <div class="hero">
    <div class="grade"><div class="g" style="color:{grade_color}">{_esc(report.grade)}</div>
      <div class="t">{_esc(report.grade_label)}</div></div>
    <div class="kicker">MCCARBON · 麦麦碳账本</div>
    <h1>你的麦门碳足迹</h1>
    <div class="sub">{_esc(identity)}{member_line} · {report.start:%Y-%m-%d} ~ {report.end:%Y-%m-%d}</div>
    <div class="big">{_kg(report.total_kg)}<span>kg CO2e</span></div>
    <div class="hint">{_esc(report.grade_hint)}</div>
  </div>

  <div class="card">
    <h2>碳排放的三层结构</h2>
    <div class="hint">餐品是主战场，包装次之，配送本身占比最小——所以「到店自提」比重选择更立竿见影</div>
    <div class="two">
      <div>{_svg_layers(report)}</div>
      <div class="legend">{layer_rows}</div>
    </div>
  </div>

  <div class="card">
    <h2>这笔碳足迹有多大</h2>
    <div class="hint">把 kg CO2e 换成更容易感知的单位</div>
    <div class="fun">{fun_html}</div>
    <div style="height:14px"></div>
    <div class="numbers">{totals_html}</div>
  </div>

  <div class="card">
    <h2>每月碳足迹</h2>
    <div class="hint">峰值月份往往就是「牛肉 + 外送」叠加的结果</div>
    {_svg_monthly(report)}
  </div>

  <div class="card">
    <h2>碳重集中在哪类食材</h2>
    <div class="hint">动物性蛋白（尤其牛肉）是整个账本的决定性变量</div>
    {_category_bars(report)}
  </div>

  <div class="card">
    <h2>最碳重的一单</h2>
    <div class="hint">看看那天你点了什么</div>
    {_heavy_card(report)}
  </div>

  <div class="card">
    <h2>减排模拟器</h2>
    <div class="hint">按可减排量排序——只算「换一下能少多少」，不替你做选择</div>
    {_reduce_rows(report, orders)}
  </div>

  <footer>
    <div class="meth">
      <b>方法学与免责声明</b><br/>
      · 本账本为<b>估算值</b>，非麦当劳官方披露数据，仅用于横向对比与减排方向判断。<br/>
      · 餐品层：参考 Vegan Society「Plate Up For The Planet」实测餐品碳足迹、
        ADEME Agribalyse 快餐汉堡品类 LCA（18.6 kg CO2e/kg，农业环节占 92.5%）。<br/>
      · 包装层：参考《中国产品全生命周期温室气体排放系数库》（PP 餐盒 186.18 g CO2e/个、
        餐具 54 g/套、塑料袋 19 g/个），按渠道分摊。<br/>
      · 配送层：参考国内外卖研究（每单平均 111.80 g CO2e，其中包装占 86%，配送段约 15.6 g）。<br/>
      · 具名因子覆盖率 {report.rated_share:.0f}%，其余餐品按同类中值外推。
    </div>
    {source_line}<br/>
    基于麦当劳 MCP 构建 · 非麦当劳官方产品 · 生成于 {generated}
  </footer>

</div>
</body>
</html>
"""


def write_html(
    report: CarbonReport,
    orders: list[Order],
    path: str,
    source_note: str = "",
    account: dict | None = None,
) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(build_html(report, orders, source_note=source_note, account=account))
