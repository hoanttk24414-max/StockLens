"""
TV3 - Phân tích tài chính doanh nghiệp.

Hàm chính:  analyze_fundamental(financial_df, style="Cân bằng", chart_dir="charts")

Đầu vào (financial_df) là bảng chuẩn hóa do financial_data.py tạo ra, dạng long-form, đơn vị VND:
    ticker, period_type ("quarter"|"year"), year, quarter (0 với dữ liệu năm),
    revenue, net_profit, total_assets, total_liabilities, equity, cfo, source, fetched_at
Chỉ phân tích 1 mã mỗi lần gọi (lọc theo ticker trước khi truyền vào, hoặc truyền `ticker=`).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

STYLES = ["Thận trọng", "Cân bằng", "Tăng trưởng"]

# Trọng số các nhóm chỉ tiêu BÊN TRONG Financial Score, theo phong cách đầu tư.
# Tăng trưởng doanh thu/lợi nhuận chỉ nằm ở nhóm "growth" (không tính trùng ở nhóm khác).
GROUP_WEIGHTS = {
    "Thận trọng":  {"profitability": 0.35, "growth": 0.15, "leverage": 0.30, "cashflow": 0.20},
    "Cân bằng":    {"profitability": 0.30, "growth": 0.30, "leverage": 0.25, "cashflow": 0.15},
    "Tăng trưởng": {"profitability": 0.20, "growth": 0.55, "leverage": 0.10, "cashflow": 0.15},
}
GROUP_LABELS = {"profitability": "Khả năng sinh lời", "growth": "Tăng trưởng",
                "leverage": "Đòn bẩy tài chính", "cashflow": "Chất lượng dòng tiền"}

# Bảng quy đổi chỉ tiêu -> điểm 0-100 (nội suy tuyến tính giữa các mốc, ngoài mốc thì lấy điểm biên).
# Đây là ngưỡng chung cho doanh nghiệp phi tài chính; nhóm có thể điều chỉnh sau khi thảo luận.
SCORE_POINTS = {
    "roe":           [(0.00, 0), (0.05, 30), (0.10, 55), (0.15, 75), (0.20, 100)],
    "net_margin":    [(0.00, 0), (0.05, 40), (0.10, 65), (0.20, 100)],
    "revenue_growth": [(-0.10, 0), (0.00, 35), (0.10, 60), (0.20, 80), (0.30, 100)],
    "profit_growth":  [(-0.20, 0), (0.00, 35), (0.10, 60), (0.20, 80), (0.30, 100)],
    "debt_to_assets": [(0.30, 100), (0.50, 75), (0.70, 40), (0.85, 10), (0.90, 0)],
    "cfo_to_profit":  [(0.00, 0), (0.50, 40), (1.00, 80), (1.20, 100)],
}
FINANCIAL_FIRM_DA = 0.85  # D/A cao hơn mức này nhiều khả năng là ngân hàng/tài chính -> không áp ngưỡng đòn bẩy

METHOD_TEXT = (
    "Financial Score (0-100) là trung bình có trọng số của bốn nhóm: khả năng sinh lời (ROE, biên lợi nhuận ròng), "
    "tăng trưởng (tăng trưởng doanh thu, lợi nhuận và tính liên tục), đòn bẩy (nợ phải trả/tổng tài sản) và chất lượng "
    "dòng tiền (dòng tiền kinh doanh/lợi nhuận sau thuế). Mỗi chỉ tiêu được quy đổi sang thang 0-100 bằng nội suy tuyến "
    "tính theo các mốc cố định. Trọng số nhóm thay đổi theo phong cách đầu tư. Chỉ tiêu nào không tính được sẽ bị loại và "
    "trọng số được chia lại cho các nhóm còn dữ liệu, không gán 0 hoặc 100 mặc định. ROE, ROA dùng vốn chủ sở hữu/tổng tài "
    "sản bình quân khi có kỳ trước, nếu không thì dùng số cuối kỳ. Số liệu quý được coi là số của riêng quý đó; kỳ gần nhất "
    "được tính theo 4 quý liên tiếp (TTM) khi mới hơn báo cáo năm."
)


# ----------------------------------------------------------------------------- tiện ích
def _score(value, key):
    if value is None or pd.isna(value):
        return np.nan
    xs, ys = zip(*SCORE_POINTS[key])
    return float(np.interp(value, xs, ys))


def _safe_div(a, b):
    if pd.isna(a) or pd.isna(b) or b == 0:
        return np.nan
    return a / b


def _growth(cur, prev):
    """Tăng trưởng so với kỳ trước; NaN nếu kỳ gốc <= 0 (tỷ lệ % không còn ý nghĩa)."""
    if pd.isna(cur) or pd.isna(prev) or prev <= 0:
        return np.nan
    return cur / prev - 1


def _fmt_pct(x):
    return "n/a" if pd.isna(x) else f"{x * 100:.1f}%"


def _fmt_bn(x):
    return "n/a" if pd.isna(x) else f"{x / 1e9:,.0f} tỷ đồng"


def _label(score):
    if pd.isna(score):
        return "chưa đủ dữ liệu"
    return "tốt" if score >= 75 else "khá" if score >= 60 else "trung bình" if score >= 40 else "yếu"


# ----------------------------------------------------------------------------- dựng bảng chỉ tiêu
NUM_COLS = ["revenue", "net_profit", "total_assets", "total_liabilities", "equity", "cfo"]


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for c in NUM_COLS:
        if c not in d.columns:
            d[c] = np.nan
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["year"] = pd.to_numeric(d["year"], errors="coerce")
    d["quarter"] = pd.to_numeric(d.get("quarter", 0), errors="coerce").fillna(0)
    d = d.dropna(subset=["year"])
    return d.drop_duplicates(["period_type", "year", "quarter"], keep="last")


def _annual_table(d: pd.DataFrame) -> pd.DataFrame:
    a = d[d["period_type"] == "year"].sort_values("year").reset_index(drop=True)
    if a.empty:
        return a
    a["label"] = "FY" + a["year"].astype(int).astype(str)
    a["revenue_prev"] = a["revenue"].shift(1)
    a["profit_prev"] = a["net_profit"].shift(1)
    # chỉ so sánh khi hai năm liền kề nhau
    gap = a["year"].diff() != 1
    a.loc[gap, ["revenue_prev", "profit_prev"]] = np.nan
    a["equity_avg"] = a[["equity"]].assign(p=a["equity"].shift(1)).mean(axis=1, skipna=True)
    a["assets_avg"] = a[["total_assets"]].assign(p=a["total_assets"].shift(1)).mean(axis=1, skipna=True)
    a.loc[gap, "equity_avg"] = a.loc[gap, "equity"]
    a.loc[gap, "assets_avg"] = a.loc[gap, "total_assets"]
    return a


def _ttm_table(d: pd.DataFrame) -> pd.DataFrame:
    q = d[d["period_type"] == "quarter"].copy()
    if q.empty:
        return q
    q = q.sort_values(["year", "quarter"]).reset_index(drop=True)
    q["idx"] = (q["year"] * 4 + q["quarter"]).astype(int)
    q = q.set_index("idx")
    full = pd.RangeIndex(q.index.min(), q.index.max() + 1)
    q = q.reindex(full)  # chèn dòng trống cho quý bị thiếu để rolling không ghép sai kỳ
    for c in ("revenue", "net_profit", "cfo"):
        q[f"{c}_ttm"] = q[c].rolling(4, min_periods=4).sum()
    q["revenue_ttm_prev"] = q["revenue_ttm"].shift(4)
    q["profit_ttm_prev"] = q["net_profit_ttm"].shift(4)
    q["equity_avg"] = q[["equity"]].assign(p=q["equity"].shift(4)).mean(axis=1, skipna=True)
    q["assets_avg"] = q[["total_assets"]].assign(p=q["total_assets"].shift(4)).mean(axis=1, skipna=True)
    q = q.dropna(subset=["revenue_ttm", "net_profit_ttm"], how="all")
    if q.empty:
        return q
    q["year"] = (q.index // 4).astype(int)
    q["quarter"] = (q.index % 4).astype(int)
    fix = q["quarter"] == 0  # idx = year*4 + quarter với quarter in 1..4 -> xử lý quý 4
    q.loc[fix, "year"] -= 1
    q.loc[fix, "quarter"] = 4
    q["label"] = "TTM Q" + q["quarter"].astype(str) + "/" + q["year"].astype(str)
    return q.reset_index(drop=True)


def _ratios(row, kind: str) -> dict:
    """Tính các tỷ số cho 1 dòng (năm hoặc TTM)."""
    if kind == "year":
        rev, np_, cfo = row["revenue"], row["net_profit"], row["cfo"]
        rev_prev, np_prev = row["revenue_prev"], row["profit_prev"]
    else:
        rev, np_, cfo = row["revenue_ttm"], row["net_profit_ttm"], row["cfo_ttm"]
        rev_prev, np_prev = row["revenue_ttm_prev"], row["profit_ttm_prev"]
    return {
        "label": row["label"], "kind": kind,
        "revenue": rev, "net_profit": np_, "cfo": cfo,
        "total_assets": row["total_assets"], "total_liabilities": row["total_liabilities"], "equity": row["equity"],
        "revenue_growth": _growth(rev, rev_prev),
        "profit_growth": _growth(np_, np_prev),
        "net_margin": _safe_div(np_, rev),
        "roe": _safe_div(np_, row["equity_avg"]),
        "roa": _safe_div(np_, row["assets_avg"]),
        "debt_to_assets": _safe_div(row["total_liabilities"], row["total_assets"]),
        "debt_to_equity": _safe_div(row["total_liabilities"], row["equity"]),
        "cfo_to_profit": _safe_div(cfo, np_) if (not pd.isna(np_) and np_ > 0) else np.nan,
    }


# ----------------------------------------------------------------------------- chấm điểm
def _group_scores(latest: dict, history: pd.DataFrame, is_financial_firm: bool) -> dict:
    prof = [_score(latest["roe"], "roe"), _score(latest["net_margin"], "net_margin")]
    # Tính liên tục: tỷ lệ các năm gần nhất (tối đa 3) có cả doanh thu và lợi nhuận tăng trưởng dương
    growth = [_score(latest["revenue_growth"], "revenue_growth"), _score(latest["profit_growth"], "profit_growth")]
    if not history.empty:
        h = history.tail(3)
        valid = h.dropna(subset=["revenue_growth", "profit_growth"], how="all")
        if len(valid) >= 2:
            ok = ((valid["revenue_growth"].fillna(-1) > 0) & (valid["profit_growth"].fillna(-1) > 0)).mean()
            growth.append(float(ok * 100))
    lev = [np.nan] if is_financial_firm else [_score(latest["debt_to_assets"], "debt_to_assets")]
    cf = [np.nan] if is_financial_firm else [_score(latest["cfo_to_profit"], "cfo_to_profit")]
    return {k: (float(np.nanmean(v)) if not all(pd.isna(v)) else np.nan)
            for k, v in {"profitability": prof, "growth": growth, "leverage": lev, "cashflow": cf}.items()}


def _combine(groups: dict, style: str):
    w = GROUP_WEIGHTS[style]
    avail = {k: v for k, v in groups.items() if not pd.isna(v)}
    coverage = sum(w[k] for k in avail)
    if coverage < 0.5:
        return None, coverage
    return sum(groups[k] * w[k] for k in avail) / coverage, coverage


# ----------------------------------------------------------------------------- biểu đồ
def _make_charts(ticker: str, annual_r: pd.DataFrame, chart_dir: str) -> list[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    os.makedirs(chart_dir, exist_ok=True)
    paths = []
    plt.rcParams["font.family"] = "DejaVu Sans"  # hỗ trợ tiếng Việt
    d = annual_r.tail(8)
    if d.empty:
        return paths
    x = np.arange(len(d))

    # 1. Doanh thu, lợi nhuận và biên lợi nhuận
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.bar(x - 0.2, d["revenue"] / 1e9, 0.4, label="Doanh thu thuần", color="#2F5D8A")
    ax.bar(x + 0.2, d["net_profit"] / 1e9, 0.4, label="Lợi nhuận sau thuế", color="#E39B2D")
    ax.set_ylabel("Tỷ đồng"); ax.set_xticks(x); ax.set_xticklabels(d["label"], rotation=0)
    ax2 = ax.twinx()
    ax2.plot(x, d["net_margin"] * 100, color="#B23A48", marker="o", label="Biên LN ròng (%)")
    ax2.set_ylabel("%")
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8, frameon=False)
    ax.set_title(f"{ticker}: Doanh thu, lợi nhuận và biên lợi nhuận ròng", fontsize=10)
    fig.tight_layout(); p = os.path.join(chart_dir, f"{ticker}_fa_revenue_profit.png")
    fig.savefig(p, dpi=150); plt.close(fig); paths.append(p)

    # 2. ROE, ROA
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.plot(x, d["roe"] * 100, marker="o", label="ROE", color="#2F5D8A")
    ax.plot(x, d["roa"] * 100, marker="s", label="ROA", color="#E39B2D")
    ax.set_xticks(x); ax.set_xticklabels(d["label"]); ax.set_ylabel("%")
    ax.legend(frameon=False, fontsize=8); ax.grid(alpha=0.25)
    ax.set_title(f"{ticker}: ROE và ROA", fontsize=10)
    fig.tight_layout(); p = os.path.join(chart_dir, f"{ticker}_fa_roe_roa.png")
    fig.savefig(p, dpi=150); plt.close(fig); paths.append(p)

    # 3. Cơ cấu nợ
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.plot(x, d["debt_to_assets"] * 100, marker="o", color="#B23A48")
    ax.set_xticks(x); ax.set_xticklabels(d["label"]); ax.set_ylabel("Nợ phải trả / Tổng tài sản (%)")
    ax.grid(alpha=0.25); ax.set_title(f"{ticker}: Tỷ lệ nợ trên tổng tài sản", fontsize=10)
    fig.tight_layout(); p = os.path.join(chart_dir, f"{ticker}_fa_leverage.png")
    fig.savefig(p, dpi=150); plt.close(fig); paths.append(p)
    return paths


# ----------------------------------------------------------------------------- nhận xét
def _comments(ticker, latest, groups, style, score, strengths, weaknesses):
    c = []
    c.append(
        f"Trong kỳ {latest['label']}, {ticker} ghi nhận doanh thu {_fmt_bn(latest['revenue'])} và lợi nhuận sau thuế "
        f"{_fmt_bn(latest['net_profit'])}, tương ứng biên lợi nhuận ròng {_fmt_pct(latest['net_margin'])}. "
        f"ROE đạt {_fmt_pct(latest['roe'])} và ROA đạt {_fmt_pct(latest['roa'])}.")
    c.append(
        f"Doanh thu thay đổi {_fmt_pct(latest['revenue_growth'])} và lợi nhuận thay đổi {_fmt_pct(latest['profit_growth'])} "
        f"so với kỳ cùng so sánh. Nợ phải trả chiếm {_fmt_pct(latest['debt_to_assets'])} tổng tài sản.")
    if not pd.isna(latest["cfo_to_profit"]):
        c.append(f"Dòng tiền từ hoạt động kinh doanh bằng {latest['cfo_to_profit']:.2f} lần lợi nhuận sau thuế.")
    if strengths:
        c.append("Điểm mạnh: " + "; ".join(strengths) + ".")
    if weaknesses:
        c.append("Điểm cần theo dõi: " + "; ".join(weaknesses) + ".")
    if score is not None:
        c.append(f"Theo phong cách {style.lower()}, Financial Score là {score:.0f}/100, mức {_label(score)}. "
                 "Điểm số chỉ tổng hợp các tiêu chí đã nêu trong phần phương pháp và không phải khuyến nghị mua bán.")
    return c


def _strengths_weaknesses(latest, is_fin):
    s, w = [], []
    def chk(cond_good, cond_bad, good, bad):
        if cond_good: s.append(good)
        if cond_bad: w.append(bad)
    roe, nm = latest["roe"], latest["net_margin"]
    chk(not pd.isna(roe) and roe >= 0.15, not pd.isna(roe) and roe < 0.08,
        f"ROE {_fmt_pct(roe)} ở mức cao", f"ROE {_fmt_pct(roe)} thấp")
    chk(not pd.isna(nm) and nm >= 0.10, not pd.isna(nm) and nm < 0.03,
        f"biên lợi nhuận ròng {_fmt_pct(nm)} tốt", f"biên lợi nhuận ròng {_fmt_pct(nm)} mỏng")
    rg, pg = latest["revenue_growth"], latest["profit_growth"]
    chk(not pd.isna(rg) and rg >= 0.10, not pd.isna(rg) and rg < 0,
        f"doanh thu tăng {_fmt_pct(rg)}", f"doanh thu giảm {_fmt_pct(rg)}")
    chk(not pd.isna(pg) and pg >= 0.10, not pd.isna(pg) and pg < 0,
        f"lợi nhuận tăng {_fmt_pct(pg)}", f"lợi nhuận giảm {_fmt_pct(pg)}")
    if not is_fin:
        da = latest["debt_to_assets"]
        chk(not pd.isna(da) and da <= 0.4, not pd.isna(da) and da >= 0.7,
            f"nợ/tổng tài sản chỉ {_fmt_pct(da)}", f"nợ/tổng tài sản cao {_fmt_pct(da)}")
        cp = latest["cfo_to_profit"]
        chk(not pd.isna(cp) and cp >= 1.0, not pd.isna(cp) and cp < 0.5,
            "dòng tiền kinh doanh hỗ trợ tốt cho lợi nhuận", "dòng tiền kinh doanh thấp so với lợi nhuận")
    return s, w


# ----------------------------------------------------------------------------- hàm chính
def analyze_fundamental(financial_df: pd.DataFrame, style: str = "Cân bằng",
                        ticker: str | None = None, chart_dir: str = "charts") -> dict:
    """
    Trả về dict:
        ticker, style, financial_score (None nếu thiếu dữ liệu), rating,
        group_scores, group_labels, weights, style_scores (điểm cho cả 3 phong cách),
        ratios_table (DataFrame các năm + kỳ TTM), latest (dict), charts (list đường dẫn PNG),
        comments (list đoạn văn), strengths, weaknesses, warnings, sources, method
    """
    if style not in GROUP_WEIGHTS:
        raise ValueError(f"Phong cách không hợp lệ: {style}. Chọn một trong {STYLES}")
    result = {"ticker": ticker, "style": style, "financial_score": None, "rating": "chưa đủ dữ liệu",
              "group_scores": {}, "group_labels": GROUP_LABELS, "weights": GROUP_WEIGHTS[style],
              "style_scores": {}, "ratios_table": pd.DataFrame(), "latest": {}, "charts": [],
              "comments": [], "strengths": [], "weaknesses": [], "warnings": [],
              "sources": {}, "method": METHOD_TEXT}

    if financial_df is None or len(financial_df) == 0:
        result["warnings"].append("Không có dữ liệu báo cáo tài chính cho mã này.")
        return result
    df = financial_df.copy()
    if "ticker" in df.columns:
        if ticker is None:
            ticker = str(df["ticker"].iloc[0])
        df = df[df["ticker"].astype(str).str.upper() == ticker.upper()]
        if df.empty:
            result["warnings"].append(f"Không có dữ liệu tài chính của mã {ticker}.")
            return result
    ticker = (ticker or "N/A").upper()
    result["ticker"] = ticker

    d = _prepare(df)
    annual = _annual_table(d)
    ttm = _ttm_table(d)

    # nguồn dữ liệu
    result["sources"] = {
        "nguồn": ", ".join(sorted(map(str, d["source"].dropna().unique()))) if "source" in d.columns else "không rõ",
        "thời điểm truy xuất": str(d["fetched_at"].dropna().max()) if "fetched_at" in d.columns and d["fetched_at"].notna().any() else "không rõ",
        "số kỳ năm": int(len(annual)), "số kỳ quý": int((d["period_type"] == "quarter").sum()),
    }

    rows = [_ratios(r, "year") for _, r in annual.iterrows()]
    annual_r = pd.DataFrame(rows)
    use_ttm = (not ttm.empty) and (annual.empty or (ttm["year"].iloc[-1] > annual["year"].max()))
    ttm_row = _ratios(ttm.iloc[-1], "ttm") if use_ttm else None
    if ttm_row is not None and pd.isna(ttm_row["revenue"]):
        ttm_row, use_ttm = None, False

    if annual_r.empty and ttm_row is None:
        result["warnings"].append("Không đủ dữ liệu (cần ít nhất báo cáo năm hoặc 4 quý liên tiếp) để phân tích tài chính.")
        return result

    latest = ttm_row if ttm_row is not None else annual_r.iloc[-1].to_dict()
    table = annual_r.copy()
    if ttm_row is not None:
        table = pd.concat([table, pd.DataFrame([ttm_row])], ignore_index=True)
    result["ratios_table"] = table
    result["latest"] = latest

    # kiểm tra nhất quán: tổng 4 quý so với số năm
    if not annual.empty and not ttm.empty:
        q = d[d["period_type"] == "quarter"]
        for _, a in annual.tail(3).iterrows():
            qq = q[q["year"] == a["year"]]
            if len(qq) == 4 and not pd.isna(a["revenue"]) and a["revenue"] > 0:
                diff = abs(qq["revenue"].sum() / a["revenue"] - 1)
                if diff > 0.05:
                    result["warnings"].append(
                        f"Tổng doanh thu 4 quý {int(a['year'])} lệch {diff * 100:.0f}% so với báo cáo năm; "
                        "số liệu quý có thể là số lũy kế hoặc thiếu dữ liệu, cần kiểm tra lại.")
                    break

    # cảnh báo thiếu dữ liệu
    miss = [k for k in ("roe", "net_margin", "revenue_growth", "profit_growth", "debt_to_assets", "cfo_to_profit")
            if pd.isna(latest.get(k))]
    names = {"roe": "ROE", "net_margin": "biên lợi nhuận ròng", "revenue_growth": "tăng trưởng doanh thu",
             "profit_growth": "tăng trưởng lợi nhuận", "debt_to_assets": "nợ/tổng tài sản", "cfo_to_profit": "dòng tiền/lợi nhuận"}
    if miss:
        result["warnings"].append("Không tính được: " + ", ".join(names[m] for m in miss) +
                                  ". Các chỉ tiêu này bị loại khỏi điểm số và trọng số được chia lại.")
    if not pd.isna(latest.get("net_profit")) and latest["net_profit"] <= 0:
        result["warnings"].append("Doanh nghiệp lỗ hoặc lợi nhuận bằng 0 trong kỳ gần nhất; tăng trưởng lợi nhuận và dòng tiền/lợi nhuận không có ý nghĩa so sánh.")

    is_fin = (not pd.isna(latest.get("debt_to_assets"))) and latest["debt_to_assets"] > FINANCIAL_FIRM_DA
    if is_fin:
        result["warnings"].append("Nợ/tổng tài sản rất cao, nhiều khả năng là ngân hàng hoặc tổ chức tài chính: "
                                  "bỏ qua nhóm đòn bẩy và dòng tiền khi chấm điểm, trọng số được chia lại cho ROE và tăng trưởng.")

    groups = _group_scores(latest, annual_r, is_fin)
    result["group_scores"] = groups
    for st in STYLES:
        sc, _cov = _combine(groups, st)
        result["style_scores"][st] = sc
    score, coverage = _combine(groups, style)
    result["financial_score"] = score
    result["rating"] = _label(score)
    if score is None:
        result["warnings"].append("Dữ liệu quá thiếu (nhóm có dữ liệu chiếm dưới 50% trọng số) nên chưa chấm Financial Score.")
    elif coverage < 1:
        result["warnings"].append(f"Financial Score tính trên nhóm có dữ liệu, chiếm {coverage * 100:.0f}% tổng trọng số.")

    s, w = _strengths_weaknesses(latest, is_fin)
    result["strengths"], result["weaknesses"] = s, w
    result["comments"] = _comments(ticker, latest, groups, style, score, s, w)
    if not annual_r.empty:
        result["charts"] = _make_charts(ticker, annual_r, chart_dir)
    return result


# ----------------------------------------------------------------------------- tiện ích nạp dữ liệu
def load_financials(ticker: str, path: str = "data/financial/financials_standardized.csv") -> pd.DataFrame:
    """Đọc bảng chuẩn hóa đã gộp và lọc theo mã."""
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df[df["ticker"].astype(str).str.upper() == ticker.upper()]


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "FPT"
    style = sys.argv[2] if len(sys.argv) > 2 else "Cân bằng"
    res = analyze_fundamental(load_financials(t), style=style, ticker=t)
    print(res["ratios_table"].to_string())
    print("Financial Score:", res["financial_score"], res["style_scores"])
    for line in res["comments"] + res["warnings"]:
        print("-", line)