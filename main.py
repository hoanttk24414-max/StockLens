"""
main.py  --  TV6: Tích hợp hệ thống + giao diện Streamlit

Chạy:   streamlit run main.py        (hoặc bấm run.bat)

Nguyên tắc tích hợp
  * Không viết lại phép tính của TV1-TV5. Chỉ GỌI hàm của họ và gom kết quả.
  * Mỗi module chạy trong try/except riêng: một module lỗi KHÔNG làm sập cả hệ thống.
    Module lỗi -> điểm = None -> scoring.py chia lại trọng số và cảnh báo (không gán điểm giả).
  * Tên tham số của mỗi bạn có thể hơi khác nhau, nên _call() tự khớp tham số theo TÊN.
    Nếu tên hàm khác hẳn, thêm tên vào FUNC_CANDIDATES bên dưới.

"Hợp đồng" đầu ra mà mỗi module nên trả về (dict):
    {"score": 0-100 hoặc None, "summary": "nhận xét ngắn", "metrics": {tên: giá trị},
     "tables": [DataFrame, ...], "charts": ["charts/xxx.png" hoặc figure Plotly, ...],
     "sources": ["Nguồn, ngày lấy"], "warnings": ["..."], "data": DataFrame (tùy chọn)}
"""
from __future__ import annotations

import importlib
import inspect
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Mô-đun nằm trong src/. Sửa PACKAGE nếu nhóm đặt chỗ khác.
PACKAGE = "src"

# Tên hàm có thể gặp trong từng module (thử theo thứ tự)
FUNC_CANDIDATES = {
    "technical": ["analyze_technical", "technical_analysis", "run"],
    "fundamental": ["analyze_fundamental", "fundamental_analysis", "run"],
    "valuation": ["analyze_valuation", "valuation_analysis", "run"],
    "news": ["analyze_news", "news_analysis", "run"],
}
FINANCIAL_LOADERS = ["get_financial_data", "load_financial_data", "fetch_financial_data", "load_financials"]
OPTIONAL_NONE = {"peers_df"}            # tham số được phép truyền None

SECTION_LABELS = {
    "market_technical": "Trang 2: Market & Technical",
    "fundamental": "Trang 3: Fundamental & Financial",
    "valuation": "Trang 4: Valuation",
    "news": "Trang 5: News & Sentiment",
    "score": "Trang 6: Investment Score, Market Risk, Why This Score",
    "personalized": "Trang 7: Personalized View & Final View",
}
# Trang 1 (Cover + Executive Summary) và trang 8 (Methodology + Sources + Disclaimer) luôn có trong PDF.
MODULE_LABELS = {"market": "Market", "technical": "Technical", "fundamental": "Fundamental",
                 "valuation": "Valuation", "news": "News", "risk": "Market Risk"}


# --------------------------------------------------------------------------
# Tiện ích gọi module của người khác
# --------------------------------------------------------------------------
def _import(name: str):
    try:
        return importlib.import_module(f"{PACKAGE}.{name}")
    except ModuleNotFoundError as exc:
        # Một số thành viên đang đặt module ở gốc dự án, số khác trong src/.
        if exc.name not in (f"{PACKAGE}.{name}", PACKAGE):
            raise
        return importlib.import_module(name)


def _find_func(module, candidates):
    for name in candidates:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"Không tìm thấy hàm nào trong {candidates} ở module {module.__name__}")


def _call(func, pool: dict):
    """Gọi func, tự khớp tham số theo tên từ pool. Thiếu tham số bắt buộc thì báo lỗi dễ hiểu."""
    kwargs = {}
    for name, p in inspect.signature(func).parameters.items():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        if name in pool and (pool[name] is not None or name in OPTIONAL_NONE):
            kwargs[name] = pool[name]
        elif p.default is inspect.Parameter.empty:
            raise TypeError(f"{func.__name__}() cần tham số '{name}' nhưng hệ thống chưa có dữ liệu này. "
                            "Hãy thống nhất với người phụ trách module về đầu vào.")
    return func(**kwargs)


