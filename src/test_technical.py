import pandas as pd
import numpy as np

from technical_analysis import analyze_technical


# Tạo 100 ngày dữ liệu mẫu
dates = pd.date_range(
    start="2026-01-01",
    periods=100,
    freq="B"
)

# Tạo giá mẫu tăng dần
close_prices = np.linspace(100, 150, 100)

price_df = pd.DataFrame({
    "Date": dates,
    "Open": close_prices - 1,
    "High": close_prices + 2,
    "Low": close_prices - 2,
    "Close": close_prices,
    "Volume": np.random.randint(
        100000,
        500000,
        size=100
    )
})


# Chạy module Technical Analysis
result = analyze_technical(price_df)


# In kết quả kiểm thử
print("Data available:", result["data_available"])

if result["data_available"]:
    print("Close:", round(result["close"], 2))
    print("MA20:", round(result["ma20"], 2))
    print("MA50:", round(result["ma50"], 2))
    print("RSI:", round(result["rsi"], 2))
else:
    print("Error:", result["error"])