# 1. Trọng số độ tin cậy của nguồn (Credibility Weight: 0.0 - 1.0)
SOURCE_CREDIBILITY = {
    "cafef.vn": 1.0,
    "vietstock.vn": 1.0,
    "vneconomy.vn": 1.0,
    "tinnhanhchungkhoan.vn": 1.0,
    "baodautu.vn": 0.95,
    "ssc.gov.vn": 1.0,           # Ủy ban chứng khoán nhà nước
    "hsx.vn": 1.0,
    "hnx.vn": 1.0,
    "tuoitre.vn": 0.85,
    "thanhnien.vn": 0.85,
    "vietnamnet.vn": 0.85,
    "unknown": 0.5               # Nguồn khác chưa kiểm chứng
}

# 2. Bộ từ khóa tích cực ngành tài chính - chứng khoán
POSITIVE_WORDS = {
    "tăng trưởng", "lợi nhuận kỷ lục", "vượt kế hoạch", "chia cổ tức", "trúng thầu",
    "mở rộng quy mô", "mua lại cổ phiếu", "doanh thu tăng", "lãi ròng tăng",
    "hợp tác chiến lược", "xuất khẩu tăng", "đạt kế hoạch", "bứt phá", "triển vọng khả quan",
    "giảm chi phí", "tái cơ cấu thành công", "phục hồi mạnh", "tăng trần", "cải thiện biên lợi nhuận"
}

# 3. Bộ từ khóa tiêu cực ngành tài chính - chứng khoán
NEGATIVE_WORDS = {
    "thua lỗ", "sụt giảm", "khởi tố", "bị phạt", "vi phạm", "đình chỉ", "hủy niêm yết",
    "chậm công bố", "nợ xấu", "bán giải chấp", "giảm sàn", "lỗ ròng", "lao dốc",
    "thanh tra", "cắt margin", "nguy cơ phá sản", "vỡ nợ", "chậm thanh toán trái phiếu",
    "khiếu nại", "gian lận", "áp lực nợ", "tụt dốc", "bê bối", "cảnh báo", "kiểm soát"
}

# 4. Các từ đảo nghĩa (Negation words)
NEGATION_WORDS = {"không", "chưa", "chẳng", "không hề", "không có"}

# 5. Các từ tăng cường độ (Intensifiers)
INTENSIFIER_WORDS = {
    "mạnh": 1.5, "đột biến": 1.8, "kỷ lục": 2.0, "sâu": 1.5, "nặng nề": 1.8,
    "vượt trội": 1.5, "rất": 1.3, "đáng kể": 1.4
}