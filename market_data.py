import requests
import pandas as pd

def get_market_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Hàm tự động gọi API để cào dữ liệu chứng khoán theo thời gian thực.
    Frontend hoặc Backend sẽ gọi hàm này và truyền tham số do người dùng nhập vào.
    
    :param ticker: Mã cổ phiếu (vd: 'FPT', 'VIC')
    :param start_date: Ngày bắt đầu 'YYYY-MM-DD'
    :param end_date: Ngày kết thúc 'YYYY-MM-DD'
    :return: pd.DataFrame chứa dữ liệu OHLCV đã làm sạch.
    """
    endpoint = "https://openapi.dnse.com.vn/price/ohlc"
    api_key = "eyJvcmciOiJkbnNlliwiaWQiOiI5NDg0M2U3MzQ4Mjc0ZDA4YWEwNDY0ZDlhMzE4MDE3MCIsImgiOiJtdXJtdXIxMjgifQ=="
    api_secret = "3jl11336oEsDZS7mF6er0ziWzS8fb7WLVoxjY8ZciTWONQwLj1nLezJgTaxqYz5MJxGWPYYbZn9mZ28KDOvILA"
    
    headers = {
        "x-api-key": api_key,
        "Authorization": f"Bearer {api_secret}"
    }
    
    # Các tham số này sẽ tự động thay đổi dựa trên giá trị Frontend truyền vào
    params = {
        "symbol": ticker.upper(),
        "startDate": start_date,
        "endDate": end_date,
        "resolution": "1D" 
    }
    
    try:
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        raw_data = data.get("data", data)
        if not raw_data:
            return pd.DataFrame()
            
        df = pd.DataFrame(raw_data)
        
        # Làm sạch và chuẩn hóa dữ liệu
        rename_map = {"t": "Date", "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"}
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        df = df.dropna()
        
        if 'Date' in df.columns and pd.api.types.is_numeric_dtype(df['Date']):
            df['Date'] = pd.to_datetime(df['Date'], unit='s')
            
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        if all(col in df.columns for col in ['High', 'Low', 'Close', 'Volume']):
            df = df[df['High'] >= df['Low']]
            df = df[(df['Close'] > 0) & (df['Volume'] >= 0)]
        
        return df

    except Exception as e:
        print(f"Lỗi hệ thống khi lấy API mã {ticker}: {e}")
        return pd.DataFrame()