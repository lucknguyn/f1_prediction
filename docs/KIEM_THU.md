# Bằng chứng kiểm tra F1 Lab

## Dự đoán trước cuối tuần ngày 06 tháng 10 năm 2026

- Bộ kiểm thử đầy đủ với MySQL thật: **45 passed trong 21,35 giây**.
- Thử tạo và lưu dự đoán cho FP1/FP2/FP3/Q/R tại chặng 202616 và SQ/S tương lai tại 202617: mỗi phiên có 22 hạng khác nhau; phiên tương lai không có nhãn giả.
- Kiểm tra MySQL không có weekend_results với driver_id hoặc team_id bằng chuỗi nan.
- Phục hồi backup trước khi có bảng weekend vào CSDL SQLite kiểm thử thành công: 4.331 kết quả nguồn, bốn bảng mới trống.
- Kiểm thử thay đổi dữ liệu hiện tại/tương lai không làm thay đổi feature trước cuối tuần; vòng FP bị xóa không làm nhãn; roster SQ và người dự bị được xử lý riêng.
- Smoke test trang mới, đường dẫn trực tiếp, đổi chặng và không phát sinh FP2/FP3 tại Singapore Sprint.

Độ phủ FP/Sprint còn ít; kiểm thử phần mềm đạt không đồng nghĩa dự đoán chính xác. Xem DU_DOAN_CUOI_TUAN.md để biết phạm vi dữ liệu và giới hạn hồi cứu.


## Bản OOP ngày 5 tháng 10 năm 2026

Sau khi tách service/repository/strategy, bộ kiểm thử được mở rộng thêm các hợp đồng OOP. Kiểm tra gồm CLI, năm trang web với MySQL thật, tạo/lưu dự đoán, thay nguồn bằng dependency trong bộ nhớ, huấn luyện trong thư mục tạm, khóa lựa chọn trước test và so sánh điểm/thứ hạng của tất cả artifact cũ. Các test train mới dùng fixture tổng hợp riêng, không ghi vào dữ liệu/mô hình demo.

Thêm kiểm tra `SessionCollector` xuất manifest cho dữ liệu thiếu và `LocalMySQLManager` chỉ đọc PID trong thư mục riêng.

**Kết quả: `35 passed in 16.75s`** với lệnh `.venv/bin/python -m pytest -q --live-db`. Không có kiểm thử bị bỏ qua hay cảnh báo trong lần chạy này. Schema và artifact mô hình trước refactor vẫn tương thích.

## Bằng chứng bản v1 trước refactor

Lệnh kiểm tra cuối gồm MySQL thật:

```bash
.venv/bin/python -m pytest -q --live-db
```

**Kết quả: 22 passed trong 23,28 giây.** Môi trường Python 3.12, MySQL 26.7.0 local qua Unix socket; versions ở requirements.lock.txt. Kết quả này là lần kiểm tra bản v1, không tự cập nhật nếu mã thay đổi về sau.

## Nội dung đã kiểm tra

- Thay label/status/điểm của race hiện tại và tương lai không làm X quá khứ thay đổi.
- Thống kê cấp đội lấy 5 race, không lấy 5 dòng tay đua.
- Race lệch roster bị loại khỏi metric full-grid; không cắt âm thầm vài tay đua.
- Race có Q nhưng chưa R tạo feature, không tự tạo nhãn.
- Duplicate tay đua cùng race bị từ chối.
- Rank là hoán vị 1..N với N = 4, 20 và 22; score hòa có thứ tự tái lập.
- MAE/RMSE/podium đối chiếu với ví dụ tính tay.
- Chia thời gian không làm race nằm ở cả train và validation.
- Pipeline xử lý danh mục đội mới/thiếu số; save/load model cho cùng dự đoán.
- Chuyển thời gian Q sang giây và quy tắc DNF.
- Import lần hai không nhân đôi kết quả; lỗi trong transaction rollback.
- FK từ chối kết quả không có entry/session hợp lệ.
- Backup/restore roundtrip và từ chối DB không trống (unit test bằng SQLite).
- Năm trang Streamlit render được khi có MySQL thật.
- Tạo/lưu prediction từ Q 2026 vòng 2, trả 22 tay đua; chặng cuối mùa chưa Q báo thiếu dữ liệu.

## Kiểm tra thủ công

Web tại http://127.0.0.1:8501 đã hiển thị “MySQL đã kết nối”, 2.063 mẫu và kết quả thực nghiệm. CSDL thực có dữ liệu ở các bảng và view prediction_comparison. Có 77 quan sát weather Q Bahrain 2024.

ZIP demo đã được đọc lại, đối chiếu SHA-256 theo MANIFEST; không chứa `.env`, `.local` hoặc `.venv`. Kiểm tra mới lại ZIP sau khi thay source/tài liệu phải đóng gói lại.

## Phạm vi của bằng chứng

Restore đã được test vòng đi-về ở unit test; chưa chạy khôi phục trên máy khác hoặc Docker. Docker compose là lựa chọn cấu hình, chưa được xác minh thực thi trên máy này vì daemon chưa chạy. Không có kiểm thử tải đồng thời nhiều người hoặc realtime feed.

Kiểm thử phần mềm không chứng minh mô hình dự đoán chính xác trong tương lai. Hiệu năng ML được ghi riêng trong BAO_CAO_THUC_NGHIEM.md; chưa có khoảng tin cậy hay kiểm định chênh lệch model.
