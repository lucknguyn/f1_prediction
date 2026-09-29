# Bằng chứng kiểm tra bản v1

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
