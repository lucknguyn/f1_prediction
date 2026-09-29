# Hướng dẫn chạy và bàn giao F1 Lab

## 1. Trên máy đang làm dự án

Trong thư mục dự án, mở Terminal:

```bash
source .venv/bin/activate
python scripts/local_mysql.py start
python -m f1lab doctor
python -m streamlit run app.py --server.port 8501
```

Mở http://127.0.0.1:8501. Giữ Terminal chạy Streamlit. Ctrl+C dừng web; `python scripts/local_mysql.py stop` dừng MySQL riêng của dự án. Không cần train lại mỗi lần trình bày.

MySQL local ở `.local/mysql`, kết nối qua `.local/mysql.sock`, không mở cổng mạng. `.env` được tạo với tài khoản riêng và quyền trên database f1_prediction. Không chia sẻ `.env`, `.local`, `.venv`. Một lần kết nối được xác minh bằng `doctor`, không chỉ bằng có lệnh mysql trên máy.

## 2. Cài trên máy khác

Dùng Python 3.12. Tạo môi trường mới, không chép `.venv` giữa các máy:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
```

Trên Windows: `py -3.12 -m venv .venv`, sau đó `.venv\Scripts\activate`. Script local_mysql.py phù hợp macOS/Linux có mysqld, không dành cho Windows. Windows hoặc máy có MySQL sẵn: dùng database riêng và cấu hình DATABASE_URL trong `.env`.

Lựa chọn A — macOS/Linux đã cài MySQL:

```bash
python scripts/local_mysql.py start
python -m f1lab restore --input deliverables/database.json.gz
python -m f1lab doctor
python -m streamlit run app.py
```

Restore chỉ chạy khi tất cả bảng dự án còn trống. Nếu không có backup, dùng pipeline ở mục 3.

Lựa chọn B — Docker đã cài và daemon đã chạy: tạo `.env` theo `.env.example`, bổ sung `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` do bạn chọn, đồng thời DATABASE_URL dùng đúng mật khẩu MYSQL_PASSWORD và cổng 3307. Ví dụ hình thức (thay giá trị mẫu, mã hóa ký tự đặc biệt trong URL):

```text
MYSQL_PASSWORD=YOUR_APP_PASSWORD
MYSQL_ROOT_PASSWORD=YOUR_ROOT_PASSWORD
DATABASE_URL=mysql+pymysql://f1:YOUR_APP_PASSWORD@127.0.0.1:3307/f1_prediction?charset=utf8mb4
```

```bash
docker compose up -d
python -m f1lab restore --input deliverables/database.json.gz
python -m streamlit run app.py
```

Compose dùng MySQL 8.4, chỉ bind cổng về 127.0.0.1. Chờ healthcheck khỏe trước restore. Trên máy dự án, Docker chưa được dùng vì daemon chưa chạy; đường MySQL qua socket đã được kiểm tra thật. requirements.lock.txt là môi trường tham chiếu macOS arm64/Python 3.12; trên OS khác cần để pip xác minh wheel phù hợp.

## 3. Chạy toàn bộ pipeline từ nguồn

```bash
python -m f1lab init-db
python -m f1lab ingest --years 2022 2023 2024 2025 2026
python -m f1lab weather --year 2024 --round 1
python -m f1lab features
python -m f1lab train --test-year 2026
python -m f1lab report
python -m streamlit run app.py
```

`ingest` tải lịch, Q và R qua adapter Ergast của FastF1 (nguồn Jolpica). Có phân trang vì API giới hạn số bản ghi; ghép lại các race bị cắt ngang trang. Nếu một mùa lỗi, các mùa khác vẫn được lưu; chạy lại tiếp tục từ raw cache. Không đưa dữ liệu giả vào để che lỗi.

`weather` lấy quan sát live timing Q qua FastF1. Dữ liệu này dùng trang khám phá; model v1 chưa dùng thời tiết vì coverage nhỏ. Script bài 1 có thể tải cả laps khi muốn học thêm; pipeline chính không cần tải toàn bộ telemetry.

`features` tính và lưu snapshot; `train` tự tạo feature lại trước khi học. `train` tạo thư mục thí nghiệm mới, không ghi đè model cũ. `artifacts/latest.json` chỉ trỏ đến thí nghiệm đã chạy xong.

## 4. Cập nhật 2026 và dự đoán

```bash
python -m f1lab ingest --years 2026 --refresh
python -m f1lab predict --race 202602
```

Mã race là mùa × 100 + vòng; `202602` là 2026 vòng 2. `--refresh` bỏ snapshot tổng hợp latest.json nhưng FastF1 vẫn có cache HTTP của thư viện; không phải cam kết thông tin realtime tức thời. Dự đoán mới sẽ tạo run/snapshot và lưu vào MySQL.

Nếu Race đã có kết quả, web ghi rõ dự đoán hồi cứu. Nếu chưa Q, pipeline từ chối. Model đã train sau race cần xem thì pipeline từ chối; hãy xem prediction validation đã lưu. Không bấm train lại chỉ để làm model học đáp án của một race cần demo.

Đã xem test 2026. Nếu phát triển feature hoặc chọn model dựa theo test này, phải chốt holdout mới cho nghiên cứu tiếp theo. Việc cập nhật kết quả các race trước vào rolling feature khác việc dùng đáp án race hiện tại.

## 5. Kiểm thử

```bash
python -m pytest -q
python -m pytest -q --live-db
```

Lệnh đầu kiểm thử core và render từ artifact; test cần DB live được skip. Lệnh thứ hai yêu cầu MySQL thật, mở năm trang và tạo/lưu một prediction demo; kiểm tra race chưa Q báo đúng. Nó bổ sung một run inference, không sửa model hoặc nhãn race.

Các test sử dụng dữ liệu tổng hợp trong bộ nhớ cho lỗi leakage/ranking; dữ liệu tổng hợp đó không được dùng huấn luyện hay hiển thị như kết quả F1 thật. SQLite chỉ dành cho unit test ràng buộc/import; ứng dụng chạy MySQL.

## 6. Báo cáo, backup và đóng gói

```bash
python -m f1lab report
python -m f1lab backup
python -m f1lab bundle
```

`report` sinh schema SQL và báo cáo từ CSV của thí nghiệm hiện tại. `backup` xuất dữ liệu các bảng thành JSON gzip, không xuất mật khẩu. `bundle` tạo `deliverables/f1-lab-demo.zip`: source, docs, SQL, dependencies, raw/processed cần thiết, model/metric và backup. Không chứa `.env`, `.local`, `.venv` hoặc secrets của Streamlit. Có MANIFEST.sha256 để kiểm tra file.

Giải nén vào thư mục có quyền ghi; cài dependencies, tạo DB riêng rồi restore. Restore chạy trong transaction theo thứ tự khóa ngoại, từ chối database có dữ liệu. Không dùng lệnh reset database đang làm việc để luyện restore; tạo database trống riêng.

Model joblib chỉ tải từ artifact do dự án tạo, không nhận upload file model tùy ý. Dữ liệu F1 lấy từ nguồn công khai, cần ghi nguồn và xem điều khoản nguồn trước khi phát hành công khai dữ liệu/model.

## 7. Lỗi thường gặp

- **Web xem được chart nhưng MySQL báo chưa kết nối:** chạy `doctor`, kiểm tra `.env` và socket/port; web có chế độ xem artifact nhưng không gọi đó là kết nối CSDL.
- **Address already in use:** server đã chạy. Mở địa chỉ hiện tại, hoặc dùng `--server.port 8502` cho một phiên khác.
- **Race chưa có Q:** đây là tình trạng thiếu dữ liệu hợp lệ; chọn chặng đã có Q hoặc cập nhật nguồn sau Q.
- **Restore từ chối:** CSDL đã có dữ liệu; tạo DB trống riêng.
- **Không tải được mùa/phiên:** kiểm tra mạng, log ingestion_runs và raw cache; tải lại hữu hạn, không xóa dữ liệu đã tải thành công.
- **Model không cùng feature version:** train lại theo protocol đã chốt, không lặng lẽ bỏ feature.
- **Không có metric F1-score:** v1 dự đoán thứ hạng; F1-score thuộc phần classifier mở rộng.
