# Đề cương: Dự đoán thứ hạng đua chính F1 2026

Ngày thiết kế: 29/09/2026. Quỹ thời gian: một người triển khai trong 7 ngày, sau đó 7 ngày để các thành viên học và luyện bảo vệ.

**Cập nhật:** đây là đề cương ban đầu. Bản v1 đã được triển khai; xem `README.md`, `HUONG_DAN.md` và `BAO_CAO_THUC_NGHIEM.md` để biết trạng thái/kết quả hiện tại. Các phần mở rộng trong đề cương không mặc nhiên có trong code.

Đây là thiết kế và kế hoạch nghiệm thu, chưa phải báo cáo kết quả thực nghiệm. Các thuật toán, cột và trang web dưới đây là những phần sẽ triển khai; không ngụ ý đã có dữ liệu, model hoặc web chạy được.

## 1. Mục tiêu và giới hạn

Tên đề tài gợi ý: **Xây dựng hệ thống dự đoán thứ hạng đua chính Formula 1 mùa giải 2026 bằng học máy, tích hợp MySQL và ứng dụng web Python.**

Người dùng chọn một chặng đã có kết quả phân hạng Q; hệ thống dùng thông tin có trước đua chính R để dự đoán thứ tự các tay đua. Với chặng đã kết thúc, hệ thống cho đối chiếu với kết quả thực tế bằng quy trình giả lập dự đoán tại thời điểm quá khứ.

Mốc dự đoán bản đầu: sau khi kết quả Q được công bố, trước R. Dùng kết quả Q đã có ở mốc này. Đây không phải hệ thống dự đoán từ đầu mùa toàn bộ các chặng, cũng không phải dự đoán trực tiếp giữa cuộc đua.

Nếu Q chưa diễn ra hoặc không có đủ dữ liệu thiết yếu, web hiển thị lý do chưa thể dự đoán. Không lấy Q từ một chặng khác hay âm thầm thay bằng thông tin sau đua. Sprint không là mục tiêu dự đoán trong bản đầu; chỉ bổ sung feature Sprint khi kiểm chứng được phiên đó kết thúc trước cutoff.

Sản phẩm bắt buộc:

- Pipeline tải và kiểm tra dữ liệu có thể chạy lại.
- MySQL có ERD, khóa, ràng buộc, truy vấn JOIN/GROUP BY, view và giao dịch import.
- Bảng feature cho mỗi tay đua ở mỗi chặng, có quy tắc chống rò rỉ dữ liệu.
- Hai baseline và bốn mô hình hồi quy được so sánh công bằng.
- Đánh giá theo thời gian, lưu model, dự đoán và kết quả thực nghiệm.
- Web có dữ liệu, dự đoán, đánh giá, giải thích phương pháp.
- Hướng dẫn cài đặt, báo cáo, kịch bản demo và tài liệu hỏi đáp.

Phần mở rộng chỉ làm sau khi phần bắt buộc chạy ổn: phân loại podium/top 10, xác suất đã hiệu chỉnh, dự đoán DNF, SHAP, dự báo thời tiết có lịch sử phát hành, learning-to-rank. Không dành tuần đầu cho đăng nhập, realtime telemetry, deep learning, triển khai cloud hoặc microservices.

## 2. Hiểu Machine Learning qua chính bài toán này

Mỗi mẫu là **một tay đua trong một chặng**. Chặng có N tay đua đủ điều kiện thì có N mẫu, không cố định số lượng ở 20. Mô hình học trên các chặng đã có đáp án.

- Feature X: thông tin đầu vào, ví dụ hạng Q, phong độ trước race, phong độ đội.
- Target y: thứ hạng race từ kết quả đã được kiểm tra.
- Training: tìm các quy luật từ lịch sử.
- Validation: thử các lựa chọn mô hình và tham số trên các chặng muộn hơn training.
- Test: kiểm tra lựa chọn đã chốt trên dữ liệu chưa dùng để chọn model.
- Inference: đưa feature của chặng cần dự đoán vào model đã huấn luyện.

Ví dụ hoàn toàn minh họa: A có hạng Q = 4, hạng trung bình 5 race trước = 6; model dự đoán điểm hạng 4,7. Những điểm dự đoán của tất cả tay đua trong cùng chặng được sắp tăng dần để tạo thứ tự 1..N. Không làm tròn riêng từng người vì sẽ bị trùng hạng. Nếu bằng điểm, phá hòa bằng hạng Q rồi định danh tay đua để tái lập kết quả.

