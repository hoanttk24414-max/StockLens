from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Callable
import math
import pandas as pd


class PeerDataError(ValueError):
    """Loi cau hinh hoac du lieu khong the xac minh."""


def _date(value):
    """Chuan hoa gia tri ngay ve Timestamp (khong co timezone)."""
    try:
        d = pd.to_datetime(value, errors="coerce", utc=True)
        return None if pd.isna(d) else d.tz_convert(None).normalize()
    except (ValueError, TypeError, OverflowError):
        return None


def _positive(x):
    """Chi chap nhan so duong huu han."""
    try:
        if isinstance(x, bool):
            return None
        x = float(x)
        return x if math.isfinite(x) and x > 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _number(x):
    try:
        if isinstance(x, bool):
            return None
        x = float(x)
        return x if math.isfinite(x) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _frame(value, name):
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, list):
        return pd.DataFrame(value)
    if isinstance(value, dict):
        return pd.DataFrame([value])
    raise PeerDataError(f"{name} phai la DataFrame, dict hoac list[dict]")


def load_universe(path: str | Path) -> pd.DataFrame:
    """Doc danh muc ma va nganh: du lieu THUC, do nhom cung cap/cap nhat."""
    path = Path(path)
    if not path.is_file():
        raise PeerDataError(f"Khong tim thay file danh muc nganh: {path}")
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str)


def _latest_market(market, ticker, as_of, max_age_days):
    """Chon gia gan nhat da giao dich, KHONG lay gia tuong lai."""
    df = _frame(market, f"market[{ticker}]")
    required = {"date", "close_vnd"}
    if df.empty or not required.issubset(df.columns):
        return None
    if "ticker" in df.columns:
        df = df[df["ticker"].astype(str).str.strip().str.upper() == ticker]
    df["_date"] = df["date"].map(_date)
    df["_price"] = df["close_vnd"].map(_positive)
    df = df[df["_date"].notna() & df["_price"].notna()].copy()
    df = df[(df["_date"] <= as_of) & (df["_date"] >= as_of - pd.Timedelta(days=max_age_days))]
    if df.empty:
        return None
    row = df.sort_values("_date").iloc[-1]
    return row["_date"], row["_price"], row.get("source")


def _latest_financial(financial, ticker, price_date):
    """Bao cao gan nhat da DUOC CONG BO vao ngay cua gia peer."""
    df = _frame(financial, f"financial[{ticker}]")
    columns = {"ticker", "report_date", "available_date", "eps_ttm_vnd",
               "parent_common_equity_vnd", "shares_outstanding"}
    if df.empty or not columns.issubset(df.columns):
        return None
    df = df[df["ticker"].astype(str).str.upper().str.strip() == ticker].copy()
    df["_report"] = df["report_date"].map(_date)
    df["_available"] = df["available_date"].map(_date)
    df = df[df["_report"].notna() & df["_available"].notna()].copy()
    df = df[(df["_report"] <= df["_available"]) & (df["_available"] <= price_date)]
    if df.empty:
        return None
    return df.sort_values(["_report", "_available"]).iloc[-1]


def get_peer_data(
    ticker: str,
    valuation_date: str,
    *,
    market_loader: Callable,
    financial_loader: Callable,
    universe: pd.DataFrame,
    max_price_age_days: int = 7,
    min_peers: int = 3,
    max_candidates: int = 100,
) -> pd.DataFrame:
    """Tao bang peers_df, tinh P/E va P/B tung peer tu du lieu TV1+TV3.

    Cho tat ca ma co trong universe va duoc TV1/TV3 ho tro.
    Chi so bi thieu/khong hop le duoc de None, KHONG dien gia tri gia.
    valuation.py se loc tiep du lieu <=31 ngay va can >=3 peers hop le/chi so.
    """
    if not callable(market_loader) or not callable(financial_loader):
        raise PeerDataError("Can cung cap hai ham lay du lieu that tu TV1/TV3")
    ticker = str(ticker).strip().upper()
    as_of = _date(valuation_date)
    if not ticker or as_of is None:
        raise PeerDataError("Ma co phieu hoac ngay dinh gia khong hop le")
    if max_price_age_days < 0 or max_price_age_days > 31:
        raise PeerDataError("max_price_age_days can trong khoang 0..31")
    universe = _frame(universe, "universe")
    if not {"ticker", "industry"}.issubset(universe.columns):
        raise PeerDataError("universe can 2 cot ticker, industry; co the them peer_group")
    u = universe.copy()
    u["ticker"] = u["ticker"].astype(str).str.strip().str.upper()
    u["industry"] = u["industry"].astype(str).str.strip()
    u = u[(u["ticker"] != "") & (u["industry"] != "")].drop_duplicates("ticker")
    selected = u[u["ticker"] == ticker]
    if selected.empty:
        raise PeerDataError(f"Ma {ticker} chua co trong danh muc nganh; can cap nhat universe")
    industry = selected.iloc[0]["industry"]
    if "peer_group" in u.columns:
        group = str(selected.iloc[0]["peer_group"]).strip()
        if group and group.lower() not in ("nan", "none"):
            candidates = u[(u["industry"] == industry) & (u["peer_group"].astype(str).str.strip() == group)]
        else:
            candidates = u[u["industry"] == industry]
    else:
        candidates = u[u["industry"] == industry]
    candidates = candidates[candidates["ticker"] != ticker].head(max_candidates)
    records = []
    for peer in candidates["ticker"]:
        try:
            market = market_loader(peer, (as_of - pd.Timedelta(days=max_price_age_days)).date().isoformat(), as_of.date().isoformat())
            price_record = _latest_market(market, peer, as_of, max_price_age_days)
            if price_record is None:
                continue
            price_date, close, market_source = price_record
            financial = financial_loader(peer)
            f = _latest_financial(financial, peer, price_date)
            if f is None:
                continue
            eps = _positive(f["eps_ttm_vnd"])
            equity = _number(f["parent_common_equity_vnd"])
            shares = _positive(f["shares_outstanding"])
            bvps = equity / shares if equity is not None and shares else None
            pe = close / eps if eps else None
            pb = close / bvps if bvps is not None and bvps > 0 else None
            if pe is None and pb is None:
                continue
            records.append({
                "ticker": peer,
                "industry": industry,
                "date": price_date.date().isoformat(),
                "available_date": price_date.date().isoformat(),
                "pe": pe,
                "pb": pb,
                "source": f"gia: {market_source or 'TV1'}; BCTC: {f.get('source') or 'TV3'}",
                "report_date": str(f["report_date"]),
                "financial_available_date": str(f["available_date"]),
            })
        except Exception:
            # 1 ma khong co du lieu khong duoc lam dung ca nhom.
            # Khong tra ve gia tri tu che de bu loi.
            continue
    cols = ["ticker", "industry", "date", "available_date", "pe", "pb",
            "source", "report_date", "financial_available_date"]
    return pd.DataFrame(records, columns=cols)


def build_peer_provider(market_loader: Callable, financial_loader: Callable,
                        universe: pd.DataFrame, **settings) -> Callable:
    """Tao get_peer_data(ticker, date) phu hop interface_to_tv1_tv3.py."""
    def provider(ticker, valuation_date):
        return get_peer_data(ticker, valuation_date, market_loader=market_loader,
                             financial_loader=financial_loader, universe=universe, **settings)
    return provider
