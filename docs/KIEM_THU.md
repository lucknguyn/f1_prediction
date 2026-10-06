# Kiểm thử F1 Lab

## Lần chạy ngày 06/10/2026

Lệnh: `python -m pytest -q --live-db`.

**51 passed trong 20,15 giây**, Python 3.12, MySQL 26.7.0 qua Unix socket. Có 35 cảnh báo tương thích timedelta của pandas/Streamlit; không có test lỗi. Phiên bản cụ thể trong requirements.lock.txt.

## Nội dung kiểm tra

- Sửa nhãn/trạng thái/điểm hiện tại và tương lai không đổi X quá khứ; trước cuối tuần không dùng FP/Q hiện tại.
- Thống kê đội lấy 5 chặng, không lấy 5 dòng tay đua; loại phiên không đủ danh sách khi tính metric toàn phiên.
- Hạng là hoán vị 1..N với N=4/20/22, phá hòa tái lập; metric so với ví dụ tính tay.
- Chia thời gian, xử lý thiếu/đội mới, save/load model, lựa chọn bằng validation trước test.
- Import lặp không nhân đôi, source trùng bị từ chối, transaction rollback, FK, backup/restore không ghi đè DB có sẵn.
- Chuẩn hóa FP loại vòng bị xóa, định danh tay đua dự bị, Sprint Qualifying, phiên tương lai không tạo nhãn giả.
- Thống kê ddof=1 và count, hồ sơ mùa loại Q-only tương lai, KMeans tái lập và ít nhất ba k hợp lệ, radar dùng toàn dân số và đảo chiều thuộc tính.
- Đồng bộ TTL, giữ mốc thành công khi nguồn lỗi, thử lại, khóa file ngăn hai tiến trình chạy trùng.
- Bốn trang Streamlit render; dự đoán Q→Race, trước cuối tuần, lưu 22 tay đua vào MySQL; Singapore Sprint không có FP2/FP3 giả.

## Bằng chứng MySQL riêng

`python -m scripts.verify_database` đã chạy 12 truy vấn SQL. EXPLAIN của truy vấn mùa 2026 dùng index season, ước lượng 23 dòng. Bằng chứng lưu ở deliverables/database-evidence.json.

Script tạo schema thử tên UUID trong MySQL cục bộ, restore backup và đối chiếu đủ 17 bảng; xác nhận FK từ chối bản ghi mồ côi, transaction rollback, và từ chối restore vào DB không trống. Schema thử đã được xóa sau kiểm tra; DB dự án giữ nguyên.

## Bằng chứng đồng bộ

`python -m f1lab sync --force` đã lấy lịch 23 chặng năm 2026, Q của 16 chặng/347 dòng và Race của 16 chặng/352 dòng. FP1/FP2/FP3 của Azerbaijan được tải bổ sung; trạng thái kết thúc ok. Raw snapshot và trạng thái ở data/raw và data/processed/sync_status.json.

## Phạm vi

Đã kiểm thử với MySQL thật trên máy hiện tại, chưa xác minh cài mới trên một máy khác hoặc Docker. Docker compose là cấu hình thay thế, chưa chạy vì daemon chưa sẵn sàng. Worker hiện dùng khóa file POSIX nên hỗ trợ macOS/Linux. Chưa kiểm thử tải nhiều người hoặc feed realtime.

Kiểm thử phần mềm không chứng minh dự đoán đúng trong tương lai. FP/Sprint ít mẫu, chưa có khoảng tin cậy hoặc kiểm định chênh lệch model. Metric thuộc thí nghiệm đã lưu và không tự thay đổi khi đồng bộ dữ liệu.
