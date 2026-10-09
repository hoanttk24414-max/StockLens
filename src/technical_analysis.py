import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def analyze_technical(price_df):
    """
    Phân tích kỹ thuật cổ phiếu từ dữ liệu giá thị trường.

    Đầu vào:
        price_df gồm các cột:
        Date, Open, High, Low, Close, Volume

    Đầu ra:
        Dictionary chứa kết quả phân tích kỹ thuật.
    """

    # Tạo bản sao để không làm thay đổi dữ liệu gốc
    df = price_df.copy()

    # Các cột bắt buộc
    required_columns = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume"
    ]

    # Kiểm tra thiếu cột
    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        return {
            "data_available": False,
            "error": f"Thiếu các cột: {missing_columns}"
        }

    # Chuẩn hóa ngày
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Chuyển các cột số về numeric
    numeric_columns = ["Open", "High", "Low", "Close", "Volume"]

    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Xóa dòng không có ngày hoặc giá đóng cửa
    df = df.dropna(subset=["Date", "Close"])

    # Sắp xếp dữ liệu từ cũ đến mới
    df = df.sort_values("Date").reset_index(drop=True)

    # Kiểm tra số phiên
    if len(df) < 50:
        return {
            "data_available": False,
            "error": (
                f"Chỉ có {len(df)} phiên giao dịch. "
                "Cần tối thiểu 50 phiên để phân tích kỹ thuật."
            )
        }

    # =========================
    # 1. MA20 VÀ MA50
    # =========================

    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA50"] = df["Close"].rolling(window=50).mean()
    # =========================
    # 2. RSI (14 PHIÊN)
    # =========================

    delta = df["Close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()

    rs = avg_gain / avg_loss

    df["RSI"] = 100 - (100 / (1 + rs))

    # Trường hợp không có phiên giảm
    df.loc[
        (avg_loss == 0) & (avg_gain > 0),
        "RSI"
    ] = 100

    # Trường hợp giá không thay đổi
    df.loc[
        (avg_loss == 0) & (avg_gain == 0),
        "RSI"
    ] = 50
    # Lấy dữ liệu phiên gần nhất
        # Lấy dữ liệu phiên gần nhất
    latest = df.iloc[-1]

    result = {
        "data_available": True,
        "close": float(latest["Close"]),
        "ma20": float(latest["MA20"]),
        "ma50": float(latest["MA50"]),
        "rsi": float(latest["RSI"]),
        "data": df
    }

    return result


if __name__ == "__main__":
    print("StockLens - Technical Analysis module is ready.")