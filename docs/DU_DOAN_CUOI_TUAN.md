# Dự đoán từng phiên trước cuối tuần F1

Cập nhật ngày 06/10/2026 giờ Việt Nam. Bản mới bổ sung trang **Toàn bộ cuối tuần** và bảy mục tiêu FP1, FP2, FP3, Q, SQ, S, R. Mỗi loại phiên được huấn luyện và chọn mô hình riêng; không dùng mô hình Race làm mô hình FP.

## Vì sao chặng ngày 4 tháng 10 chưa xuất hiện

Web cũ đọc artifact thí nghiệm ngày 29/09/2026 và dữ liệu đã tải tại thời điểm đó. Nó không tự thu thập dữ liệu sau mỗi race. Chặng mới Bahrain GP tại Malaysia ngày 04/10/2026 đã được bổ sung thành chặng 202616 qua lần refresh FastF1 ngày 06/10. Backtest Q → Race đã được chạy lại và vẫn giữ artifact cũ.

Nguồn đối chiếu lịch: https://www.formula1.com/en/racing/2026/bahrain

Sidebar hiện hiển thị ngày cập nhật dữ liệu 2026. Nút cập nhật trên trang cuối tuần tải lịch và kết quả Q/R vào MySQL; nó không tự tải toàn bộ FP/Sprint hoặc huấn luyện lại các thí nghiệm đã lưu. Các bước này có lệnh riêng bên dưới.

## Thời điểm dự đoán

Tất cả dự đoán trong trang mới dùng cùng mốc **một giây trước phiên đầu tiên của cuối tuần**, thường là trước FP1. Không sử dụng FP1, FP2, FP3, Q hoặc Sprint của chính chặng hiện tại làm feature, kể cả khi đang xem lại một chặng đã kết thúc.

Chế độ Q → Race vẫn tồn tại ở trang Dự đoán và đối chiếu như một thí nghiệm riêng có nhiều thông tin hơn. Không so trực tiếp hai MAE nếu số chặng, danh sách người tham dự và cách chia khác nhau; cần so trên cùng tập chặng trước khi kết luận chế độ nào tốt hơn.

Lịch phiên lấy từ FastF1. Một cuối tuần thông thường có FP1/FP2/FP3/Q/R; cuối tuần Sprint dùng đúng các phiên nguồn cung cấp, có thể có FP1/SQ/S/Q/R. Phiên không tồn tại trong lịch không xuất hiện trong lựa chọn. Không tạo FP2/FP3 giả cho Singapore Sprint.

## Mục tiêu và đặc trưng

FP dự đoán thứ tự theo vòng nhanh nhất có thời gian hợp lệ và không bị xóa. Bảng FP không phải race pace: lượng nhiên liệu, lốp và chương trình thử xe có thể khác nhau. Tay đua không có vòng hợp lệ có nhãn thiếu; chặng thiếu toàn bộ nhãn 1 đến N không được đánh giá full-grid.

Q/SQ dùng thứ hạng phân hạng; S/R dùng thứ hạng phiên từ nguồn. Việc dự đoán Q không đồng nghĩa đoán một thời gian vòng cụ thể hoặc từng vòng Q1/Q2/Q3. Bản này chưa ước lượng xác suất thắng hay khoảng tin cậy.

Đầu vào gồm phong độ lịch sử cùng loại phiên của tay đua/đội, phong độ Race lịch sử, lịch sử ở đường đua, số mẫu, vòng trong mùa và đội/đường đua. Thứ hạng lịch sử được quy đổi tương đối theo số người tham dự để xử lý khác biệt 20 và 22 tay đua. Chỉ sử dụng phiên có giờ bắt đầu cộng khoảng đệm 6 giờ trước cutoff. Khoảng đệm này là quy tắc kỹ thuật bảo thủ, không chứng minh thời điểm công bố chính thức.

Điền thiếu, scale và one-hot nằm trong pipeline fit trên train. Mô hình gồm Linear Regression, Random Forest, HistGradientBoosting và baseline phong độ phiên. Chọn theo MAE hạng trung bình từng chặng trên validation 2025, refit bằng dữ liệu trước 2026; sau đó đánh giá năm 2026. Lựa chọn được ghi trước khi tính metric test.

## Giới hạn dữ liệu và danh sách tay đua

Lịch sử Q/R lấy từ các mùa 2022–2025. Bộ FP/SQ/S hiện là mẫu các chặng 2024–2025, có số phiên ít hơn đáng kể. Web hiển thị số phiên train, validation và test riêng; không coi vài phiên test là bằng chứng độ chính xác ổn định. Có thể mở rộng bằng weekend-data.

