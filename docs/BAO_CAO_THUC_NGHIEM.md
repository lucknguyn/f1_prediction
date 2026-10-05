# Báo cáo thực nghiệm — F1 Lab 2026

Thí nghiệm: `20261005T173624-3a10a1`. Hoàn thành UTC: 2026-10-05T17:36:30.625153. Báo cáo được sinh từ các CSV thực nghiệm, không điền điểm giả.

## 1. Bài toán và phạm vi

Dự đoán thứ tự các tay đua trước Race, sau Q. Một mẫu là một tay đua/chặng. Dữ liệu mới tải là dữ liệu hồi cứu: chưa có snapshot công bố lịch sử đúng cutoff. Mốc `cutoff_utc` dùng thời gian dự kiến bắt đầu Race làm giới hạn trước race; không chứng minh thời điểm kết quả Q lần đầu công bố.

## 2. Dữ liệu và coverage

Có 2,085 mẫu feature của 103 chặng Q hợp lệ. Coverage kiểm tra 108 chặng đã có Q; 99 chặng đủ nhãn để đánh giá toàn bộ danh sách. Lịch tương lai chưa có Q không nằm trong dataset feature.

- 2022: 22 chặng có Q; 22 chặng đủ điều kiện; 0 chặng chưa đủ.
- 2023: 22 chặng có Q; 21 chặng đủ điều kiện; 1 chặng chưa đủ.
- 2024: 24 chặng có Q; 21 chặng đủ điều kiện; 3 chặng chưa đủ.
- 2025: 24 chặng có Q; 21 chặng đủ điều kiện; 3 chặng chưa đủ.
- 2026: 16 chặng có Q; 14 chặng đủ điều kiện; 2 chặng chưa đủ.

Các chặng bị loại khỏi đánh giá đầy đủ:

- 2023 R10, British Grand Prix: Q 20 người, R 20 người; thiếu/trùng vị trí hoặc lệch danh sách. Cần xem nguồn gốc từng trường hợp; số người bằng nhau chưa chứng minh các vị trí hợp lệ.
- 2024 R08, Monaco Grand Prix: Q 20 người, R 20 người; thiếu/trùng vị trí hoặc lệch danh sách. Cần xem nguồn gốc từng trường hợp; số người bằng nhau chưa chứng minh các vị trí hợp lệ.
- 2024 R15, Dutch Grand Prix: Q 20 người, R 20 người; thiếu/trùng vị trí hoặc lệch danh sách. Cần xem nguồn gốc từng trường hợp; số người bằng nhau chưa chứng minh các vị trí hợp lệ.
- 2024 R17, Azerbaijan Grand Prix: Q 20 người, R 20 người; thiếu/trùng vị trí hoặc lệch danh sách. Cần xem nguồn gốc từng trường hợp; số người bằng nhau chưa chứng minh các vị trí hợp lệ.
- 2025 R07, Emilia Romagna Grand Prix: Q 20 người, R 20 người; thiếu/trùng vị trí hoặc lệch danh sách. Cần xem nguồn gốc từng trường hợp; số người bằng nhau chưa chứng minh các vị trí hợp lệ.
- 2025 R09, Spanish Grand Prix: Q 20 người, R 19 người; thiếu/trùng vị trí hoặc lệch danh sách. Cần xem nguồn gốc từng trường hợp; số người bằng nhau chưa chứng minh các vị trí hợp lệ.
- 2025 R21, São Paulo Grand Prix: Q 19 người, R 20 người; thiếu/trùng vị trí hoặc lệch danh sách. Cần xem nguồn gốc từng trường hợp; số người bằng nhau chưa chứng minh các vị trí hợp lệ.
- 2026 R01, Australian Grand Prix: Q 19 người, R 22 người; thiếu/trùng vị trí hoặc lệch danh sách. Cần xem nguồn gốc từng trường hợp; số người bằng nhau chưa chứng minh các vị trí hợp lệ.
- 2026 R14, Spanish Grand Prix: Q 20 người, R 22 người; thiếu/trùng vị trí hoặc lệch danh sách. Cần xem nguồn gốc từng trường hợp; số người bằng nhau chưa chứng minh các vị trí hợp lệ.

