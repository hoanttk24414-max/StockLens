"""
scoring.py  --  TV6: Tổng hợp Investment Score

Đầu vào : điểm thành phần 0-100 từ các module (Fundamental, Valuation, Technical, News)
          + Risk Score do chính file này tính từ market_summary() của TV1.
Đầu ra  : dict kết quả, dùng thẳng được trong giao diện và report.py.

LƯU Ý: bộ trọng số và ngưỡng phân loại là GIẢ ĐỊNH THIẾT KẾ của nhóm,
không phải kết luận thực nghiệm. Phải nêu rõ điều này trong báo cáo.
"""
from __future__ import annotations

from typing import Optional

# --------------------------------------------------------------------------
# 1. Cấu hình (sửa ở đây nếu nhóm đổi ý)
# --------------------------------------------------------------------------
COMPONENTS = ["fundamental", "valuation", "technical", "news", "risk"]

COMPONENT_LABELS = {
    "fundamental": "Tài chính (Fundamental)",
    "valuation": "Định giá (Valuation)",
    "technical": "Kỹ thuật (Technical)",
    "news": "Tin tức (News)",
    "risk": "An toàn (Market Risk, điểm cao = an toàn hơn)",
}

# Tên ngắn dùng trong biểu đồ/bảng của PDF (khớp bố cục StockLens)
SHORT_LABELS = {"fundamental": "Fundamental", "valuation": "Valuation", "technical": "Technical",
                "news": "News", "risk": "Safety/Risk"}

# Mỗi bộ trọng số phải có tổng = 1.0 (được kiểm tra khi import file)
STYLE_WEIGHTS = {
    # Ưu tiên nền tảng doanh nghiệp, định giá hợp lý và ít biến động
    "Thận trọng": {"fundamental": 0.30, "valuation": 0.25, "technical": 0.10, "news": 0.10, "risk": 0.25},
    # Bộ trọng số ban đầu của nhóm
    "Cân bằng": {"fundamental": 0.25, "valuation": 0.25, "technical": 0.25, "news": 0.15, "risk": 0.10},
    # Ưu tiên tăng trưởng, động lực giá và tin tức; chấp nhận định giá cao hơn
    "Tăng trưởng": {"fundamental": 0.30, "valuation": 0.10, "technical": 0.30, "news": 0.20, "risk": 0.10},
}
DEFAULT_STYLE = "Cân bằng"
# Base Investment Score luôn dùng bộ trọng số chuẩn của nhóm: 25/25/25/15/10
BASE_WEIGHTS = {"fundamental": 0.25, "valuation": 0.25, "technical": 0.25, "news": 0.15, "risk": 0.10}

# (ngưỡng dưới, nhãn) -- xét từ cao xuống thấp
# Lưu ý: nhãn "Thận trọng" trùng tên với phong cách đầu tư "Thận trọng";
# nếu thấy dễ nhầm, đổi nhãn ở đây (ví dụ "Cần thận trọng").
RATING_BANDS = [
    (65, "Tích cực"),
    (50, "Trung lập"),
    (0, "Thận trọng"),
]

# Nếu các thành phần có điểm chiếm ít hơn tỷ lệ này -> không kết luận
MIN_COVERED_WEIGHT = 0.60
# Phải có ít nhất một trong hai thành phần nền tảng
CORE_COMPONENTS = ("fundamental", "valuation")

# Giả định cho Risk Score (tuyến tính giữa hai mốc)
VOL_BEST, VOL_WORST = 0.15, 0.60   # biến động năm: 15% -> 100 điểm, từ 60% trở lên -> 0 điểm
DD_BEST, DD_WORST = 0.00, -0.50    # sụt giảm tối đa: 0% -> 100 điểm, từ -50% trở xuống -> 0 điểm


def _check_weights() -> None:
    for style, w in STYLE_WEIGHTS.items():
        assert set(w) == set(COMPONENTS), f"{style}: thiếu/thừa thành phần"
        assert abs(sum(w.values()) - 1.0) < 1e-9, f"{style}: tổng trọng số != 1"


_check_weights()


# --------------------------------------------------------------------------
# 2. Risk Score từ dữ liệu thị trường (TV1)
# --------------------------------------------------------------------------
def _linear(value: float, best: float, worst: float) -> float:
    """Ánh xạ tuyến tính: best -> 100, worst -> 0, ngoài khoảng thì chặn."""
    t = (value - worst) / (best - worst)
    return max(0.0, min(1.0, t)) * 100