Phân biệt rõ hai giá trị lưu và hiển thị: `predicted_score` là đầu ra hồi quy; `predicted_rank` là thứ tự sau sắp xếp trong chặng. Điểm 4,7 không phải xác suất thắng hay cam kết về thứ hạng.

## 3. Luồng xử lý và công nghệ

FastF1 → snapshot dữ liệu thô + manifest → kiểm tra/làm sạch → MySQL → tạo feature theo thời điểm → chia train/validation/test → preprocessing và huấn luyện → đánh giá → lưu pipeline/model + dự đoán → Streamlit.

Chọn Python, FastF1, pandas, NumPy cho dữ liệu; MySQL và SQLAlchemy/PyMySQL cho lưu trữ; scikit-learn và CatBoost cho ML; Streamlit và Plotly cho web. Đây là đề xuất phù hợp thời gian, không phải tuyên bố công cụ nào luôn tốt nhất. Khóa phiên bản phụ thuộc sau khi kiểm tra tích hợp.

Streamlit cho phép viết giao diện bằng Python và ghép biểu đồ nhanh, phù hợp người triển khai duy nhất. Không thêm Flask/FastAPI nếu chưa có yêu cầu môn học về REST API hoặc kiến trúc backend/frontend tách riêng.

Tách các module `ingestion`, `cleaning`, `database`, `features`, `training`, `evaluation` và `app`. Web gọi phần xử lý dùng chung, không chứa toàn bộ thuật toán trong một tệp giao diện. Thu thập/huấn luyện bằng lệnh riêng; demo chủ yếu đọc dữ liệu và model đã lưu để không phải chờ train.

## 4. Thu thập dữ liệu

Khởi đầu với một chặng Q và R để xác minh schema. Sau đó khảo sát 2022–2025 và các chặng 2026 đã hoàn thành, ghi rõ coverage thực tế. Đây là cửa sổ đề xuất, không khẳng định mọi phiên đều tải đủ. Mở rộng từ 2018 chỉ khi cần và còn thời gian; dữ liệu cũ hơn không mặc nhiên giúp tốt hơn.

Nhóm cần lấy: lịch sự kiện, định danh tay đua/đội, kết quả Q và R, vòng chạy khi cần phân tích pace, thời tiết phiên tập luyện/Q. Không tải toàn bộ telemetry ngay từ đầu. Tên dùng để hiển thị; định danh ổn định dùng để liên kết. Đội của tay đua phải gắn với lần tham dự chặng, không gắn cố định cho cả sự nghiệp.

Collector cần có cache, timeout/retry hữu hạn ở lớp điều phối, nhật ký lỗi, tiếp tục từ phiên đã hoàn thành, và manifest số dòng/thiếu dữ liệu. Không gọi lại API khi người dùng đổi từng biểu đồ. Dữ liệu nguồn lỗi không được thay bằng dữ liệu giả để báo đã tải thành công.

Lưu cả snapshot nguyên bản và dữ liệu sạch: snapshot phục vụ truy vết, không dùng trực tiếp train. Báo cáo riêng số chặng mong đợi, tải thành công, thiếu Q, thiếu nhãn và bị loại theo quy tắc.

### Thời tiết

FastF1 cung cấp quan sát thời tiết của phiên, không phải dự báo tương lai được lưu tại mốc dự đoán. Thời tiết R là dữ liệu hậu kiểm nếu dự đoán trước R.

Bản đầu có thể dùng thống kê thời tiết Q dưới tên `quali_*`; chúng chỉ mô tả điều kiện Q, không được gọi là thời tiết race. Tác dụng phải kiểm tra bằng thí nghiệm bỏ/thêm nhóm feature. Nếu bổ sung dự báo race sau này, phải lưu nơi dự báo, thời điểm phát hành và giờ áp dụng; backtest cần dự báo đã thực sự tồn tại ở cutoff. Không dùng thời tiết thực tế quá khứ thay thế dự báo quá khứ rồi gọi đó là dự đoán trước race.

### Mốc dữ liệu và sửa đổi kết quả

Nguồn truy xuất hôm nay có thể chứa kết quả đã sửa sau một cuộc đua. `collected_at` là lúc tải về, khác `available_at` là lúc nguồn công bố. Nếu không có snapshot lịch sử đúng thời điểm, báo cáo phải ghi backtest hồi cứu có hạn chế về phiên bản thông tin, không khẳng định mô phỏng point-in-time tuyệt đối.

