# test_news.py
from src.news_analysis import analyze_news
from datetime import datetime, timedelta
from tabulate import tabulate

def test_pipeline():
    test_tickers = ["HPG", "VNM", "FPT"]
    
    # Lấy tự động 90 ngày gần nhất tính tới hôm nay để luôn có tin thực tế
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    for ticker in test_tickers:
        print("=" * 70)
        print(f"KIỂM THỬ MODULE TIN TỨC VỚI MÃ: {ticker} ({start_date} -> {end_date})")
        print("=" * 70)
        
        result = analyze_news(ticker, start_date, end_date)
        
        print(f"\n📊 KẾT QUẢ ĐÁNH GIÁ CHUNG:")
        print(f" - News Score (0-100) : {result['news_score']}/100")
        print(f" - Mức độ tin cậy     : {result['confidence_level']}")
        print(f" - Tổng số tin tìm thấy: {result['total_articles']}")
        print(f" - Phân bố cảm xúc    : {result['sentiment_distribution']}")
        
        print(f"\n🌟 TOP TIN NỔI BẬT & ĐÁNH GIÁ TÁC ĐỘNG:")
        for idx, item in enumerate(result['prominent_news'], 1):
            print(f"[{idx}] {item['date']} - {item['title']} ({item['source']})")
            print(f"    * Cảm xúc : {item['sentiment']}")
            print(f"    * Tác động: {item['impact_explanation']}\n")

        df = result['news_dataframe']
        if not df.empty:
            print("📋 BẢNG ĐỐI CHIẾU MẪU (5 BÀI):")
            sample = df[['title', 'sentiment', 'sentiment_score', 'source']].head(5)
            print(tabulate(sample, headers='keys', tablefmt='psql', showindex=False))

if __name__ == "__main__":
    test_pipeline()