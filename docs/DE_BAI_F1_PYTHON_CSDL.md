# Đề xuất bài tập lớn Python và Cơ sở dữ liệu về F1

## Phân tích đề mẫu và định hướng đề F1

Đề mẫu yêu cầu xây dựng bài tập lớn bằng Python theo chuỗi thu thập dữ liệu, phân tích thống kê, phân cụm và đề xuất phương pháp ước lượng. Bản đề F1 dưới đây giữ mức độ và cấu trúc chấm điểm của môn Python, đồng thời bổ sung yêu cầu riêng cho môn Cơ sở dữ liệu. Đây là đề xuất để trao đổi với giảng viên, chưa phải đề đã được giảng viên phê duyệt.

### Những yêu cầu chính của đề mẫu

- Phần I có 4 điểm: thu thập nhiều nhóm thống kê cầu thủ từ FBref, lọc đối tượng, sắp xếp và xuất results.csv; dữ liệu thiếu được biểu diễn bằng N/a.

- Phần II có 2 điểm: tìm ba giá trị cao nhất và thấp nhất, tính trung bình, trung vị, độ lệch chuẩn toàn bộ và theo đội; xuất results2.csv và vẽ histogram.

- Phần III có 3 điểm: K-means, giải thích số cụm, PCA xuống hai chiều và chương trình radar so sánh hai cầu thủ qua tham số dòng lệnh.

- Phần IV có 1 điểm: thu thập giá trị chuyển nhượng và đề xuất cách ước lượng. Sản phẩm nộp gồm project web hoặc tích hợp học máy và báo cáo Word.

### Cách chuyển sang chủ đề F1

Đối tượng phân tích đổi từ cầu thủ sang tay đua trong từng chặng. Đội bóng đổi thành đội đua; thống kê thi đấu đổi thành kết quả phân hạng, thành tích lịch sử và các chỉ số phong độ. Phân cụm giúp khám phá nhóm có đặc điểm tương đồng; mô hình dự đoán có giám sát dùng để ước lượng thứ hạng đua chính.

K-means không thay thế mô hình dự đoán thứ hạng. Điểm cụm chỉ mô tả sự tương đồng trong bộ đặc trưng, không tự chứng minh tay đua giỏi hoặc xe mạnh. Các chỉ số phong độ là đại diện quan sát được, chịu ảnh hưởng của nhiều yếu tố.

### Những điểm cần làm rõ

Đề mẫu dùng mùa 2024–2025 ở phần thu thập nhưng dùng 2023–2024 ở một số yêu cầu sau. Bản F1 thống nhất lịch sử 2022–2025 và các chặng 2026 có dữ liệu tại ngày chốt. Quy định nhóm 10 người và hạn 30/10/2026 thuộc đề mẫu; cần xác nhận việc áp dụng cho đề tài F1, không tự coi là yêu cầu mới của hai môn.

## Đề bài Python về phân tích và dự đoán F1

### Tên đề tài và mục tiêu

Xây dựng hệ thống phân tích dữ liệu và dự đoán thứ hạng đua chính Formula 1 mùa giải 2026 bằng Python, tích hợp MySQL và ứng dụng web.

Người dùng chọn một chặng có kết quả phân hạng Q. Hệ thống tạo dự đoán sau Q và trước đua chính R; với chặng đã kết thúc, hệ thống đối chiếu dự đoán với kết quả thực tế. Đầu ra là thứ tự tay đua trong cùng chặng, không phải xác suất thắng.

Phạm vi lịch sử: 2022–2025 để xây dựng và kiểm chứng phương pháp; năm 2026 để đánh giá hồi cứu hoặc trình diễn dự đoán các chặng đã có Q. Ghi ngày chốt dữ liệu, số chặng tải được và số chặng bị loại. Không yêu cầu kết quả của chặng chưa diễn ra.

### Phần I Thu thập và xử lý dữ liệu 4 điểm