Grid xuất phát có thể khác hạng Q vì án phạt. Ở cutoff sau Q, bản đầu dùng hạng Q; không tự lấy final `GridPosition` từ kết quả R làm đầu vào. Phiên bản dự đoán ngay trước R dùng grid chỉ khi có nguồn/snapshot chứng minh grid đó đã công bố trước cutoff.

## 5. Từ “xe mạnh, kỹ năng, phong độ” sang feature

FastF1 không trả một điểm kỹ năng thật hay sức mạnh xe thật. Ta xây các **chỉ số đại diện**; chúng chịu ảnh hưởng của xe, tay đua, chiến thuật và hoàn cảnh. Không diễn giải chúng như đã tách biệt được nguyên nhân.

Bộ ban đầu khoảng 12–20 đặc trưng, lựa chọn cuối cùng theo coverage và validation:

- `quali_position`: hạng Q hiện tại, đã có trước cutoff.
- `quali_gap_pct`: chênh lệch thời gian tương đối so với mốc cùng phần Q và cùng điều kiện có thể so sánh. Ưu tiên Q1 cùng nhóm; không so Q1 mưa với Q3 khô như ngang điều kiện. Thiếu lượt hợp lệ thì để thiếu, không lấy 0.
- `driver_mean_position_last5`: trung bình hạng ở tối đa 5 race trước đó.
- `driver_mean_points_last5`, `driver_dnf_rate_last10`: điểm và tỷ lệ bỏ cuộc lịch sử.
- `driver_history_count`: số race quá khứ dùng được, giúp nhận biết tay đua ít dữ liệu.
- `driver_circuit_mean_position`, `driver_circuit_count`: thành tích các lần trước trên đúng đường đua; không gộp hai địa điểm chỉ vì cùng quốc gia.
- `team_mean_position_last5`: trung bình thành tích của đội qua 5 race trước, tổng hợp đội theo race trước khi tính rolling.
- `team_points_before_race`: điểm tích lũy đúng trước race, reset theo mùa; cần quy tắc Sprint/án phạt nếu tái dựng điểm chính thức.
- `teammate_quali_gap_history`: chênh lệch với đồng đội ở các chặng trước có dữ liệu so sánh hợp lệ; là proxy, không là kỹ năng thuần túy.
- Đường đua, đội, vòng trong mùa, số người tham dự theo danh sách đã biết ở cutoff.
- Thống kê nhiệt độ/mưa Q nếu có và chứng minh thêm giá trị.

Tính toán mọi thống kê chỉ dùng nguồn trước cutoff. Với rolling lịch sử cần loại chặng hiện tại trước khi lấy trung bình; thường là sắp theo thời gian rồi `shift(1)` trước rolling trong từng nhóm. Thống kê cấp đội phải shift theo **chặng**, không shift tùy tiện từng dòng tay đua khiến thành tích đồng đội cùng race lọt vào.

Tên tay đua không phải con số để đưa trực tiếp vào Linear Regression. Bản đầu ưu tiên các thống kê lịch sử và ít biến danh mục; dùng one-hot encoding có xử lý danh mục mới. ID lưu để JOIN/hiển thị; việc thêm ID vào model phải là thí nghiệm riêng để kiểm tra ghi nhớ danh tính.

Rookie/đội mới: giữ cờ thiếu lịch sử và số mẫu, dùng giá trị thay thế học trên training. Không lấy thành tích tương lai để bù; không tự gán đội mới kế thừa toàn bộ thành tích đội cũ nếu chưa có chính sách rõ ràng.

## 6. Làm sạch dữ liệu

Làm sạch cấu trúc trước khi nạp dữ liệu sạch: chuẩn hóa khóa, kiểu dữ liệu, đơn vị giây, UTC, kiểm tra trùng và miền giá trị. Điền thiếu/scale/encoding phục vụ ML thực hiện sau khi chia tập và fit trên training của từng fold.

Quy tắc đề xuất:

