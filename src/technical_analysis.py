import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def analyze_technical(price_df, chart_dir="charts"):
    """
    Phân tích kỹ thuật cổ phiếu từ dữ liệu TV1.

    Input:
        DataFrame gồm Date, Open, High, Low, Close, Volume.

    Output:
        Dictionary chứa chỉ báo, tín hiệu, điểm số,
        nhận xét và đường dẫn biểu đồ PNG.
    """

    def unavailable(message):
        return {
            "data_available": False,
            "technical_score": None,
            "label": "Unavailable",
            "positives": [],
            "risks": [],
            "technical_view": message,
            "charts": {},
            "error": message
        }

    # ==================================================
    # 1. KIỂM TRA VÀ CHUẨN HÓA DỮ LIỆU
    # ==================================================

    if not isinstance(price_df, pd.DataFrame):
        return unavailable("Dữ liệu đầu vào không phải DataFrame.")

    required = [
        "Date", "Open", "High", "Low", "Close", "Volume"
    ]

    missing = [c for c in required if c not in price_df.columns]

    if missing:
        return unavailable(f"Thiếu các cột: {missing}")

    df = price_df.copy()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=required)

    df = df[
        (df["Open"] > 0)
        & (df["High"] > 0)
        & (df["Low"] > 0)
        & (df["Close"] > 0)
        & (df["Volume"] >= 0)
        & (df["High"] >= df["Low"])
        & (df["High"] >= df["Open"])
        & (df["High"] >= df["Close"])
        & (df["Low"] <= df["Open"])
        & (df["Low"] <= df["Close"])
    ]

    df = (
        df.sort_values("Date")
        .drop_duplicates(subset=["Date"], keep="last")
        .reset_index(drop=True)
    )

    if len(df) < 50:
        return unavailable(
            f"Chỉ có {len(df)} phiên hợp lệ. "
            "Cần ít nhất 50 phiên giao dịch."
        )

    # ==================================================
    # 2. MOVING AVERAGES
    # ==================================================

    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA50"] = df["Close"].rolling(50).mean()

    # ==================================================
    # 3. RSI (14)
    # ==================================================

    delta = df["Close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss

    df["RSI"] = 100 - (100 / (1 + rs))

    df.loc[
        (avg_loss == 0) & (avg_gain > 0), "RSI"
    ] = 100

    df.loc[
        (avg_loss == 0) & (avg_gain == 0), "RSI"
    ] = 50

    # ==================================================
    # 4. MACD (12, 26, 9)
    # ==================================================

    df["EMA12"] = df["Close"].ewm(
        span=12, adjust=False
    ).mean()

    df["EMA26"] = df["Close"].ewm(
        span=26, adjust=False
    ).mean()

    df["MACD"] = df["EMA12"] - df["EMA26"]

    df["MACD_Signal"] = df["MACD"].ewm(
        span=9, adjust=False
    ).mean()

    df["MACD_Histogram"] = (
        df["MACD"] - df["MACD_Signal"]
    )

    # ==================================================
    # 5. VOLUME
    # ==================================================

    df["AvgVolume20"] = df["Volume"].rolling(20).mean()

    df["VolumeRatio"] = (
        df["Volume"] /
        df["AvgVolume20"].replace(0, np.nan)
    )

    # ==================================================
    # 6. VOLATILITY
    # ==================================================

    df["DailyReturn"] = df["Close"].pct_change()

    df["Volatility20"] = (
        df["DailyReturn"].rolling(20).std()
        * np.sqrt(252)
    )

    # ==================================================
    # 7. GIÁ TRỊ PHIÊN GẦN NHẤT
    # ==================================================

    latest = df.iloc[-1]

    close = float(latest["Close"])
    ma20 = float(latest["MA20"])
    ma50 = float(latest["MA50"])
    rsi = float(latest["RSI"])

    macd = float(latest["MACD"])
    macd_signal = float(latest["MACD_Signal"])
    macd_histogram = float(latest["MACD_Histogram"])

    volume = float(latest["Volume"])
    avg_volume_20 = float(latest["AvgVolume20"])

    volume_ratio = float(latest["VolumeRatio"])
    volatility = float(latest["Volatility20"])

    if not np.isfinite(volume_ratio):
        volume_ratio = None

    if not np.isfinite(volatility):
        return unavailable("Không đủ dữ liệu tính biến động giá.")

    # ==================================================
    # 8. PHÂN TÍCH TÍN HIỆU
    # ==================================================

    signals = {}
    positives = []
    risks = []

    # -------- MA --------

    if close > ma20 > ma50:
        ma_signal = "Positive"
        ma_score = 100

        positives.append(
            "Giá nằm trên MA20 và MA20 nằm trên MA50, "
            "cho thấy xu hướng tăng."
        )

    elif close < ma20 < ma50:
        ma_signal = "Negative"
        ma_score = 0

        risks.append(
            "Giá nằm dưới MA20 và MA20 nằm dưới MA50, "
            "cho thấy xu hướng giảm."
        )

    else:
        ma_signal = "Neutral"
        ma_score = 50

    signals["MA"] = {
        "signal": ma_signal,
        "score": ma_score
    }

    # -------- RSI --------

    if rsi > 70:
        rsi_signal = "Negative"
        rsi_score = 25

        risks.append(
            f"RSI = {rsi:.2f}, cổ phiếu đang ở vùng quá mua."
        )

    elif rsi < 30:
        rsi_signal = "Neutral"
        rsi_score = 50

        risks.append(
            f"RSI = {rsi:.2f}, cổ phiếu đang ở vùng quá bán."
        )

    else:
        rsi_signal = "Positive"
        rsi_score = 100

        positives.append(
            f"RSI = {rsi:.2f}, chưa vào vùng quá mua/quá bán."
        )

    signals["RSI"] = {
        "signal": rsi_signal,
        "score": rsi_score
    }

    # -------- MACD --------

    if macd > macd_signal:
        macd_label = "Positive"
        macd_score = 100

        positives.append(
            "MACD nằm trên Signal Line, động lượng tích cực."
        )

    elif macd < macd_signal:
        macd_label = "Negative"
        macd_score = 0

        risks.append(
            "MACD nằm dưới Signal Line, động lượng suy yếu."
        )

    else:
        macd_label = "Neutral"
        macd_score = 50

    signals["MACD"] = {
        "signal": macd_label,
        "score": macd_score
    }

    # -------- VOLUME --------

    # Khối lượng cao chỉ tích cực nếu giá phiên cuối tăng.
    price_change = close - float(df.iloc[-2]["Close"])

    if volume_ratio is None:
        volume_label = "Neutral"
        volume_score = 50

    elif volume_ratio >= 1.2 and price_change > 0:
        volume_label = "Positive"
        volume_score = 100

        positives.append(
            "Khối lượng tăng trên 20% so với trung bình "
            "20 phiên và giá tăng."
        )

    elif volume_ratio >= 1.2 and price_change < 0:
        volume_label = "Negative"
        volume_score = 25

        risks.append(
            "Khối lượng giao dịch cao trong phiên giảm giá."
        )

    elif volume_ratio < 0.8:
        volume_label = "Neutral"
        volume_score = 50

        risks.append(
            "Khối lượng giao dịch thấp hơn trung bình 20 phiên."
        )

    else:
        volume_label = "Neutral"
        volume_score = 50

    signals["Volume"] = {
        "signal": volume_label,
        "score": volume_score
    }

    # -------- VOLATILITY --------

    if volatility < 0.20:
        volatility_label = "Positive"
        volatility_score = 100

    elif volatility <= 0.40:
        volatility_label = "Neutral"
        volatility_score = 50

    else:
        volatility_label = "Negative"
        volatility_score = 0

        risks.append(
            f"Biến động giá thường niên hóa đạt "
            f"{volatility * 100:.2f}%, tương đối cao."
        )

    signals["Volatility"] = {
        "signal": volatility_label,
        "score": volatility_score
    }

    # ==================================================
    # 9. TECHNICAL SCORE
    # ==================================================

    technical_score = (
        ma_score * 0.30
        + rsi_score * 0.20
        + macd_score * 0.25
        + volume_score * 0.10
        + volatility_score * 0.15
    )

    technical_score = round(technical_score, 2)

    if technical_score >= 70:
        label = "Positive"
    elif technical_score >= 40:
        label = "Neutral"
    else:
        label = "Negative"

    # ==================================================
    # 10. NHẬN XÉT TỰ ĐỘNG
    # ==================================================

    technical_view = (
        f"Technical Score đạt {technical_score}/100, "
        f"xếp loại {label}. "
        f"Giá đóng cửa đạt {close:,.2f}, "
        f"MA20 = {ma20:,.2f}, MA50 = {ma50:,.2f}. "
        f"RSI đạt {rsi:.2f}. "
        f"MACD = {macd:.4f}, "
        f"Signal = {macd_signal:.4f}. "
        f"Biến động giá thường niên hóa trong "
        f"20 phiên đạt {volatility * 100:.2f}%."
    )

    if positives:
        technical_view += (
            " Điểm tích cực: " + "; ".join(positives) + "."
        )

    if risks:
        technical_view += (
            " Rủi ro cần lưu ý: " + "; ".join(risks) + "."
        )

    # ==================================================
    # 11. XUẤT BIỂU ĐỒ PNG
    # ==================================================

    os.makedirs(chart_dir, exist_ok=True)

    chart_paths = {
        "price_ma": os.path.join(
            chart_dir, "technical_price_ma.png"
        ),
        "rsi": os.path.join(
            chart_dir, "technical_rsi.png"
        ),
        "macd": os.path.join(
            chart_dir, "technical_macd.png"
        )
    }

    # -------- BIỂU ĐỒ GIÁ + MA --------

    fig, ax = plt.subplots(figsize=(10, 4))

    ax.plot(df["Date"], df["Close"], label="Close")
    ax.plot(df["Date"], df["MA20"], label="MA20")
    ax.plot(df["Date"], df["MA50"], label="MA50")

    ax.set_title("Stock Price and Moving Averages")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.legend()
    ax.grid(alpha=0.25)

    fig.autofmt_xdate()
    fig.tight_layout()

    fig.savefig(chart_paths["price_ma"], dpi=150)
    plt.close(fig)

    # -------- BIỂU ĐỒ RSI --------

    fig, ax = plt.subplots(figsize=(10, 3.5))

    ax.plot(df["Date"], df["RSI"], label="RSI (14)")
    ax.axhline(70, linestyle="--", color="red")
    ax.axhline(30, linestyle="--", color="green")

    ax.set_ylim(0, 100)
    ax.set_title("Relative Strength Index")
    ax.set_xlabel("Date")
    ax.set_ylabel("RSI")
    ax.legend()
    ax.grid(alpha=0.25)

    fig.autofmt_xdate()
    fig.tight_layout()

    fig.savefig(chart_paths["rsi"], dpi=150)
    plt.close(fig)

    # -------- BIỂU ĐỒ MACD --------

    fig, ax = plt.subplots(figsize=(10, 3.5))

    ax.plot(df["Date"], df["MACD"], label="MACD")
    ax.plot(
        df["Date"],
        df["MACD_Signal"],
        label="Signal"
    )

    ax.bar(
        df["Date"],
        df["MACD_Histogram"],
        label="Histogram",
        alpha=0.4
    )

    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_title("MACD (12, 26, 9)")
    ax.set_xlabel("Date")
    ax.set_ylabel("MACD")
    ax.legend()
    ax.grid(alpha=0.25)

    fig.autofmt_xdate()
    fig.tight_layout()

    fig.savefig(chart_paths["macd"], dpi=150)
    plt.close(fig)

    # ==================================================
    # 12. OUTPUT CHUẨN CHO TV6
    # ==================================================

    return {
        "data_available": True,

        "technical_score": technical_score,
        "score": technical_score,
        "label": label,

        "analysis_date": str(
            latest["Date"].date()
        ),
        "observations": len(df),

        "close": close,
        "ma20": ma20,
        "ma50": ma50,
        "rsi": rsi,

        "macd": macd,
        "macd_signal": macd_signal,
        "macd_histogram": macd_histogram,

        "volume": volume,
        "avg_volume_20": avg_volume_20,
        "volume_ratio": volume_ratio,
        "volatility": volatility,

        "signals": signals,

        "positives": positives,
        "risks": risks,

        "technical_view": technical_view,
        "commentary": technical_view,

        "charts": chart_paths,

        "data": df
    }


if __name__ == "__main__":
    print("StockLens Technical Analysis module ready.")
