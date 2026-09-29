# Bài 1 — Một tay đua, một chặng, một hàng dữ liệu

## Mục tiêu học

Phân biệt dữ liệu thô, feature (đặc trưng đầu vào) và label/target (đáp án cần học). Thực hành tải một phiên trước khi tải nhiều mùa.

Ví dụ minh họa, không phải dữ liệu thật: trước cuộc đua, tay đua A xếp thứ 4 ở phân hạng, trung bình 5 chặng trước về thứ 6, đội có phong độ tốt. Đó là các feature. Sau cuộc đua, A được xếp thứ 3: số 3 là label. Mô hình học quan hệ này từ nhiều chặng quá khứ.

Một phiên có thể là FP1/FP2/FP3 (tập luyện), Q (phân hạng), S (Sprint), SQ (phân hạng Sprint), R (đua chính). Dự án chính dự đoán R. Không giả định cuối tuần nào cũng có đủ mọi phiên.

## Chuẩn bị

Các lệnh dưới đây chạy trong thư mục dự án. Nên dùng môi trường riêng với Python 3.11 hoặc 3.12 nếu môi trường hiện tại gặp lỗi tương thích thư viện. Python được phát hiện lúc khảo sát là 3.14.7; chưa kiểm tra cài bộ thư viện trên phiên bản đó.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-ingest.txt
python scripts/collect_session.py --year 2024 --round 1 --session Q
python scripts/collect_session.py --year 2024 --round 1 --session R
```

2024 vòng 1 chỉ là chặng chọn để kiểm tra cách tải, không phải tập dữ liệu đủ để huấn luyện. Việc tải cần Internet; lần đầu chậm hơn do chưa có cache. Không xóa cache sau mỗi lần chạy.

## Chương trình làm gì?

1. Nhận năm, vòng đua và mã phiên bằng tham số dòng lệnh.
2. Bật cache để FastF1 tái sử dụng dữ liệu đã tải.
3. Yêu cầu kết quả, vòng chạy và thời tiết; chưa tải telemetry tần suất cao.
4. Ghi `results.csv`, `laps.csv`, `weather_data.csv` nếu có dữ liệu.
5. Ghi `manifest.json`: nguồn, phiên bản thư viện, thời điểm xuất, số dòng và số giá trị thiếu.

Mỗi lần xuất vào một thư mục timestamp mới để không ghi đè lần trước. Trường `exported_at_utc` chỉ là lúc xuất trên máy: dữ liệu có thể đến từ cache và không chứng minh được lúc thông tin lần đầu công bố. CSV ở đây lưu dạng thô; thời gian vòng chạy vẫn cần chuyển sang giây ở bước xử lý.

FastF1 có thể tải thiếu một phần phiên mà không dừng toàn bộ. Manifest phân biệt `exported`, `empty`, `unavailable`; phải đọc báo cáo trước khi dùng dữ liệu. Nếu mạng hoặc phiên lỗi khiến chương trình dừng trước khi xuất, chưa có snapshot hoàn chỉnh để sử dụng.

## Bài đọc dữ liệu

- Trong kết quả Q, `Position` nghĩa là vị trí phân hạng.
- Trong kết quả R, `Position` nghĩa là thứ hạng cuộc đua, là ứng viên làm nhãn.
- `Q2` hoặc `Q3` trống có thể là tay đua không vào vòng tiếp theo; không được thay bằng 0 giây.
- `Status` của R phục vụ xác định kết quả/DNF và phân tích hậu kiểm; không dùng trạng thái cuộc đua cần dự đoán làm feature.
- Thời tiết R đã xảy ra cũng không được đưa vào dự đoán trước R.
- `GridPosition` trong kết quả R không tự chứng minh được grid đó đã biết tại cutoff sau Q. Bản đầu dùng vị trí Q; nâng cấp grid sau khi có snapshot nguồn trước giờ đua.

## Hoàn thành bài khi

- Có manifest của Q và R, kiểm tra được số dòng, cột và thiếu dữ liệu.
- Giải thích được vì sao cùng tên `Position` nhưng khác vai trò ở Q và R.
- Nói được 3 thông tin có thể biết trước race và 3 thông tin chỉ biết sau race.
- Xác định được khóa ghép: mùa + chặng + định danh tay đua; không ghép chỉ bằng tên hiển thị hoặc số xe.

Script hiện là công cụ thực hành đầu tiên, chưa phải collector sản xuất: chưa có retry có kiểm soát, điều phối nhiều mùa, kiểm tra phiên tương lai, nạp MySQL hay bộ kiểm thử tích hợp API. Những việc đó thuộc giai đoạn dữ liệu trong đề cương.