- Trùng: kiểm tra theo khóa nghiệp vụ session + driver, hoặc session + driver + lap; xung đột nội dung cần log, không tùy tiện giữ dòng đầu.
- Thiếu label race: không tự điền đáp án. Giữ ở vùng cách ly và thống kê coverage; dataset train chỉ nhận chặng đáp ứng quy tắc nhãn đã chốt.
- Thiếu Q2/Q3 do không vượt qua vòng: đây là thiếu có ý nghĩa, không bằng 0 giây. Thêm cờ đã vào Q2/Q3 nếu dùng các cột này.
- Thiếu số: median training và missing indicator, hoặc cách xử lý native của thuật toán được cấu hình rõ. Đừng dùng median cả dataset.
- Thiếu danh mục: nhóm `unknown`; danh mục mới ở test không làm pipeline lỗi.
- Dữ liệu ngoài miền hợp lý: cách ly và kiểm tra nguồn. Hạng 0/âm không tự biến thành người về nhất.
- Vòng chậm do pit, in/out lap, safety car, mưa, cờ đỏ: không coi tất cả là lỗi. Nếu tính pace, lọc theo bối cảnh, cờ chính xác, track status và loại lốp; báo số lap còn lại. Chỉ làm phần pace nâng cao khi kịp thời gian.
- Phân phối lệch: không tự xóa điểm dữ liệu thật. Cân nhắc biến đổi log cho đại lượng dương phù hợp, hoặc mô hình cây; mọi ngưỡng clipping phải học từ training.
- Chuẩn hóa: numeric scaling cho Linear/Ridge; mô hình cây không bắt buộc. Dùng Pipeline để train và dự đoán áp dụng cùng quy trình.

“Dữ liệu lệch” có hai nghĩa: phân phối số có đuôi dài, và lớp hiếm trong classification. Với podium, số người không podium lớn hơn: xem precision/recall, class weight và ngưỡng chọn từ validation. Không SMOTE trước chia thời gian, không bắt buộc cân bằng một cách máy móc.

### DNF, DNS, DSQ

Không xóa mọi DNF vì đây là một phần của kết quả race thực tế. Dùng thứ hạng số từ nguồn khi nguồn cung cấp và kiểm tra được; lưu riêng trạng thái DNF/DNS/DSQ cùng giá trị phân loại gốc. Không ép tất cả DNF về cùng một hạng cuối.

Phạm vi chính: dự đoán thứ tự theo kết quả nguồn trên tập tay đua tham dự được xác định trước race. Chính sách xử lý DNS/DSQ hoặc thiếu thứ hạng phải được chốt sau khảo sát một số phiên: giữ raw, gắn cờ, và loại chặng không đủ nhãn khỏi metric thứ hạng đầy đủ nếu chưa có quy tắc nhất quán. Báo số chặng bị loại và sai lệch chọn mẫu có thể gây ra. Không âm thầm dựa vào danh sách người finish để quyết định ai được dự đoán.

## 7. Thiết kế MySQL

CSDL chuẩn hóa để quản lý dữ liệu; bảng feature phi chuẩn hóa để phục vụ ML. Hai phần có mục đích khác nhau. Có thể chưa lưu từng lap vào MySQL ở bản tối thiểu, nhưng bảng dưới đây là thiết kế đích.

- `drivers`: định danh và thông tin hiển thị tay đua.
- `teams`: định danh đội và tên hiển thị; alias/lịch sử đổi tên khi cần.
- `circuits`: định danh đường đua, tên, địa điểm.
- `races`: năm, vòng, đường đua, lịch giờ UTC; unique mùa + vòng.
- `entries`: race + driver + team, danh sách tham dự và nguồn/thời điểm snapshot. Giải quyết tay đua đổi đội.
- `sessions`: race + loại phiên + thời điểm, unique race + loại phiên.
- `session_results`: session + entry, Q times hoặc race position, trạng thái và điểm. Ràng buộc entry phải thuộc race của session qua FK ghép hoặc kiểm tra giao dịch.
- `weather_observations`: session + thời điểm quan sát, các giá trị thời tiết.
- `laps` (mở rộng): session + entry + số vòng, thời gian, lốp, cờ chất lượng.
- `ingestion_runs`: phiên nào tải, trạng thái, phiên bản nguồn, số dòng, đường dẫn raw, lỗi.
- `feature_snapshots`: race + entry + cutoff + phiên bản feature, các cột đầu vào và nguồn truy vết. Tách label khỏi allowlist feature.
- `model_runs`: thuật toán, tham số, cutoff training, tập validation/test, seed, phiên bản thư viện và đường dẫn artifact.
- `predictions`: model run + feature snapshot, score và rank; unique tránh ghi trùng.
- `evaluation_metrics`: model run + tập/fold/race + tên metric + giá trị.

Với phạm vi một tuần, triển khai bảng thiết yếu trước; `laps` và metadata chi tiết có thể để file raw. Không cố làm tất cả schema nâng cao trước khi có luồng dự đoán chạy.

Nội dung để trình bày môn CSDL:

- ERD và quan hệ 1–n/n–n thông qua entries.
- PK/FK/UNIQUE/NOT NULL/CHECK phù hợp phiên bản MySQL.
- Chuẩn hóa để tránh lặp tên đội/tay đua ở mọi dòng.
- Index theo mùa/vòng, driver/race, model/race; minh họa EXPLAIN trên truy vấn thật.
- JOIN để xem dự đoán, thực tế, tên tay đua và đội.
- GROUP BY để thống kê phong độ đội; window function cho lịch sử nếu phù hợp.
- View đối chiếu dự đoán và kết quả; CRUD quản lý lần chạy/ghi chú dữ liệu, không sửa đáp án để cải thiện metric.
- Import một phiên trong transaction; lỗi giữa chừng rollback. Chạy lại không sinh bản ghi trùng, giữ phiên bản snapshot ở nơi thích hợp.
- Cấu hình DB bằng biến môi trường, không commit mật khẩu; export/restore database mẫu để demo.

Stored procedure/trigger chỉ bổ sung khi rubric yêu cầu hoặc có nghiệp vụ cụ thể. Không thêm để đủ số lượng rồi không giải thích được vai trò.

## 8. Các mô hình sẽ thử

Baseline là mốc so sánh đơn giản, không phải tên một mô hình phức tạp:

1. Xếp thứ tự race giống thứ tự Q.
2. Xếp theo hạng trung bình 5 race trước, fallback rõ ràng khi thiếu lịch sử.

Bốn mô hình chính:

1. **Linear Regression:** mốc ML dễ giải thích, giả định quan hệ tuyến tính. Ridge là biến thể thêm regularization để hạn chế hệ số quá lớn; có thể thử thay thế khi cần.
2. **Random Forest Regressor:** kết hợp nhiều cây quyết định; học quan hệ phi tuyến và tương tác.
3. **HistGradientBoosting Regressor:** boosting trong scikit-learn; các bước sau học sửa sai của các bước trước.
4. **CatBoost Regressor:** lựa chọn boosting để so sánh trên dữ liệu dạng bảng; cấu hình xử lý danh mục/thiếu rõ ràng.

Giữ cùng thông tin đầu vào, cùng tập chia, cùng metric. Có thể preprocessing khác theo yêu cầu thuật toán nhưng không cho model nào thông tin tương lai. Tuning nhỏ có giới hạn số thử và thời gian. Nếu CatBoost gặp cài đặt kéo dài, dùng ExtraTrees Regressor thay, ghi quyết định; không mất cả ngày cho một thư viện.

Không chọn sẵn Random Forest/CatBoost là “tốt nhất”. Chỉ kết luận mô hình nào tốt hơn sau thí nghiệm. Nếu baseline Q thắng, trình bày thẳng kết quả và sử dụng baseline làm lựa chọn triển khai hợp lý; đồ án vẫn có giá trị phương pháp.

## 9. Đánh giá đúng bài toán

Chốt trước metric chọn model: **MAE của thứ hạng sau sắp xếp, tính mỗi race rồi lấy trung bình các race validation**. Spearman là tiêu chí phụ; ưu tiên mô hình đơn giản hơn nếu chênh lệch không đáng kể và kết quả ổn định.

- MAE rank: sai trung bình bao nhiêu bậc. Ví dụ minh họa MAE = 2 nghĩa là trung bình lệch 2 bậc, không có nghĩa chính xác 98%.
- RMSE rank: nhạy hơn với các sai lệch lớn, cho thấy có dự đoán sai rất xa hay không.
- Spearman theo race: độ phù hợp giữa hai thứ tự; cao hơn tốt hơn. Trường hợp không tính được ghi null và báo số race hợp lệ.
- Winner hit rate: tỷ lệ race dự đoán đúng người hạng 1.
- Podium overlap@3: số người trùng giữa hai nhóm podium chia 3, lấy trung bình theo race; không yêu cầu đúng vị trí trong podium.
- Exact podium order rate: tỷ lệ race đúng cả 3 vị trí podium, khắt khe hơn overlap.
- Top-10 overlap: mức trùng hai nhóm top 10, nếu N đủ; không tự đồng nhất top 10 với số người được điểm ở mọi trường hợp đặc biệt.
- Raw MAE/RMSE và R² trên đầu ra hồi quy liên tục: thông tin bổ sung để phân tích model; ghi rõ khác metric của rank sau sắp xếp. R² có thể âm, không là phần trăm dự đoán đúng.
- Thời gian train/inference và tỷ lệ feature thiếu: đánh giá khả năng demo và vận hành.