def _normalize(out, key=None):
    """Đưa mọi kiểu trả về về dạng dict theo hợp đồng."""
    if out is None:
        return None
    if isinstance(out, (int, float)):
        return {"score": float(out)}
    if isinstance(out, dict):
        res = dict(out)
        if key == "fundamental":
            res.setdefault("score", res.get("financial_score"))
            latest = res.get("latest") or {}
            res.setdefault("metrics", {k: latest.get(src) for k, src in {
                "Revenue": "revenue", "Net Profit": "net_profit", "Revenue Growth": "revenue_growth",
                "Profit Growth": "profit_growth", "ROE": "roe", "ROA": "roa",
                "Net Margin": "net_margin", "Debt Ratio": "debt_to_assets",
                "Cash Flow / Net Profit": "cfo_to_profit",
            }.items() if latest.get(src) is not None})
            res.setdefault("tables", [res["ratios_table"]] if res.get("ratios_table") is not None else [])
            res.setdefault("positives", res.get("strengths", []))
            res.setdefault("risks", res.get("weaknesses", []))
            res.setdefault("summary", " ".join(map(str, res.get("comments") or [])))
            res.setdefault("data", None)
        elif key == "technical":
            res.setdefault("summary", res.get("technical_view") or res.get("commentary"))
        res.setdefault("metrics", {})
        res.setdefault("tables", [])
        res.setdefault("charts", [])
        res.setdefault("positives", [])
        res.setdefault("risks", [])
        res.setdefault("sources", [])
        res.setdefault("warnings", [])
        res.setdefault("score", None)
        return res
    raise TypeError(f"Kiểu trả về không hỗ trợ: {type(out).__name__} (cần số hoặc dict)")


# --------------------------------------------------------------------------
# Dữ liệu giả lập (CHỈ để thử hệ thống; đánh dấu rõ trong PDF)
# --------------------------------------------------------------------------
def _mock(name: str) -> dict:
    scores = {"technical": 72, "fundamental": 81, "valuation": 66, "news": 74}
    return {"score": scores[name], "label": "Neutral", "positives": ["[GIẢ LẬP] Yếu tố tích cực mẫu"],
            "risks": ["[GIẢ LẬP] Rủi ro mẫu"],
            "summary": f"[GIẢ LẬP] Nhận xét mẫu cho phần {MODULE_LABELS[name]}.",
            "metrics": {"Chỉ tiêu mẫu A": 1.23, "Chỉ tiêu mẫu B": 45.6}, "tables": [], "charts": [],
            "sources": ["Dữ liệu giả lập"], "warnings": ["Dữ liệu giả lập, không dùng để đánh giá đầu tư."]}