- Thu thập qua FastF1 và nguồn kết quả mà FastF1 truy cập: lịch mùa giải, chặng, đường đua, tay đua, đội tại mỗi chặng, kết quả Q và R. Có lưu dữ liệu gốc, cache và nhật ký lỗi. 1,5 điểm.

- Dữ liệu tối thiểu gồm mã mùa/chặng/tay đua/đội/đường đua, thời gian chặng, hạng Q, thời gian Q1/Q2/Q3 khi có, hạng R, điểm và trạng thái hoàn thành. Thu thập thời tiết Q cho ít nhất một phiên để minh họa nguồn bổ sung; công bố độ phủ, không bắt buộc đưa vào mô hình. 0,5 điểm.

- Chuẩn hóa mã, thời gian UTC, đơn vị giây, kiểu dữ liệu; kiểm tra trùng, giá trị ngoài miền và thiếu. Không tự điền nhãn R. Q2/Q3 thiếu do không tham gia không được đổi thành 0 giây; không xóa mọi tay đua bỏ cuộc. Nêu cách xử lý từng trường hợp. 1 điểm.

- Tạo bảng đặc trưng với mỗi dòng là một tay đua/chặng: hạng Q, chênh lệch Q hợp lệ, phong độ các chặng trước, tỷ lệ bỏ cuộc lịch sử, phong độ đội, thành tích đường đua và số mẫu lịch sử. Không sử dụng kết quả R hiện tại làm đầu vào. 0,5 điểm.

- Xuất results.csv, data_dictionary.csv và quality_report.json. Sắp theo mùa, vòng và mã tay đua; ghi rõ đơn vị, nguồn và quy tắc thiếu. CSV có thể biểu diễn thiếu bằng N/a; trong Python dùng giá trị thiếu và trong MySQL dùng NULL. 0,5 điểm.

Nêu rõ thời tiết Q là quan sát của Q. Thời tiết thực tế R, chiến thuật R và grid cuối cùng lấy từ kết quả R không được đưa vào dự đoán trước R nếu chưa chứng minh chúng đã được công bố trước thời điểm dự đoán.

## Thống kê và phân cụm trong môn Python

### Phần II Thống kê và trực quan hóa 2 điểm

- Với mỗi thuộc tính số có ý nghĩa, tính mean, median, std và số quan sát hợp lệ cho toàn bộ dữ liệu, theo đội và theo mùa. Xuất results2.csv theo dạng mỗi dòng là nhóm và thuộc tính, gồm group_type, group_id, season, attribute, count, mean, median, std. Thống nhất cách tính std mẫu. 0,5 điểm.

- Tìm ba bản ghi cao nhất và thấp nhất của từng thuộc tính số, kèm tay đua, chặng và mùa. Với đánh giá phong độ tay đua, bổ sung bảng tổng hợp theo tay đua/mùa và số chặng; không chỉ chọn một cuộc đua may mắn. 0,5 điểm.

- Vẽ histogram toàn bộ và theo đội cho các thuộc tính số được chọn bằng bộ lọc, loại các mã định danh. Ghi đơn vị, khoảng thời gian, số mẫu và quy tắc xử lý thiếu; xuất biểu đồ khi cần. 0,5 điểm.

- Nhận xét đội có phong độ tốt theo các tiêu chí cụ thể như điểm trung bình, hạng trung bình và tỷ lệ bỏ cuộc; phân biệt hạng thấp là tốt với điểm cao là tốt. Không dùng một tiêu chí để kết luận sức mạnh xe thuần túy. 0,5 điểm.

### Phần III K means PCA và radar 3 điểm

- Tạo bảng tổng hợp tay đua/mùa từ một mùa lịch sử đã chốt; tối thiểu có hạng Q trung bình, hạng R trung bình, điểm trung bình, tỷ lệ bỏ cuộc và số chặng. Chỉ đưa các thuộc tính định lượng có ý nghĩa vào K-means, không đưa tên hoặc mã ID. 0,5 điểm.