Không cần nhồi mọi metric. F1-score phù hợp bài toán có nhãn lớp như podium/non-podium; không trực tiếp dùng F1-score cho giá trị dự đoán 4,7. Nếu mở rộng classification: precision, recall, F1, confusion matrix; ROC-AUC/PR-AUC cho score phù hợp; log loss/Brier và calibration khi công bố xác suất. Ngưỡng chọn trên validation. Fold chỉ có một lớp cần ghi metric không xác định. Accuracy riêng lẻ có thể gây hiểu nhầm với lớp hiếm.

Metric phải ghi số race và số tay đua thực sự được đánh giá. Lưu sai số mỗi race; xem cả chặng tốt và tệ thay vì chọn vài ví dụ đẹp. Nếu có thời gian, bootstrap theo race để ước lượng khoảng biến thiên, không coi các tay đua trong cùng race là quan sát độc lập.

## 10. Chia dữ liệu, backtest và 2026

Không chia random các dòng tay đua. Chia theo ngày race và giữ nguyên toàn bộ tay đua của một race ở cùng fold. Không dùng TimeSeriesSplit trực tiếp trên từng dòng nếu nó cắt ngang một race.

Thiết kế đề xuất, điều chỉnh theo coverage:

1. Train 2022–2023 → validation 2024.
2. Train 2022–2024 → validation 2025.
3. Chọn feature/siêu tham số bằng hai fold validation; có thể chia các block race nhỏ hơn nếu cần.
4. Refit cấu hình đã chọn trên 2022–2025.
5. Đánh giá các race 2026 đã hoàn thành, chưa dùng để chọn cấu hình; chỉ đưa vào các race đủ dữ liệu theo quy tắc đã công bố.

Khi đánh giá tuần tự 2026, kết quả một race đã diễn ra được phép góp vào rolling feature cho race sau. Nếu cập nhật model sau từng race thì đó là một giao thức walk-forward riêng: dự đoán và lưu trước, mới bổ sung đáp án và refit; quy tắc cập nhật được chốt trước và không chọn lại thuật toán theo test. Phân biệt báo cáo model đóng băng với báo cáo model cập nhật.

Nếu sau khi xem test 2026 ta thay model/feature theo kết quả đó, phải gọi 2026 là dữ liệu phát triển và dành một block muộn hơn làm holdout mới. Không tiếp tục gọi cùng dữ liệu là test độc lập.

2026 có thay đổi lớn về quy định kỹ thuật. Vì vậy quan hệ sức mạnh đội của các mùa cũ có thể giảm độ phù hợp. Đề xuất thử cửa sổ lịch sử ngắn/dài trên validation, coi thông tin Q hiện tại là tín hiệu quan trọng, và báo cáo 2026 riêng. Thêm cột `is_2026` đơn thuần không giải quyết được vấn đề nếu training không có biến thiên đó.

Hạn chế phải nêu: dữ liệu race ít, tay đua/đội phụ thuộc lẫn nhau, DNF và chiến thuật khó biết trước, dữ liệu sửa sau cuộc đua, thời tiết tương lai thiếu nguồn, thay đổi luật. Không hứa một mức độ chính xác khi chưa chạy.

## 11. Web demo

Thiết kế năm trang hoặc tab:

1. **Tổng quan:** câu hỏi dự đoán, cutoff, số mùa/race thực sự có dữ liệu, phiên bản model và thời điểm cập nhật.
2. **Khám phá dữ liệu:** lọc mùa/tay đua/đội; biểu đồ phong độ lịch sử, Q so với R, phân phối và thiếu dữ liệu. Ghi đơn vị, nguồn, phạm vi thời gian.
3. **Dự đoán:** chọn race; kiểm tra Q và lịch sử; hiển thị rank, tên, đội, score và một số feature giúp giải thích. Chưa có kết quả R thì không hiển thị metric giả.
4. **Đối chiếu lịch sử:** dự đoán ngoài mẫu so với thực tế bằng biểu đồ nối hai thứ hạng; highlight sai lệch và các chỉ số từng race. Phân biệt backtest với dự đoán tương lai.
5. **So sánh mô hình và phương pháp:** baseline, metric validation/test tách biệt, thời gian, tập dữ liệu; mô tả leakage và feature importance.

Feature importance ưu tiên permutation importance trên validation theo protocol đã chốt. Nó biểu thị mức mô hình phụ thuộc vào feature, không chứng minh quan hệ nhân quả; feature tương quan có thể chia sẻ mức quan trọng. SHAP là mở rộng nếu kịp.

