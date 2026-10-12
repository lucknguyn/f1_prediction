# Đánh giá toàn diện F1 Lab ngày 12 tháng 10 năm 2026

## Kết luận

Dự án đã đạt mức một bài tập lớn tích hợp có nội dung khá đầy đủ: Python, hướng đối tượng, MySQL, thống kê, phân cụm, ML và web đều có triển khai. Điểm mạnh là quy trình dữ liệu có kiểm thử, so sánh baseline và đánh giá theo thời gian. Điểm yếu chính nằm ở vòng đời dự đoán sau khi cuộc đua kết thúc, kiểm tra chất lượng phiên, cập nhật lịch khi nguồn thay đổi và tính đầy đủ của bộ bàn giao.

Có thể dùng để demo học thuật với dữ liệu đã chuẩn bị và giải thích đúng giới hạn. Chưa nên trình bày là một hệ thống dự đoán F1 có độ chính xác cao hoặc một sản phẩm đã vận hành ổn định trên nhiều máy. Việc đánh giá này không thay thế thang điểm chính thức của giảng viên.

## Phương pháp và bằng chứng

- Đọc mã nguồn, đề bài F1, tài liệu đối chiếu, schema, CLI, giao diện và thí nghiệm đã lưu.
- Chạy bộ kiểm thử hiện có: 49 passed, 2 skipped, 10,71 giây. Hai test bị bỏ qua là test tạo/lưu dự đoán vào DB thật; không đồng nghĩa chúng đạt trong lần đánh giá này.
- Chạy riêng hai test giao diện đọc MySQL thật: 2 passed, 3,92 giây. Bốn trang render được; đã tắt tự đồng bộ và không bấm lưu dự đoán.
- Tạo ba tình huống tái hiện riêng trên SQLite/tập giả: cả ba tái hiện được hành vi thiếu sót được mô tả bên dưới. Đây là test chứng minh lỗi, không phải ba chức năng mới đã được sửa.
- Đọc MySQL thật, trạng thái sync và artifact; kiểm tra đường dẫn model trong backup so với ZIP.
- Dùng nguồn F1 chính thức để đối chiếu độ mới của lịch/kết quả. Không sửa dữ liệu hoặc mô hình của ứng dụng, không chạy ingest/train/sync trong cuộc đánh giá.
- Không cài lại toàn bộ trên máy mới và không chạy Docker; khả năng tái lập môi trường mới chưa được xác nhận.

Bằng chứng cấu trúc nằm ở deliverables/audit-2026-10-12.json. Kiểm thử cũ 51 passed ngày 06/10 là bằng chứng lịch sử, không được ghi thành kết quả mới của lần này.

## 1 Các yêu cầu Python

Thu thập và xử lý: đã có FastF1/Jolpica, snapshot, chuyển thời gian, giữ thiếu/DNF, kiểm tra trùng và tạo đặc trưng lịch sử. Thời tiết chỉ có 77 quan sát thuộc một phiên Q; là minh họa nguồn bổ sung, chưa đủ để học tác động thời tiết cho toàn mùa. Sức mạnh xe/kỹ năng hiện được biểu diễn gián tiếp qua thành tích đội/tay đua; không có phép đo độc lập chứng minh các đại lượng này.

Thống kê và EDA: có count/mean/median/std mẫu, nhóm đội/mùa, top/bottom, histogram, bảng hồ sơ tay đua và các file đầu ra. Một hạn chế của Q1/Q2/Q3 là thời gian vòng ở đường đua khác nhau không so sánh trực tiếp được; IQR toàn tập chỉ nên dùng để kiểm tra nguồn, không kết luận thời gian dài là bất thường về thành tích.

Phân cụm: KMeans có median/StandardScaler, nhiều giá trị k, inertia/silhouette và seed; PCA có phương sai giải thích. Mùa 2025 có 21 tay đua, k=3, silhouette khoảng 0,608; PCA2D khoảng 95,44% phương sai. Điều này chứng minh biểu diễn được hồ sơ thành tích, không chứng minh ba nhóm kỹ năng thực sự. n_races có thể khiến cụm phản ánh độ phủ tham dự. Nên thử bỏ n_races và kiểm tra độ ổn định cụm.