- Xử lý thiếu và chuẩn hóa trước K-means. Thử ít nhất ba giá trị k phù hợp số mẫu, dùng elbow và silhouette để giải thích lựa chọn; lưu seed, số mẫu và các trường hợp không tính được metric. Số mẫu ít là giới hạn phải thảo luận. 1 điểm.

- Dùng PCA giảm bộ đặc trưng đã chuẩn hóa xuống hai chiều để vẽ cụm; báo cáo tỷ lệ phương sai giải thích của hai thành phần. Mô tả từng cụm bằng tâm cụm hoặc thống kê gốc; không gọi mã cụm là thứ hạng. 0,5 điểm.

- Viết radarChartPlot.py nhận --p1, --p2, --season và --Attribute. So sánh hai tay đua trong cùng mùa trên các thuộc tính đã chuẩn hóa chung. Ghi chiều tốt/xấu của mỗi trục, xử lý tên không tồn tại và xuất hình. Ví dụ thuộc tính: quali_mean, race_mean, points_mean, dnf_rate. 1 điểm.

Phân cụm là phân tích khám phá riêng. Không sử dụng trực tiếp kết quả tổng hợp cả mùa 2026 làm đặc trưng cho dự đoán một chặng đầu mùa 2026 vì sẽ chứa thông tin tương lai.

## Dự đoán và sản phẩm nộp môn Python

### Phần IV Dự đoán thứ hạng đua chính 1 điểm

- Xây dựng ít nhất ba mô hình thông dụng gồm Linear Regression, Random Forest và một mô hình boosting; so sánh với baseline dùng hạng Q. Các phương pháp dùng cùng tập dữ liệu và cách chia theo thời gian. 0,25 điểm.

- Chia train và validation theo các mùa lịch sử; toàn bộ tay đua một chặng phải cùng tập. Điền thiếu, chuẩn hóa và mã hóa chỉ fit trên train. Chọn mô hình bằng validation trước khi xem test, lưu quy tắc lựa chọn và phiên bản dữ liệu. 0,25 điểm.

- Sắp điểm dự đoán trong mỗi chặng thành hạng 1 đến N, có quy tắc phá hòa. Báo cáo MAE và RMSE của hạng, Spearman theo chặng, tỷ lệ đúng người thắng và tỷ lệ trùng nhóm podium; giải thích cách tổng hợp. Có thể báo cáo R² của đầu ra hồi quy riêng. Không dùng F1-score cho thứ hạng nếu chưa định nghĩa một bài toán phân loại. 0,25 điểm.

- Lưu mô hình và dự đoán; demo đối chiếu trên chặng đã đua, phân tích một trường hợp sai số thấp và một trường hợp sai số cao. Baseline thắng ML vẫn là kết quả hợp lệ nếu quy trình đúng và báo cáo trung thực. 0,25 điểm.

### Tổ chức chương trình theo OOP

Tách lớp thu thập, xây dựng đặc trưng, truy cập CSDL, huấn luyện, đánh giá và giao diện. Có lớp trừu tượng cho mô hình với fit và predict, các triển khai thay thế được cho nhau; giải thích đóng gói, trừu tượng, kế thừa và đa hình bằng chính code. Đây là yêu cầu tổ chức chung, không cộng thêm điểm ngoài thang 10.

### Sản phẩm bắt buộc

- Mã nguồn, môi trường phụ thuộc và hướng dẫn chạy từ máy mới; cấu hình mẫu không chứa mật khẩu thật.

- Dữ liệu xuất, từ điển dữ liệu, báo cáo chất lượng, biểu đồ EDA, kết quả cụm/PCA/radar và bảng so sánh mô hình.

- Web Python có trang dữ liệu, thống kê, phân cụm, so sánh tay đua, dự đoán và đối chiếu. Có thể dùng Streamlit; demo dùng dữ liệu và mô hình đã lưu để tránh phụ thuộc mạng.