Không hiển thị “xác suất thắng 85%” nếu chỉ có mô hình hồi quy. Nếu slider thay đổi thời tiết/hạng Q được bổ sung, phải ghi là kịch bản giả định, không phải dữ liệu quan sát hay giải thích nhân quả.

## 12. Lộ trình 7 ngày triển khai

### Ngày 1 — Hiểu dữ liệu và kiểm tra nguồn

Học X/y, phiên Q/R, cutoff, cache. Chạy collector một chặng; lập data dictionary; kiểm tra các trường thiếu, ID và kết quả đặc biệt. Sau đó thu thập hàng loạt có log và coverage. Đầu ra: snapshot thật, manifest, quyết định phạm vi dữ liệu. Nếu nguồn lỗi, ưu tiên tập lịch sử truy cập được và ghi giới hạn; không trì hoãn cả pipeline để chờ đủ mọi mùa.

### Ngày 2 — CSDL và làm sạch

Vẽ ERD, tạo schema/MySQL, viết import idempotent và validation. Đầu ra: dữ liệu sạch truy vấn được, báo cáo thiếu/trùng, 3–5 truy vấn dùng trong demo. Hiểu vì sao cần FK và transaction.

### Ngày 3 — Feature và baseline

Tạo snapshot trước race; rolling lịch sử; chia tập theo race và thời gian. Chạy baseline Q và baseline phong độ trước khi train model phức tạp. Đầu ra: dataset feature, feature dictionary, baseline metrics. Đây là mốc bắt buộc để kiểm tra bài toán có làm đúng hay không.

### Ngày 4 — Huấn luyện và đánh giá

Chạy bốn model với preprocessing fit đúng fold, tuning nhỏ; lưu prediction/metric/artifact. Đầu ra: bảng so sánh có số thật, model được chọn bằng validation, kiểm tra 2026 theo protocol. Giải thích được vì sao chọn hoặc không chọn model phức tạp.

### Ngày 5 — Web

Ghép MySQL và model vào Streamlit; làm các trang bắt buộc, biểu đồ Plotly, export CSV. Đầu ra: một luồng từ chọn race đến dự đoán/đối chiếu chạy đầy đủ. Nếu thiếu thời gian, gộp các trang thành tab, giữ chức năng khoa học cốt lõi.

### Ngày 6 — Kiểm thử và nội dung báo cáo

Kiểm tra leakage, missing, đội/tay đua mới, pipeline save/load, DB import lần hai, web lỗi nguồn; viết kết quả/thảo luận/giới hạn từ số thật. Đầu ra: demo ổn định, ERD, ảnh giao diện và hướng dẫn cài.

### Ngày 7 — Chạy lại, đóng băng và bàn giao

Chạy quy trình trên môi trường sạch hoặc môi trường kiểm chứng, backup DB/model/dữ liệu demo, ghi phiên bản phụ thuộc, quay demo. Chọn một chặng dự đoán khá tốt và một chặng sai đáng kể để phân tích. Đầu ra: bản nộp tái lập được và tài liệu cho nhóm. Không thêm feature lớn vào ngày cuối.

## 13. Tuần hai: để cả nhóm hiểu và bảo vệ

- Ngày 8–9: các thành viên tự chạy demo; hiểu pipeline, X/y, cutoff, baseline và MAE.
- Ngày 10: mỗi người trình bày một phần dữ liệu, CSDL, ML hoặc web; người khác đặt câu hỏi.
- Ngày 11: hoàn thiện slide bằng số liệu thật, không chép toàn bộ mã vào slide.
- Ngày 12: chạy kịch bản đúng thời lượng, thử mất mạng và khôi phục DB/model.
- Ngày 13: bảo vệ thử, tập trung điểm yếu và vì sao các lựa chọn hợp lý.
- Ngày 14: rà bản nộp, nguồn, file, máy demo; chỉ sửa lỗi cần thiết.

Bạn phụ trách kỹ thuật chính, nhưng mỗi thành viên nên hiểu tối thiểu một dự đoán đi từ nguồn nào, vào bảng nào, thành feature nào, model xử lý ra sao và metric nào xác định sai đúng.

## 14. Kiểm thử quan trọng

