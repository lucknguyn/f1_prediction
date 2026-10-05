# Học dự án và chuẩn bị bảo vệ

## Bài 1 — Đi từ một ví dụ đến ML

Một hàng là một tay đua ở một chặng. Ví dụ minh họa: A có hạng Q 4, trung bình 5 race trước hạng 6, đội có hạng trung bình 5. Model nhận những thông tin này và dự đoán điểm hạng 4,7. Sắp điểm của toàn bộ tay đua để có thứ tự 1..N. Sau race, hạng thực tế của A là 3: sai số của hạng cuối được đem đánh giá.

X là feature; y là đáp án. `label` và `status` của race hiện tại được lưu để hậu kiểm, nhưng không nằm trong `FEATURES` của model. Một cột có trong CSV không có nghĩa nó được đưa vào train.

Mở `f1lab/features.py`, đọc `NUMERIC`, `CATEGORICAL`, `FEATURES`; tìm dòng `history = ...`. Câu cần tự nói được: **dù CSDL đã có kết quả race đang kiểm tra, feature của race ấy chỉ dùng quá khứ**.

## Bài 2 — Dữ liệu từ đâu và sạch ra sao?

Pipeline chính gọi adapter Ergast của FastF1, hiện truy cập Jolpica, để lấy lịch/kết quả. Weather gọi live timing FastF1. Đây là gọi API qua thư viện; không tự quét HTML website.

Đọc `download_year` trong `f1lab/ingest.py`: có cache, phân trang và ghép race bị chia ở ranh giới trang. Sau đó đọc `seconds`, `positive_int` và `import_year`.

- Chuẩn hóa Q time từ chuỗi phút:giây sang số giây. `1:32.123` = 92,123 giây.
- Không biến thiếu Q3 thành 0 giây; chưa có lap hợp lệ thì giữ thiếu.
- Position thiếu/không hợp lệ là NULL; không tự đặt đáp án.
- PK/UNIQUE giúp chống trùng; duplicate nguồn có xung đột làm import dừng.
- Import trong transaction: nếu lỗi thì rollback, không để một phần phiên được coi là hoàn chỉnh.
- Q và R phải khớp danh sách và đủ vị trí khi đánh giá full grid. Bị loại cần báo coverage.

Làm sạch cấu trúc khác với imputation để train. Median/scaler/encoder chỉ được fit từ training trong Pipeline. Nếu median lấy cả test, mô hình đã dùng thông tin test dù chưa dùng y.

## Bài 3 — Các feature v1 có ý nghĩa gì?

Tất cả feature trong X phải có trước Race theo định nghĩa bài toán:

- `quali_position`: hạng Q hiện tại; thấp hơn thường tốt hơn.
- `q1_gap_pct`: % chậm hơn thời gian Q1 nhanh nhất cùng phiên. 1 nghĩa chậm hơn 1%; có thể chịu ảnh hưởng thay đổi thời tiết trong phiên.
- `reached_q2`, `reached_q3`: có thời gian hợp lệ phần Q2/Q3; là proxy, không hoàn toàn tương đương vượt vòng.
- `driver_form5`: hạng Race trung bình tối đa 5 lần trước của tay đua.
- `driver_points5`: điểm Race trung bình 5 lần trước; không bao gồm Sprint.
- `driver_dnf10`: tỷ lệ trạng thái DNF theo quy tắc dự án, tối đa 10 lần trước; DSQ/DNS không được gộp vào DNF.
- `driver_history_count`: số race lịch sử có hạng sử dụng được.
- `team_form5`: lấy trung bình thành tích đội từng race, rồi trung bình 5 race trước. Không lấy 5 dòng tay đua thay 5 race.
- `team_points5`: tổng điểm Race đội ở mỗi chặng, rồi trung bình 5 race trước.
- `circuit_form`: hạng trung bình lịch sử tay đua trên đường đua này.
- `circuit_count`: số lần lịch sử trên đường đua đó.
- `season_round`: vòng hiện tại trong mùa.
- `field_size`: số tay đua trong kết quả Q dùng làm roster, không hard-code 20.
- `team_id`, `circuit_id`: danh mục, mã hóa one-hot; gặp danh mục mới không gây lỗi.

