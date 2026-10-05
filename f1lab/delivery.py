"""Xuất báo cáo số thật, schema và bản demo tái lập được; không xuất secrets."""
from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
from sqlalchemy import DateTime, func, select
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable

from .config import AppConfig
from .db import VIEW_SQL, Base, utcnow


class BackupService:
    def __init__(self, db, config=None):
        self.db = db
        self.config = config if config is not None else AppConfig()

    def backup(self, output):
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {"format": "f1lab-db-v1", "created_at_utc": utcnow().isoformat(), "tables": {}}
        with self.db.connect() as conn, conn.begin():
            for table in Base.metadata.sorted_tables:
                records = [dict(row) for row in conn.execute(select(table)).mappings()]
                for row in records:
                    for column in table.columns:
                        if isinstance(column.type, DateTime) and row[column.name] is not None:
                            row[column.name] = row[column.name].isoformat()
                    if table.name == "model_runs" and row.get("artifact"):
                        path = Path(row["artifact"])
                        if path.is_absolute() and path.is_relative_to(self.config.root):
                            row["artifact"] = str(path.relative_to(self.config.root))
                payload["tables"][table.name] = records
        temp = output.with_suffix(output.suffix + ".tmp")
        with gzip.open(temp, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, allow_nan=False)
        temp.replace(output)
        return {name: len(records) for name, records in payload["tables"].items()}

    def restore(self, source):
        with gzip.open(source, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        new_tables = {"weekend_sessions", "weekend_results", "weekend_runs", "weekend_predictions"}
        names = set(payload.get("tables", {}))
        expected = set(Base.metadata.tables)
        if payload.get("format") != "f1lab-db-v1" or names not in (expected, expected - new_tables):
            raise ValueError("Backup không đúng schema/format của dự án")
        for name in expected - names:
            payload["tables"][name] = []
        with self.db.begin() as conn:
            for table in Base.metadata.sorted_tables:
                if conn.execute(select(func.count()).select_from(table)).scalar():
                    raise ValueError("Chỉ restore vào CSDL trống; không ghi đè dữ liệu đang có")
            for table in Base.metadata.sorted_tables:
                records = payload["tables"][table.name]
                for row in records:
                    for column in table.columns:
                        if isinstance(column.type, DateTime) and row.get(column.name) is not None:
                            row[column.name] = datetime.fromisoformat(row[column.name])
                for start in range(0, len(records), 500):
                    conn.execute(table.insert(), records[start:start + 500])
        return {name: len(rows) for name, rows in payload["tables"].items()}

class ReportService:
    def __init__(self, config=None):
        self.config = config if config is not None else AppConfig()

    def export_schema(self):
        folder = self.config.root / "sql"
        folder.mkdir(exist_ok=True)
        statements = ["-- Generated from SQLAlchemy models; MySQL 8.4+\n-- Select an empty database before running.\nSET NAMES utf8mb4;"]
        for table in Base.metadata.sorted_tables:
            ddl = str(CreateTable(table).compile(dialect=mysql.dialect())).strip()
            statements.append(ddl + " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
            for index in sorted(table.indexes, key=lambda x: x.name):
                statements.append(str(CreateIndex(index).compile(dialect=mysql.dialect())) + ";")
        statements.append(VIEW_SQL + ";")
        generated = "\n\n".join(statements)
        (folder / "schema.sql").write_text("\n".join(line.rstrip() for line in generated.splitlines()) + "\n", encoding="utf-8")

    def write_report(self):
        summary = json.loads((self.config.root / "artifacts" / "latest.json").read_text())
        folder = self.config.root / "artifacts" / summary["experiment"]
        metrics = pd.read_csv(folder / "metrics.csv")
        leaderboard = pd.read_csv(folder / "validation_leaderboard.csv")
        race_metrics = pd.read_csv(folder / "race_metrics.csv")
        predictions = pd.read_csv(folder / "predictions.csv")
        features = pd.read_csv(folder / "features.csv")
        coverage_path = folder / "coverage.csv"
        if not coverage_path.exists():
            processed = self.config.root / "data" / "processed"
            if hashlib.sha256((processed / "features.csv").read_bytes()).hexdigest() != summary["data_sha256"]:
                raise ValueError("Thiếu coverage của thí nghiệm; dataset hiện tại khác snapshot đã train")
            coverage_path.write_text((processed / "coverage.csv").read_text())
        coverage = pd.read_csv(coverage_path)
        sections = ["# Báo cáo thực nghiệm — F1 Lab 2026", "",
            f"Thí nghiệm: `{summary['experiment']}`. Hoàn thành UTC: {summary['created_at']}. Báo cáo được sinh từ các CSV thực nghiệm, không điền điểm giả.", "",
            "## 1. Bài toán và phạm vi", "",
            "Dự đoán thứ tự các tay đua trước Race, sau Q. Một mẫu là một tay đua/chặng. Dữ liệu mới tải là dữ liệu hồi cứu: chưa có snapshot công bố lịch sử đúng cutoff. Mốc `cutoff_utc` dùng thời gian dự kiến bắt đầu Race làm giới hạn trước race; không chứng minh thời điểm kết quả Q lần đầu công bố.", "",
            "## 2. Dữ liệu và coverage", "",
            f"Có {len(features):,} mẫu feature của {features.race_id.nunique()} chặng Q hợp lệ. Coverage kiểm tra {len(coverage)} chặng đã có Q; {int((coverage.status == 'ready').sum())} chặng đủ nhãn để đánh giá toàn bộ danh sách. Lịch tương lai chưa có Q không nằm trong dataset feature.", ""]
        for year, group in coverage.groupby("season"):
            sections.append(f"- {year}: {len(group)} chặng có Q; {int((group.status == 'ready').sum())} chặng đủ điều kiện; {int((group.status != 'ready').sum())} chặng chưa đủ.")
        sections += ["", "Các chặng bị loại khỏi đánh giá đầy đủ:", ""]
        for row in coverage[coverage.status != "ready"].itertuples():
            sections.append(f"- {row.season} R{row.race_id % 100:02d}, {row.race_name}: Q {row.q_entries} người, R {row.r_entries} người; thiếu/trùng vị trí hoặc lệch danh sách. Cần xem nguồn gốc từng trường hợp; số người bằng nhau chưa chứng minh các vị trí hợp lệ.")
        sections += ["", "Không xóa DNF hàng loạt. Giữ thứ hạng số của nguồn khi đủ 1..N. Loại chặng thiếu nhãn hoặc Q không hợp lệ có thể gây thiên lệch chọn mẫu; kết quả chỉ đại diện tập được đánh giá.", "",
            "## 3. Feature và xử lý", "",
            "Bộ v1 có 14 feature số và 2 danh mục (đội, đường đua). Bao gồm hạng Q, gap Q1, tín hiệu Q2/Q3, phong độ và điểm race 5 chặng trước, tỷ lệ DNF lịch sử, số mẫu lịch sử, phong độ ở đường đua, vòng trong mùa và số tay đua. Chỉ dùng lịch sử race có start + 6 giờ trước cutoff; đây là khoảng đệm kỹ thuật, không là snapshot xác minh giờ công bố kết quả.", "",
            "Q2/Q3 có thời gian hợp lệ là proxy tham gia vòng, không chứng minh đầy đủ tình trạng vượt vòng nếu tay đua không ghi được thời gian. Q1 gap có thể bị ảnh hưởng điều kiện thay đổi trong phiên. DNF được định nghĩa theo chuỗi trạng thái: Finished/+Laps là không DNF; DSQ/DNS/Withdrawn/Excluded để thiếu; trạng thái khác coi là DNF. Đây là quy tắc dự án, cần kiểm tra nếu nguồn thêm trạng thái.", "",
            "Numeric: median từ training, cờ thiếu và StandardScaler. Danh mục: imputation/one-hot với handle_unknown=ignore. ID tay đua không đưa vào X. Label/status hiện tại tách khỏi allowlist. Thời tiết Q đã lưu để khám phá, chưa dùng trong model vì độ phủ chưa đủ.", "",
            "## 4. Giao thức huấn luyện", "",
            "Train các mùa trước 2024 → validation 2024; train các mùa trước 2025 → validation 2025. Toàn bộ tay đua một chặng nằm cùng tập. Sáu phương pháp dùng cùng feature/tập chia. Cấu hình cố định, seed 42; bản này chưa tìm siêu tham số hay kiểm chứng thống kê chênh lệch.", "",
            "Chọn theo MAE rank trung bình mỗi race trên toàn bộ validation; Spearman dùng phá hòa. Lựa chọn được lưu trước khi tính metric 2026. Sau đó refit với dữ liệu trước 2026; model đóng băng, rolling feature có thể cập nhật bằng những race 2026 đã diễn ra trước chặng đang dự đoán.", "",
            "## 5. Kết quả validation", ""]
        for row in leaderboard.itertuples():
            sections.append(f"- **{row.model}**: MAE {row.mae_rank:.3f} bậc; Spearman {row.spearman:.3f}; {row.n_races} race validation.")
        sections += ["", f"Lựa chọn triển khai: **{summary['selected']}**. Baseline cũng là ứng viên hợp lệ; không đổi lựa chọn dựa vào test.", "",
            f"## 6. Test {summary['test_year']}", ""]
        test = metrics[metrics.split == "test"]
        if test.empty:
            sections.append("Chưa có nhãn test đủ điều kiện; không có metric để công bố.")
        for row in test.itertuples():
            sections.append(f"- **{row.model}**: MAE rank {row.mae_rank:.3f}; RMSE rank {row.rmse_rank:.3f}; Spearman {row.spearman:.3f}; đúng người thắng {row.winner_hit:.1%}; podium overlap {row.podium_overlap:.1%}; R² raw {row.r2_raw:.3f}; {row.n_races} race / {row.n_drivers} mẫu.")
        selected_test = test[test.model == summary["selected"]]
        if not selected_test.empty:
            row = selected_test.iloc[0]
            sections += ["", f"Với {summary['selected']}, MAE {row.mae_rank:.3f} nghĩa là lệch trung bình khoảng {row.mae_rank:.2f} bậc. Winner hit {row.winner_hit:.1%} chỉ đo người thắng, không là độ chính xác toàn bảng. Podium overlap không yêu cầu đúng thứ tự podium. R² raw dùng điểm hồi quy, khác chất lượng thứ hạng sau sắp xếp."]
        sections += ["", "## 7. Hai chặng để phân tích khi demo", ""]
        selected_races = race_metrics[(race_metrics.model == summary["selected"]) & (race_metrics.split == "test")]
        if not selected_races.empty:
            for label, row in [("Sai số thấp nhất", selected_races.loc[selected_races.mae_rank.idxmin()]),
                               ("Sai số cao nhất", selected_races.loc[selected_races.mae_rank.idxmax()])]:
                race = predictions[(predictions.model == summary["selected"]) & (predictions.race_id == row.race_id)]
                sections.append(f"- {label}: {race.race_name.iloc[0]} ({int(row.race_id)}), MAE {row.mae_rank:.3f} bậc. Mở trên web để xem tay đua nào lệch nhiều; không suy ra nguyên nhân tai nạn/chiến thuật chỉ từ metric.")
        sections += ["", "## 8. Thảo luận và giới hạn", "",
            "Trong cấu hình v1, bốn model ML chưa vượt baseline Q theo metric chọn trước. Có thể lịch sử thành tích mang thêm nhiễu, Q đã là tín hiệu mạnh, hoặc cấu hình/feature chưa phù hợp; các giải thích này là giả thuyết cần thí nghiệm thêm. Không kết luận Machine Learning luôn kém hơn baseline.", "",
            "Đã xem test 2026 nên mọi thay đổi dùng kết quả này để chọn model/feature phải coi phần test đó là dữ liệu phát triển. Nghiên cứu tiếp theo cần holdout muộn hơn hoặc giao thức đánh giá mới chốt trước. Không điều chỉnh rồi tiếp tục gọi điểm cùng test là độc lập.", "",
            "2026 có đổi luật; mỗi race có các tay đua phụ thuộc lẫn nhau; DNF, án phạt và chiến thuật khó biết trước. Chưa có forecast thời tiết lưu tại cutoff, chưa có khoảng tin cậy, chưa thử learning-to-rank. Bản này là nghiên cứu hồi cứu và demo học tập.", "",
            "## 9. Tái lập và bằng chứng", "",
            f"SHA-256 dataset: `{summary['data_sha256']}`. Phiên bản thư viện: requirements.lock.txt. Cấu hình mô hình: f1lab/models.py. Giao thức thí nghiệm: f1lab/ml.py. Metric đầy đủ: artifacts/{summary['experiment']}/metrics.csv. Prediction từng tay đua: predictions.csv. Tập chia và model lưu theo run_id trong MySQL.", "",
            "Đối chiếu lưu nguồn và cutoff ở ingestion_runs/feature_snapshots; prediction_comparison là view JOIN các bảng. Xem HUONG_DAN.md để chạy lại, backup/restore và kiểm thử. Báo cáo kiểm thử riêng ghi kết quả của lần chạy cuối.", "",
            "## 10. Nguồn", "",
            "- [FastF1](https://github.com/theOehrly/Fast-F1): adapter Ergast truy cập Jolpica cho kết quả; live timing cho thời tiết Q.",
            "- [Jolpica](https://github.com/jolpica/jolpica-f1).",
            "- [scikit-learn: cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html).",
            "- [FIA: bối cảnh luật 2026](https://www.fia.com/news/fia-statement-amendments-2026-f1-regulations).", ""]
        target = self.config.root / "docs" / "BAO_CAO_THUC_NGHIEM.md"
        target.write_text("\n".join(sections), encoding="utf-8")
        return target

class BundleService:
    def __init__(self, config=None):
        self.config = config if config is not None else AppConfig()

    def create_bundle(self):
        summary = json.loads((self.config.root / "artifacts" / "latest.json").read_text())
        paths = []
        for dirname in ["f1lab", "scripts", "tests", "docs", "sql", ".streamlit"]:
            for path in (self.config.root / dirname).rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix in {".py", ".md", ".sql", ".toml", ".png"} and path.name != "secrets.toml":
                    paths.append(path)
        for filename in ["README.md", "app.py", "radarChartPlot.py", "requirements.txt", "requirements.lock.txt", "requirements-ingest.txt", "compose.yaml", ".env.example", ".gitignore"]:
            paths.append(self.config.root / filename)
        paths += [p for p in (self.config.root / "artifacts" / summary["experiment"]).rglob("*") if p.is_file()]
        paths.append(self.config.root / "artifacts" / "latest.json")
        weekend_latest = self.config.artifacts_dir / "weekend/latest.json"
        if weekend_latest.exists():
            weekend = json.loads(weekend_latest.read_text())
            paths.append(weekend_latest)
            paths += [p for p in (weekend_latest.parent / weekend["experiment"]).rglob("*") if p.is_file()]
        paths += list((self.config.root / "data" / "raw").glob("*/latest.json"))
        paths += list((self.config.root / "data" / "raw").glob("*/round_*/Q/weather.csv"))
        paths += [p for p in (self.config.root / "data" / "processed").glob("*") if p.is_file() and p.suffix not in (".lock", ".tmp") and p.name != "sync_status.json"]
        paths += [p for p in (self.config.processed_dir / "analysis").rglob("*") if p.is_file()]
        paths += list((self.config.root / "deliverables").glob("*.docx"))
        paths += list((self.config.root / "deliverables").glob("*-evidence.json"))
        backup = self.config.root / "deliverables" / "database.json.gz"
        if not backup.exists():
            raise ValueError("Chạy backup trước khi đóng gói")
        paths.append(backup)
        out = self.config.root / "deliverables" / "f1-lab-demo.zip"
        manifest = []
        with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
            for path in sorted(set(paths)):
                relative = path.relative_to(self.config.root)
                archive.write(path, "f1_prediction/" + str(relative))
                manifest.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}")
            archive.writestr("f1_prediction/MANIFEST.sha256", "\n".join(manifest))
        return out

# Compatibility adapters.
def backup_database(db, output):
    return BackupService(db).backup(output)


def restore_database(db, source):
    return BackupService(db).restore(source)


def export_schema():
    return ReportService().export_schema()


def write_report():
    return ReportService().write_report()


def create_bundle():
    return BundleService().create_bundle()