- Báo cáo Word trình bày bài toán, dữ liệu, OOP, phương pháp, kết quả thực tế, giới hạn, CSDL và hướng dẫn demo. Không điền kết quả mô hình giả.

### Lưu ý khi đánh giá năm 2026

Nếu đã dùng kết quả test 2026 để điều chỉnh mô hình, coi phần đó là dữ liệu phát triển và dành các chặng muộn hơn làm holdout mới, hoặc mô tả rõ là đánh giá khám phá. Nếu nguồn tải hồi cứu có sửa kết quả sau chặng, công bố hạn chế về thời điểm thông tin; không khẳng định backtest tái dựng tuyệt đối dữ liệu đã biết trước race.

## Đề bài Cơ sở dữ liệu cho hệ thống F1

Sử dụng cùng hệ thống F1 làm sản phẩm tích hợp. Thang điểm CSDL dưới đây là đề xuất riêng trên 10 điểm vì đề mẫu chỉ quy định phần Python; cần giảng viên môn CSDL xác nhận trước khi dùng làm tiêu chí chấm chính thức.

### Phần I Phân tích nghiệp vụ và thiết kế 2 điểm

- Mô tả nghiệp vụ thu thập chặng, tay đua đổi đội, phiên Q/R, dự đoán và đánh giá. Vẽ ERD, xác định lực lượng quan hệ, khóa chính, khóa ngoại và khóa nghiệp vụ. 1 điểm.

- Trình bày chuẩn hóa đến 3NF cho các bảng nghiệp vụ cốt lõi. Giải thích bảng tham dự chặng để ghi đội của tay đua tại từng chặng; giải thích snapshot đặc trưng như dữ liệu phục vụ tái lập. 1 điểm.

### Phần II Cài đặt schema và ràng buộc 2 điểm

- Cài đặt MySQL với các nhóm bảng tay đua, đội, đường đua, chặng, tham dự, phiên, kết quả, nhật ký thu thập, snapshot, lần chạy mô hình, dự đoán và metric. Nộp script tạo schema và mô tả cột. 1 điểm.

- Thực thi PK, FK, UNIQUE, NOT NULL và CHECK thích hợp; ví dụ duy nhất mùa/vòng, duy nhất chặng/loại phiên, duy nhất phiên/tay đua. Kiểm tra kết quả không gắn phiên của chặng A với tay đua tham dự chặng B. Giá trị chưa biết dùng NULL. 1 điểm.

### Phần III Nhập dữ liệu và giao dịch 2 điểm

- Viết chương trình Python nhập dữ liệu sạch với truy vấn có tham số. Import lặp không nhân bản bản ghi; quy định cập nhật khi nguồn sửa kết quả. Thực hiện trong transaction. 1 điểm.

- Chứng minh commit thành công và rollback khi dữ liệu không hợp lệ; tạo dữ liệu kiểm thử riêng cho trùng khóa, sai FK và thiếu trường bắt buộc. Nhật ký ghi được số lượng và nguyên nhân lỗi. 1 điểm.

### Phần IV Truy vấn và khai thác 2 điểm

- Nộp tối thiểu tám truy vấn có mục đích: kết quả Q/R; lịch sử đội của tay đua; thống kê đội/mùa; top tay đua; tỷ lệ bỏ cuộc theo định nghĩa; chất lượng dữ liệu; so sánh dự đoán với thực tế; lịch sử mô hình. Có JOIN nhiều bảng, GROUP BY, HAVING, truy vấn con và ít nhất một window function. 1,5 điểm.

- Tạo view đối chiếu dự đoán và giải thích vì sao dùng view. Web phải đọc/ghi được dữ liệu nghiệp vụ từ MySQL, không chỉ trình diễn CSV. 0,5 điểm.

### Phần V Chỉ mục và phân quyền 1 điểm

Giải thích chỉ mục phục vụ một truy vấn lọc hoặc JOIN, dùng EXPLAIN chứng minh cách truy cập; không hứa cải thiện tốc độ khi dữ liệu nhỏ. Tách tài khoản ứng dụng khỏi quản trị; không lưu thông tin bí mật trong mã nguồn. Mỗi nội dung 0,5 điểm.

