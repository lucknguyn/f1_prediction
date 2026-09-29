"""Bài 1: thu thập một phiên F1; chưa tạo feature hoặc huấn luyện ML."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path


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

    # Import sau argparse để --help vẫn chạy khi chưa cài FastF1.
    import fastf1

    args.cache.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(args.cache))
    session = fastf1.get_session(args.year, args.round_number, args.session)
    # Tắt telemetry để lần đầu tải nhẹ hơn. Laps và weather vẫn được yêu cầu.
    session.load(laps=True, telemetry=False, weather=True, messages=False)

    now = datetime.now(timezone.utc)
    folder = args.output / str(args.year) / f"round_{args.round_number:02d}" / args.session / now.strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True, exist_ok=False)
    report = {
        "source": "FastF1",
        "fastf1_version": importlib.metadata.version("fastf1"),
        "year": args.year,
        "round": args.round_number,
        "session": args.session,
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
    results_ok = report["datasets"]["results"]["status"] == "exported"
    report["status"] = "partial" if any(v["status"] != "exported" for v in report["datasets"].values()) else "exported"
    (folder / "manifest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"folder": str(folder.resolve()), "status": report["status"], "datasets": report["datasets"]}, indent=2, ensure_ascii=False))
    # Có dữ liệu phân hạng/kết quả mới có thể làm bài tiếp theo.
    return 0 if results_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
