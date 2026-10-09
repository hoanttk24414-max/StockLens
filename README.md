# 📈 StockLens

### Hệ thống phân tích và đánh giá cơ hội đầu tư cổ phiếu Việt Nam

**Stock Investment Analysis & Automated Reporting System**

---

## 🎯 Giới thiệu

StockLens là dự án xây dựng hệ thống hỗ trợ phân tích và đánh giá cơ hội đầu tư cổ phiếu trên thị trường chứng khoán Việt Nam, được phát triển bằng ngôn ngữ Python.

Hệ thống được thiết kế nhằm cho phép người dùng nhập mã cổ phiếu, lựa chọn khoảng thời gian và phong cách đầu tư, từ đó thực hiện các phân tích và tổng hợp kết quả thành báo cáo.

Dự án hướng tới khả năng mở rộng cho nhiều mã cổ phiếu được nguồn dữ liệu hỗ trợ, không giới hạn ở một doanh nghiệp cụ thể.

## 🚀 Các chức năng chính

- **Market Data:** Thu thập, làm sạch và chuẩn hóa dữ liệu giá cổ phiếu, khối lượng giao dịch.
- **Technical Analysis:** Phân tích xu hướng giá qua MA20, MA50, RSI, MACD và các chỉ báo kỹ thuật.
- **Fundamental Analysis:** Đánh giá tăng trưởng doanh thu, lợi nhuận, ROA, ROE, biên lợi nhuận và tình hình tài chính doanh nghiệp.
- **Valuation Analysis:** Tính P/E, P/B, so sánh doanh nghiệp tương đồng và xây dựng Valuation Score.
- **News Analysis:** Thu thập và phân loại tin tức theo mức độ tích cực, trung lập và tiêu cực.
- **Investment Score:** Tổng hợp điểm số theo phong cách đầu tư Thận trọng, Cân bằng và Tăng trưởng.
- **Automated PDF Report:** Xuất báo cáo phân tích cổ phiếu theo nội dung người dùng lựa chọn.

## 🧠 Quy trình hoạt động

1. Người dùng nhập mã cổ phiếu và khoảng thời gian phân tích.
2. Hệ thống truy xuất dữ liệu thị trường, tài chính và tin tức từ các nguồn được hỗ trợ.
3. Các module thực hiện phân tích độc lập.
4. Hệ thống tính điểm đánh giá và tổng hợp nhận xét.
5. Người dùng lựa chọn nội dung và xuất báo cáo PDF.

## 🛠️ Công nghệ sử dụng và dự kiến tích hợp

| Công nghệ | Vai trò |
|---|---|
| Python | Ngôn ngữ lập trình chính |
| Pandas, NumPy | Xử lý và phân tích dữ liệu |
| Requests | Giao tiếp API dữ liệu |
| Streamlit | Giao diện người dùng dự kiến |
| Plotly / Matplotlib | Trực quan hóa dữ liệu |
| ReportLab | Xuất báo cáo PDF dự kiến |
| GitHub | Quản lý và cộng tác mã nguồn |

## 📂 Cấu trúc dự án

```text
StockLens/
├── data/
├── src/
├── fundamental_analysis.py
├── interface_to_tv1_tv3.py
├── README.md
└── .gitignore
```

*Cấu trúc được cập nhật theo tiến độ phát triển của nhóm.*

## 📊 Phương pháp đánh giá

StockLens dự kiến sử dụng các điểm thành phần theo thang điểm 0–100:

- Technical Score
- Financial Score
- Valuation Score
- News Score
- Safety / Risk Score

Investment Score được tổng hợp theo bộ trọng số tương ứng với phong cách đầu tư được lựa chọn.

Các điểm số chỉ phục vụ nghiên cứu, hỗ trợ phân tích, không phải cam kết lợi nhuận hoặc khuyến nghị mua bán chắc chắn.

## 👥 Phân công phát triển

| Thành viên | Module |
|---|---|
| Nhã | Thu thập dữ liệu thị trường |
| Hoàn | Phân tích kỹ thuật |
| Hà | Phân tích tài chính |
| Linh | Phân tích định giá |
| Hưng | Phân tích tin tức |
| Thư | Tích hợp hệ thống, tính điểm tổng hợp và xuất PDF |

## 📌 Trạng thái dự án

**Đang phát triển – Development in Progress**

Các module đang được xây dựng, kiểm thử và kết nối. Khả năng truy xuất dữ liệu thực tế phụ thuộc vào nguồn API, quyền truy cập và mức độ đầy đủ của dữ liệu.

---

**StockLens | Dự án môn Gói phần mềm 1**
