# F1 Race Predictor 2026

**Cập nhật 06/10/2026:** đã có [dự đoán từng phiên trước cuối tuần](docs/DU_DOAN_CUOI_TUAN.md) cho FP1, FP2, FP3, Q, SQ, Sprint và Race, không cần Q của chặng hiện tại. Mở trang **Toàn bộ cuối tuần**. Chặng ngày 04/10 tại Malaysia đã được cập nhật. Nội dung Q → Race bên dưới là thí nghiệm riêng của v1.


Đồ án kết hợp Machine Learning, cơ sở dữ liệu MySQL và web Python.

**Trạng thái:** bản v1 đã chạy toàn bộ dữ liệu → MySQL → feature → huấn luyện → đánh giá → web. Có dữ liệu thật 2022–2025 và 15 chặng 2026 ở snapshot hiện tại; 13 chặng 2026 đủ điều kiện đánh giá. Không có dữ liệu hay metric giả.

Mở [hướng dẫn chạy](docs/HUONG_DAN.md) để sử dụng, [báo cáo thực nghiệm](docs/BAO_CAO_THUC_NGHIEM.md) để đọc kết quả, và [tài liệu học/bảo vệ](docs/HOC_VA_BAO_VE.md) để hiểu code. [Đề cương](docs/DE_CUONG.md) giữ bản thiết kế ban đầu, bao gồm cả phần mở rộng chưa triển khai.

Phạm vi v1: dự đoán thứ hạng đua chính sau phân hạng Q; dùng lịch sử trước Race. Web Streamlit/Plotly, MySQL, scikit-learn và CatBoost. Đây là backtest hồi cứu; nguồn Q có thể có sửa đổi sau sự kiện. Thời tiết Q được lưu để khám phá, chưa đưa vào model v1.

Code được tổ chức theo OOP với service, repository và chiến lược mô hình dùng chung `fit()`/`predict()`. Đọc [kiến trúc và cách học OOP](docs/OOP.md) để xem trách nhiệm từng lớp, sơ đồ quan hệ và ví dụ sử dụng.

## Mở demo trên máy hiện tại

```bash
source .venv/bin/activate
python scripts/local_mysql.py start
python -m streamlit run app.py --server.port 8501
```

Mở http://127.0.0.1:8501. Nếu web đã chạy, chỉ cần mở địa chỉ này. Không phải tải dữ liệu hoặc train lại cho mỗi lần demo.

## Lấy bản demo từ GitHub

Repo giữ mã nguồn, tài liệu và `deliverables/f1-lab-demo.zip`. Các thư mục dữ liệu, mô hình và bản sao lưu nằm **bên trong ZIP**, không được commit riêng lẻ. ZIP đã loại `.env`, `.local` và `.venv`.

Trên máy mới, tải ZIP từ repo và giải nén vào một thư mục trống. ZIP tạo thư mục `f1_prediction/` chứa cả source lẫn dữ liệu demo. Vào thư mục vừa giải nén, cài Python 3.12 và MySQL, rồi làm theo [hướng dẫn cài máy khác](docs/HUONG_DAN.md#2-cài-trên-máy-khác). Máy đã có project và MySQL như hiện tại chỉ cần dùng các lệnh ở mục trên.

## Kết quả ban đầu

Đã so sánh Linear Regression, Random Forest, HistGradientBoosting và CatBoost với hai baseline. Theo MAE validation 2024–2025, **Baseline Q** được chọn. Test 2026: MAE khoảng **3,427 bậc** trên **13 race / 286 mẫu**. Bốn model ML chưa vượt baseline theo metric này; đây là kết quả cần báo cáo trung thực, không phải lỗi phần mềm. Xem báo cáo cho toàn bộ metric và giới hạn.

## Các file làm gì?

- `docs/DE_CUONG.md`: bài toán, dữ liệu, MySQL, mô hình, đánh giá, web, lộ trình, bảo vệ đồ án.
- `docs/BAI_01.md`: giải thích và hướng dẫn thu thập một chặng trước khi mở rộng.
- `docs/HUONG_DAN.md`: cài đặt, chạy, cập nhật, backup/restore, kiểm thử và lỗi thường gặp.
- `docs/HOC_VA_BAO_VE.md`: đọc code theo luồng, data dictionary, cách giải thích mô hình/metric và hỏi đáp.
- `docs/BAO_CAO_THUC_NGHIEM.md`: báo cáo sinh từ số liệu chạy thật.
- `docs/ERD.md`, `sql/schema.sql`, `sql/demo_queries.sql`: sơ đồ và nội dung môn CSDL.
- `f1lab/ingest.py`: tải dữ liệu qua FastF1, làm sạch cấu trúc và import transaction.
- `f1lab/features.py`: tạo thống kê quá khứ và lưu snapshot đầu vào.
- `f1lab/models.py`: `RaceModel`, các chiến lược baseline/hồi quy và `ModelFactory`.
- `f1lab/ml.py`: `ExperimentTrainer`, `PredictionService`, `TemporalSplitter` và `RaceEvaluator`.
- `f1lab/repositories.py`: các lớp truy vấn kết quả, lưu snapshot/run và đọc artifact.
- `f1lab/config.py`: cấu hình đường dẫn có thể truyền vào khi kiểm thử.
- `f1lab/db.py`: các bảng và khóa SQLAlchemy/MySQL.
- `f1lab/delivery.py`: báo cáo, schema, backup/restore và đóng gói demo.
- `app.py`: điểm khởi chạy Streamlit; `f1lab/web.py` chứa lớp `DashboardApp` và năm trang.
- `scripts/collect_session.py`: tải một phiên bằng FastF1, lưu CSV và manifest kiểm tra dữ liệu.
- `scripts/local_mysql.py`: MySQL riêng qua socket trên máy Unix có mysqld.
- `requirements.lock.txt`: phiên bản môi trường đã chạy; Python 3.12.
- `tests/`: kiểm tra leakage, rank, metric, import và web. Chạy `python -m pytest -q --live-db` để kiểm tra cả MySQL.

## Những gì chưa nằm trong v1

Chưa có classifier/xác suất podium, forecast thời tiết lưu ở cutoff, SHAP, tuning lớn, live prediction giữa Race hay website công khai. F1-score dành cho bài toán phân loại bổ sung; v1 tập trung thứ hạng và các metric tương ứng.

Không dùng kết quả đua chính của chặng cần dự đoán làm đặc trưng đầu vào. `Race.Position` là nhãn; `Qualifying.Position` có thể là đặc trưng nếu đã có trước thời điểm dự đoán.