# --------------------------------------------------------------------------
# Luồng xử lý chính (không phụ thuộc Streamlit nên test được)
# --------------------------------------------------------------------------
def run_pipeline(ticker: str, start_date: str, end_date: str, style: str, demo: bool = False) -> dict:
    ticker = ticker.strip().upper()
    scoring = _import("scoring")
    results: dict = {}
    errors: dict = {}

    # 1. Dữ liệu thị trường (TV1) -- các bước sau đều cần nó
    price_df, summary = None, None
    try:
        md = _import("market_data")
        price_df = md.get_market_data(ticker, start_date, end_date)
        summary = md.market_summary(price_df)
        results["market"] = {"score": None, "metrics": _market_metrics(summary),
                             "summary": _market_text(summary), "tables": [price_df.tail(10)],
                             "charts": [], "sources": [f"Giá lịch sử qua vnstock, nguồn: {summary['source']}, "
                                                       f"lấy lúc {price_df.attrs.get('fetched_at')}"],
                             "warnings": summary.get("warnings", []), "raw": summary}
    except Exception as exc:  # noqa: BLE001
        errors["market"] = f"{type(exc).__name__}: {exc}"

    # 2. Risk Score (TV6 tự tính từ dữ liệu của TV1)
    risk = scoring.compute_risk_score(summary) if summary else None
    if risk:
        results["risk"] = risk

    # 3. Các module phân tích. Dữ liệu dùng chung nằm trong pool.
    last_close = None
    if price_df is not None and not price_df.empty:
        close_column = "close" if "close" in price_df.columns else "Close" if "Close" in price_df.columns else None
        if close_column:
            last_close = float(price_df[close_column].iloc[-1])
    pool = {"ticker": ticker, "symbol": ticker, "start_date": start_date, "end_date": end_date,
            "start": start_date, "end": end_date, "price_df": price_df, "df": price_df,
            "prices": price_df, "price": last_close, "style": style,
            "financial_df": None, "peers_df": None}

    for key in ["technical", "fundamental", "valuation", "news"]:
        if key == "technical" and price_df is None:
            errors[key] = "Không có dữ liệu giá từ TV1 nên không phân tích kỹ thuật được."
            continue
        try:
            module = _import({"technical": "technical_analysis", "fundamental": "fundamental_analysis",
                              "valuation": "valuation", "news": "news_analysis"}[key])
            if key == "fundamental" and pool["financial_df"] is None:
                for loader in FINANCIAL_LOADERS:       # nếu TV3 có hàm tải BCTC thì dùng
                    if hasattr(module, loader):
                        pool["financial_df"] = _call(getattr(module, loader), pool)
                        break
            result = _normalize(_call(_find_func(module, FUNC_CANDIDATES[key]), pool), key)
            results[key] = result
            if key == "fundamental" and result and result.get("data") is not None:
                pool["financial_df"] = result["data"]      # để TV4 dùng cho P/E, P/B
        except Exception as exc:  # noqa: BLE001
            errors[key] = f"{type(exc).__name__}: {exc}"
            if demo:
                results[key] = _mock(key)

    components = {k: results.get(k) for k in ["fundamental", "valuation", "technical", "news", "risk"]}
    investment_all = scoring.compute_all_profiles(components, style)
    company = ((results.get("fundamental") or {}).get("company_name") or (results.get("valuation") or {}).get("company_name")
               or ticker)
    meta = {"company": company, "period": f"{start_date} – {end_date}",
            "updated": (price_df.attrs.get("fetched_at", "") if price_df is not None else "").replace("T", " ") or "—"}
    return {"ticker": ticker, "style": style, "results": results, "errors": errors,
            "investment": investment_all["selected_result"], "investment_all": investment_all,
            "price_df": price_df, "meta": meta, "demo": demo and bool(errors)}


def _pct(x):
    return "—" if x is None else f"{x:.1%}"


def _market_metrics(s: dict) -> dict:
    return {"Giá đóng cửa gần nhất (" + s["price_unit"] + ")": s["last_close"],
            "Lợi suất 1 tháng": _pct(s["return_1m"]), "Lợi suất 3 tháng": _pct(s["return_3m"]),
            "Lợi suất 6 tháng": _pct(s["return_6m"]), "Lợi suất 1 năm": _pct(s["return_1y"]),
            "Độ biến động năm": _pct(s["volatility_annual"]), "Sụt giảm tối đa": _pct(s["max_drawdown"]),
            "Cao nhất 52 tuần": s["high_52w"], "Thấp nhất 52 tuần": s["low_52w"],
            "Khối lượng TB 20 phiên": s["avg_volume_20d"]}


def _market_text(s: dict) -> str:
    return (f"{s['ticker']} có {s['n_sessions']} phiên giao dịch từ {s['from_date']} đến {s['to_date']}. "
            f"Giá đóng cửa gần nhất {s['last_close']:,.2f} ({s['price_unit']}), "
            f"lợi suất 1 năm {_pct(s['return_1y'])}, độ biến động năm {_pct(s['volatility_annual'])}.")


