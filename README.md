# F1 Lab — bài tập lớn Python và Cơ sở dữ liệu

Dự đoán FP1, FP2, FP3, Qualifying, Sprint Qualifying, Sprint và Race từ lịch sử **trước cuối tuần**. Chỉ hiện phiên có thật trong lịch. Có thí nghiệm Q → Race riêng để đối chứng, phân tích thống kê, KMeans/PCA, radar và MySQL.

## Chạy demo trên máy hiện tại

```bash
source .venv/bin/activate
python scripts/local_mysql.py start
python -m streamlit run app.py --server.port 8501
```

Mở http://127.0.0.1:8501. Nếu cổng đã có chính web dự án thì mở lại, không chạy thêm; muốn phiên khác dùng `--server.port 8502`. Không cần train lại khi mở web.

Web gồm bốn mục: **Dự đoán · Phân tích · Mô hình · Dữ liệu**. Phần hướng dẫn học, OOP và bảo vệ chuyển vào docs, các chức năng dữ liệu và đối chiếu vẫn còn.

## Tự cập nhật lịch và kết quả

Khi web đang chạy và MySQL kết nối, một tiến trình nền kiểm tra mỗi phút; chỉ thực hiện đồng bộ tối đa một lần mỗi 15 phút. Năm lấy từ đồng hồ UTC. Lịch/Q/R toàn mùa được cập nhật; FP/Sprint chưa có ở hai chặng gần nhất được tải bổ sung. Nguồn chưa công bố kết quả thì không tạo nhãn giả. Chờ tối thiểu 6 giờ sau giờ bắt đầu phiên theo khoảng đệm dự án.

Sidebar ghi lần cập nhật và tình trạng nguồn; sau lượt đồng bộ mới, trang tự tải lại. Có thể bấm **Xem dữ liệu mới** để đọc lại MySQL. Mất mạng vẫn dùng dữ liệu đã lưu và thử lại chu kỳ sau. Máy tắt/web dừng thì không đồng bộ. Worker hiện hỗ trợ macOS/Linux (khóa file POSIX).

```bash
python -m f1lab sync --force        # Đồng bộ ngay, không đợi 15 phút
F1_AUTO_SYNC=0 python -m streamlit run app.py  # Demo offline từ dữ liệu sẵn có
```

Lịch mới không làm thay đổi model đã chọn hoặc metric backtest cũ. Khi cần cập nhật nghiên cứu, chủ động chạy weekend-train; tránh chọn thuật toán dựa trên test đã xem.

## Phân tích và đầu ra nộp bài

```bash
python -m f1lab analyze --season 2025
python radarChartPlot.py --p1 norris --p2 max_verstappen --season 2025
python radarChartPlot.py --p1 norris --p2 max_verstappen --season 2025 --Attribute quali_mean race_mean points_mean
```

Đầu ra ở `data/processed/analysis/`: results.csv, results2.csv, data_dictionary.csv, quality_report.json, extremes.csv, driver_season.csv, kết quả KMeans/PCA và các PNG. Radar chuẩn hóa theo toàn bộ tay đua cùng mùa; phía ngoài là tốt hơn, riêng n_races là độ phủ.

Kết quả snapshot ngày 06/10/2026: nguồn Q/R có 16 chặng 2026; thí nghiệm Q→Race có 14 chặng test đủ điều kiện. Baseline Q thắng validation, MAE test khoảng 3,435 bậc. Mô hình trước cuối tuần được chọn riêng từng phiên; không ép Random Forest hay CatBoost phải thắng baseline. KMeans mùa 2025 có 21 tay đua, chọn k=3; PCA2D giải thích khoảng 95,4% phương sai. Các con số này thuộc lần chạy đã lưu, không phải cam kết dự đoán tương lai.

## Máy mới và bản bàn giao

Giải nén `deliverables/f1-lab-demo.zip` vào thư mục trống. ZIP gồm source, tài liệu, báo cáo Word, dữ liệu phân tích, model và backup MySQL; không chứa .env/.local/.venv. GitHub chưa được đẩy tiếp theo yêu cầu tạm dừng trước đó.

Cài Python 3.12 và MySQL; trên macOS/Linux có mysqld:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
python scripts/local_mysql.py start
python -m f1lab init-db
python -m f1lab restore --input deliverables/database.json.gz
python -m streamlit run app.py
```

Chỉ restore vào CSDL trống. Có thể dùng compose.yaml/MySQL riêng rồi cấu hình DATABASE_URL trong .env; xem [hướng dẫn đầy đủ](docs/HUONG_DAN.md). Không có backup thì thu thập nguồn và train theo tài liệu, không restore đè DB đang có.

## Các lệnh kiểm tra và đóng gói

```bash
python -m pytest -q --live-db
python -m scripts.verify_database
python -m f1lab report
python -m f1lab backup
python -m f1lab bundle
```

verify_database dùng root của MySQL riêng để tạo schema thử có tên UUID, kiểm tra rồi xóa schema thử. Không xóa DB dự án. Bằng chứng ở deliverables/database-evidence.json.

## Đọc để học và thuyết trình

- [Chia module và đường đọc code](docs/SYSTEM_MODULES.md).
- [Đối chiếu yêu cầu đã thực hiện](docs/DOI_CHIEU_DE_BAI.md).
- [Đề bài F1](docs/DE_BAI_F1_PYTHON_CSDL.md), [OOP](docs/OOP.md), [ERD](docs/ERD.md).
- [Dự đoán trước cuối tuần](docs/DU_DOAN_CUOI_TUAN.md), [báo cáo đối chứng Q→Race](docs/BAO_CAO_THUC_NGHIEM.md).
- [Học và bảo vệ](docs/HOC_VA_BAO_VE.md), [hướng dẫn vận hành](docs/HUONG_DAN.md).

Giới hạn: danh sách tham gia hồi cứu; nguồn có thể sửa sau sự kiện; FP/Sprint ít mẫu; chưa có forecast thời tiết lưu tại cutoff, xác suất podium hay dự đoán trong lúc đua. Thời tiết Q được lưu/visual riêng. F1-score thuộc bài toán phân loại, không phải chỉ số nên gắn tùy ý vào hồi quy thứ hạng.
