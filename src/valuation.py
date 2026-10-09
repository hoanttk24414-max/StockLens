"""TV4 - MODULE PHAN TICH DINH GIA CO PHIEU (LINH).

No ticker is hard-coded. All monetary input values must be in VND (NOT thousand VND).
Market/financial/peer information must be fetched by upstream TV1/TV3 integrations.
This module deliberately DOES NOT invent data or download an undocumented API.

Public API: analyze_valuation(price, financial_df, peers_df)
Returns a JSON-serializable dict, including a transparent score and audit warnings.
"""
from __future__ import annotations

from typing import Any
import math
import pandas as pd

# Scoring rules: illustrative research rubric, NOT a forecast or trading advice.
MIN_PEERS = 3  # So doanh nghiep so sanh toi thieu cho moi chi so
SCORE_WEIGHTS = {"pe": 0.60, "pb": 0.40}  # PE 60%, PB 40%
SCORE_BANDS = ((0.75, 90), (0.90, 75), (1.10, 60), (1.30, 40))


def _num(value: Any) -> float | None:
    """Convert a real number safely; reject NaN, infinities and booleans."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def _day(value: Any) -> pd.Timestamp | None:
    """Parse a calendar date; return a tz-naive normalized Timestamp."""
    if value is None or pd.isna(value):
        return None
    try:
        day = pd.to_datetime(value, errors="coerce", utc=True)
        return None if pd.isna(day) else day.tz_convert(None).normalize()
    except (TypeError, ValueError, OverflowError):
        return None


def _table(value: Any, label: str) -> pd.DataFrame:
    """Accept TV3 inputs as DataFrame, list[dict], or a single dict."""
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, dict):
        return pd.DataFrame([value])
    if isinstance(value, list):
        return pd.DataFrame(value)
    raise TypeError(f"{label} must be a DataFrame, dict or list[dict]")


def _record_price(price: Any, warnings: list[str]) -> dict[str, Any] | None:
    """TV1 may provide one snapshot dict or a history DataFrame with close_vnd/date."""
    df = _table(price, "price")
    required = {"ticker", "date", "close_vnd"}
    if df.empty or not required.issubset(df.columns):
        warnings.append("TV1 price must contain ticker, date, close_vnd.")
        return None
    df["_day"] = df["date"].apply(_day)
    df["_close"] = df["close_vnd"].apply(_num)
    df = df[df["_day"].notna() & df["_close"].notna() & (df["_close"] > 0)]
    if df.empty:
        warnings.append("No valid positive closing price and date from TV1.")
        return None
    # Khong lay ma co phieu khac; khong chap nhan nhieu ma trong cung dau vao.
    tickers = df["ticker"].astype(str).str.upper().str.strip().unique()
    if len(tickers) != 1 or not tickers[0] or tickers[0] in ("NAN", "NONE"):
        warnings.append("TV1 must supply exactly one valid ticker.")
        return None
    df = df.sort_values("_day")
    row = df.iloc[-1].to_dict()
    row["ticker"] = str(row["ticker"]).strip().upper()
    row["date"] = row["_day"].date().isoformat()
    row["close_vnd"] = float(row["_close"])
    if not row["ticker"]:
        warnings.append("Ticker is empty.")
        return None
    return row


def _financial_record(financial_df: Any, ticker: str, as_of: pd.Timestamp,
                      warnings: list[str]) -> dict[str, Any] | None:
    """Use the newest report *already published* by valuation date.

    Required: ticker, report_date, available_date, eps_ttm_vnd,
    parent_common_equity_vnd, shares_outstanding.
    Optional: roe, revenue_growth, profit_growth, debt_to_equity, source.
    """
    df = _table(financial_df, "financial_df")
    required = {"ticker", "report_date", "available_date", "eps_ttm_vnd",
                "parent_common_equity_vnd", "shares_outstanding"}
    missing = required.difference(df.columns)
    if missing:
        warnings.append("TV3 is missing columns: " + ", ".join(sorted(missing)))
        return None
    df = df[df["ticker"].astype(str).str.upper().str.strip() == ticker].copy()
    if df.empty:
        warnings.append(f"TV3 has no financial reports for {ticker}.")
        return None
    df["_report"] = df["report_date"].apply(_day)
    df["_available"] = df["available_date"].apply(_day)
    df = df[df["_report"].notna() & df["_available"].notna()
            & (df["_report"] <= as_of) & (df["_available"] <= as_of)
            & (df["_report"] <= df["_available"])].copy()
    if df.empty:
        warnings.append("No financial report published by valuation date: future data excluded.")
        return None
    df = df.sort_values(["_report", "_available"])
    row = df.iloc[-1].to_dict()
    row["report_date"] = row["_report"].date().isoformat()
    row["available_date"] = row["_available"].date().isoformat()
    return row


def calculate_pe(close_vnd: Any, eps_ttm_vnd: Any) -> float | None:
    """P/E=price/EPS(TTM), meaningful in this conventional form only if EPS>0."""
    price, eps = _num(close_vnd), _num(eps_ttm_vnd)
    return price / eps if price is not None and price > 0 and eps is not None and eps > 0 else None


def calculate_pb(close_vnd: Any, equity_vnd: Any,
                 shares_outstanding: Any) -> tuple[float | None, float | None]:
    """BVPS=parent common equity / shares; P/B=price/BVPS when BVPS>0."""
    price, equity, shares = map(_num, (close_vnd, equity_vnd, shares_outstanding))
    if equity is None or shares is None or shares <= 0:
        return None, None
    bvps = equity / shares
    if price is None or price <= 0 or bvps <= 0:
        return bvps, None
    return bvps, price / bvps


def _peers(peers_df: Any, ticker: str, as_of: pd.Timestamp,
           warnings: list[str], industry: str | None) -> dict[str, Any]:
    """Only use grounded contemporaneous peers; NEVER create peers from ticker names.

    Required peer fields: ticker, industry, date, available_date, pe, pb.
    Source and reason are highly recommended. Independent comparisons per metric.
    """
    result = {"count_pe": 0, "count_pb": 0, "median_pe": None,
              "median_pb": None, "pe_rows": [], "pb_rows": []}
    if peers_df is None:
        warnings.append("No peer dataset: cannot score relative valuation.")
        return result
    df = _table(peers_df, "peers_df")
    required = {"ticker", "industry", "date", "available_date", "pe", "pb"}
    missing = required.difference(df.columns)
    if missing:
        warnings.append("Peer data missing: " + ", ".join(sorted(missing)))
        return result
    df = df.copy()
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df = df[df["ticker"] != ticker]
    df["_day"] = df["date"].apply(_day)
    df["_published"] = df["available_date"].apply(_day)
    df = df[(df["_day"].notna()) & (df["_published"].notna())
            & (df["_day"] <= as_of) & (df["_published"] <= as_of)]
    if industry:
        df = df[df["industry"].astype(str).str.casefold().str.strip() == industry.casefold().strip()]
    else:
        warnings.append("Target industry missing; cannot validate industry comparability.")
        return result
    if df.empty:
        warnings.append("No published peer multiples in the matching industry.")
        return result
    # 31 calendar days: a stated project policy, not a market convention.
    df = df[(as_of - df["_day"]).dt.days <= 31].copy()
    if df.empty:
        warnings.append("Peer valuations are older than 31 days; comparisons omitted.")
        return result
    df = df.sort_values(["_day", "_published"]).drop_duplicates("ticker", keep="last")
    for metric in ("pe", "pb"):
        metric_df = df.copy()
        metric_df[metric] = metric_df[metric].apply(_num)
        metric_df = metric_df[metric_df[metric].notna() & (metric_df[metric] > 0)]
        rows = [{"ticker": str(r["ticker"]), metric: float(r[metric]),
                 "date": r["_day"].date().isoformat(),
                 "source": str(r.get("source", "") or "")}
                for _, r in metric_df.iterrows()]
        result[f"count_{metric}"] = len(rows)
        result[f"{metric}_rows"] = rows
        if len(rows) >= MIN_PEERS:
            result[f"median_{metric}"] = float(metric_df[metric].median())
        else:
            warnings.append(f"Only {len(rows)} valid {metric.upper()} peers; need >= {MIN_PEERS}.")
    return result


def _grade(relative_multiple: float) -> int:
    """Higher score means less expensive relative to selected peer median."""
    for maximum, score in SCORE_BANDS:
        if relative_multiple <= maximum:
            return score
    return 20


def calculate_valuation_score(pe: float | None, pb: float | None,
                              median_pe: float | None,
                              median_pb: float | None) -> dict[str, Any]:
    """Reweight available components; disclose coverage. No neutral-point imputation."""
    sub = {}
    if _num(pe) is not None and pe > 0 and _num(median_pe) is not None and median_pe > 0:
        sub["pe"] = _grade(pe / median_pe)
    if _num(pb) is not None and pb > 0 and _num(median_pb) is not None and median_pb > 0:
        sub["pb"] = _grade(pb / median_pb)
    coverage = sum(SCORE_WEIGHTS[k] for k in sub)
    # Chinh sach an toan: chi co PB (40% trong so) thi KHONG xuat diem tong.
    # Chi co PE (60% trong so) co the xuat diem TAM THOI, kem canh bao.
    score = (round(sum(SCORE_WEIGHTS[k] * v for k, v in sub.items()) / coverage, 2)
             if coverage >= 0.60 - 1e-9 else None)
    return {"valuation_score": score, "score_coverage": round(coverage, 2),
            "pe_score": sub.get("pe"), "pb_score": sub.get("pb"),
            "is_partial_score": bool(coverage and coverage < 1)}


def _comment(pe: float | None, pb: float | None,
             comp: dict[str, Any], score: dict[str, Any],
             financial: dict[str, Any] | None) -> dict[str, str]:
    """Viet nhan xet tu dong bang tieng Viet, khong suy dien khuyen nghi mua/ban."""
    parts = []
    parts.append(f"P/E TTM: {pe:.2f} lan." if pe is not None
                 else "Khong tinh duoc P/E do EPS TTM am, bang 0 hoac thieu.")
    parts.append(f"P/B: {pb:.2f} lan." if pb is not None
                 else "Khong tinh duoc P/B do BVPS khong hop le hoac thieu du lieu.")
    for key, value in (("pe", pe), ("pb", pb)):
        med = comp[f"median_{key}"]
        if value is not None and med is not None and med > 0:
            gap = (value / med - 1) * 100
            relative = "cao hon" if gap > 0 else "thap hon" if gap < 0 else "bang"
            parts.append(f"{key.upper()} {relative} trung vi nhom {abs(gap):.1f}% "
                         f"(trung vi {med:.2f} lan).")
    if score["valuation_score"] is None:
        parts.append("Chua du du lieu tin cay de tinh Valuation Score tong hop.")
    else:
        qualifier = " (diem tam thoi do thieu mot thanh phan)" if score["is_partial_score"] else ""
        parts.append(f"Valuation Score: {score['valuation_score']:.1f}/100{qualifier}.")
    if financial:
        roe = _num(financial.get("roe"))
        growth = _num(financial.get("profit_growth"))
        if roe is not None:
            parts.append(f"ROE: {roe:.1%}. Can xem xet ROE khi danh gia P/B.")
        if growth is not None:
            parts.append(f"Tang truong loi nhuan: {growth:.1%}. Can doi chieu voi P/E.")
    base = " ".join(parts)
    return {
        "summary": base,
        "than_trong": base + " Phong cach than trong: kiem tra dong tien, no vay va bien an toan; gia re tuong doi khong dong nghia an toan.",
        "can_bang": base + " Phong cach can bang: ket hop them phan tich tai chinh, ky thuat va rui ro.",
        "tang_truong": base + " Phong cach tang truong: kiem tra tinh ben vung cua tang truong EPS truoc khi chap nhan boi so cao.",
    }


def analyze_valuation(price: Any, financial_df: Any, peers_df: Any) -> dict[str, Any]:
    """Analyze ANY selected ticker using the data supplied by TV1, TV3 and peers.

    price: TV1 dict or historical DataFrame (ticker, date, close_vnd).
    financial_df: TV3 DataFrame, values VND and known report publication date.
    peers_df: independent contemporaneous peer multiples, or None.

    Score is an *illustrative relative valuation rubric* (0..100), NOT buy/sell.
    Missing data returns None and warnings, never fabricated 0 or 100.
    """
    warnings: list[str] = []
    snapshot = _record_price(price, warnings)
    if snapshot is None:
        return {"status": "insufficient_data", "ticker": None, "valuation_score": None,
                "warnings": warnings}
    ticker = snapshot["ticker"]
    as_of = _day(snapshot["date"])
    assert as_of is not None
    f = _financial_record(financial_df, ticker, as_of, warnings)
    eps = _num(f.get("eps_ttm_vnd")) if f else None
    equity = _num(f.get("parent_common_equity_vnd")) if f else None
    shares = _num(f.get("shares_outstanding")) if f else None
    pe = calculate_pe(snapshot["close_vnd"], eps)
    bvps, pb = calculate_pb(snapshot["close_vnd"], equity, shares)
    if eps is None or eps <= 0:
        warnings.append("EPS TTM is nonpositive/missing: conventional P/E not meaningful.")
    if pb is None:
        warnings.append("Cannot calculate valid P/B: nonpositive/missing BVPS.")
    industry = str(f.get("industry", "")).strip() if f else ""
    peers = _peers(peers_df, ticker, as_of, warnings, industry or None)
    score = calculate_valuation_score(pe, pb, peers["median_pe"], peers["median_pb"])
    if score["is_partial_score"]:
        warnings.append("Valuation Score has incomplete component coverage; see score_coverage.")
    if score["valuation_score"] is None and score["pb_score"] is not None and score["pe_score"] is None:
        warnings.append("Only P/B available: component shown, no overall Valuation Score under project policy.")
    comments = _comment(pe, pb, peers, score, f)
    return {
        "status": ("partial" if score["valuation_score"] is not None and score["is_partial_score"]
                   else "ok" if score["valuation_score"] is not None else "insufficient_comparison"),
        "ticker": ticker, "as_of_date": snapshot["date"],
        "close_vnd": snapshot["close_vnd"], "eps_ttm_vnd": eps,
        "parent_common_equity_vnd": equity, "shares_outstanding": shares,
        "bvps_vnd": bvps, "pe": pe, "pb": pb,
        "industry": industry or None,
        "financial_report_date": f.get("report_date") if f else None,
        "financial_available_date": f.get("available_date") if f else None,
        "comparison": peers,
        **score,
        "method": {"peer_policy": "same industry, available by valuation date, <=31 calendar days old, >=3 unique peers per ratio",
                   "minimum_coverage_for_total_score": 0.60,
                   "score_pe_weight": SCORE_WEIGHTS["pe"],
                   "score_pb_weight": SCORE_WEIGHTS["pb"],
                   "score_bands": "<=0.75:90; <=0.90:75; <=1.10:60; <=1.30:40; >1.30:20",
                   "interpretation": "A relative multiple discount only; not intrinsic value or expected return."},
        "comments": comments,
        "sources": {"price": snapshot.get("source"),
                    "financial": f.get("source") if f else None,
                    "peers": "See comparison.pe_rows and comparison.pb_rows"},
        "warnings": warnings,
    }