Radar: chuẩn hóa theo toàn bộ dân số cùng mùa, đảo chiều hạng/DNF, xử lý trục không biến thiên và kiểm tra tên. Hợp lý hơn chuẩn hóa chỉ giữa hai người. n_races phải tiếp tục được đọc như độ phủ; hình lớn hơn không tự động nghĩa là tay đua giỏi hơn.

OOP: Database, service, repository, RaceModel và các chiến lược thể hiện đóng gói, trừu tượng, kế thừa/đa hình. Đây là OOP thực sự, không chỉ đặt hàm vào một lớp. Các package cuối tuần đã tách trách nhiệm khá rõ. Điểm cần cải thiện là WeekendTrainer/PredictionService tạo trực tiếp nhiều dependency, nên kiểm thử phải gán lại thuộc tính; web.py vẫn khá lớn. Chưa cần làm thêm một framework hoặc nhiều lớp chỉ để tăng số lượng class.

## 2 Thiết kế CSDL

Điểm mạnh: 17 bảng có PK/FK/UNIQUE/CHECK; entries giữ lịch sử đội theo chặng; kết quả cốt lõi có FK ghép để bảo đảm phiên và người tham dự cùng chặng. Có view, nhật ký, snapshot, lịch sử run/metric và dự đoán. SQL demo có JOIN, GROUP BY, HAVING, subquery, window và EXPLAIN. Có bằng chứng lịch sử về rollback và restore trên MySQL thật.

JSON feature là lựa chọn snapshot hợp lý, nhưng phần giải thích 3NF trong tài liệu vẫn ở mức mô tả. Nên bổ sung khóa ứng viên và các phụ thuộc hàm cụ thể cho drivers/teams/races/entries/sessions/results nếu môn CSDL yêu cầu chứng minh chuẩn hóa.

Core sessions/results và weekend_sessions/results lưu trùng một phần Q/R. Tách giao thức là có lý do, nhưng phải quy định phiên bản nguồn và đồng bộ để tránh hai bảng chứa kết quả khác nhau. Ràng buộc hiện chưa bảo đảm thứ hạng duy nhất/toàn bộ 1..N trong một phiên; kiểm tra này cần thuộc về quy tắc dữ liệu ở service, không chỉ CHECK rank > 0.

Tài khoản f1 tách root và secrets bị loại khỏi ZIP. Tuy nhiên f1 có ALL PRIVILEGES trong schema và CLI initialize chạy trước cả lệnh đọc; phù hợp demo, chưa phải phân quyền production. Nên tách khởi tạo schema/migration khỏi chạy ứng dụng rồi giảm quyền tài khoản runtime nếu triển khai rộng.

## 3 Chất lượng ML

Giao thức đáng giữ: không chia random từng tay đua; chọn bằng validation trước test; preprocessing fit trên train; cùng đặc trưng/tập chia cho các ứng viên; biến điểm thành hoán vị 1..N. MAE/RMSE rank, Spearman, winner hit, podium và R² raw được giải thích đúng. F1-score không cần thêm khi chưa có mục tiêu phân loại.

Đối chứng sau Q trên 14 chặng/308 mẫu test 2026:

- Baseline Q: MAE 3,435; Spearman 0,681; winner hit 71,4%.
- Linear Regression: MAE 3,539.
- Random Forest: MAE 3,552.
- HistGradientBoosting: MAE 3,792.
- CatBoost: MAE 3,545.

Chọn Baseline Q là đúng với tiêu chí validation. Một mô hình hồi quy có R² raw cao hơn nhưng MAE rank kém hơn vẫn có thể xảy ra vì hai metric đo hai đầu ra khác nhau. Winner hit 71,4% không phải độ chính xác toàn bảng.

