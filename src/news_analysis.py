# news_analysis.py
import pandas as pd

# Tự động nhận diện dù bạn để file ở thư mục gốc hay bên trong thư mục src/
try:
    from src.news_crawler import NewsCrawler
    from src.sentiment_engine import SentimentEngine
    from src.scoring import NewsScorer
except ModuleNotFoundError:
    from news_crawler import NewsCrawler
    from sentiment_engine import SentimentEngine
    from scoring import NewsScorer

crawler = NewsCrawler()
engine = SentimentEngine()
scorer = NewsScorer()
def analyze_news(ticker: str, start_date: str, end_date: str) -> dict:
    """
    Module phân tích tin tức và cảm xúc (Sentiment Analysis) - StockLens.
    
    Input:
        ticker (str): Mã cổ phiếu (vd: 'HPG', 'VNM', 'FPT')
        start_date (str): 'YYYY-MM-DD'
        end_date (str): 'YYYY-MM-DD'
        
    Output:
        Dictionary chứa điểm tin tức, độ tin cậy, phân bố cảm xúc,
        top tin tức nổi bật và DataFrame chuẩn hóa.
    """
    ticker = ticker.strip().upper()
    
    # 1. Thu thập tin tức
    raw_articles = crawler.fetch_news(ticker=ticker)

    # 2. Lọc thời gian và khử trùng lặp
    cleaned = crawler.filter_and_deduplicate(raw_articles, start_date, end_date)
    
    if not cleaned:
        return {
            "data_available": False,
            "ticker": ticker,
            "news_score": 50.0,
            "confidence_level": "None",
            "total_articles": 0,
            "sentiment_distribution": {"positive": 0, "neutral": 0, "negative": 0},
            "prominent_news": [],
            "news_dataframe": pd.DataFrame(),
            "summary": "Không tìm thấy tin tức trong khoảng thời gian phân tích."
        }

    # 3. Phân loại cảm xúc
    for item in cleaned:
        combined = f"{item['title']}. {item['summary']}"
        item["sentiment"] = engine.analyze_text(combined)

    # 4. Tính toán News Score
    score_result = scorer.calculate_news_score(cleaned, end_date)

    # 5. DataFrame chuẩn hóa
    df_data = []
    for item in cleaned:
        df_data.append({
            "ticker": item["ticker"],
            "title": item["title"],
            "publish_date": item["publish_date"].strftime("%Y-%m-%d %H:%M"),
            "source": item["source_name"],
            "credibility": item["source_credibility"],
            "sentiment": item["sentiment"]["label"],
            "sentiment_score": item["sentiment"]["score"],
            "impact_explanation": item["sentiment"]["impact_explanation"],
            "url": item["url"]
        })
    df_normalized = pd.DataFrame(df_data)

    # 6. Top tin nổi bật
    prominent_formatted = []
    for p in score_result["prominent_news"]:
        prominent_formatted.append({
            "title": p["title"],
            "date": p["publish_date"].strftime("%d/%m/%Y"),
            "source": p["source_name"],
            "sentiment": p["sentiment"]["label"],
            "impact_explanation": p["sentiment"]["impact_explanation"],
            "url": p["url"]
        })

    return {
        "data_available": True,
        "ticker": ticker,
        "start_date": start_date,
        "end_date": end_date,
        "news_score": score_result["news_score"],
        "confidence_level": score_result["confidence_level"],
        "total_articles": len(cleaned),
        "sentiment_distribution": score_result["sentiment_distribution"],
        "prominent_news": prominent_formatted,
        "news_dataframe": df_normalized,
        "summary": score_result["note"]
    }