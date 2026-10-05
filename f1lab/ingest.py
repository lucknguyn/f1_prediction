"""Thu thập có cache, phân trang và provenance qua FastF1/Jolpica."""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

import fastf1
import numpy as np
import pandas as pd
from fastf1.ergast import Ergast
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .config import AppConfig
from .db import ( Circuit, Driver, Entry, IngestionRun, Race, RaceSession,
                 Result, Team, Weather, utcnow)


def seconds(value):
    if value is None or value == "":
        return None
    try:
        parts = str(value).split(":")
        number = sum(float(x) * 60 ** i for i, x in enumerate(reversed(parts)))
        return number if np.isfinite(number) and number > 0 else None
    except (ValueError, TypeError):
        return None

def positive_int(value):
    try:
        number = float(value)
        return int(number) if np.isfinite(number) and number > 0 and number.is_integer() else None
    except (TypeError, ValueError):
        return None

class FastF1DataSource:
    def __init__(self, config=None, api_factory=Ergast):
        self.config = config if config is not None else AppConfig()
        self.api_factory = api_factory

    def setup_cache(self):
        path = self.config.root / "cache" / "fastf1"
        path.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(path))

    def download_year(self, year: int, refresh: bool = False) -> dict:
        self.setup_cache()
        folder = self.config.root / "data" / "raw" / str(year)
        folder.mkdir(parents=True, exist_ok=True)
        cached = folder / "latest.json"
        if cached.exists() and not refresh:
            return json.loads(cached.read_text())
        api = self.api_factory(result_type="raw", auto_cast=False, limit=100)
        payload = {"year": year, "source": "FastF1 Ergast adapter / Jolpica",
                   "fastf1_version": fastf1.__version__, "exported_at": utcnow().isoformat(),
                   "point_in_time": False}
        # Một trang có thể cắt ngang race: ghép theo mùa/vòng, không mất tay đua.
        for key, method, subkey in [
            ("schedule", api.get_race_schedule, None),
            ("qualifying", api.get_qualifying_results, "QualifyingResults"),
            ("results", api.get_race_results, "Results"),
        ]:
            merged, offset = {}, 0
            for _ in range(100):
                for attempt in range(3):
                    try:
                        response = method(season=year, limit=100, offset=offset)
                        break
                    except Exception:
                        if attempt == 2:
                            raise
                        time.sleep(2 ** attempt)
                count = 0
                for item in response:
                    race_key = (item["season"], item["round"])
                    count += len(item[subkey]) if subkey else 1
                    if race_key not in merged:
                        merged[race_key] = item
                    elif subkey:
                        merged[race_key][subkey].extend(item[subkey])
                offset += count
                if offset >= response.total_results:
                    break
                if count == 0:
                    raise ValueError(f"Empty page before total results: {year}/{key}/{offset}")
            else:
                raise ValueError("Pagination exceeded 100 pages")
            payload[key] = list(merged.values())
            print(f"{year} {key}: {len(merged)} chặng / {offset} bản ghi", flush=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        encoded = json.dumps(payload, ensure_ascii=False, indent=2)
        (folder / f"snapshot-{stamp}.json").write_text(encoded)
        temp = folder / "latest.tmp"
        temp.write_text(encoded)
        temp.replace(cached)
        return payload

    def load_weather(self, year, round_number):
        self.setup_cache()
        event = fastf1.get_session(year, round_number, "Q")
        event.load(laps=False, telemetry=False, weather=True, messages=False)
        weather = event.weather_data
        if weather.empty:
            raise ValueError("Nguồn không có thời tiết Q")
        return weather


class IngestionRepository:
    def __init__(self, db):
        self.db = db

    def import_year(self, payload):
        count, missing_positions = 0, 0
        exported = datetime.fromisoformat(payload["exported_at"])
        with Session(self.db) as session, session.begin():
            races = {int(x["round"]): x for x in payload["schedule"]}
            for item in payload["qualifying"] + payload["results"]:
                races.setdefault(int(item["round"]), item)
            for item in races.values():
                circuit = item["Circuit"]
                session.merge(Circuit(id=circuit["circuitId"], name=circuit["circuitName"], country=circuit["Location"]["country"]))
            session.flush()
            for item in races.values():
                rid = int(item["season"]) * 100 + int(item["round"])
                start = pd.Timestamp(item["date"] + "T" + item.get("time", "00:00:00Z")).tz_convert("UTC").tz_localize(None).to_pydatetime()
                session.merge(Race(id=rid, season=int(item["season"]), round=int(item["round"]),
                                   name=item["raceName"], circuit_id=item["Circuit"]["circuitId"], start_utc=start))
            session.flush()
            # Định danh đội/tay đua trước, sau đó entries, rồi session_results.
            for key, kind, sub in [("qualifying", "Q", "QualifyingResults"), ("results", "R", "Results")]:
                for item in payload[key]:
                    rid = int(item["season"]) * 100 + int(item["round"])
                    sid = f"{rid}-{kind}"
                    seen = set()
                    for row in item[sub]:
                        d, t = row["Driver"], row["Constructor"]
                        if d["driverId"] in seen:
                            raise ValueError(f"Duplicate source driver in {sid}: {d['driverId']}")
                        seen.add(d["driverId"])
                        session.merge(Driver(id=d["driverId"], name=f"{d['givenName']} {d['familyName']}", code=d.get("code")))
                        session.merge(Team(id=t["constructorId"], name=t["name"]))
                    session.flush()
                    for row in item[sub]:
                        entry = session.get(Entry, (rid, row["Driver"]["driverId"]))
                        tid = row["Constructor"]["constructorId"]
                        if entry is not None and entry.team_id != tid:
                            raise ValueError(f"Team conflict between sessions: {rid}/{entry.driver_id}")
                        session.merge(Entry(race_id=rid, driver_id=row["Driver"]["driverId"], team_id=tid))
                    session.merge(RaceSession(id=sid, race_id=rid, kind=kind, exported_at=exported, source=payload["source"]))
                    session.flush()
                    # Thay toàn bộ bản chuẩn hóa của phiên trong cùng transaction.
                    session.execute(delete(Result).where(Result.session_id == sid))
                    for row in item[sub]:
                        position = positive_int(row.get("position"))
                        missing_positions += position is None
                        session.add(Result(session_id=sid, race_id=rid, driver_id=row["Driver"]["driverId"],
                                           position=position, q1_seconds=seconds(row.get("Q1")),
                                           q2_seconds=seconds(row.get("Q2")), q3_seconds=seconds(row.get("Q3")),
                                           points=float(row["points"]) if "points" in row else None,
                                           status=row.get("status")))
                        count += 1
                    session.flush()
            details = {"season": payload["year"], "result_rows": count, "missing_positions": missing_positions,
                       "schedule_races": len(races), "q_races": len(payload["qualifying"]),
                       "r_races": len(payload["results"]), "source_exported_at": payload["exported_at"]}
            session.add(IngestionRun(id=str(uuid.uuid4()), source=payload["source"], status="imported", details=details))
        return details

    def save_weather(self, weather, year, round_number):
        sid = f"{year * 100 + round_number}-Q"
        with Session(self.db) as session, session.begin():
            if session.get(RaceSession, sid) is None:
                raise ValueError("Cần import kết quả Q trước thời tiết")
            session.execute(delete(Weather).where(Weather.session_id == sid))
            for _, row in weather.iterrows():
                vals = {out: (float(row[src]) if pd.notna(row[src]) else None) for out, src in
                        [("air_temp", "AirTemp"), ("track_temp", "TrackTemp"), ("humidity", "Humidity"), ("wind_speed", "WindSpeed")]}
                session.merge(Weather(session_id=sid, elapsed_seconds=row["Time"].total_seconds(),
                                      rainfall=int(row["Rainfall"]) if pd.notna(row["Rainfall"]) else None, **vals))
            session.add(IngestionRun(id=str(uuid.uuid4()), source="FastF1 live timing Q weather", status="imported",
                                     details={"season": year, "round": round_number, "rows": len(weather), "exported_at": utcnow().isoformat()}))
        return {"session": sid, "weather_rows": len(weather)}


    def record_failure(self, year, error):
        with Session(self.db) as session, session.begin():
            session.add(IngestionRun(id=str(uuid.uuid4()), source="FastF1 / Jolpica", status="failed",
                                     details={"season": year, "error": str(error)[:500]}))


class IngestionService:
    def __init__(self, db, config=None, source=None, repository=None):
        self.config = config if config is not None else AppConfig()
        self.source = source if source is not None else FastF1DataSource(self.config)
        self.repository = repository if repository is not None else IngestionRepository(db)

    def ingest(self, year, refresh=False):
        return self.repository.import_year(self.source.download_year(year, refresh))

    def collect_weather(self, year, round_number):
        weather = self.source.load_weather(year, round_number)
        path = self.config.raw_dir / str(year) / f"round_{round_number:02d}" / "Q"
        path.mkdir(parents=True, exist_ok=True)
        weather.to_csv(path / "weather.csv", index=False)
        return self.repository.save_weather(weather, year, round_number)


# Compatibility adapters.
def cache_setup():
    return FastF1DataSource().setup_cache()


def download_year(year, refresh=False):
    return FastF1DataSource().download_year(year, refresh)


def import_year(db, payload):
    return IngestionRepository(db).import_year(payload)


def collect_weather(db, year, round_number):
    return IngestionService(db).collect_weather(year, round_number)