Trước cuối tuần, mô hình được chọn riêng theo loại phiên, test đã lưu:

- FP1: MAE 4,727 trên 3 phiên, baseline lịch sử.
- FP2: MAE 4,000 trên 1 phiên, baseline lịch sử.
- FP3: MAE 3,364 trên 1 phiên, HistGradientBoosting.
- Q: MAE 2,786 trên 16 phiên, baseline lịch sử.
- SQ: MAE 5,000 trên 1 phiên, Random Forest.
- Sprint: MAE 4,136 trên 2 phiên, baseline lịch sử.
- Race: MAE 4,358 trên 16 phiên; Spearman 0,565; đúng người thắng 1/16, baseline lịch sử.

Đây là kết quả của snapshot thí nghiệm, không bao gồm Singapore mới diễn ra. FP/Sprint có ít mẫu đến mức một kết quả tốt/xấu có thể chỉ phản ánh một cuối tuần. Không so sánh trực tiếp MAE 3,435 sau Q và 4,358 trước cuối tuần để đánh giá thuật toán: thời điểm đầu vào, phạm vi dữ liệu và số chặng khác nhau.

Có nguy cơ thông tin hồi cứu qua roster và field_size: quá khứ dùng người thực sự xuất hiện trong kết quả phiên; tương lai dùng roster Race gần nhất. Hai chế độ có thể khác tay đua dự bị/đổi đội/số người. Code không dùng trực tiếp nhãn hiện tại trong X, nhưng backtest chưa tái dựng đúng toàn bộ thông tin biết trước cutoff. Model không biết lượng nhiên liệu/chương trình thử xe nên FP khó diễn giải.

Đã xem test 2026, nên cần khóa một tập holdout mới trước các chặng tương lai. Nên báo khoảng tin cậy/bootstrap theo chặng, không coi 352 dòng tay đua là 352 quan sát độc lập. Học ranking theo cặp hoặc mục tiêu podium có thể là thí nghiệm mở rộng sau khi sửa tính đúng đắn; không bảo đảm sẽ tốt hơn.

## 4 Các thiếu sót đã xác nhận

### P2 A Chưa hoàn thành vòng đời đối chiếu dự đoán cũ

weekend_engine/repository.py:45 lưu actual_rank tại lúc dự đoán. save_session:31 chỉ thay bảng kết quả phiên; không cập nhật đối chiếu run cũ. web.py chỉ lấy đầu ra trong session_state sau khi bấm dự đoán, không có màn hình chọn run cũ. Người dùng dự đoán trước cuộc đua, đóng web, mở lại sau cuộc đua thì không xem được đối chiếu dự đoán ban đầu qua giao diện.

Đã tái hiện: lưu forecast có label NULL, nhập kết quả position=1; actual_rank của forecast vẫn NULL. CSDL hiện có 9 run Singapore với 198 dòng chưa có nhãn; nguồn cục bộ cũng chưa cập nhật Singapore, vì vậy chưa coi 198 dòng đó là bằng chứng đã có actual mà vẫn NULL. Lỗi cập nhật sau khi có actual được chứng minh ở tình huống riêng.

Khắc phục: giữ forecast bất biến, truy vấn JOIN dự đoán cũ với kết quả mới theo session/driver, có created_at/cutoff và phiên bản nguồn. Thêm bộ chọn run; phân biệt run được lưu trước cutoff với chạy hồi cứu. Không yêu cầu người dùng bấm dự đoán lại để xem một dự đoán cũ.

### P2 B ready chưa có nghĩa là thứ hạng hợp lệ

weekend_engine/collection.py:105 chỉ kiểm tra position khác NULL. Đã tái hiện hai người cùng position=1 vẫn nhận ready. SQL đọc thật phát hiện năm phiên Q ready có vị trí trùng hoặc không đủ hoán vị 1..N: 202310-Q, 202408-Q, 202415-Q, 202417-Q, 202507-Q.

