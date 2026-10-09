import numpy as np
import pandas as pd

from technical_analysis import analyze_technical


# ==================================================
# TEST MODULE TECHNICAL ANALYSIS - TV2
# ==================================================

def create_test_data():
    """
    Tạo dữ liệu OHLCV mẫu để kiểm thử module TV2.
    Không sử dụng dữ liệu này trong hệ thống chính thức.
    """

    np.random.seed(42)

    n = 120

    dates = pd.bdate_range(
        start="2026-01-01",
        periods=n
    )

    # Tạo chuỗi giá mô phỏng
    returns = np.random.normal(
        loc=0.0005,
        scale=0.015,
        size=n
    )

    close = (
        100
        * np.cumprod(1 + returns)
    )

    open_price = (
        close
        * (
            1
            + np.random.normal(
                0,
                0.005,
                n
            )
        )
    )

    high = (
        np.maximum(
            open_price,
            close
        )
        * (
            1
            + np.random.uniform(
                0.001,
                0.02,
                n
            )
        )
    )

    low = (
        np.minimum(
            open_price,
            close
        )
        * (
            1
            - np.random.uniform(
                0.001,
                0.02,
                n
            )
        )
    )

    volume = np.random.randint(
        100_000,
        1_000_000,
        n
    )

    price_df = pd.DataFrame({
        "Date": dates,
        "Open": open_price,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume
    })

    return price_df


# ==================================================
# CHẠY TEST
# ==================================================

def main():

    print("=" * 55)
    print("STOCKLENS - TEST TECHNICAL ANALYSIS")
    print("=" * 55)

    # Tạo price_df mẫu
    price_df = create_test_data()

    print(
        f"\nDa tao {len(price_df)} "
        "phien du lieu test."
    )

    print("\n5 dong dau:")
    print(price_df.head())

    # Gọi module TV2
    result = analyze_technical(
        price_df,
        chart_dir="charts"
    )

    # Kiểm tra kết quả
    if not result["data_available"]:

        print("\nTEST THAT BAI")

        print(
            "Loi:",
            result.get("error")
        )

        return

    # ==================================================
    # HIỂN THỊ KẾT QUẢ
    # ==================================================

    print("\n" + "=" * 55)
    print("KET QUA TECHNICAL ANALYSIS")
    print("=" * 55)

    print(
        "\nTechnical Score:",
        result["technical_score"]
    )

    print(
        "Label:",
        result["label"]
    )

    print(
        "\nAnalysis Date:",
        result["analysis_date"]
    )

    print(
        "Observations:",
        result["observations"]
    )

    # --------------------------------------------------
    # INDICATORS
    # --------------------------------------------------

    print("\n--- INDICATORS ---")

    print(
        f"Close: "
        f"{result['close']:.2f}"
    )

    print(
        f"MA20: "
        f"{result['ma20']:.2f}"
    )

    print(
        f"MA50: "
        f"{result['ma50']:.2f}"
    )

    print(
        f"RSI: "
        f"{result['rsi']:.2f}"
    )

    print(
        f"MACD: "
        f"{result['macd']:.4f}"
    )

    print(
        f"MACD Signal: "
        f"{result['macd_signal']:.4f}"
    )

    print(
        f"MACD Histogram: "
        f"{result['macd_histogram']:.4f}"
    )

    print(
        f"Volume: "
        f"{result['volume']:.0f}"
    )

    print(
        f"Avg Volume 20: "
        f"{result['avg_volume_20']:.0f}"
    )

    if result["volume_ratio"] is not None:

        print(
            f"Volume Ratio: "
            f"{result['volume_ratio']:.2f}"
        )

    print(
        f"Volatility: "
        f"{result['volatility'] * 100:.2f}%"
    )

    # --------------------------------------------------
    # SIGNALS
    # --------------------------------------------------

    print("\n--- SIGNALS ---")

    for name, detail in result["signals"].items():

        print(
            f"{name}: "
            f"{detail['signal']} "
            f"({detail['score']}/100)"
        )

    # --------------------------------------------------
    # POSITIVES
    # --------------------------------------------------

    print("\n--- POSITIVES ---")

    if result["positives"]:

        for item in result["positives"]:
            print("+", item)

    else:

        print(
            "Khong co diem tich cuc "
            "noi bat."
        )

    # --------------------------------------------------
    # RISKS
    # --------------------------------------------------

    print("\n--- RISKS ---")

    if result["risks"]:

        for item in result["risks"]:
            print("-", item)

    else:

        print(
            "Khong co canh bao "
            "noi bat."
        )

    # --------------------------------------------------
    # COMMENTARY
    # --------------------------------------------------

    print("\n--- TECHNICAL VIEW ---")

    print(
        result["technical_view"]
    )

    # --------------------------------------------------
    # CHARTS
    # --------------------------------------------------

    print("\n--- CHARTS ---")

    for name, path in result["charts"].items():

        print(
            name,
            "=>",
            path
        )

    print("\n" + "=" * 55)

    print(
        "TEST THANH CONG - "
        "MODULE TV2 HOAT DONG!"
    )

    print("=" * 55)


if __name__ == "__main__":
    main()
