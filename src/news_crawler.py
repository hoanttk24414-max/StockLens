# news_crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
from urllib.parse import urlparse, quote
from dateutil import parser as date_parser
try:
    from src.config import SOURCE_CREDIBILITY
except ModuleNotFoundError:
    from config import SOURCE_CREDIBILITY
class NewsCrawler:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_news(self, ticker: str) -> list:
        """
        Thu thập tin tức tự động kết hợp:
        1. API tin tức TCBS theo mã cổ phiếu
        2. Google News RSS tiếng Việt theo từ khóa cổ phiếu
        """
        articles = []
        ticker = ticker.upper().strip()

        # NGUỒN 1: API TCBS theo mã chứng khoán (Rất nhanh và chuẩn)
        try:
            tcbs_url = f"https://apipubanalytics.tcbs.com.vn/e-commercial/news/search?ticker={ticker}&page=0&size=30"
            res = requests.get(tcbs_url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                items = data.get("listNews", [])
                for item in items:
                    title = item.get("title", "")
                    summary = item.get("head", "") or title
                    pub_str = item.get("publishDate", "")
                    pub_date = self._parse_date(pub_str)
                    link = item.get("url", "") or f"https://cafef.vn/{ticker}.chn"
                    
                    articles.append({
                        "ticker": ticker,
                        "title": title,
                        "summary": summary,
                        "publish_date": pub_date,
                        "source": "tcbs/cafef",
                        "url": link
                    })
        except Exception as e:
            print(f"[Warning] Lỗi lấy nguồn TCBS cho {ticker}: {e}")

        # NGUỒN 2: Google News RSS Tiếng Việt (Bổ sung đa dạng nguồn báo chí)
        try:
            query = quote(f"{ticker} cổ phiếu OR chứng khoán")
            rss_url = f"https://news.google.com/rss/search?q={query}&hl=vi&gl=VN&ceid=VN:vi"
            res = requests.get(rss_url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "xml")
                items = soup.find_all("item")
                for it in items[:25]:
                    title = it.title.text if it.title else ""
                    link = it.link.text if it.link else ""
                    pub_str = it.pubDate.text if it.pubDate else ""
                    pub_date = self._parse_date(pub_str)
                    
                    # Tách tên nguồn ở đuôi tiêu đề (ví dụ: "Hòa Phát tăng trưởng - CafeF")
                    source_name = "google_news"
                    if " - " in title:
                        parts = title.rsplit(" - ", 1)
                        title = parts[0]
                        source_name = parts[1].strip()

                    articles.append({
                        "ticker": ticker,
                        "title": title,
                        "summary": title,
                        "publish_date": pub_date,
                        "source": source_name,
                        "url": link
                    })
        except Exception as e:
            print(f"[Warning] Lỗi lấy nguồn Google News cho {ticker}: {e}")

        return articles

    def _parse_date(self, date_str: str) -> datetime:
        if not date_str:
            return datetime.now()
        try:
            return date_parser.parse(date_str).replace(tzinfo=None)
        except Exception:
            return datetime.now()

    def filter_and_deduplicate(self, articles: list, start_date: str, end_date: str) -> list:
        """
        - Lọc theo khoảng thời gian [start_date, end_date]
        - Khử trùng lặp tiêu đề
        - Gán trọng số uy tín nguồn tin
        """
        dt_start = datetime.strptime(start_date, "%Y-%m-%d")
        dt_end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

        filtered = []
        seen_titles = []

        for item in articles:
            p_date = item["publish_date"]
            # Kiểm tra khoảng thời gian
            if not (dt_start <= p_date <= dt_end):
                continue

            # Khử trùng lặp (Jaccard similarity >= 0.7)
            title = item["title"]
            if self._is_duplicate(title, seen_titles):
                continue
            seen_titles.append(title)

            # Xác định độ tin cậy nguồn tin
            domain = self._get_domain(item.get("source", "") + " " + item.get("url", ""))
            item["source_credibility"] = SOURCE_CREDIBILITY.get(domain, SOURCE_CREDIBILITY["unknown"])
            item["source_name"] = domain if domain != "unknown" else item.get("source", "Báo chí")

            filtered.append(item)

        filtered.sort(key=lambda x: x["publish_date"], reverse=True)
        return filtered

    def _get_domain(self, text: str) -> str:
        text_lower = text.lower()
        for known in SOURCE_CREDIBILITY:
            if known in text_lower:
                return known
        return "unknown"

    def _is_duplicate(self, title: str, seen_titles: list, threshold: float = 0.7) -> bool:
        words1 = set(re.findall(r"\w+", title.lower()))
        for seen in seen_titles:
            words2 = set(re.findall(r"\w+", seen.lower()))
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            if union > 0 and (intersection / union) >= threshold:
                return True
        return False