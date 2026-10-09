# scoring.py
import numpy as np
from datetime import datetime

class NewsScorer:
    def __init__(self, lambda_decay: float = 0.05, min_news_threshold: int = 5):
        self.lambda_decay = lambda_decay
        self.min_news_threshold = min_news_threshold

    def calculate_news_score(self, analyzed_articles: list, end_date_str: str) -> dict:
        """
        Tính News Score theo thang điểm 0-100 kèm các chỉ số thống kê
        """
        total_news = len(analyzed_articles)

        # Trường hợp không có bài viết nào phù hợp trong kỳ
        if total_news == 0:
            return {
                "news_score": 50.0,
                "confidence_level": "None (0 bài viết)",
                "confidence_ratio": 0.0,
                "sentiment_distribution": {
                    "positive": 0, "neutral": 0, "negative": 0
                },
                "prominent_news": [],
                "note": "Không tìm thấy tin tức trong kỳ phân tích. Điểm mặc định ở mức trung tính 50."
            }

        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        
        weighted_scores = []
        total_weights = []
        pos_cnt = 0
        neu_cnt = 0
        neg_cnt = 0

        for item in analyzed_articles:
            # 1. Điểm cảm xúc từng bài (-1.0 đến 1.0)
            s_i = item["sentiment"]["score"]
            label = item["sentiment"]["label"]
            if label == "Tích cực": pos_cnt += 1
            elif label == "Tiêu cực": neg_cnt += 1
            else: neu_cnt += 1

            # 2. Trọng số thời gian (Exponential Decay)
            delta_days = max(0, (end_date - item["publish_date"]).days)
            w_time = np.exp(-self.lambda_decay * delta_days)

            # 3. Trọng số nguồn tin
            w_source = item.get("source_credibility", 0.8)

            w_total = w_time * w_source
            weighted_scores.append(w_total * s_i)
            total_weights.append(w_total)

            # Đánh giá mức độ ảnh hưởng của bài viết để chọn tin nổi bật
            item["impact_weight"] = round(float(w_total * abs(s_i)), 3)

        # 4. Điểm cảm xúc thô [-1.0, 1.0]
        sum_weights = sum(total_weights)
        raw_sentiment = sum(weighted_scores) / sum_weights if sum_weights > 0 else 0.0

        # 5. Hệ số tin cậy theo quy mô số lượng tin (Confidence Dampening)
        confidence_ratio = min(1.0, total_news / self.min_news_threshold)
        adjusted_sentiment = raw_sentiment * confidence_ratio

        # 6. Quy đổi sang thang điểm 0 - 100
        news_score = 50.0 + (50.0 * adjusted_sentiment)
        news_score = round(float(np.clip(news_score, 0.0, 100.0)), 1)

        # Đánh giá mức độ tin cậy
        if total_news >= 8: conf_level = "High"
        elif total_news >= 4: conf_level = "Medium"
        else: conf_level = "Low"

        # 7. Trích xuất top 3 tin nổi bật nhất
        sorted_news = sorted(analyzed_articles, key=lambda x: x["impact_weight"], reverse=True)
        prominent = sorted_news[:3]

        return {
            "news_score": news_score,
            "confidence_level": conf_level,
            "confidence_ratio": round(confidence_ratio, 2),
            "sentiment_distribution": {
                "positive": pos_cnt,
                "neutral": neu_cnt,
                "negative": neg_cnt
            },
            "prominent_news": prominent,
            "note": f"Phân tích dựa trên {total_news} bài viết đã làm sạch."
        }