FeatureBuilder loại các target không đủ điều kiện khi train/evaluate, nhưng lịch sử làm X ở weekend_engine/features.py:12 chỉ lọc thời gian và position notna; các phiên có rank không hợp lệ vẫn có thể góp vào phong độ. Vì vậy chưa thể nói mọi dữ liệu ready là sạch.

Khắc phục: một bộ kiểm tra dùng chung cho ingestion/status/target/history; kiểm tra duy nhất ID, rank dương/duy nhất, roster/độ phủ và thời gian vòng hợp lệ. Công bố chính sách NC/DNS/DSQ riêng, tránh tự bịa rank cho nguồn thiếu.

### P2 C Không loại phiên đã biến mất khỏi lịch nguồn

collection.py:43 duyệt phiên mới và merge, không vô hiệu hóa phiên cũ không còn trong nguồn. Đã tái hiện lịch đổi từ có FP3 sang Sprint: FP3 cũ vẫn trong repository; web đọc toàn bộ sessions sẽ tiếp tục hiển thị phiên thừa.

Khắc phục: lưu snapshot lịch/active flag, đối chiếu phiên hiện tại với lịch mới theo chặng; đánh dấu canceled/superseded và lọc menu. Không xóa lịch sử kết quả/dự đoán đã có.

### P2 D Bản ZIP không khép kín lịch sử model trong backup

delivery.py:172–178 chỉ thêm hai thí nghiệm latest vào ZIP, trong khi backup mang toàn bộ model_runs/weekend_runs. Đã đếm 19 đường dẫn artifact được backup tham chiếu nhưng không có trong ZIP: 18 model của thí nghiệm core cũ và một model Race cuối tuần cũ.

Model hiện hành vẫn đủ để chạy demo. Thiếu sót ảnh hưởng khả năng mở lại/tái lập lịch sử run trên máy khác. Khắc phục bằng cách đóng gói toàn bộ artifact được backup tham chiếu, hoặc tạo backup demo giới hạn các run phù hợp một cách minh bạch. Kiểm tra tham chiếu này trước khi coi bundle hoàn tất, không chỉ kiểm tra checksum các file đã có.

### P2 E Trạng thái lỗi nguồn và trạng thái dữ liệu đang có bị trộn

collect_one:110 trả unavailable khi refresh lỗi; save_session thay metadata dù rows=None giữ nguyên dữ liệu cũ. Phiên có kết quả tốt có thể mang unavailable; chi tiết rows/label_definition bị thay bằng error. Cần tách data_status, last_fetch_status và last_success, giữ nguồn cũ rõ ràng khi tải lỗi.

SyncWorker:96 bỏ qua returncode; timeout chỉ ghi log. Nếu lỗi trước SyncService hoặc process bị kill, sync_status có thể không phản ánh lỗi mới. Cần ghi trạng thái kết thúc thất bại từ worker và heartbeat để biết worker còn sống; không cần tăng số lần crawl liên tục.

## 5 Độ mới dữ liệu và vận hành

Lần đồng bộ thành công gần nhất được đọc là 07/10/2026 08:12 giờ Việt Nam. Đến ngày đánh giá 12/10, Singapore FP1/SQ/S/Q/R trong MySQL vẫn scheduled, không có kết quả. F1 chính thức đã công bố kết quả Race ngày 11/10: https://www.formula1.com/en/results/2026/races/1296/singapore/race-result.

Trong lúc đánh giá không có tiến trình lắng nghe cổng 8501. Đây phù hợp giới hạn đã ghi: worker dừng khi web dừng. Không đủ bằng chứng kết luận thuật toán sync chắc chắn hỏng, nhưng cho thấy cơ chế hiện tại không phải dịch vụ luôn cập nhật. Nên bổ sung cảnh báo stale rõ ràng và nút tải lại nguồn có tác dụng thực sự; nút Xem dữ liệu mới chỉ xóa cache và đọc lại DB, không gọi tải API ngay.

Nếu cần dữ liệu cập nhật khi web không mở, dùng lịch chạy của hệ điều hành/server hoặc một worker độc lập. Đây là lựa chọn triển khai thêm, không phải bắt buộc dùng một nền tảng cloud cho bài tập lớn.

