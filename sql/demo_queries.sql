-- Chạy trong database f1_prediction; toàn bộ truy vấn ở đây chỉ đọc.

-- 1. JOIN kết quả Race với tay đua, đội và chặng.
SELECT r.season, r.`round`, r.name AS race, d.name AS driver,
       t.name AS team, z.position, z.status, z.points
FROM session_results z
JOIN sessions s ON s.id = z.session_id
JOIN races r ON r.id = z.race_id
JOIN drivers d ON d.id = z.driver_id
JOIN entries e ON e.race_id = z.race_id AND e.driver_id = z.driver_id
JOIN teams t ON t.id = e.team_id
WHERE s.kind = 'R' AND r.season = 2026
ORDER BY r.`round`, z.position;

-- 2. Phong độ đội theo mùa; điểm ở đây chỉ là Race, không bao gồm Sprint.
SELECT r.season, t.name AS team, COUNT(*) AS driver_race_samples,
       AVG(z.position) AS mean_position, SUM(z.points) AS race_points
FROM session_results z
JOIN sessions s ON s.id = z.session_id
JOIN races r ON r.id = z.race_id
JOIN entries e ON e.race_id = z.race_id AND e.driver_id = z.driver_id
JOIN teams t ON t.id = e.team_id
WHERE s.kind = 'R'
GROUP BY r.season, t.id, t.name
ORDER BY r.season DESC, mean_position;

-- 3. View: chọn đúng run_id để không trộn nhiều model hoặc nhiều lần chạy.
SELECT run_id, race, driver, team, model, predicted_rank, actual_rank,
       ABS(predicted_rank - actual_rank) AS absolute_error
FROM prediction_comparison
WHERE run_id = (SELECT id FROM model_runs WHERE name='Baseline Q' AND split='test'
                ORDER BY created_at DESC,id DESC LIMIT 1)
ORDER BY `round`, predicted_rank;

-- 4. Thiếu Q2/Q3 không đồng nghĩa lỗi nguồn: có thể không vào phần Q đó.
SELECT r.season, COUNT(*) AS q_samples,
       SUM(z.q1_seconds IS NULL) AS missing_q1,
       SUM(z.q2_seconds IS NULL) AS missing_q2,
       SUM(z.q3_seconds IS NULL) AS missing_q3
FROM session_results z JOIN sessions s ON s.id = z.session_id
JOIN races r ON r.id = z.race_id
WHERE s.kind = 'Q'
GROUP BY r.season;

-- 5. Window function dùng các hàng trước, không lấy race hiện tại.
SELECT d.name AS driver, r.season, r.`round`, z.position,
       AVG(z.position) OVER (
           PARTITION BY z.driver_id ORDER BY r.start_utc
           ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
       ) AS mean_position_previous5
FROM session_results z JOIN sessions s ON s.id = z.session_id
JOIN races r ON r.id = z.race_id JOIN drivers d ON d.id = z.driver_id
WHERE s.kind = 'R'
ORDER BY d.name, r.start_utc;

-- 6. Phân tích kế hoạch truy vấn; MySQL có thể chọn scan với bảng nhỏ.
EXPLAIN SELECT id, season, `round`, name
FROM races WHERE season = 2026 ORDER BY `round`;

-- 7. Lịch sử đổi đội: nhiều hơn một đội qua các mùa (GROUP BY + HAVING).
SELECT d.id, d.name, COUNT(DISTINCT e.team_id) AS teams_joined
FROM entries e JOIN drivers d ON d.id=e.driver_id
GROUP BY d.id,d.name HAVING COUNT(DISTINCT e.team_id)>1
ORDER BY teams_joined DESC,d.id;

-- 8. Top tay đua theo điểm Race từng mùa; không cộng điểm Sprint.
SELECT r.season,d.name,SUM(z.points) AS race_points,COUNT(*) AS starts
FROM session_results z JOIN sessions s ON s.id=z.session_id
JOIN races r ON r.id=z.race_id JOIN drivers d ON d.id=z.driver_id
WHERE s.kind='R'
GROUP BY r.season,d.id,d.name
ORDER BY r.season DESC,race_points DESC;

-- 9. DNF: không gộp DNS/DSQ vào hỏng xe; tỷ lệ dùng các trạng thái xác định.
SELECT r.season,t.name,
 AVG(CASE WHEN z.status IS NULL OR z.status IN ('Disqualified','Did not start','Withdrawn','Excluded') THEN NULL
          WHEN z.status='Finished' OR z.status LIKE '+%' THEN 0 ELSE 1 END) AS dnf_rate
FROM session_results z JOIN sessions s ON s.id=z.session_id
JOIN races r ON r.id=z.race_id JOIN entries e ON e.race_id=z.race_id AND e.driver_id=z.driver_id
JOIN teams t ON t.id=e.team_id WHERE s.kind='R'
GROUP BY r.season,t.id,t.name ORDER BY r.season DESC,dnf_rate;

-- 10. Lịch sử mô hình và số dự đoán: LEFT JOIN giữ cả run chưa có dự đoán.
SELECT m.id,m.name,m.split,m.created_at,COUNT(p.snapshot_id) AS predictions
FROM model_runs m LEFT JOIN predictions p ON p.run_id=m.id
GROUP BY m.id,m.name,m.split,m.created_at ORDER BY m.created_at DESC;

-- 11. Lịch cập nhật độc lập với ngày huấn luyện; xem đủ FP/Q/Sprint/Race.
SELECT r.season,r.`round`,r.name,s.kind,s.start_utc,s.status,s.collected_at
FROM weekend_sessions s JOIN races r ON r.id=s.race_id
WHERE r.season=(SELECT MAX(season) FROM races)
ORDER BY s.start_utc;

-- 12. Dự đoán trước cuối tuần: đối chiếu một lần chạy cụ thể mới nhất.
SELECT w.id AS run_id,w.model,d.name,p.rank,p.actual_rank,
 ABS(p.rank-p.actual_rank) AS absolute_error
FROM weekend_runs w JOIN weekend_predictions p ON p.run_id=w.id
JOIN drivers d ON d.id=p.driver_id
WHERE w.id=(SELECT id FROM weekend_runs ORDER BY created_at DESC,id DESC LIMIT 1)
ORDER BY p.rank;
