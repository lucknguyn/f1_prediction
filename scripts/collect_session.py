"""Bài 1: thu thập một phiên F1; chưa tạo feature hoặc huấn luyện ML."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path


class SessionCollector:
    def __init__(self, output=Path("data/raw"), cache=Path("cache/fastf1"), api=None):
        self.output, self.cache = Path(output), Path(cache)
        self.api = api

    def collect(self, year, round_number, kind="Q"):
        # Chỉ nạp dependency khi thực sự thu thập; --help không cần FastF1.
        fastf1 = self.api if self.api is not None else importlib.import_module("fastf1")

        self.cache.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(self.cache))
        session = fastf1.get_session(year, round_number, kind)
        # Tắt telemetry để lần đầu tải nhẹ hơn. Laps và weather vẫn được yêu cầu.
        session.load(laps=True, telemetry=False, weather=True, messages=False)

        now = datetime.now(timezone.utc)
        folder = self.output / str(year) / f"round_{round_number:02d}" / kind / now.strftime("%Y%m%dT%H%M%S%fZ")
        folder.mkdir(parents=True, exist_ok=False)
        report = {
            "source": "FastF1",
            "fastf1_version": importlib.metadata.version("fastf1"),
            "year": year,
            "round": round_number,
            "session": kind,
            "event_name": str(session.event["EventName"]),
            "exported_at_utc": now.isoformat(),
            "note": "Export time is not original publication time; cached/revised data may be returned. CSV is a raw export, not an ML-ready dataset.",
            "datasets": {},
        }
        for name in ("results", "laps", "weather_data"):
            try:
                frame = getattr(session, name)
            except fastf1.core.DataNotLoadedError as exc:
                report["datasets"][name] = {"status": "unavailable", "error": str(exc)}
                continue
            if frame is None or frame.empty:
                report["datasets"][name] = {"status": "empty", "rows": 0}
                continue
            frame.to_csv(folder / f"{name}.csv", index=False)
            report["datasets"][name] = {
                "status": "exported",
                "rows": len(frame),
                "columns": list(frame.columns),
                "missing_by_column": {str(k): int(v) for k, v in frame.isna().sum().items()},
            }
        report["status"] = "partial" if any(v["status"] != "exported" for v in report["datasets"].values()) else "exported"
        (folder / "manifest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return folder, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--round", required=True, type=int, dest="round_number")
    parser.add_argument("--session", choices=["FP1", "FP2", "FP3", "Q", "S", "SQ", "R"], default="Q")
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    parser.add_argument("--cache", type=Path, default=Path("cache/fastf1"))
    args = parser.parse_args()
    if args.round_number < 1 or args.year < 2018:
        parser.error("Bài thực hành dùng year >= 2018 và round >= 1.")

    collector = SessionCollector(args.output, args.cache)
    folder, report = collector.collect(args.year, args.round_number, args.session)
    print(json.dumps({"folder": str(folder.resolve()), "status": report["status"], "datasets": report["datasets"]}, indent=2, ensure_ascii=False))
    return 0 if report["datasets"]["results"]["status"] == "exported" else 1


if __name__ == "__main__":
    raise SystemExit(main())