Không xóa DNF hàng loạt. Giữ thứ hạng số của nguồn khi đủ 1..N. Loại chặng thiếu nhãn hoặc Q không hợp lệ có thể gây thiên lệch chọn mẫu; kết quả chỉ đại diện tập được đánh giá.

## 3. Feature và xử lý

Bộ v1 có 14 feature số và 2 danh mục (đội, đường đua). Bao gồm hạng Q, gap Q1, tín hiệu Q2/Q3, phong độ và điểm race 5 chặng trước, tỷ lệ DNF lịch sử, số mẫu lịch sử, phong độ ở đường đua, vòng trong mùa và số tay đua. Chỉ dùng lịch sử race có start + 6 giờ trước cutoff; đây là khoảng đệm kỹ thuật, không là snapshot xác minh giờ công bố kết quả.

Q2/Q3 có thời gian hợp lệ là proxy tham gia vòng, không chứng minh đầy đủ tình trạng vượt vòng nếu tay đua không ghi được thời gian. Q1 gap có thể bị ảnh hưởng điều kiện thay đổi trong phiên. DNF được định nghĩa theo chuỗi trạng thái: Finished/+Laps là không DNF; DSQ/DNS/Withdrawn/Excluded để thiếu; trạng thái khác coi là DNF. Đây là quy tắc dự án, cần kiểm tra nếu nguồn thêm trạng thái.

Numeric: median từ training, cờ thiếu và StandardScaler. Danh mục: imputation/one-hot với handle_unknown=ignore. ID tay đua không đưa vào X. Label/status hiện tại tách khỏi allowlist. Thời tiết Q đã lưu để khám phá, chưa dùng trong model vì độ phủ chưa đủ.

## 4. Giao thức huấn luyện

Train các mùa trước 2024 → validation 2024; train các mùa trước 2025 → validation 2025. Toàn bộ tay đua một chặng nằm cùng tập. Sáu phương pháp dùng cùng feature/tập chia. Cấu hình cố định, seed 42; bản này chưa tìm siêu tham số hay kiểm chứng thống kê chênh lệch.

Chọn theo MAE rank trung bình mỗi race trên toàn bộ validation; Spearman dùng phá hòa. Lựa chọn được lưu trước khi tính metric 2026. Sau đó refit với dữ liệu trước 2026; model đóng băng, rolling feature có thể cập nhật bằng những race 2026 đã diễn ra trước chặng đang dự đoán.

## 5. Kết quả validation

- **Baseline Q**: MAE 3.086 bậc; Spearman 0.703; 42 race validation.
- **Random Forest**: MAE 3.370 bậc; Spearman 0.675; 42 race validation.
- **CatBoost**: MAE 3.394 bậc; Spearman 0.669; 42 race validation.
- **Linear Regression**: MAE 3.444 bậc; Spearman 0.664; 42 race validation.
- **HistGradientBoosting**: MAE 3.853 bậc; Spearman 0.595; 42 race validation.
- **Baseline phong độ**: MAE 3.954 bậc; Spearman 0.578; 42 race validation.

Lựa chọn triển khai: **Baseline Q**. Baseline cũng là ứng viên hợp lệ; không đổi lựa chọn dựa vào test.

## 6. Test 2026

