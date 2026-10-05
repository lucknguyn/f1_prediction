import hashlib
import json
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import fastf1
import pandas as pd
from ..config import AppConfig
from ..db import utcnow
from ..ingest import FastF1DataSource
from ..repositories import ResultRepository
from .common import KINDS, utc_timestamp
from .repository import WeekendRepository


class WeekendCollector:
    def __init__(self, db, config=None, api=fastf1):
        self.config = config or AppConfig()
        self.repository = WeekendRepository(db)
        self.core_results = ResultRepository(db)
        self.api = api

    def collect(self, years, kinds=None, rounds=None, refresh=False, schedule_only=False):
        FastF1DataSource(self.config).setup_cache()
        existing = self.repository.sessions()
        done = set(existing.loc[existing.status == "ready", "id"]) if not existing.empty else set()
        report, jobs = [], []
        for year in years:
            schedule = self.api.get_event_schedule(year, include_testing=False)
            source_file = self.config.raw_dir / str(year) / "weekend_schedule.csv"
            source_file.parent.mkdir(parents=True, exist_ok=True)
            schedule.to_csv(source_file, index=False)
            q_r = {kind: self.core_results.read(kind) for kind in ("Q", "R")}
            for _, event in schedule.iterrows():
                number = int(event.RoundNumber)
                if rounds and number not in rounds:
                    continue
                rid = year * 100 + number
                starts = [utc_timestamp(event[f"Session{i}DateUtc"]) for i in range(1, 6)
                          if pd.notna(event.get(f"Session{i}DateUtc"))]
                if not starts:
                    continue
                cutoff = min(starts) - timedelta(seconds=1)
                for i in range(1, 6):
                    kind = KINDS.get(event.get(f"Session{i}"))
                    if not kind or (kinds and kind not in kinds) or pd.isna(event.get(f"Session{i}DateUtc")):
                        continue
                    sid = f"{rid}-{kind}"
                    if sid in done and not refresh and not schedule_only:
                        continue
                    start = utc_timestamp(event[f"Session{i}DateUtc"])
                    values = dict(id=sid, race_id=rid, kind=kind, start_utc=start.to_pydatetime(),
                        cutoff_utc=cutoff.to_pydatetime(), history_after_utc=(start + timedelta(hours=6)).to_pydatetime(),
                        collected_at=utcnow(), source="FastF1 schedule and timing / Jolpica", details={},
                        status="not_collected" if start.to_pydatetime() + timedelta(hours=6) < utcnow() else "scheduled")
                    if schedule_only:
                        previous = existing[existing.id == sid]
                        if not previous.empty:
                            if previous.status.iloc[0] != "scheduled" or values["status"] != "not_collected":
                                values["status"] = previous.status.iloc[0]
                            values["collected_at"] = pd.Timestamp(previous.collected_at.iloc[0]).to_pydatetime()
                            details = previous.details.iloc[0]
                            values["details"] = json.loads(details) if isinstance(details, str) else details
                        self.repository.save_session(values)
                        report.append({"session": sid, "status": values["status"]})
                        continue
                    known = q_r[kind][q_r[kind].race_id == rid] if kind in q_r else None
                    jobs.append((values, year, number, kind, known))
        # Network reads độc lập; ghi MySQL tuần tự ở thread điều phối.
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(self.collect_one, *job) for job in jobs]
            for future in as_completed(futures):
                values, rows = future.result()
                self.repository.save_session(values, rows)
                report.append({"session": values["id"], "status": values["status"], **values["details"]})
                print(report[-1], flush=True)
        path = self.config.processed_dir / "weekend_collection.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        return report

    def collect_one(self, values, year, number, kind, known):
        rows = None
        try:
            if values["start_utc"] + timedelta(hours=6) < utcnow():
                if known is not None:
                    if known.empty:
                        raise ValueError("Chưa có kết quả phiên trong nguồn Q/R")
                    rows = known.rename(columns={"q1_seconds": "best_seconds"}).to_dict("records")
                    for row in rows:
                        row["position"] = int(row["position"]) if pd.notna(row["position"]) else None
                        row["best_seconds"] = float(row["best_seconds"]) if pd.notna(row["best_seconds"]) else None
                else:
                    session = self.api.get_session(year, number, kind)
                    session.load(laps=True, telemetry=False, weather=False, messages=True)
                    identities = None
                    invalid = session.results.DriverId.astype(str).str.lower().isin(["nan", "none", "", "<na>"])
                    if invalid.any():
                        official = self.api.get_session(year, number, "Q")
                        official.load(laps=False, telemetry=False, weather=False, messages=False)
                        identities = official.results
                    rows = self.normalize(session, kind, identities)
                if not rows or not any(row["position"] is not None for row in rows):
                    rows = None
                    raise ValueError("Không có kết quả hợp lệ")
                values["status"] = "ready" if all(row["position"] is not None for row in rows) else "partial"
                values["details"] = {"rows": len(rows), "label_definition": "fastest_valid_lap" if kind.startswith("FP") else "session_classification"}
                folder = self.config.raw_dir / str(year) / f"round_{number:02d}" / kind
                folder.mkdir(parents=True, exist_ok=True)
                pd.DataFrame(rows).to_csv(folder / "weekend_results.csv", index=False)
        except Exception as exc:
            rows = None
            values["status"] = "unavailable"
            values["details"] = {"error": str(exc)[:500]}
        return values, rows

    @staticmethod
    def normalize(session, kind, identities=None):
        results = session.results.copy()
        best = {}
        if kind.startswith("FP"):
            laps = session.laps
            # Deleted laps không được dùng. Nếu nguồn thiếu cờ, không khẳng định vòng hợp lệ.
            if "Deleted" not in laps or laps.Deleted.dtype != bool:
                raise ValueError("Nguồn FP thiếu cờ Deleted")
            laps = laps[(laps.Deleted == False) & laps.LapTime.notna() & (laps.LapTime.dt.total_seconds() > 0)]  # noqa: E712
            best = laps.groupby("DriverNumber").LapTime.min().dt.total_seconds().to_dict()
            ordered = sorted(best, key=lambda number: (best[number], str(number)))
            positions = {str(number): i + 1 for i, number in enumerate(ordered)}
        else:
            positions = {}
        rows = []
        for _, row in results.iterrows():
            driver_id, team_id = str(row.get("DriverId", "")), str(row.get("TeamId", ""))
            missing = {"nan", "none", "", "<na>"}
            if driver_id.lower() in missing:
                match = identities[identities.Abbreviation == row.Abbreviation] if identities is not None else pd.DataFrame()
                if len(match) == 1 and str(match.DriverId.iloc[0]).lower() not in missing:
                    driver_id, team_id = str(match.DriverId.iloc[0]), str(match.TeamId.iloc[0])
                else:
                    # Tay đua dự bị FP không có Ergast ID: giữ định danh nguồn riêng, không gán cho người ngồi cùng xe.
                    name = str(row.FullName)
                    if name.lower() in missing or str(row.Abbreviation).lower() in missing:
                        raise ValueError("Thiếu định danh tay đua trong live timing")
                    driver_id = "live-" + hashlib.sha256(name.encode()).hexdigest()[:20]
            if team_id.lower() in missing:
                matches = identities[identities.TeamName == row.TeamName] if identities is not None else pd.DataFrame()
                if not matches.empty and str(matches.TeamId.iloc[0]).lower() not in missing:
                    team_id = str(matches.TeamId.iloc[0])
                elif str(row.TeamName).lower() not in missing:
                    team_id = "live-team-" + hashlib.sha256(str(row.TeamName).encode()).hexdigest()[:16]
                else:
                    raise ValueError("Thiếu định danh đội trong live timing")
            position = positions.get(str(row.DriverNumber)) if kind.startswith("FP") else row.Position
            position = int(position) if pd.notna(position) and float(position) > 0 else None
            rows.append(dict(driver_id=driver_id, driver_name=str(row.FullName), team_id=team_id,
                             team_name=str(row.TeamName), position=position, best_seconds=best.get(str(row.DriverNumber))))
        return rows