Worker dùng fcntl nên hỗ trợ macOS/Linux, chưa chạy Windows theo cùng luồng. MySQL local helper cũng thiên về Unix; Docker có cấu hình nhưng chưa được chạy kiểm chứng. README cần nói rõ hệ điều hành/môi trường đã nghiệm thu để thành viên không bất ngờ lúc demo.

## 6 Kiểm thử và bàn giao

Các test hiện có tốt ở phép tính, leakage theo giá trị label, chia thời gian, model save/load, nhập transaction và smoke giao diện. Tuy nhiên chúng chưa bắt ba tình huống vừa tái hiện và thiếu trường hợp phục hồi lịch sử model từ ZIP, timeout worker, lịch sửa, source partial/ready và dự đoán trước cutoff được mở lại sau cuộc đua.

51 test không có nghĩa toàn bộ dự án đã đúng. Nên thêm test theo các hành vi người dùng cụ thể, tránh chỉ tăng số test mô phỏng hàm. Có thể thêm CI chạy unit test; live DB nên dùng schema/container thử, không ghi thêm run vào database demo mỗi lần kiểm thử.

Các file code/tài liệu trong ZIP đã đọc không có chênh lệch với workspace, ngoại trừ data/raw/2026/latest.json đã có snapshot mới. Bản sao lưu ZIP ngày 06/10 khác nhật ký DB hiện tại do đồng bộ sau đó; đây là snapshot đóng gói, không phải lỗi checksum. Báo cáo Word là snapshot được soạn sẵn, chưa có builder trong repo để tự tạo lại từ các số mới. Đề bài gốc của dự án vẫn có phần “chưa bổ sung KMeans/radar” dù tài liệu đối chiếu hiện hành đã nói hoàn thành; nên đánh dấu phần đó là kế hoạch lịch sử.

Schema dùng create_all, không có migration để đổi bảng sau khi triển khai. Với bài tập một phiên bản điều này chấp nhận được; nếu tiếp tục thay schema cần cơ chế migration thay vì kỳ vọng create_all tự sửa bảng cũ.

## 7 Thứ tự hoàn thiện đề xuất

1. Hoàn thành lưu và mở lại dự đoán trước cutoff, JOIN kết quả sau cuộc đua và đánh giá đúng run cũ.
2. Sửa validator phiên, lọc lịch sử không hợp lệ, đối chiếu lịch sửa và tách lỗi tải khỏi dữ liệu đã có; thêm test tái hiện.
3. Đồng bộ Singapore và kiểm tra trạng thái nguồn bằng luồng có giám sát; không thay model hoặc lựa chọn dựa trên chặng vừa xem.
4. Đóng gói đủ artifact được backup tham chiếu; nghiệm thu giải nén/cài/restore/demo từ thư mục/môi trường sạch.
5. Cập nhật báo cáo và tài liệu theo cùng snapshot; khóa holdout mới và mở rộng FP/Sprint trước khi cải tiến thuật toán.

Không cần ưu tiên thêm đăng nhập, thông báo, SHAP, nhiều thuật toán hoặc thiết kế web cầu kỳ trước các mục trên. Đầu tư vào tính đúng đắn và giải thích dễ hiểu có lợi trực tiếp cho bài tập Python/CSDL.

## Quyết định về khả năng nộp bài

Về khối lượng và phạm vi: đã đủ chất liệu cho một bài tập lớn có chất lượng. Về nghiệm thu: nên xử lý các thiếu sót P2 và kiểm tra bàn giao trước khi chốt bản nộp. Về ML: có quy trình thực nghiệm đáng trình bày, nhưng tuyên bố phù hợp hiện tại là “hệ thống nghiên cứu và demo dự đoán thứ hạng F1”, kèm độ phủ/sai số/giới hạn; chưa có bằng chứng cho tuyên bố “dự đoán tốt mọi phiên”.