- Thay đổi label tương lai không làm feature quá khứ thay đổi.
- Race hiện tại không góp vào rolling của chính nó; kiểm tra riêng cấp tay đua và đội.
- Không có race nằm đồng thời ở train và validation/test; mọi thời gian train trước fold cần dự đoán.
- Imputer/scaler/encoder không được fit từ validation/test.
- N tay đua đầu vào tạo N rank duy nhất; không hard-code 20; trường hợp bằng score có tie-break ổn định.
- Input thiếu lịch sử hoặc danh mục mới vẫn chạy đúng quy tắc; thiếu Q thiết yếu thì báo rõ.
- Metric kiểm tra bằng ví dụ tính tay; phân biệt rank và score, podium set và podium order.
- Nạp lại cùng phiên không tăng bản ghi ngoài dự kiến; transaction lỗi rollback.
- Model lưu rồi load cho dự đoán nhất quán trên snapshot cố định.
- Web dùng đúng model/feature version, không chọn model train sau ngày race rồi gọi đó là backtest.

## 15. Bộ tài liệu nộp và kịch bản demo

Nộp source, hướng dẫn môi trường, phụ thuộc đã khóa, schema SQL/ERD, dữ liệu demo phù hợp quyền sử dụng, model, báo cáo chất lượng dữ liệu, metrics thật, báo cáo học thuật, slide và video dự phòng. Raw cache lớn không cần đưa toàn bộ vào repository. Ghi nguồn, thời gian tải và hạn chế sử dụng/phân phối dữ liệu theo điều khoản nguồn.

Báo cáo nên trình bày: vấn đề → dữ liệu và phạm vi → CSDL → xử lý và feature → mô hình → giao thức đánh giá → kết quả → web → giới hạn và hướng phát triển. Không có kết quả trước thực nghiệm.

Demo khoảng 8–10 phút, chỉnh theo quy định giảng viên:

1. Nêu bài toán và mốc dự đoán bằng một ví dụ dễ hiểu.
2. Mở dữ liệu và chỉ một trường thiếu có ý nghĩa; cho thấy cách xử lý.
3. Mở ERD và truy vấn JOIN của dự đoán với tay đua/đội.
4. Chọn chặng lịch sử và hiển thị dự đoán ngoài mẫu, rồi đối chiếu kết quả.
5. So sánh model với baseline; giải thích MAE và lý do lựa chọn.
6. Cho xem chặng sai nhiều và phân tích hạn chế.
7. Nếu có race 2026 đủ Q nhưng chưa R tại lúc demo, dự đoán tương lai; nếu không, dùng backtest đã ghi nhãn rõ. Không giả lập một race là chưa đua trong khi gọi đó là dự đoán thật.

Các câu cần trả lời được: Vì sao dùng ML? Vì sao cần baseline? Vì sao không chia random? Vì sao không dùng thời tiết race đã xảy ra? Tại sao Q3 trống không điền 0? Khóa ngoại giải quyết gì? Vì sao chọn model? R² âm nghĩa gì? DNF xử lý ra sao? 2026 khác lịch sử thì model có đáng tin không? Nếu baseline thắng thì kết luận gì?

## 16. Nguồn kỹ thuật và thể thao

- [Mã nguồn FastF1 — cấu trúc Session và kết quả](https://github.com/theOehrly/Fast-F1/blob/master/fastf1/core.py): dùng kiểm tra các trường, load và khả năng thiếu dữ liệu. Website tài liệu FastF1 bị 403 ở lần khảo sát này, nên đã đối chiếu mã nguồn chính thức.
- [FastF1](https://github.com/theOehrly/Fast-F1): nguồn thư viện; xác minh khả năng tải từng phiên bằng thực nghiệm, không suy ra mọi chặng đều sẵn có.
- [scikit-learn: cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html): chia tập, chọn model và fit preprocessing trong training. Thiết kế chia theo cả race lẫn thời gian là lựa chọn áp dụng của dự án.
- [scikit-learn: metrics](https://scikit-learn.org/stable/modules/model_evaluation.html): tham khảo định nghĩa metric khi triển khai.
- [FIA: thay đổi quy định 2026](https://www.fia.com/news/fia-statement-amendments-2026-f1-regulations): bối cảnh thay đổi kỹ thuật; suy luận của đề cương là cần kiểm tra riêng khả năng tổng quát hóa sang 2026, không phải FIA xác nhận hiệu năng model.

## 17. Trạng thái thực hiện ban đầu

Đã tạo đề cương, README và script thực hành thu thập một phiên. Đã khảo sát máy có lệnh Python, MySQL và Docker; điều đó chưa chứng minh MySQL server hoặc Docker daemon đang chạy. Chưa cài dependency, chưa tải dữ liệu thật, chưa huấn luyện và chưa có web hoàn chỉnh. Bước thực hành tiếp theo là chạy bài 1, kiểm tra dữ liệu thực tế rồi mới chốt schema/feature bằng bằng chứng.