Tay đua mới chưa có lịch sử: `history_count=0`, một số thống kê là thiếu. Model có missing indicator và median training. Không lấy tương lai bù vào. `driver_id` dùng JOIN và phá hòa, không đưa trực tiếp vào model.

Các chỉ số phong độ là đại diện cho nhiều yếu tố, không phải điểm kỹ năng thuần túy. Một tay đua về thấp có thể do xe, pit, tai nạn hoặc phạt; dữ liệu tổng hợp không tự tách được từng nguyên nhân.

## Bài 4 — MySQL giải quyết việc gì?

Mở `docs/ERD.md` và `sql/demo_queries.sql`. Sau đó mở `f1lab/db.py`.

`entries` ghi tay đua nào thuộc đội nào ở race nào. Ví dụ tay đua đổi đội: sửa team trong một bảng drivers duy nhất sẽ làm lịch sử sai; entries giữ quan hệ theo từng race.

`sessions` tách Q/R; cùng cột position nhưng Q là input, R là label. `feature_snapshots` ghi bộ X cụ thể của từng lần tạo. `model_runs` ghi model học đến khi nào. `predictions` liên kết đúng run với đúng snapshot. `evaluation_metrics` lưu metric tổng hợp và từng race.

View `prediction_comparison` JOIN các bảng để trình bày tên race/tay đua/đội cùng dự đoán và thực tế. View không chép dữ liệu sang một bảng mới. Index tăng khả năng tìm kiếm nhưng không bảo đảm luôn nhanh hơn full scan với bảng nhỏ; xem EXPLAIN để giải thích.

## Bài 5 — Từng thuật toán hoạt động ra sao?

**Linear Regression:** học tổng có trọng số của feature. Dễ giải thích nhưng khó biểu diễn mọi quan hệ phi tuyến. Mã hóa danh mục thành cột số trước khi học.

**Random Forest:** tạo nhiều cây quyết định từ các mẫu/feature khác nhau rồi trung bình dự đoán. Cây chia dữ liệu theo điều kiện; nhiều cây giảm độ phụ thuộc vào một cây đơn lẻ.

**HistGradientBoosting:** xây mô hình theo các bước để giảm lỗi của dự đoán hiện tại. Histogram giúp xử lý các ngưỡng số hiệu quả.

**CatBoost:** một thuật toán boosting khác. Trong bản này cũng dùng cùng preprocessing one-hot để so sánh đầu vào công bằng; chưa khai thác chế độ native categorical của CatBoost. Không trình bày rằng code v1 đang dùng native categorical nếu không có trong cấu hình.

**Baseline Q:** lấy thứ tự phân hạng làm dự đoán. **Baseline phong độ:** lấy hạng trung bình 5 race trước, thiếu lịch sử thì dùng Q. Hai baseline giúp biết ML thêm giá trị hay chỉ làm phức tạp bài toán.

Mở `f1lab/models.py`, đọc `RaceModel`, `ModelFactory` và `_regression_pipeline`; sau đó mở `f1lab/ml.py`, đọc `TemporalSplitter.split`, `ExperimentTrainer._run_fold` và `ExperimentTrainer.train` để xem leaderboard. Cấu hình v1 cố định, seed 42; không có grid search. Không nói “đã tối ưu tất cả tham số”. Xem `docs/OOP.md` để hiểu đóng gói, kế thừa và đa hình trong code thật.

## Bài 6 — Tự tính metric

Ví dụ minh họa 4 tay đua: thực tế A–B–C–D, dự đoán B–A–C–D. Sai số hạng lần lượt 1, 1, 0, 0.

- MAE = (1+1+0+0)/4 = 0,5 bậc.
- RMSE = căn((1²+1²+0²+0²)/4) ≈ 0,707 bậc.
- Winner hit = 0 vì sai người thắng.
- Podium overlap = 1 vì tập A/B/C trùng hoàn toàn.
- Exact podium = 0 vì thứ tự podium khác nhau.

Vì vậy một chỉ số không thể mô tả toàn bộ dự đoán. Metric tính từng race rồi lấy trung bình race. R² raw dùng điểm hồi quy liên tục, không phải % đoán đúng; có thể âm. F1-score có ý nghĩa cho phân loại như podium/non-podium, chưa có classifier trong v1.

