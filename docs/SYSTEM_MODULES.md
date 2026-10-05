# Các module của F1 Lab

Chia theo công việc của hệ thống, không tạo module đăng nhập/đội trưởng/đăng ký giải của một hệ thống quản lý giải đấu khác. Dự án này phân tích dữ liệu F1 công khai, không tổ chức giải đấu.

## 1. Dữ liệu và cơ sở dữ liệu

- `db.py`: Database quản lý kết nối; 17 bảng SQLAlchemy và view đối chiếu.
- `repositories.py`: đọc kết quả Q/R, lưu snapshot đặc trưng, mô hình, dự đoán.
- `weekend_engine/repository.py`: WeekendRepository lưu lịch phiên, kết quả, lần dự đoán và thứ hạng từng người.
- Quy tắc: khóa ngoại/khóa ghép ngăn bản ghi mồ côi/trùng; transaction giữ một lần nhập nhất quán. SQL dùng tham số.

## 2. Thu thập và cập nhật

- `ingest.py`: FastF1DataSource tải nguồn; IngestionRepository nhập; IngestionService điều phối. Lưu snapshot nguồn, thời gian tải và lỗi.
- `weekend_engine/collection.py`: WeekendCollector lấy lịch FP1/FP2/FP3/Q/SQ/S/R thực tế. Cuối tuần Sprint không tự sinh FP2/FP3.
- `sync.py`: SyncService đồng bộ có khoảng cách 15 phút và khóa file; SyncWorker chạy tiến trình nền khi web còn hoạt động. Đọc năm hiện tại từ đồng hồ UTC, không hardcode năm/chặng.
- Nguồn lỗi: giữ dữ liệu đã có, hiển thị trạng thái chưa hoàn chỉnh, thử lại. Dữ liệu có thể chỉ có sau phiên ít nhất 6 giờ theo khoảng đệm của dự án.

## 3. Phân tích dữ liệu

- `analysis/service.py`: AnalysisService ghép kết quả Q/R, thống kê, chất lượng, tổng hợp tay đua/mùa, KMeans và PCA. RadarComparison chuẩn hóa trên toàn dân số cùng mùa.
- `analysis/plots.py`: histogram, elbow/silhouette, PCA và radar PNG để nộp báo cáo.
- `analysis/web.py`: trang thống kê, nhóm tay đua và radar; gọi service, không tự viết SQL.
- Dữ liệu tổng kết mùa chỉ phục vụ mô tả; không đưa vào đặc trưng dự đoán các chặng trong chính mùa đó.

## 4. Học máy và đánh giá

- `models.py`: RaceModel là lớp trừu tượng với fit/predict; baseline và các mô hình hồi quy kế thừa, dùng đa hình qua ModelFactory.
- `features.py`, `ml.py`: FeatureBuilder, TemporalSplitter, ExperimentTrainer và RaceEvaluator cho thí nghiệm Q → Race.
- `weekend_engine/features.py`: WeekendFeatureBuilder chỉ dùng lịch sử trước phiên đầu của cuối tuần.
- `weekend_engine/training.py`: baseline lịch sử, Linear Regression, Random Forest, HistGradientBoosting; chọn riêng từng loại phiên bằng validation.
- CatBoost tiếp tục có trong thí nghiệm Q → Race. Không ép một thuật toán thắng để đáp ứng tên trong đề mẫu.

## 5. Dự đoán và giao diện

- `weekend_engine/prediction.py`: WeekendPredictionService kiểm tra cutoff, chọn model đúng loại phiên, xếp điểm thành thứ hạng duy nhất và lưu MySQL.
- `ml.py`: PredictionService cho đối chứng sau Q.
- `web.py`: DashboardApp với bốn mục Dự đoán, Phân tích, Mô hình, Dữ liệu.
- `app.py` chỉ khởi chạy DashboardApp. `__main__.py` chỉ tiếp nhận tham số CLI và gọi service.
- `weekend.py` giữ đường import tương thích với joblib cũ; nghiệp vụ đã chuyển vào package weekend_engine.

## 6. Kiểm thử và bàn giao

- `delivery.py`: BackupService, ReportService, BundleService.
- `scripts/verify_database.py`: chạy 12 truy vấn, EXPLAIN, kiểm tra FK/rollback và restore vào schema MySQL thử riêng, sau đó xóa schema thử.
- `tests/`: kiểm tra leakage, phép tính, model, API nhập liệu, đồng bộ và giao diện.
- `docs/`: hướng dẫn chạy, đọc code, ERD, đề bài, đối chiếu yêu cầu, học thuyết trình.

## Vì sao là OOP?

Đóng gói kết nối trong Database; trừu tượng hóa thuật toán qua RaceModel; kế thừa ở các chiến lược mô hình; đa hình ở fit/predict. Service nhận repository/config/nguồn từ bên ngoài để kiểm thử không cần gọi mạng. Tách trách nhiệm không có nghĩa mọi file đều phải kế thừa một lớp lớn.

Luồng đọc để học: app.py → DashboardApp → WeekendPredictionService → WeekendFeatureBuilder + WeekendRepository → mô hình fit/predict → bảng weekend_runs/weekend_predictions. Sau đó đọc ingest.py, sync.py, analysis/service.py và tests.