# --------------------------------------------------------------------------
# Giao diện Streamlit
# --------------------------------------------------------------------------
def render():
    import streamlit as st
    import report as report_mod
    import scoring

    st.set_page_config(page_title="Phân tích cơ hội đầu tư cổ phiếu", page_icon="📈", layout="wide")
    st.title("📈 Hệ thống phân tích cơ hội đầu tư cổ phiếu")
    st.caption("Công cụ hỗ trợ phân tích, không phải khuyến nghị mua/bán.")

    with st.sidebar:
        st.header("Thiết lập")
        ticker = st.text_input("Mã cổ phiếu", "FPT").strip().upper()
        end_d = st.date_input("Đến ngày", date.today())
        start_d = st.date_input("Từ ngày", date.today() - timedelta(days=365 * 2))
        style = st.selectbox("Phong cách đầu tư", list(scoring.STYLE_WEIGHTS), index=1)
        with st.expander("Trọng số của phong cách này"):
            for k, v in scoring.STYLE_WEIGHTS[style].items():
                st.write(f"{scoring.COMPONENT_LABELS[k]}: {v:.0%}")
        sections = st.multiselect("Nội dung đưa vào PDF", list(SECTION_LABELS),
                                  default=list(SECTION_LABELS), format_func=SECTION_LABELS.get)
        demo = st.checkbox("Chế độ thử (dùng dữ liệu giả cho module chưa xong)", value=False)
        run = st.button("Phân tích", type="primary", use_container_width=True)

    if run:
        with st.spinner("Đang thu thập dữ liệu và phân tích..."):
            st.session_state["out"] = run_pipeline(ticker, str(start_d), str(end_d), style, demo)

    out = st.session_state.get("out")
    if not out:
        st.info("Nhập mã cổ phiếu ở thanh bên trái rồi bấm **Phân tích**.")
        return

    inv = out["investment"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Investment Score", "—" if inv["total"] is None else f"{inv['total']}/100")
    c2.metric("Xếp loại", inv["rating"])
    c3.metric("Phong cách", out["style"])
    if out["demo"]:
        st.warning("Có dữ liệu GIẢ LẬP trong kết quả này. Không dùng để nộp bài hoặc đánh giá thật.")
    st.write(inv["explanation"])
    for w in inv["warnings"]:
        st.warning(w)
    for k, msg in out["errors"].items():
        st.error(f"Module **{k}** lỗi: {msg}")

    if inv["components"]:
        import pandas as pd
        st.dataframe(pd.DataFrame([{"Thành phần": r["label"], "Điểm": r["score"],
                                    "Trọng số áp dụng": f"{r['weight']:.0%}", "Đóng góp": r["contribution"]}
                                   for r in inv["components"]]), hide_index=True, use_container_width=True)

    allr = out["investment_all"]
    st.subheader("Điểm theo phong cách đầu tư")
    st.table({"Base (25/25/25/15/10)": [allr["base"]["total"]],
              **{s: [r["total"]] for s, r in allr["profiles"].items()}})

    for key, res in out["results"].items():
        if not res:
            continue
        with st.expander(MODULE_LABELS.get(key, key), expanded=False):
            if res.get("summary"):
                st.write(res["summary"])
            if res.get("metrics"):
                st.table({k: [v] for k, v in res["metrics"].items()})
            for tbl in (res.get("tables") or []):
                st.dataframe(tbl)
            charts = res.get("charts") or []
            charts = charts.values() if isinstance(charts, dict) else charts
            for ch in charts:
                if isinstance(ch, (str, Path)):
                    if Path(ch).exists():
                        st.image(str(ch))
                else:
                    st.plotly_chart(ch, use_container_width=True)

    st.divider()
    if st.button("Tạo báo cáo PDF"):
        try:
            path = report_mod.generate_report(out["ticker"], out["style"], out["results"], out["investment_all"],
                                              sections=sections, errors=out["errors"], demo=out["demo"],
                                              meta=out["meta"])
            with open(path, "rb") as f:
                st.download_button("⬇ Tải báo cáo PDF", f.read(), file_name=Path(path).name,
                                  mime="application/pdf")
            st.success(f"Đã tạo {Path(path).name}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Không tạo được PDF: {exc}")
            st.code(traceback.format_exc())


if __name__ == "__main__":
    render()