### Phần VI Sao lưu phục hồi và demo 1 điểm

Nộp script sao lưu và phục hồi vào CSDL trống cùng hướng dẫn. Đối chiếu số dòng và các quan hệ sau phục hồi. Demo ít nhất một truy vấn, một tình huống từ chối dữ liệu sai và một lần lưu dự đoán. Không yêu cầu trigger hoặc stored procedure nếu không có nghiệp vụ phù hợp.

## Đối chiếu dự án hiện tại và kế hoạch hoàn thiện

Các ghi nhận dưới đây dựa trên cấu trúc OOP, tài liệu thiết kế CSDL và báo cáo thí nghiệm đang có trong dự án. Chúng giúp xác định phần cần làm tiếp, không thay thế việc nghiệm thu từng yêu cầu của đề mới.

### Những nền tảng đã có

- Thu thập Q/R qua FastF1, dữ liệu lịch sử, kiểm tra chất lượng và xây dựng đặc trưng trước race; dữ liệu thời tiết Q có độ phủ hạn chế và chưa nằm trong mô hình v1.

- OOP cho thu thập, đặc trưng, CSDL, mô hình, huấn luyện, dự đoán và web. Có bốn mô hình hồi quy và hai baseline; có đánh giá theo thời gian, lưu artifact và đối chiếu trên web.

- Schema MySQL, ERD, ràng buộc, giao dịch nhập, view, truy vấn demo, sao lưu và phục hồi. Cần rà soát chứng cứ cho đủ từng mục CSDL đề xuất, đặc biệt bộ tám truy vấn, EXPLAIN và phân quyền.

### Những phần phải bổ sung để sát đề mẫu

- Bảng mean/median/std/count đầy đủ, top và bottom ba giá trị, histogram có bộ lọc đội/mùa, và xuất đúng results2.csv.

- Bảng tay đua/mùa, K-means với lý do chọn k, PCA hai chiều và nhận xét cụm. Những chức năng này chưa được nghiệm thu trong bản hiện tại.

- Radar so sánh hai tay đua, tham số dòng lệnh và trang so sánh trên web; chuẩn hóa và chiều ý nghĩa của từng chỉ số.

- Chuẩn hóa bộ tệp nộp theo đề mới và viết báo cáo Word hoàn chỉnh. Báo cáo thực nghiệm dạng Markdown hiện có chưa thay thế bản Word yêu cầu.

### Lộ trình đề xuất cho một tuần kỹ thuật

Ngày 1 chốt đề và đầu ra; ngày 2 hoàn thiện thống kê/CSV; ngày 3 làm K-means/PCA; ngày 4 làm radar và ghép web; ngày 5 rà soát truy vấn, phân quyền và phục hồi MySQL; ngày 6 viết báo cáo; ngày 7 kiểm thử từ môi trường mới và đóng gói. Tuần sau dành cho thành viên đọc code, phân công và luyện bảo vệ.

### Kịch bản nghiệm thu

Chạy từ bản đóng gói; mở dữ liệu và histogram; xem cụm cùng giải thích k; so sánh hai tay đua; chọn chặng có Q để dự đoán và đối chiếu; mở truy vấn SQL/view; minh họa một ràng buộc và rollback; phục hồi CSDL thử nghiệm. Mọi thành viên cần giải thích được dòng dữ liệu từ nguồn đến biểu đồ và dự đoán.

### Tài liệu căn cứ

Đề mẫu: Bai_tap_Python_1.docx do người dùng cung cấp. Tài liệu dự án: docs/OOP.md, docs/ERD.md, docs/BAO_CAO_THUC_NGHIEM.md. Các thang điểm, đầu ra và lộ trình F1 trong tài liệu này là phương án đề xuất; không sao chép yêu cầu bóng đá sang F1 một cách máy móc.
