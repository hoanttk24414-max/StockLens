"""
report.py  --  TV6: Xuất PDF StockLens theo BỐ CỤC CHÍNH THỨC 8 TRANG

  Trang 1  Cover + Executive Summary
  Trang 2  Market & Technical            (TV1 + TV2)
  Trang 3  Fundamental & Financial       (TV3)
  Trang 4  Valuation                     (TV4)
  Trang 5  News & Sentiment              (TV5)
  Trang 6  Investment Score + Market Risk + Why This Score
  Trang 7  Personalized View + Final View
  Trang 8  Methodology + Data Sources + Disclaimer

generate_report(ticker, style, results, investment_all, sections, output_path, errors, demo, meta)

results["<module>"] theo "hợp đồng" đầu ra (các khóa không bắt buộc, thiếu thì bỏ qua phần đó):
    score, label, summary, metrics{}, tables[DataFrame], charts[png], positives[], risks[], sources[], warnings[]
    technical : signals [[Indicator, Value, Signal], ...], details {"Xu hướng giá": "...", ...}
    news      : sentiment {"positive": %, "neutral": %, "negative": %}; tables[0] = bảng Key News
    valuation : peer_table (DataFrame) nếu có dữ liệu đáng tin cậy; nếu không có -> in thông báo, KHÔNG tự tạo số
    market    : raw = dict của market_data.market_summary()

PHÔNG TIẾNG VIỆT: đặt DejaVuSans.ttf + DejaVuSans-Bold.ttf vào thư mục fonts/ ở gốc repo
(hoặc dùng Arial có sẵn trên Windows/macOS).
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepInFrame, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

# Root-level scoring.py computes the Investment Score. src/scoring.py is TV5's NewsScorer.
import scoring

ROOT = Path(__file__).resolve().parent

# Nội dung các trang 2–7 có thể được chọn; khung PDF vẫn luôn đủ 8 trang.
SECTION_TITLES = {
    "market_technical": "Market & Technical Analysis",
    "fundamental": "Fundamental & Financial Analysis",
    "valuation": "Valuation Analysis",
    "news": "News & Sentiment Analysis",
    "score": "Investment Score, Market Risk & Why This Score",
    "personalized": "Personalized View & Final View",
}

FONT_CANDIDATES = [
    (ROOT / "fonts" / "DejaVuSans.ttf", ROOT / "fonts" / "DejaVuSans-Bold.ttf"),
    (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
    (Path("/Library/Fonts/Arial.ttf"), Path("/Library/Fonts/Arial Bold.ttf")),
    (Path("/System/Library/Fonts/Supplemental/Arial.ttf"), Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")),
    (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
]
F, FB = "VN-Regular", "VN-Bold"

NAVY, GREY, LIGHT = colors.HexColor("#12355B"), colors.HexColor("#5F6B7A"), colors.HexColor("#F2F5F9")
GREEN, LGREEN, AMBER, RED, NA = (colors.HexColor("#1B8A4B"), colors.HexColor("#5BAA3C"),
                                 colors.HexColor("#D99A00"), colors.HexColor("#C0392B"), colors.HexColor("#8A94A3"))

PAGE_W, PAGE_H = A4
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 1.7 * cm, 1.9 * cm, 1.7 * cm
FRAME_W = PAGE_W - 2 * MARGIN_X
FRAME_H = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM - 0.2 * cm

LAST_LAYOUT: dict = {}   # trang -> tỷ lệ chiếm khung (>1 nghĩa là nội dung phải co lại), dùng để kiểm thử


def _register_fonts() -> None:
    if F in pdfmetrics.getRegisteredFontNames():
        return
    for regular, bold in FONT_CANDIDATES:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont(F, str(regular)))
            pdfmetrics.registerFont(TTFont(FB, str(bold)))
            return
    raise FileNotFoundError("Không tìm thấy phông hỗ trợ tiếng Việt. Hãy đặt DejaVuSans.ttf và "
                            "DejaVuSans-Bold.ttf vào thư mục fonts/ ở gốc repo rồi chạy lại.")


# --------------------------------------------------------------------------
# Kiểu chữ và thành phần giao diện nhỏ
# --------------------------------------------------------------------------
def _styles() -> dict:
    def ps(name, **kw):
        base = dict(fontName=F, fontSize=9.4, leading=13, textColor=colors.HexColor("#1D2733"))
        base.update(kw)
        return ParagraphStyle(name, **base)
    return {
        "brand": ps("brand", fontName=FB, fontSize=11, textColor=GREY, alignment=TA_CENTER, leading=14),
        "sub": ps("sub", fontSize=9, textColor=GREY, alignment=TA_CENTER),
        "name": ps("name", fontName=FB, fontSize=19, leading=23, alignment=TA_CENTER, textColor=NAVY),
        "kind": ps("kind", fontName=FB, fontSize=10, alignment=TA_CENTER, textColor=GREY, spaceBefore=2),
        "h1": ps("h1", fontName=FB, fontSize=13.5, leading=17, textColor=NAVY, spaceAfter=2),
        "h2": ps("h2", fontName=FB, fontSize=9.6, leading=12.5, textColor=NAVY, spaceBefore=5, spaceAfter=2),
        "body": ps("body", spaceAfter=3),
        "bullet": ps("bullet", leftIndent=8, bulletIndent=0, spaceAfter=1.5),
        "small": ps("small", fontSize=7.8, leading=10.5, textColor=GREY),
        "warn": ps("warn", fontSize=8, textColor=colors.HexColor("#8A4B00")),
        "cell": ps("cell", fontSize=8.3, leading=10.8),
        "cell_b": ps("cell_b", fontName=FB, fontSize=8.3, leading=10.8, textColor=colors.white),
        "kpi_l": ps("kpi_l", fontSize=7, leading=9, textColor=GREY, alignment=TA_CENTER),
        "kpi_v": ps("kpi_v", fontName=FB, fontSize=12, leading=15, alignment=TA_CENTER, textColor=NAVY),
        "big": ps("big", fontName=FB, fontSize=30, leading=34, alignment=TA_CENTER, textColor=colors.white),
        "big_s": ps("big_s", fontName=FB, fontSize=11, leading=14, alignment=TA_CENTER, textColor=colors.white),
        "ban_l": ps("ban_l", fontName=FB, fontSize=9.5, textColor=colors.white),
        "ban_r": ps("ban_r", fontName=FB, fontSize=10.5, textColor=colors.white, alignment=2),
    }


def _p(text, style):
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def _fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "Có" if v else "Không"
    if isinstance(v, float):
        if abs(v) >= 1000:
            return f"{v:,.0f}"
        return f"{v:,.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def _pct(v) -> str:
    return "—" if v is None else f"{v:.1%}"


def _metric_fmt(label, value):
    name = str(label).lower()
    if value is None:
        return "—"
    if any(term in name for term in ("growth", "roe", "roa", "margin", "debt ratio")):
        try:
            return _pct(float(value))
        except (TypeError, ValueError):
            return str(value)
    return _fmt(value)


def _score_color(score):
    if score is None:
        return NA
    return GREEN if score >= 80 else LGREEN if score >= 65 else AMBER if score >= 50 else RED


def _find(res, names, default=None):
    """Tìm giá trị trong metrics của module theo danh sách tên (không phân biệt hoa thường)."""
    metrics = (res or {}).get("metrics") or {}
    low = {str(k).strip().lower(): v for k, v in metrics.items()}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return default


def _img(path, max_w, max_h):
    if not (isinstance(path, (str, os.PathLike)) and os.path.exists(str(path))
            and str(path).lower().endswith((".png", ".jpg", ".jpeg"))):
        return None
    im = Image(str(path))
    ratio = min(max_w / im.imageWidth, max_h / im.imageHeight, 1.0 * max_w / im.imageWidth)
    ratio = min(ratio, max_w / im.imageWidth, max_h / im.imageHeight)
    im.drawWidth, im.drawHeight = im.imageWidth * ratio, im.imageHeight * ratio
    return im


def _pick_charts(res, keywords_list):
    """Chọn file ảnh theo từ khóa trong tên file; không khớp thì lấy lần lượt theo thứ tự."""
    raw = (res or {}).get("charts", [])
    raw = list(raw.values()) if isinstance(raw, dict) else raw
    charts = []
    for chart in raw:
        if not isinstance(chart, (str, os.PathLike)):
            continue
        path = Path(chart)
        if not path.is_absolute() and not path.exists():
            path = ROOT / path
        if path.exists():
            charts.append(path)
    picked, rest = [], list(charts)
    for kws in keywords_list:
        hit = next((c for c in rest if any(k in os.path.basename(str(c)).lower() for k in kws)), None)
        if hit is None and rest:
            hit = rest[0]
        if hit is not None:
            picked.append(hit)
            rest.remove(hit)
        else:
            picked.append(None)
    return picked


def _table(rows, header, st, widths=None, highlight=None, zebra=True):
    data = [[_p(h, st["cell_b"]) for h in header]] + [[_p(c, st["cell"]) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C8D0DA")),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2)]
    if zebra:
        style.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]))
    if highlight is not None:
        style.append(("BACKGROUND", (0, highlight + 1), (-1, highlight + 1), colors.HexColor("#DCEBFA")))
    t.setStyle(TableStyle(style))
    return t


def _df_table(df, st, max_rows=8, widths=None):
    df = df.head(max_rows)
    return _table([[_fmt(v) for v in row] for row in df.itertuples(index=False)],
                  [str(c) for c in df.columns], st, widths)


def _banner(title, score, label, st):
    right = "Chưa có điểm" if score is None else f"{score:.0f}/100" + (f" — {label}" if label else "")
    t = Table([[_p(title, st["ban_l"]), _p(right, st["ban_r"])]], colWidths=[FRAME_W * 0.5, FRAME_W * 0.5])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _score_color(score)), ("TOPPADDING", (0, 0), (-1, -1), 4),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return t


def _kpis(items, st, cols=4):
    items = [(a, b) for a, b in items]
    while len(items) % cols:
        items.append(("", ""))
    rows = []
    for i in range(0, len(items), cols):
        chunk = items[i:i + cols]
        rows.append([[_p(l, st["kpi_l"]), _p(v, st["kpi_v"])] for l, v in chunk])
    t = Table(rows, colWidths=[FRAME_W / cols] * cols)
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#C8D0DA")),
                           ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E1E6EC")),
                           ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def _two_cols(l_title, l_items, r_title, r_items, st, empty="Chưa có dữ liệu."):
    def block(title, items):
        cell = [_p(title, st["h2"])]
        cell += [Paragraph("• " + escape(str(x)), st["bullet"]) for x in items] or [_p(empty, st["small"])]
        return cell
    t = Table([[block(l_title, l_items), block(r_title, r_items)]], colWidths=[FRAME_W / 2] * 2)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEAFTER", (0, 0), (0, 0), 0.3, colors.HexColor("#C8D0DA")),
                           ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]))
    return t


def _bars(rows, st):
    """rows: [(nhãn, điểm hoặc None)] -> thanh điểm ngang."""
    data = []
    for label, score in rows:
        d = Drawing(FRAME_W * 0.45, 9)
        d.add(Rect(0, 1, FRAME_W * 0.45, 7, fillColor=colors.HexColor("#E4E9F0"), strokeColor=None))
        if score is not None:
            d.add(Rect(0, 1, FRAME_W * 0.45 * max(0, min(score, 100)) / 100, 7, fillColor=_score_color(score), strokeColor=None))
        data.append([_p(label, st["cell"]), d, _p("—" if score is None else f"{score:.0f}/100", st["cell"])])
    t = Table(data, colWidths=[FRAME_W * 0.25, FRAME_W * 0.47, FRAME_W * 0.16])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    return t


def _no_data(text, st):
    return _p(text, st["warn"])


# --------------------------------------------------------------------------
# Biểu đồ do TV6 tự vẽ (radar, sentiment) -- cần matplotlib
# --------------------------------------------------------------------------
def _make_radar(components, ticker, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:  # noqa: BLE001
        return None
    rows = [r for r in components if r["available"]]
    if len(rows) < 3:
        return None
    labels = [scoring.SHORT_LABELS[r["name"]] for r in rows]
    vals = [r["score"] for r in rows]
    ang = np.linspace(0, 2 * np.pi, len(rows), endpoint=False).tolist()
    vals_c, ang_c = vals + vals[:1], ang + ang[:1]
    fig = plt.figure(figsize=(3.4, 3.1))
    ax = fig.add_subplot(111, polar=True)
    ax.plot(ang_c, vals_c, color="#12355B", linewidth=1.8)
    ax.fill(ang_c, vals_c, color="#12355B", alpha=0.22)
    ax.set_xticks(ang)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(["25", "50", "75", "100"], fontsize=6, color="#666666")
    fig.tight_layout()
    path = out_dir / f"radar_{ticker}.png"
    fig.savefig(path, dpi=170)
    plt.close(fig)
    return path


def _make_sentiment(sent, ticker, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return None
    vals = [sent.get("positive") or 0, sent.get("neutral") or 0, sent.get("negative") or 0]
    if sum(vals) <= 0:
        return None
    fig, ax = plt.subplots(figsize=(3.4, 1.7))
    ax.barh(["Positive", "Neutral", "Negative"], vals, color=["#1B8A4B", "#8A94A3", "#C0392B"])
    for i, v in enumerate(vals):
        ax.text(v + 0.8, i, f"{v:.0f}%", va="center", fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, max(vals) * 1.25 + 5)
    ax.tick_params(labelsize=8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    path = out_dir / f"sentiment_{ticker}.png"
    fig.savefig(path, dpi=170)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------
# Các trang
# --------------------------------------------------------------------------
def _header_title(title, st):
    return [_p(title, st["h1"]), Spacer(1, 2)]


def _view(res, st, title="View"):
    summary = res.get("summary") or res.get("technical_view") or res.get("commentary")
    if not summary and res.get("comments"):
        summary = " ".join(map(str, res["comments"]))
    return [_p(title, st["h2"]), _p(summary or "Chưa có nhận xét từ module.", st["body"])]


def page1(ctx, st):
    res, inv, base = ctx["results"], ctx["all"], ctx["all"]["base"]
    mk = (res.get("market") or {}).get("raw") or {}
    unit = mk.get("price_unit", "")
    story = [_p("STOCKLENS", st["brand"]), _p("Stock Investment Analysis System", st["sub"]), Spacer(1, 14),
             _p(f"{ctx['company']} – {ctx['ticker']}", st["name"]), _p("INVESTMENT ANALYSIS REPORT", st["kind"]),
             Spacer(1, 8)]
    if ctx["demo"]:
        story += [_p("DỮ LIỆU GIẢ LẬP — chỉ để thử hệ thống, không dùng để đánh giá đầu tư.", st["warn"]), Spacer(1, 4)]
    selected = inv.get("selected_result") or base
    total = selected.get("total")
    box = Table([[_p("INVESTMENT SCORE" + f" ({ctx['style']})", st["big_s"])],
                 [_p("—" if total is None else f"{total}/100", st["big"])],
                 [_p(selected["rating"].upper(), st["big_s"])]], colWidths=[FRAME_W * 0.6])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _score_color(total)), ("TOPPADDING", (0, 0), (-1, -1), 4),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    outer = Table([[box]], colWidths=[FRAME_W])
    outer.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story += [outer, Spacer(1, 8)]
    kp = [("Current Price" + (f" ({unit})" if unit else ""), _fmt(mk.get("last_close"))),
          ("Return (cả giai đoạn)", _pct(mk.get("return_period"))),
          ("P/E", _fmt(_find(res.get("valuation"), ["P/E", "PE"]))),
          ("P/B", _fmt(_find(res.get("valuation"), ["P/B", "PB"]))),
          ("ROE", _metric_fmt("ROE", _find(res.get("fundamental"), ["ROE"]))),
          ("Market Risk Score", "—" if not res.get("risk") else f"{res['risk']['score']:.0f}/100"),
          ("Investor Profile", ctx["style"]), ("Analysis Period", ctx["period"]), ("Data Updated", ctx["updated"])]
    story += [_kpis(kp, st, cols=3), Spacer(1, 8)]
    story.append(_p("Base Score Breakdown (25/25/25/15/10)", st["h2"]))
    story.append(_bars([(scoring.SHORT_LABELS[r["name"]], r["score"]) for r in base.get("components", [])]
                       or [(scoring.SHORT_LABELS[n], None) for n in scoring.COMPONENTS], st))
    story.append(Spacer(1, 8))
    ups, downs = scoring.explain_score(res, base)
    drivers = [x for k in ["fundamental", "valuation", "technical", "news"] for x in ((res.get(k) or {}).get("positives") or [])[:1]]
    risks = [x for k in ["fundamental", "valuation", "technical", "news"] for x in ((res.get(k) or {}).get("risks") or [])[:1]]
    story.append(_two_cols("Key Drivers", (drivers or ups)[:5], "Key Risks", (risks or downs)[:5], st,
                           empty="Không có yếu tố nổi bật từ dữ liệu hiện có."))
    story += [Spacer(1, 6), _p("Base Score dùng trọng số chuẩn 25/25/25/15/10; điểm theo phong cách đầu tư xem ở trang 7. "
                               "Kết quả hỗ trợ phân tích, không phải khuyến nghị mua/bán.", st["small"])]
    return story


def page2(ctx, st):
    res = ctx["results"]
    mk = (res.get("market") or {}).get("raw") or {}
    tech = res.get("technical")
    unit = mk.get("price_unit", "")
    story = _header_title("Market & Technical Analysis", st)
    if mk:
        story.append(_kpis([
            ("Current Price" + (f" ({unit})" if unit else ""), _fmt(mk.get("last_close"))),
            ("Return (cả giai đoạn)", _pct(mk.get("return_period"))),
            ("High / Low (giai đoạn)", f"{_fmt(mk.get('high_period'))} / {_fmt(mk.get('low_period'))}"),
            ("Average Volume 20 phiên", _fmt(mk.get("avg_volume_20d"))),
            ("Volatility (năm)", _pct(mk.get("volatility_annual"))),
            ("Analysis Period", ctx["period"])], st, cols=3))
    else:
        story.append(_no_data("Không có dữ liệu thị trường (module TV1 lỗi hoặc chưa có kết quả).", st))
    if not tech:
        story += [Spacer(1, 6), _no_data("Không có kết quả phân tích kỹ thuật (module TV2 lỗi hoặc chưa có kết quả).", st)]
        return story
    price_c, rsi_c, macd_c = _pick_charts(tech, [["price", "ma"], ["rsi"], ["macd"]])
    story.append(_p("2.2 Price Trend", st["h2"]))
    im = _img(price_c, FRAME_W, 6.2 * cm)
    story.append(im or _no_data("Thiếu biểu đồ giá + MA20/MA50 (technical_price_ma.png).", st))
    close, ma20, ma50 = tech.get("close"), tech.get("ma20"), tech.get("ma50")
    comparisons = []
    if close is not None and ma20 is not None:
        comparisons.append(f"Close {'trên' if close >= ma20 else 'dưới'} MA20")
    if close is not None and ma50 is not None:
        comparisons.append(f"Close {'trên' if close >= ma50 else 'dưới'} MA50")
    if ma20 is not None and ma50 is not None:
        comparisons.append(f"MA20 {'trên' if ma20 >= ma50 else 'dưới'} MA50")
    if comparisons:
        story.append(_p("Xu hướng giá: " + "; ".join(comparisons) + ".", st["body"]))
    story.append(_p("2.3 Momentum (RSI, MACD)", st["h2"]))
    rsi_value = tech.get("rsi")
    rsi_label = ("Quá mua" if rsi_value is not None and rsi_value >= 70 else
                 "Quá bán" if rsi_value is not None and rsi_value <= 30 else
                 "Trung lập" if rsi_value is not None else "—")
    story.append(_kpis([("RSI (14)", _fmt(rsi_value)), ("RSI Status", rsi_label),
                        ("MACD", _fmt(tech.get("macd"))), ("Signal Line", _fmt(tech.get("macd_signal"))),
                        ("Histogram", _fmt(tech.get("macd_histogram")))], st, cols=3))
    left, right = _img(rsi_c, FRAME_W / 2 - 3, 4.6 * cm), _img(macd_c, FRAME_W / 2 - 3, 4.6 * cm)
    if left or right:
        t = Table([[left or _no_data("Thiếu technical_rsi.png", st), right or _no_data("Thiếu technical_macd.png", st)]],
                  colWidths=[FRAME_W / 2] * 2)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(t)
    else:
        story.append(_no_data("Thiếu biểu đồ RSI/MACD.", st))
    story.append(_p("2.4 Volume & Volatility", st["h2"]))
    story.append(_kpis([("Average Volume 20 phiên", _fmt(tech.get("avg_volume_20"))),
                        ("Volume phiên gần nhất", _fmt(tech.get("volume"))),
                        ("Volume change so với TB20", _pct(tech.get("volume_ratio") - 1)
                         if tech.get("volume_ratio") is not None else "—"),
                        ("Volatility", _pct(tech.get("volatility")))], st, cols=4))
    sig = tech.get("signals")
    if sig:
        story += [_p("2.5 Technical Signals", st["h2"]),
                  _table([[_fmt(c) for c in r] for r in sig], ["Indicator", "Value", "Signal"], st,
                         widths=[FRAME_W * 0.34, FRAME_W * 0.33, FRAME_W * 0.33])]
    story += [_p("2.6 Technical Score & View", st["h2"]), Spacer(1, 2),
              _banner("TECHNICAL SCORE", tech.get("score"), tech.get("label"), st)]
    story += _view(tech, st, "Technical View")
    return story


def page3(ctx, st):
    fa = ctx["results"].get("fundamental")
    story = _header_title("Fundamental & Financial Analysis", st)
    if not fa:
        return story + [_no_data("Không có kết quả phân tích tài chính (module TV3 lỗi hoặc chưa có kết quả).", st)]
    metrics = list((fa.get("metrics") or {}).items())[:8]
    if metrics:
        story += [_p("3.1–3.2 Financial Performance, Profitability & Financial Health", st["h2"]),
                  _kpis([(k, _metric_fmt(k, v)) for k, v in metrics], st, cols=4)]
    charts = [_img(c, FRAME_W, 7.4 * cm) for c in (fa.get("charts") or [])[:2]]
    charts = [c for c in charts if c]
    for c in charts:
        story += [Spacer(1, 4), c]
    if not charts:
        story += [Spacer(1, 4), _no_data("Thiếu biểu đồ Revenue & Net Profit.", st)]
    for tbl in (fa.get("tables") or [])[:2]:
        if hasattr(tbl, "head"):
            story += [Spacer(1, 4), _df_table(tbl, st, max_rows=7)]
    story += [Spacer(1, 6), _banner("FUNDAMENTAL SCORE", fa.get("score"), fa.get("label"), st),
              _two_cols("Strengths", fa.get("positives") or [], "Risks", fa.get("risks") or [], st)]
    story += _view(fa, st, "Fundamental View")
    return story


def page4(ctx, st):
    va = ctx["results"].get("valuation")
    story = _header_title("Valuation Analysis", st)
    if not va:
        return story + [_no_data("Không có kết quả định giá (module TV4 lỗi hoặc chưa có kết quả).", st)]
    metrics = list((va.get("metrics") or {}).items())[:8]
    if metrics:
        story += [_p("4.1 Valuation Snapshot", st["h2"]), _kpis([(k, _fmt(v)) for k, v in metrics], st, cols=4)]
    story.append(_p("4.2 Relative Valuation", st["h2"]))
    peer = va.get("peer_table")
    if peer is not None and hasattr(peer, "head"):
        story.append(_df_table(peer, st, max_rows=10))
    else:
        story.append(_no_data("Không đủ dữ liệu đáng tin cậy để thực hiện so sánh với nhóm doanh nghiệp cùng ngành.", st))
    for tbl in (va.get("tables") or [])[:1]:
        if hasattr(tbl, "head"):
            story += [Spacer(1, 4), _df_table(tbl, st, max_rows=8)]
    for c in [_img(c, FRAME_W, 5.5 * cm) for c in (va.get("charts") or [])[:1]]:
        if c:
            story += [Spacer(1, 4), c]
    story += [Spacer(1, 6), _banner("VALUATION SCORE", va.get("score"), va.get("label"), st),
              _two_cols("Positive factors", va.get("positives") or [], "Risks", va.get("risks") or [], st)]
    story += _view(va, st, "Valuation View")
    return story


def page5(ctx, st):
    nw = ctx["results"].get("news")
    story = _header_title("News & Sentiment Analysis", st)
    if not nw:
        return story + [_no_data("Không có kết quả tin tức (module TV5 lỗi hoặc chưa có kết quả).", st)]
    sent = nw.get("sentiment") or {}
    story += [_p("5.1 Sentiment Overview", st["h2"]),
              _kpis([("Positive", f"{sent.get('positive', 0):.0f}%" if sent else "—"),
                     ("Neutral", f"{sent.get('neutral', 0):.0f}%" if sent else "—"),
                     ("Negative", f"{sent.get('negative', 0):.0f}%" if sent else "—"),
                     ("News Score", "—" if nw.get("score") is None else f"{nw['score']:.0f}/100")], st, cols=4)]
    chart = _img((nw.get("charts") or [None])[0], FRAME_W * 0.6, 4.2 * cm) or \
        (_img(_make_sentiment(sent, ctx["ticker"], ctx["out_dir"]), FRAME_W * 0.6, 4.2 * cm) if sent else None)
    if chart:
        story += [Spacer(1, 4), chart]
    story.append(_p("5.2 Key News", st["h2"]))
    tbls = [t for t in (nw.get("tables") or []) if hasattr(t, "head")]
    if tbls:
        story.append(_df_table(tbls[0], st, max_rows=8, widths=[FRAME_W * w for w in (0.12, 0.43, 0.17, 0.14, 0.14)]
                               if tbls[0].shape[1] == 5 else None))
    else:
        story.append(_no_data("Không có bảng tin nổi bật.", st))
    story += [Spacer(1, 4), _two_cols("Positive Catalysts", nw.get("positives") or [], "News-related Risks",
                                      nw.get("risks") or [], st),
              Spacer(1, 4), _banner("NEWS SCORE", nw.get("score"), nw.get("label"), st)]
    story += _view(nw, st, "News View")
    return story


def page6(ctx, st):
    res, base = ctx["results"], ctx["all"]["base"]
    story = _header_title("Investment Score, Market Risk & Why This Score", st)
    story.append(_p("6.1 Base Investment Score (trọng số chuẩn 25/25/25/15/10)", st["h2"]))
    if base.get("total") is None:
        story.append(_no_data(base.get("explanation", "Không đủ dữ liệu để tính Investment Score."), st))
    else:
        story.append(_banner("INVESTMENT SCORE", base["total"], base["rating"], st))
        rows = [[scoring.SHORT_LABELS[r["name"]], "—" if r["score"] is None else f"{r['score']:.0f}",
                 f"{r['weight']:.0%}", f"{r['contribution']:.1f}"] for r in base["components"]]
        rows.append(["Total", "", "100%", f"{base['total']}/100"])
        table = _table(rows, ["Component", "Score", "Weight", "Contribution"], st,
                       widths=[FRAME_W * 0.18, FRAME_W * 0.09, FRAME_W * 0.1, FRAME_W * 0.16])
        radar = _img(_make_radar(base["components"], ctx["ticker"], ctx["out_dir"]), FRAME_W * 0.38, 5.2 * cm)
        story.append(Spacer(1, 3))
        side = Table([[table, radar or ""]], colWidths=[FRAME_W * 0.58, FRAME_W * 0.42])
        side.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(side)
        for w in base.get("warnings", []):
            story.append(_p("• " + w, st["warn"]))
    story.append(_p("6.2 Market Risk Assessment", st["h2"]))
    risk = res.get("risk")
    if risk:
        d = risk.get("details", {})
        story += [_banner("MARKET RISK SCORE", risk["score"], "", st), Spacer(1, 3),
                  _p(risk.get("summary", ""), st["body"]),
                  _p("Market Risk Score hiện chỉ dùng Volatility và Maximum Drawdown nên được gọi là Market Risk, "
                     "chưa phải Overall Risk (chưa gồm rủi ro tài chính và rủi ro tin tức).", st["small"])]
    else:
        story.append(_no_data("Không tính được Market Risk Score (thiếu dữ liệu giá).", st))
    story.append(_p("6.3 Why This Score?", st["h2"]))
    ups, downs = scoring.explain_score(res, base)
    story.append(_two_cols("Factors Increasing the Score ↑", ups[:7], "Factors Reducing the Score ↓", downs[:7], st,
                           empty="Không có yếu tố nổi bật theo ngưỡng 70/60 điểm."))
    return story


def page7(ctx, st):
    res, allr = ctx["results"], ctx["all"]
    sel, style = allr["selected_result"], ctx["style"]
    story = _header_title("Personalized Investment View & Final View", st)
    story.append(_p("7.1–7.2 Investor Profile và Profile-adjusted Score", st["h2"]))
    names = list(allr["profiles"])
    rows = []
    for s in names:
        r = allr["profiles"][s]
        w = scoring.STYLE_WEIGHTS[s]
        rows.append([s + (" (đã chọn)" if s == style else ""), "—" if r["total"] is None else f"{r['total']:.1f}", r["rating"],
                     " / ".join(f"{int(round(w[k] * 100))}" for k in scoring.COMPONENTS)])
    story.append(_table(rows, ["Profile", "Adjusted Score", "Xếp loại", "Trọng số F/V/T/N/R (%)"], st,
                        widths=[FRAME_W * 0.3, FRAME_W * 0.18, FRAME_W * 0.22, FRAME_W * 0.3],
                        highlight=names.index(style)))
    story.append(_p(f"Base Score (luôn dùng 25/25/25/15/10): {allr['base']['total']}/100. Adjusted Score thay đổi theo "
                    "trọng số của phong cách; mức ưu tiên bên dưới được suy ra từ chính các trọng số đó.", st["small"]))
    story.append(Spacer(1, 3))
    tr = scoring.profile_traits(style)
    story.append(_table([[a, b, f"{c:.0%}"] for a, b, c in tr], ["Tiêu chí của phong cách " + style, "Mức độ", "Trọng số"], st,
                        widths=[FRAME_W * 0.5, FRAME_W * 0.25, FRAME_W * 0.25]))
    story.append(_p("7.3 Personalized View", st["h2"]))
    fits, cares = [], []
    for r in sel.get("components", []):
        if not r["available"]:
            continue
        w = scoring.STYLE_WEIGHTS[style][r["name"]]
        line = f"{scoring.SHORT_LABELS[r['name']]} {r['score']:.0f}/100 (phong cách này đặt trọng số {w:.0%})"
        if w >= 0.2 and r["score"] >= scoring.STRONG:
            fits.append(line + " — phù hợp với ưu tiên của phong cách.")
        elif w >= 0.2 and r["score"] < scoring.WEAK:
            cares.append(line + " — thấp ở thành phần mà phong cách này coi trọng.")
        elif r["score"] < scoring.WEAK:
            cares.append(line + " — thành phần yếu cần theo dõi.")
    story.append(_two_cols("Suitable Characteristics", fits, "Points to Consider", cares, st,
                           empty="Không có điểm nổi bật theo ngưỡng 70/60 điểm."))
    story.append(_p("7.4 Final Investment View", st["h2"]))
    story.append(_p(scoring.final_view(ctx["ticker"], res, allr["base"], sel), st["body"]))
    return story


def page8(ctx, st):
    res = ctx["results"]
    story = _header_title("Methodology, Data Sources & Disclaimer", st)
    story.append(_p("8.1 Methodology", st["h2"]))
    bw = scoring.BASE_WEIGHTS
    items = [
        "Return = giá đóng cửa cuối kỳ / giá đóng cửa đầu kỳ − 1. Volatility = độ lệch chuẩn lợi suất ngày × √252. "
        "Maximum Drawdown = mức sụt giảm lớn nhất từ đỉnh trước đó. Average Volume = khối lượng trung bình 20 phiên gần nhất.",
        "Kỹ thuật: MA20/MA50, RSI, MACD và các tín hiệu do module Technical định nghĩa; từng tín hiệu riêng lẻ không phải bằng chứng chắc chắn.",
        "Tài chính và định giá: các tỷ số (ROE, ROA, biên lợi nhuận, tỷ lệ nợ, P/E, P/B) tính từ báo cáo tài chính và giá cùng thời điểm.",
        "Tin tức: phân loại Positive/Neutral/Negative theo quy tắc của module News; điểm có độ tin cậy giới hạn khi số tin ít.",
        f"Base Investment Score = {bw['fundamental']:.0%}×Fundamental + {bw['valuation']:.0%}×Valuation + {bw['technical']:.0%}×Technical + "
        f"{bw['news']:.0%}×News + {bw['risk']:.0%}×Safety/Risk. Ngưỡng xếp loại (≥65 Tích cực; "
        "50–<65 Trung lập; <50 Thận trọng) là giả định thiết kế của nhóm, không phải kết luận thực nghiệm.",
        "Profile-adjusted Score dùng bộ trọng số của phong cách Thận trọng / Cân bằng / Tăng trưởng. Khi thiếu một thành phần, "
        "hệ thống chia lại trọng số cho các thành phần còn lại và ghi cảnh báo; không gán điểm 0 hoặc 100 thay thế.",
        "Market Risk Score = trung bình điểm Volatility (15% → 100 điểm, ≥60% → 0 điểm) và điểm Maximum Drawdown (0% → 100 điểm, ≤−50% → 0 điểm).",
    ]
    for it in items:
        story.append(Paragraph("• " + escape(it), st["bullet"]))
    story.append(_p("8.2 Data Sources", st["h2"]))
    rows = []
    for label, key in [("Market", "market"), ("Financial Statements", "fundamental"), ("Valuation", "valuation"),
                       ("News", "news")]:
        srcs = (res.get(key) or {}).get("sources") or []
        if isinstance(srcs, dict):
            src_text = "; ".join(f"{k}: {v}" for k, v in srcs.items())
        elif isinstance(srcs, (list, tuple, set)):
            src_text = "; ".join(map(str, srcs))
        else:
            src_text = str(srcs) if srcs else ""
        rows.append([label, src_text or "Chưa ghi nguồn", ctx["updated"] if src_text else "—"])
    peer = "Có" if (res.get("valuation") or {}).get("peer_table") is not None else "N.A."
    rows.append(["Peer/Industry", "Theo module Valuation" if peer == "Có" else "N.A. (không đủ dữ liệu đáng tin cậy)", "—"])
    story.append(_table(rows, ["Data", "Source", "Updated"], st, widths=[FRAME_W * 0.2, FRAME_W * 0.6, FRAME_W * 0.2]))
    notes = []
    for key, r in res.items():
        for w in (r or {}).get("warnings", []) or []:
            notes.append(f"[{key}] {w}")
    for key, msg in (ctx["errors"] or {}).items():
        notes.append(f"Module '{key}' gặp lỗi và không được đưa vào điểm: {msg}")
    if notes:
        story.append(_p("Cảnh báo dữ liệu và hạn chế", st["h2"]))
        for n in notes[:8]:
            story.append(Paragraph("• " + escape(n), st["bullet"]))
    story.append(_p("8.3 Disclaimer", st["h2"]))
    story.append(_p("StockLens là hệ thống hỗ trợ phân tích, tổng hợp dữ liệu và phương pháp do nhóm xây dựng. Kết quả phân tích "
                    "và điểm số không phải khuyến nghị mua, bán hoặc nắm giữ chứng khoán. Dữ liệu có thể chưa đầy đủ hoặc đã "
                    "thay đổi; người dùng tự chịu trách nhiệm với quyết định đầu tư và nên tham khảo ý kiến chuyên gia được cấp phép.",
                    st["body"]))
    return story


PAGE_BUILDERS = {"market_technical": page2, "fundamental": page3, "valuation": page4, "news": page5,
                 "score": page6, "personalized": page7}


# --------------------------------------------------------------------------
# Hàm chính
# --------------------------------------------------------------------------
def generate_report(ticker, style, results, investment_all, sections=None, output_path=None,
                    errors=None, demo=False, meta=None) -> str:
    _register_fonts()
    st = _styles()
    ticker = ticker.upper()
    meta = meta or {}
    out_dir = ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    chart_dir = ROOT / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_path or out_dir / f"{ticker}_Investment_Report.pdf")

    ctx = {"ticker": ticker, "style": style, "results": results, "all": investment_all, "errors": errors or {},
           "demo": demo, "company": meta.get("company") or ticker, "period": meta.get("period", "—"),
           "updated": meta.get("updated", datetime.now().strftime("%d/%m/%Y %H:%M")), "out_dir": chart_dir}

    selected_sections = set(PAGE_BUILDERS) if sections is None else set(sections)
    builders = [("cover", page1)]
    for key, page_builder in PAGE_BUILDERS.items():
        if key in selected_sections:
            builders.append((key, page_builder))
        else:
            title = SECTION_TITLES[key]
            builders.append((key, lambda _ctx, _st, title=title: [
                _header_title(title, _st)[0],
                _no_data("Người dùng đã không chọn nội dung này cho báo cáo.", _st)
            ]))
    builders.append(("methodology", page8))

    story, LAST_LAYOUT_local = [], {}
    for i, (key, fn) in enumerate(builders, 1):
        try:
            content = fn(ctx, st)
        except Exception as exc:  # noqa: BLE001 - một trang lỗi không được làm hỏng cả PDF
            content = [_p(f"Không dựng được trang '{key}': {type(exc).__name__}: {exc}", st["warn"])]
        # đo mức chiếm khung để biết trang nào quá dài
        used = 0.0
        for fl in content:
            _, h = fl.wrap(FRAME_W, FRAME_H)
            used += h + getattr(fl, "spaceBefore", 0) + getattr(fl, "spaceAfter", 0)
        LAST_LAYOUT_local[key] = round(used / FRAME_H, 2)
        story.append(KeepInFrame(FRAME_W, FRAME_H, content, mode="shrink"))
        if i < len(builders):
            story.append(PageBreak())
    LAST_LAYOUT.clear()
    LAST_LAYOUT.update(LAST_LAYOUT_local)

    def deco(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_H - 0.55 * cm, PAGE_W, 0.55 * cm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont(FB, 7.5)
        canvas.drawString(MARGIN_X, PAGE_H - 0.39 * cm, f"STOCKLENS  |  {ticker} Investment Analysis Report")
        canvas.setFillColor(GREY)
        canvas.setFont(F, 7)
        canvas.drawString(MARGIN_X, 0.9 * cm, "StockLens hỗ trợ phân tích, không phải khuyến nghị mua/bán/nắm giữ.")
        canvas.drawRightString(PAGE_W - MARGIN_X, 0.9 * cm, f"Trang {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                            topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM, title=f"{ticker} Investment Report")
    doc.build(story, onFirstPage=deco, onLaterPages=deco)
    return output_path
