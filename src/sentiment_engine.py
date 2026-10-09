# sentiment_engine.py
import re
try:
    from src.config import POSITIVE_WORDS, NEGATIVE_WORDS, NEGATION_WORDS, INTENSIFIER_WORDS
except ModuleNotFoundError:
    from config import POSITIVE_WORDS, NEGATIVE_WORDS, NEGATION_WORDS, INTENSIFIER_WORDS
class SentimentEngine:
    def analyze_text(self, text: str) -> dict:
        """
        Phân tích cảm xúc dựa trên từ điển tài chính kết hợp xử lý phủ định & tăng cường độ
        Trả về: {'label': str, 'score': float (-1.0 đến 1.0), 'impact_explanation': str}
        """
        text_lower = text.lower()
        score = 0.0
        pos_matches = []
        neg_matches = []

        # Tách câu/mệnh đề để xét ngữ cảnh phủ định trong từng mệnh đề
        clauses = re.split(r"[,;.\n]", text_lower)

        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue

            words = clause.split()
            has_negation = any(neg in clause for neg in NEGATION_WORDS)

            # Kiểm tra từ tích cực
            for pw in POSITIVE_WORDS:
                if pw in clause:
                    val = 1.0
                    # Xét từ tăng cường
                    for int_word, factor in INTENSIFIER_WORDS.items():
                        if int_word in clause:
                            val *= factor
                            break
                    if has_negation:
                        score -= val * 0.8  # "không tăng trưởng" -> thành điểm âm
                        neg_matches.append(f"không {pw}")
                    else:
                        score += val
                        pos_matches.append(pw)

            # Kiểm tra từ tiêu cực
            for nw in NEGATIVE_WORDS:
                if nw in clause:
                    val = 1.0
                    for int_word, factor in INTENSIFIER_WORDS.items():
                        if int_word in clause:
                            val *= factor
                            break
                    if has_negation:
                        score += val * 0.7  # "không thua lỗ" -> thành điểm dương
                        pos_matches.append(f"không {nw}")
                    else:
                        score -= val
                        neg_matches.append(nw)

        # Chuẩn hóa score về dải [-1.0, 1.0]
        if score > 0:
            norm_score = min(1.0, score / 2.5)
        elif score < 0:
            norm_score = max(-1.0, score / 2.5)
        else:
            norm_score = 0.0

        # Gán nhãn cảm xúc
        if norm_score >= 0.2:
            label = "Tích cực"
        elif norm_score <= -0.2:
            label = "Tiêu cực"
        else:
            label = "Trung lập"

        impact = self._generate_impact_explanation(label, pos_matches, neg_matches, text)

        return {
            "label": label,
            "score": round(norm_score, 2),
            "pos_keywords": list(set(pos_matches)),
            "neg_keywords": list(set(neg_matches)),
            "impact_explanation": impact
        }

    def _generate_impact_explanation(self, label: str, pos_keys: list, neg_keys: list, text: str) -> str:
        """Tự động sinh nhận định tác động tới hoạt động kinh doanh và giá cổ phiếu"""
        text_lower = text.lower()

        if label == "Tích cực":
            reasons = []
            if any(k in text_lower for k in ["lợi nhuận", "doanh thu", "lãi", "kỷ lục"]):
                reasons.append("cải thiện kết quả tài chính và biên lợi nhuận")
            if any(k in text_lower for k in ["cổ tức", "mua lại"]):
                reasons.append("gia tăng quyền lợi trực tiếp cho cổ đông")
            if any(k in text_lower for k in ["trúng thầu", "mở rộng", "hợp tác"]):
                reasons.append("mở rộng thị phần và tiềm năng doanh thu trung - dài hạn")
            
            detail = ", ".join(reasons) if reasons else "tạo tâm lý hưng phấn ngắn hạn cho dòng tiền"
            return f"Thông tin tích cực giúp {detail}; hỗ trợ đà tăng giá của cổ phiếu."

        elif label == "Tiêu cực":
            reasons = []
            if any(k in text_lower for k in ["lỗ", "giảm", "lao dốc"]):
                reasons.append("suy giảm hiệu quả hoạt động kinh doanh")
            if any(k in text_lower for k in ["khởi tố", "vi phạm", "thanh tra", "bị phạt"]):
                reasons.append("rủi ro pháp lý và tổn hại uy tín quản trị doanh nghiệp")
            if any(k in text_lower for k in ["nợ", "trái phiếu", "vỡ nợ"]):
                reasons.append("gia tăng áp lực thanh khoản và cấu trúc vốn")

            detail = ", ".join(reasons) if reasons else "tạo áp lực bán ra từ nhà đầu tư"
            return f"Thông tin tiêu cực tiềm ẩn rủi ro: {detail}; có thể tác động giảm giá cổ phiếu trong ngắn hạn."

        else:
            return "Tin tức mang tính cập nhật hoạt động thường niên, tác động trung tính hoặc chưa đủ dữ liệu định lượng đến giá cổ phiếu."