def compute_risk_score(market_summary: dict) -> Optional[dict]:
    """Risk Score 0-100 (cao = an toàn tương đối). Trả về None nếu thiếu dữ liệu."""
    vol = market_summary.get("volatility_annual")
    dd = market_summary.get("max_drawdown")
    if vol is None or dd is None:
        return None
    vol_score = _linear(vol, VOL_BEST, VOL_WORST)
    dd_score = _linear(dd, DD_BEST, DD_WORST)
    return {
        "score": round(0.5 * vol_score + 0.5 * dd_score, 1),
        "summary": (f"Độ biến động năm {vol:.1%}, mức sụt giảm tối đa {dd:.1%} "
                    f"trong giai đoạn {market_summary.get('from_date')} - {market_summary.get('to_date')}."),
        "details": {"volatility_annual": vol, "max_drawdown": dd,
                    "vol_score": round(vol_score, 1), "dd_score": round(dd_score, 1)},
    }


# --------------------------------------------------------------------------
# 3. Tổng hợp Investment Score
# --------------------------------------------------------------------------
def _extract(item) -> Optional[float]:
    """Nhận số, hoặc dict có khóa 'score' (hợp đồng đầu ra của các module). None = thiếu."""
    if item is None:
        return None
    value = item.get("score") if isinstance(item, dict) else item
    if value is None:
        return None
    value = float(value)
    if not 0 <= value <= 100:
        raise ValueError(f"Điểm phải nằm trong 0-100, nhận được {value}")
    return value


def classify(score: float) -> str:
    for threshold, label in RATING_BANDS:
        if score >= threshold:
            return label
    return RATING_BANDS[-1][1]


def compute_investment_score(components: dict, style: str = DEFAULT_STYLE, weights: Optional[dict] = None) -> dict:
    """
    components : {"fundamental": ..., "valuation": ..., "technical": ..., "news": ..., "risk": ...}
                 mỗi giá trị là số 0-100, dict có khóa 'score', hoặc None nếu module lỗi/thiếu dữ liệu.
    style      : "Thận trọng" | "Cân bằng" | "Tăng trưởng"
    """
    if weights is None:
        if style not in STYLE_WEIGHTS:
            raise ValueError(f"Phong cách không hợp lệ: {style}. Chọn một trong {list(STYLE_WEIGHTS)}")
        weights = STYLE_WEIGHTS[style]
    else:
        assert abs(sum(weights.values()) - 1.0) < 1e-9, "Tổng trọng số truyền vào phải bằng 1"
    scores = {name: _extract(components.get(name)) for name in COMPONENTS}

    warnings: list[str] = []
    available = [n for n in COMPONENTS if scores[n] is not None]
    missing = [n for n in COMPONENTS if scores[n] is None]
    covered = sum(weights[n] for n in available)

    for n in missing:
        warnings.append(f"Thiếu điểm {COMPONENT_LABELS[n]} (trọng số {weights[n]:.0%}); "
                        "không gán điểm 0 hay 100 thay thế.")

    base = {"style": style, "weights_original": dict(weights), "warnings": warnings}

    if covered < MIN_COVERED_WEIGHT or not any(c in available for c in CORE_COMPONENTS):
        warnings.append("Dữ liệu không đủ để kết luận: cần ít nhất một trong hai thành phần "
                        "Tài chính/Định giá và các thành phần có điểm phải chiếm từ "
                        f"{MIN_COVERED_WEIGHT:.0%} trọng số.")
        return {**base, "total": None, "rating": "Không đủ dữ liệu", "components": [],
                "weights_used": {}, "explanation": "Không thể tính Investment Score do thiếu dữ liệu."}

    # Chia lại trọng số cho các thành phần còn điểm (tổng vẫn = 1)
    weights_used = {n: weights[n] / covered for n in available}
    if missing:
        warnings.append("Trọng số của các thành phần còn lại đã được chia lại theo tỷ lệ để tổng = 100%.")

    rows, total = [], 0.0
    for n in COMPONENTS:
        w = weights_used.get(n, 0.0)
        contrib = (scores[n] or 0.0) * w
        total += contrib
        rows.append({"name": n, "label": COMPONENT_LABELS[n], "score": scores[n],
                     "weight": w, "contribution": round(contrib, 2), "available": scores[n] is not None})
    total = round(total, 1)
    rating = classify(total)

    best = max((r for r in rows if r["available"]), key=lambda r: r["score"])
    worst = min((r for r in rows if r["available"]), key=lambda r: r["score"])
    explanation = (
        f"Với bộ trọng số \"{style}\", Investment Score là {total}/100 ({rating}). "
        f"Thành phần điểm cao nhất: {best['label']} ({best['score']:.0f}); "
        f"thấp nhất: {worst['label']} ({worst['score']:.0f}). "
        "Đây là mô hình tổng hợp hỗ trợ phân tích, không phải khuyến nghị mua/bán."
    )
    return {**base, "total": total, "rating": rating, "components": rows,
            "weights_used": weights_used, "explanation": explanation}


# --------------------------------------------------------------------------
# 4. Base score + điểm theo từng phong cách (trang 6 và 7 của PDF)
# --------------------------------------------------------------------------
def compute_all_profiles(components: dict, selected_style: str = DEFAULT_STYLE) -> dict:
    """Base Score (25/25/25/15/10) + Profile-adjusted Score cho cả ba phong cách."""
    base = compute_investment_score(components, style="Cơ sở 25/25/25/15/10", weights=BASE_WEIGHTS)
    profiles = {s: compute_investment_score(components, s) for s in STYLE_WEIGHTS}
    return {"base": base, "profiles": profiles, "selected": selected_style,
            "selected_result": profiles[selected_style]}


