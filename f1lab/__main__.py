"""CLI chỉ phân tích tham số và gọi service; nghiệp vụ nằm trong các lớp riêng."""
import argparse
import json
from pathlib import Path

from .config import AppConfig
from .db import Database


class F1LabCLI:
    def __init__(self, config=None, database=None):
        self.config = config if config is not None else AppConfig()
        self.database = database if database is not None else Database(config=self.config)

    def build_parser(self):
        parser = argparse.ArgumentParser(description="F1 Lab — dữ liệu, MySQL, ML theo kiến trúc OOP")
        sub = parser.add_subparsers(dest="command", required=True)
        for name in ("init-db", "doctor", "report", "bundle", "features"):
            sub.add_parser(name)
        backup = sub.add_parser("backup")
        backup.add_argument("--output", type=Path, default=self.config.root / "deliverables/database.json.gz")
        restore = sub.add_parser("restore")
        restore.add_argument("--input", type=Path, default=self.config.root / "deliverables/database.json.gz")
        ingest = sub.add_parser("ingest")
        ingest.add_argument("--years", nargs="+", type=int, default=[2022, 2023, 2024, 2025, 2026])
        ingest.add_argument("--refresh", action="store_true")
        weather = sub.add_parser("weather")
        weather.add_argument("--year", type=int, required=True)
        weather.add_argument("--round", type=int, required=True)
        train = sub.add_parser("train")
        train.add_argument("--test-year", type=int, default=2026)
        predict = sub.add_parser("predict")
        predict.add_argument("--race", type=int, required=True, help="VD 202601")
        return parser

    def run(self, argv=None):
        args = self.build_parser().parse_args(argv)
        try:
            self.execute(args)
        finally:
            self.database.close()

    def execute(self, args):
        if args.command == "report":
            from .delivery import ReportService
            service = ReportService(self.config)
            service.export_schema()
            print(service.write_report())
            return
        if args.command == "bundle":
            from .delivery import BundleService
            print(BundleService(self.config).create_bundle())
            return
        self.database.initialize()
        db = self.database.engine
        if args.command in {"backup", "restore"}:
            from .delivery import BackupService
            service = BackupService(db, self.config)
            print(service.backup(args.output) if args.command == "backup" else service.restore(args.input))
        elif args.command == "doctor":
            from .repositories import DashboardRepository
            version, counts, rows = DashboardRepository(db).diagnostics()
            print("MySQL:", version)
            for name, count in counts.items():
                print(name, count)
            print("view rows:", rows)
        elif args.command == "ingest":
            self.ingest_years(db, args.years, args.refresh)
        elif args.command == "weather":
            from .ingest import IngestionService
            print(IngestionService(db, self.config).collect_weather(args.year, args.round))
        elif args.command == "features":
            from .features import FeatureService
            print(FeatureService(db, self.config).build_and_save()[1])
        elif args.command == "train":
            from .ml import ExperimentTrainer
            print(json.dumps(ExperimentTrainer(db, self.config).train(args.test_year), indent=2, ensure_ascii=False))
        elif args.command == "predict":
            from .ml import PredictionService
            print(PredictionService(db, self.config).predict(args.race).to_string(index=False))
        else:
            print("MySQL schema và view đã sẵn sàng.")

    def ingest_years(self, db, years, refresh):
        from .ingest import IngestionService
        service = IngestionService(db, self.config)
        errors = []
        for year in years:
            try:
                print(json.dumps(service.ingest(year, refresh), ensure_ascii=False), flush=True)
            except Exception as exc:
                service.repository.record_failure(year, exc)
                errors.append(f"{year}: {exc}")
                print(f"FAILED {year}: {exc}", flush=True)
        if errors:
            raise SystemExit("Một số mùa tải lỗi; các mùa thành công đã được lưu. Chạy lại để tiếp tục.")


def main():
    F1LabCLI().run()


if __name__ == "__main__":
    main()
