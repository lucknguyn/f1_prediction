import argparse
import json
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from .db import IngestionRun, engine, initialize


def main():
    parser = argparse.ArgumentParser(description="F1 Lab — các bước dữ liệu, MySQL, ML")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    sub.add_parser("doctor")
    sub.add_parser("report")
    sub.add_parser("bundle")
    backup = sub.add_parser("backup")
    backup.add_argument("--output", type=Path, default=Path("deliverables/database.json.gz"))
    restore = sub.add_parser("restore")
    restore.add_argument("--input", type=Path, default=Path("deliverables/database.json.gz"))
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--years", nargs="+", type=int, default=[2022, 2023, 2024, 2025, 2026])
    ingest.add_argument("--refresh", action="store_true")
    weather = sub.add_parser("weather")
    weather.add_argument("--year", type=int, required=True)
    weather.add_argument("--round", type=int, required=True)
    sub.add_parser("features")
    train = sub.add_parser("train")
    train.add_argument("--test-year", type=int, default=2026)
    predict = sub.add_parser("predict")
    predict.add_argument("--race", type=int, required=True, help="VD 202601")
    args = parser.parse_args()
    if args.command == "report":
        from .delivery import export_schema, write_report
        export_schema()
        print(write_report())
        return
    if args.command == "bundle":
        from .delivery import create_bundle
        print(create_bundle())
        return
    db = engine()
    initialize(db)
    if args.command == "backup":
        from .delivery import backup_database
        print(backup_database(db, args.output))
    elif args.command == "restore":
        from .delivery import restore_database
        print(restore_database(db, args.input))
    elif args.command == "doctor":
        from sqlalchemy import select, func, text
        from .db import Base
        with db.connect() as conn:
            print("MySQL:", conn.execute(text("SELECT VERSION()")).scalar())
            for table in Base.metadata.sorted_tables:
                print(table.name, conn.execute(select(func.count()).select_from(table)).scalar())
            print("view rows:", conn.execute(text("SELECT COUNT(*) FROM prediction_comparison")).scalar())
    elif args.command == "ingest":
        from .ingest import download_year, import_year
        errors = []
        for year in args.years:
            try:
                print(json.dumps(import_year(db, download_year(year, args.refresh)), ensure_ascii=False), flush=True)
            except Exception as exc:
                with Session(db) as session, session.begin():
                    session.add(IngestionRun(id=str(uuid.uuid4()), source="FastF1 / Jolpica", status="failed",
                                             details={"season": year, "error": str(exc)[:500]}))
                errors.append(f"{year}: {exc}")
                print(f"FAILED {year}: {exc}", flush=True)
        if errors:
            raise SystemExit("Một số mùa tải lỗi; các mùa thành công đã được lưu. Chạy lại để tiếp tục.")
    elif args.command == "weather":
        from .ingest import collect_weather
        print(collect_weather(db, args.year, args.round))
    elif args.command == "features":
        from .features import build_and_save
        print(build_and_save(db)[1])
    elif args.command == "train":
        from .ml import train_experiment
        print(json.dumps(train_experiment(db, args.test_year), indent=2, ensure_ascii=False))
    elif args.command == "predict":
        from .ml import predict_race
        print(predict_race(db, args.race).to_string(index=False))
    else:
        print("MySQL schema và view đã sẵn sàng.")


if __name__ == "__main__":
    main()