- **Baseline Q**: MAE rank 3.435; RMSE rank 4.875; Spearman 0.681; đúng người thắng 71.4%; podium overlap 57.1%; R² raw 0.361; 14 race / 308 mẫu.
- **Baseline phong độ**: MAE rank 4.351; RMSE rank 5.779; Spearman 0.568; đúng người thắng 7.1%; podium overlap 31.0%; R² raw 0.290; 14 race / 308 mẫu.
- **Linear Regression**: MAE rank 3.539; RMSE rank 5.036; Spearman 0.660; đúng người thắng 64.3%; podium overlap 61.9%; R² raw 0.428; 14 race / 308 mẫu.
- **Random Forest**: MAE rank 3.552; RMSE rank 4.924; Spearman 0.673; đúng người thắng 50.0%; podium overlap 54.8%; R² raw 0.430; 14 race / 308 mẫu.
- **HistGradientBoosting**: MAE rank 3.792; RMSE rank 5.093; Spearman 0.651; đúng người thắng 35.7%; podium overlap 57.1%; R² raw 0.403; 14 race / 308 mẫu.
- **CatBoost**: MAE rank 3.545; RMSE rank 4.985; Spearman 0.666; đúng người thắng 57.1%; podium overlap 54.8%; R² raw 0.415; 14 race / 308 mẫu.

Với Baseline Q, MAE 3.435 nghĩa là lệch trung bình khoảng 3.44 bậc. Winner hit 71.4% chỉ đo người thắng, không là độ chính xác toàn bảng. Podium overlap không yêu cầu đúng thứ tự podium. R² raw dùng điểm hồi quy, khác chất lượng thứ hạng sau sắp xếp.

## 7. Hai chặng để phân tích khi demo

- Sai số thấp nhất: Austrian Grand Prix (202608), MAE 1.818 bậc. Mở trên web để xem tay đua nào lệch nhiều; không suy ra nguyên nhân tai nạn/chiến thuật chỉ từ metric.
- Sai số cao nhất: Canadian Grand Prix (202605), MAE 5.273 bậc. Mở trên web để xem tay đua nào lệch nhiều; không suy ra nguyên nhân tai nạn/chiến thuật chỉ từ metric.

## 8. Thảo luận và giới hạn

Trong cấu hình v1, bốn model ML chưa vượt baseline Q theo metric chọn trước. Có thể lịch sử thành tích mang thêm nhiễu, Q đã là tín hiệu mạnh, hoặc cấu hình/feature chưa phù hợp; các giải thích này là giả thuyết cần thí nghiệm thêm. Không kết luận Machine Learning luôn kém hơn baseline.

Đã xem test 2026 nên mọi thay đổi dùng kết quả này để chọn model/feature phải coi phần test đó là dữ liệu phát triển. Nghiên cứu tiếp theo cần holdout muộn hơn hoặc giao thức đánh giá mới chốt trước. Không điều chỉnh rồi tiếp tục gọi điểm cùng test là độc lập.

2026 có đổi luật; mỗi race có các tay đua phụ thuộc lẫn nhau; DNF, án phạt và chiến thuật khó biết trước. Chưa có forecast thời tiết lưu tại cutoff, chưa có khoảng tin cậy, chưa thử learning-to-rank. Bản này là nghiên cứu hồi cứu và demo học tập.

## 9. Tái lập và bằng chứng

SHA-256 dataset: `ead900f084627c8aa3c587ceeee909031f165b4fc3928672f8da9be882a5386b`. Phiên bản thư viện: requirements.lock.txt. Cấu hình mô hình: f1lab/models.py. Giao thức thí nghiệm: f1lab/ml.py. Metric đầy đủ: artifacts/20261005T173624-3a10a1/metrics.csv. Prediction từng tay đua: predictions.csv. Tập chia và model lưu theo run_id trong MySQL.

Đối chiếu lưu nguồn và cutoff ở ingestion_runs/feature_snapshots; prediction_comparison là view JOIN các bảng. Xem HUONG_DAN.md để chạy lại, backup/restore và kiểm thử. Báo cáo kiểm thử riêng ghi kết quả của lần chạy cuối.

## 10. Nguồn

- [FastF1](https://github.com/theOehrly/Fast-F1): adapter Ergast truy cập Jolpica cho kết quả; live timing cho thời tiết Q.
- [Jolpica](https://github.com/jolpica/jolpica-f1).
- [scikit-learn: cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html).
- [FIA: bối cảnh luật 2026](https://www.fia.com/news/fia-statement-amendments-2026-f1-regulations).
