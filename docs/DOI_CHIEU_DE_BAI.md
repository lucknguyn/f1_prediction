# Đối chiếu đề bài F1 với sản phẩm

Đề gốc của cô là ví dụ định dạng. Đề F1 trong DE_BAI_F1_PYTHON_CSDL.md là phạm vi tham chiếu; mô hình và giao diện được chọn theo tính phù hợp, không sao chép nghiệp vụ bóng đá.

## Python

1. Thu thập dữ liệu thật: FastF1/Jolpica 2022–2026, Q/R; thêm lịch và kết quả từng phiên cuối tuần. Raw snapshot và ingestion_runs ghi nguồn, ngày tải, lỗi. Thời tiết Q lưu riêng và có đồ thị; chưa dùng làm feature do ít mẫu.
2. Xử lý: trường thiếu giữ NaN/NULL/N/a đúng tầng; không điền nhãn; Q2/Q3 thiếu không coi là 0; DNF giữ lại; kiểm tra trùng, vị trí hợp lệ, danh sách đầy đủ. IQR chỉ gắn cờ, không xóa mọi giá trị cực trị.
3. Đầu ra: `data/processed/analysis/results.csv`, `data_dictionary.csv`, `quality_report.json`. Một dòng/tay đua/chặng; sắp mùa/vòng/driver_id. Thời gian Q1/Q2/Q3 theo giây.
4. Thống kê: `results2.csv` có count/mean/median/std mẫu, nhóm toàn bộ/đội/mùa/đội-mùa; `extremes.csv` có ba cao/thấp mỗi thuộc tính; histogram PNG; web lọc đội/mùa.
5. Tổng hợp: `driver_season.csv` và bảng thành tích đội; DNF và hạng chiều thấp tốt, điểm chiều cao tốt. Không diễn giải thành sức mạnh xe thuần túy.
6. Phân cụm: KMeans thử k=2..6 khi đủ mẫu, median + StandardScaler, seed42, elbow và silhouette; PCA2D có phương sai giải thích, tâm cụm ở đơn vị gốc. Mặc định báo cáo mùa hoàn tất 2025; mẫu ít, mang tính khám phá.
7. Radar: `radarChartPlot.py --p1 --p2 --season --Attribute`, xuất PNG, cùng phương pháp chuẩn hóa với web. driver_id được liệt kê trong driver_season.csv. Tối thiểu ba thuộc tính, thông báo lỗi nếu tên không có.
8. Học máy: Q→Race có Linear Regression, Random Forest, HistGradientBoosting, CatBoost và 2 baseline; trước cuối tuần có 3 hồi quy và baseline riêng phiên. Chọn bằng validation trước test; model tốt nhất có thể là baseline.
9. Đánh giá: MAE/RMSE hạng, Spearman, winner hit, podium, top10 và MAE/RMSE/R² điểm liên tục. F1-score không áp dụng trực tiếp cho hồi quy xếp hạng; chưa có classifier podium/xác suất thắng. Hai chặng sai ít/nhiều có trong BAO_CAO_THUC_NGHIEM.md.
10. Web 4 mục; OOP thực sự trong service/repository/model; tài liệu, báo cáo Word, kiểm thử và ZIP bàn giao.

## CSDL

1. ERD và giải thích chuẩn hóa: ERD.md; 17 bảng, khóa chính/ngoại/UNIQUE/CHECK và index ở schema.sql.
2. Nhập lặp không nhân đôi: khóa theo phiên/tay đua; transaction, kiểm thử nguồn trùng và xung đột đội.
3. `demo_queries.sql`: 12 truy vấn cho kết quả, đội/mùa, đối chiếu đúng run, thiếu Q, lịch sử, thay đổi đội, điểm, DNF, lịch sử model, lịch phiên, dự đoán cuối tuần. Có JOIN/GROUP BY/HAVING/subquery/window/EXPLAIN.
4. View prediction_comparison và bảng dự đoán được web đọc/ghi thật. JSON feature là snapshot có chủ đích, không thay các quan hệ chính bằng một file JSON lớn.
5. Tài khoản ứng dụng f1 tách root; .env/.local không vào ZIP. Tài khoản ứng dụng có quyền trong schema dự án để khởi tạo bảng/view; không phải cấu hình production tối thiểu quyền.
6. `scripts/verify_database.py`: bằng chứng thực thi SQL, kế hoạch index, FK từ chối bản ghi mồ côi, rollback, backup/restore đủ 17 bảng trên MySQL thật. Từ chối restore vào DB không trống.

## Mở rộng so với đề

Lịch tự đồng bộ khi web chạy, không phụ thuộc ngày train. Mặc định dự đoán trước cuối tuần và chỉ hiện các phiên có thật. Chặng vừa qua và sắp tới đọc từ nguồn; nhãn sự kiện không được suy đoán theo tên quốc gia. Q→Race là đối chứng lựa chọn riêng.

## Giới hạn phải trình bày

- API có thể cập nhật chậm hoặc sửa lịch/kết quả. Mất mạng vẫn xem dữ liệu cũ; cần xem mốc đồng bộ. Máy tắt hoặc web dừng thì worker dừng.
- Cutoff trước cuối tuần loại dữ liệu FP/Q hiện tại; lịch sử lấy sau start+6h là khoảng đệm kỹ thuật, chưa có snapshot xác minh giờ công bố từng dữ kiện.
- Danh sách tay đua lịch sử lấy hồi cứu; phiên tương lai tạm dùng Race gần nhất, cần xác nhận tay đua dự bị/đổi đội.
- FP dự đoán vòng nhanh nhất hợp lệ, không phải tốc độ chạy dài. FP/Sprint có ít phiên huấn luyện/đánh giá.
- Đã xem test 2026: nghiên cứu thay đổi thuật toán tiếp theo cần holdout tương lai, không dùng test cũ để chọn model rồi gọi là đánh giá độc lập.
- Không thể cam kết độ chính xác cao với tai nạn, chiến thuật, thay đổi luật và những yếu tố chưa được đo.