def _level(weight: float) -> str:
    return "Cao" if weight >= 0.25 else "Trung bình" if weight >= 0.15 else "Thấp"


def profile_traits(style: str) -> list:
    """Mức độ ưu tiên suy ra từ TRỌNG SỐ của phong cách (không gõ tay)."""
    w = STYLE_WEIGHTS[style]
    return [("Ưu tiên an toàn (Market Risk)", _level(w["risk"]), w["risk"]),
            ("Tập trung nền tảng doanh nghiệp", _level(w["fundamental"]), w["fundamental"]),
            ("Tập trung định giá", _level(w["valuation"]), w["valuation"]),
            ("Tập trung tín hiệu kỹ thuật", _level(w["technical"]), w["technical"]),
            ("Tập trung tin tức", _level(w["news"]), w["news"])]


STRONG, WEAK = 70, 60   # ngưỡng để coi một thành phần là điểm mạnh / điểm yếu


def explain_score(results: dict, inv: dict) -> tuple:
    """Why This Score?: trả về (yếu tố làm tăng điểm, yếu tố làm giảm điểm) lấy từ kết quả module."""
    ups, downs = [], []
    rows = [r for r in inv.get("components", []) if r["available"]]
    for r in sorted(rows, key=lambda r: -r["score"]):
        txt = f"{SHORT_LABELS[r['name']]}: {r['score']:.0f}/100, đóng góp {r['contribution']:.1f} điểm."
        if r["score"] >= STRONG:
            ups.append(txt)
        elif r["score"] < WEAK:
            downs.append(txt)
    for key in ["fundamental", "valuation", "technical", "news"]:
        res = results.get(key) or {}
        ups += [f"[{SHORT_LABELS[key]}] {x}" for x in (res.get("positives") or [])[:2]]
        downs += [f"[{SHORT_LABELS[key]}] {x}" for x in (res.get("risks") or [])[:2]]
    return ups, downs


def final_view(ticker: str, results: dict, base: dict, selected: dict) -> str:
    """Kết luận tự động (khoảng 100-150 từ), chỉ dùng số lấy từ biến, không khẳng định mua/bán."""
    if selected.get("total") is None:
        return (f"Dựa trên dữ liệu hiện tại, chưa đủ thông tin để tổng hợp Investment Score cho {ticker}. "
                "Cần bổ sung dữ liệu tài chính hoặc định giá trước khi đưa ra đánh giá. "
                "Kết quả không phải khuyến nghị mua, bán hay nắm giữ.")
    names = {"technical": "kỹ thuật", "fundamental": "tài chính", "valuation": "định giá", "news": "tin tức"}
    parts = []
    for key in ["technical", "fundamental", "valuation", "news"]:
        res = results.get(key)
        if res and res.get("score") is not None:
            lab = f" ({res['label']})" if res.get("label") else ""
            parts.append(f"{names[key]} {res['score']:.0f}/100{lab}")
    s = (f"Dựa trên dữ liệu hiện tại, {ticker} có Investment Score cơ sở {base['total']}/100 ({base['rating']}) "
         f"và {selected['total']}/100 ({selected['rating']}) theo phong cách {selected['style']}. ")
    if parts:
        s += "Các thành phần gồm: " + "; ".join(parts) + ". "
    risk = results.get("risk")
    if risk and risk.get("score") is not None:
        s += f"Market Risk Score đạt {risk['score']:.0f}/100, phản ánh biến động giá và mức sụt giảm đã quan sát. "
    rows = [r for r in selected["components"] if r["available"]]
    if len(rows) >= 2:
        hi, lo = max(rows, key=lambda r: r["score"]), min(rows, key=lambda r: r["score"])
        s += (f"Thành phần mạnh nhất là {SHORT_LABELS[hi['name']]} ({hi['score']:.0f}), "
              f"yếu nhất là {SHORT_LABELS[lo['name']]} ({lo['score']:.0f}). ")
    s += ("Đây là kết quả tổng hợp từ dữ liệu và phương pháp do nhóm xây dựng, không phải khuyến nghị "
          "mua, bán hay nắm giữ; nhà đầu tư cần tự thẩm định.")
    return s


# --------------------------------------------------------------------------
# Chạy thử: python src/scoring.py
# --------------------------------------------------------------------------
if __name__ == "__main__":
    demo = {"fundamental": 85, "valuation": 72, "technical": 78, "news": 80, "risk": 70}
    for st in STYLE_WEIGHTS:
        r = compute_investment_score(demo, st)
        print(f"{st:12s} -> {r['total']:5.1f}  {r['rating']}")
