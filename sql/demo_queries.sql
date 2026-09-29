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
WHERE season = 2026 AND model = 'Baseline Q' AND split = 'test'
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