Với chặng đã kết thúc, danh sách người tham dự được lấy hồi cứu từ phiên đích. Kết quả và thời gian vòng của phiên đó chỉ làm nhãn, không làm feature; tuy nhiên chưa có snapshot chứng minh danh sách người tham dự đã biết trước cutoff. Vì vậy đây là backtest với hạn chế về roster, chưa phải mô phỏng point-in-time tuyệt đối.

Với phiên tương lai chưa có danh sách, hệ thống tạm dùng danh sách Race gần nhất trước cutoff và ghi rõ nguồn này. Danh sách đó có thể không phản ánh thay đổi đội, tay đua dự bị hoặc tay đua FP. Cần bổ sung nguồn danh sách đăng ký có thời điểm phát hành để dự đoán phục vụ thực tế.

Sprint Qualifying có thể thiếu DriverId. Collector liên kết mã viết tắt với kết quả Q cùng sự kiện khi nguồn có duy nhất một đối chiếu; đây là bước chuẩn hóa định danh hồi cứu, không lấy kết quả Q vào X. Tay đua dự bị FP chưa có Ergast ID được giữ định danh live timing riêng. Không gán người dự bị vào ID của tay đua chính và không nhận chuỗi nan làm ID.

Nguồn tải hôm nay có thể đã sửa kết quả. Chưa có snapshot công bố lịch sử; collected_at không phải available_at. Đã xem kết quả 2026 trong quá trình phát triển, nên đánh giá mới năm 2026 là khám phá. Khi điều chỉnh theo các kết quả này, cần holdout muộn hơn đã chốt trước cho nghiên cứu tiếp theo.

## Cách chạy

```bash
# Cập nhật lịch và kết quả lõi
.venv/bin/python -m f1lab ingest --years 2026 --refresh

# Mở rộng các phiên lịch sử; cache và các phiên ready giúp chạy tiếp
.venv/bin/python -m f1lab weekend-data --years 2024 2025 2026

# Có thể giới hạn theo chặng hoặc phiên
.venv/bin/python -m f1lab weekend-data --years 2026 --rounds 16 --kinds FP1 FP2 FP3 Q R

# Huấn luyện và chọn riêng từng loại phiên
.venv/bin/python -m f1lab weekend-train --test-year 2026

# Dự đoán Race trước cuối tuần, không dùng Q hiện tại
.venv/bin/python -m f1lab weekend-predict --session 202616-R

# Phiên Sprint tương lai
.venv/bin/python -m f1lab weekend-predict --session 202617-S

# Web
.venv/bin/python -m streamlit run app.py --server.port 8501
```

Mở http://127.0.0.1:8501/?page=weekend, chọn mùa/chặng/phiên và bấm Dự đoán và lưu phiên. Chặng 202616 có FP1/FP2/FP3/Q/R để đối chiếu thật; 202617 có SQ và S để demo khi chưa có nhãn. Các dự đoán vừa tạo sau sự kiện được ghi là hồi cứu, không được trình bày như đã dự đoán từ trước.

## OOP và MySQL

WeekendCollector thu thập và chuẩn hóa; WeekendRepository truy cập MySQL; WeekendFeatureBuilder tạo X; WeekendFormModel/WeekendRegressionModel triển khai RaceModel; WeekendTrainer điều phối chọn model; WeekendPredictionService tạo và lưu dự đoán. Network được đọc tối đa ba luồng; việc ghi CSDL theo từng phiên diễn ra tuần tự trong transaction.

Bổ sung weekend_sessions, weekend_results, weekend_runs, weekend_predictions với khóa ngoại và ràng buộc. Run lưu cutoff, artifact, nguồn danh sách; prediction lưu feature snapshot, score, rank và nhãn khi có. Backup mang các bảng mới; restore vẫn nhận backup v1 trước khi có bốn bảng này. Bundle mang cả artifact Q → Race và artifact từng phiên mới nhất.

## Kiểm chứng

Kiểm thử bao gồm thay đổi mọi kết quả FP/Q/R hiện tại và tương lai nhưng X không đổi; xử lý đội mới/tay đua thiếu lịch sử; loại vòng bị xóa; ánh xạ ID SQ và người dự bị; huấn luyện riêng từng phiên; từ chối model học sau cutoff; dự đoán tương lai không có nhãn; đổi chặng trên web; không phát sinh FP2/FP3 cho Sprint weekend. Đã tạo và lưu dự đoán thật cho cả bảy loại phiên với bảng 22 hạng không trùng.