## Bài 7 — Đọc đúng kết quả hiện tại

Mở báo cáo thực nghiệm, không học thuộc điểm trong đề cương. Baseline Q đang được chọn bằng validation. Các model ML có thể tốt hơn ở vài chỉ số hoặc vài chặng nhưng chưa thắng MAE rank tổng hợp.

Câu trả lời khi giảng viên hỏi “sao ML không thắng?”:

> Em đặt baseline trước và dùng cùng tập kiểm tra theo thời gian. Trong cấu hình đã chạy, Q là tín hiệu mạnh và các thống kê lịch sử chưa cải thiện MAE tổng thể. Em báo cáo cả kết quả này; hướng tiếp theo là kiểm tra feature/cấu hình bằng protocol mới, thay vì chọn riêng chặng dự đoán đẹp.

Đây là kết luận trong phạm vi thực nghiệm, không chứng minh mọi ML đều kém. Đã xem test 2026; thay feature dựa theo test cần holdout mới.

## Hỏi đáp khi bảo vệ

**Tại sao dự đoán sau Q?** Đây là cutoff đã chốt để bài toán khả thi và có tín hiệu hiện tại. Dự đoán trước Q cần một bộ feature/protocol khác.

**Tại sao không dùng final GridPosition trong kết quả R?** Có thể gồm án phạt chỉ biết sau cutoff Q. V1 dùng hạng Q; nâng cấp grid cần snapshot trước race.

**Tại sao không dùng thời tiết thực tế R?** Thông tin đó chưa tồn tại trước R. Weather Q chỉ mô tả điều kiện Q, không phải forecast R.

**Dữ liệu ít thì thêm deep learning?** Mô hình phức tạp hơn không tự khắc phục thiếu dữ liệu. Trước hết kiểm tra baseline, feature, chia tập và chất lượng nhãn.

**Test và validation khác gì?** Validation chọn model/tham số; test dùng báo cáo sau khi đã khóa lựa chọn. Dùng test chọn model làm kết quả mất tính độc lập.

**Ngẫu nhiên 80/20 có vấn đề gì?** Có thể đem race tương lai vào train, hoặc tay đua cùng race vào cả hai tập. V1 giữ nguyên race và chia theo mùa.

**Có chắc dữ liệu đã biết ở đúng cutoff lịch sử?** Chưa chứng minh tuyệt đối. Nguồn truy xuất hiện tại có thể sửa kết quả; báo cáo ghi backtest hồi cứu và giới hạn này.

**DNF là dữ liệu bẩn?** Không. Bỏ cuộc là kết quả thật và phải giữ khi có thứ hạng hợp lệ. Không xóa tất cả DNF để làm metric đẹp hơn.

**Tại sao không có F1-score?** Bài toán chính là thứ hạng; MAE/Spearman/podium overlap phù hợp. Classifier podium sẽ có precision/recall/F1 riêng nếu mở rộng.

**Cột importance lớn chứng minh nguyên nhân?** Không; nó biểu thị model phụ thuộc vào feature trong thí nghiệm hoán vị. Feature tương quan có thể chia sẻ importance.

**2026 đổi luật thì sao?** Đây là nguy cơ thay đổi phân phối. Em đánh giá 2026 riêng và chưa khẳng định model tổng quát tốt cho mọi giai đoạn.

## Kịch bản trình bày 8–10 phút

1. 1 phút: bài toán, cutoff và một mẫu X/y.
2. 1 phút: nguồn/coverage; vì sao Q3 thiếu không điền 0.
3. 1–2 phút: ERD, entries và view JOIN.
4. 2 phút: chọn backtest 2026, xem dự đoán/thực tế và MAE.
5. 1–2 phút: bảng so sánh model/baseline và cách chia tập.
6. 1 phút: một chặng sai nhiều, giới hạn và hướng phát triển.

Mỗi thành viên tự chạy ít nhất một lần, tự tính ví dụ metric và nói được đường đi của một prediction. Người viết code có thể phụ trách kỹ thuật, nhưng nhóm phải cùng hiểu lựa chọn và giới hạn của nghiên cứu.
