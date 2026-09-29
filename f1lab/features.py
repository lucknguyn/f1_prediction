"""Tạo feature bằng quá khứ nghiêm ngặt; label không nằm trong allowlist X."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ROOT, FeatureSnapshot

VERSION = "prerace-v1"
NUMERIC = ["quali_position", "q1_gap_pct", "reached_q2", "reached_q3", "driver_form5",
           "driver_points5", "driver_dnf10", "driver_history_count", "team_form5",
           "team_points5", "circuit_form", "circuit_count", "season_round", "field_size"]
CATEGORICAL = ["team_id", "circuit_id"]
FEATURES = NUMERIC + CATEGORICAL


def read_results(db, kind):
    sql = text("""SELECT r.id AS race_id, r.season, r.round AS season_round,
           r.name AS race_name, r.start_utc, r.circuit_id, z.driver_id,
           d.name AS driver_name, e.team_id, t.name AS team_name,
           z.position, z.points, z.status, z.q1_seconds, z.q2_seconds, z.q3_seconds
        FROM session_results z JOIN sessions s ON z.session_id = s.id
        JOIN races r ON r.id = z.race_id JOIN drivers d ON d.id = z.driver_id
        JOIN entries e ON e.race_id = z.race_id AND e.driver_id = z.driver_id
        JOIN teams t ON t.id = e.team_id
        WHERE s.kind = :kind ORDER BY r.start_utc, z.position, z.driver_id""")
    with db.connect() as conn:
        return pd.read_sql(sql, conn, params={"kind": kind}, parse_dates=["start_utc"])


def dnf(status):
    if pd.isna(status) or status in {"Disqualified", "Did not start", "Withdrawn", "Excluded"}:
        return np.nan
    return float(not (status == "Finished" or str(status).startswith("+")))


def _mean(frame, column, last=None):
    series = frame[column].tail(last) if last is not None else frame[column]
    return float(series.mean()) if series.notna().any() else np.nan


def build_features(qualifying: pd.DataFrame, results: pd.DataFrame):
    """Pure function để test leakage mà không cần mạng/MySQL."""
    if qualifying.empty:
        raise ValueError("Chưa có kết quả Q. Chạy ingest trước.")
    q = qualifying.sort_values(["start_utc", "race_id", "driver_id"]).copy()
    r = results.sort_values(["start_utc", "race_id", "driver_id"]).copy()
    if q.duplicated(["race_id", "driver_id"]).any() or r.duplicated(["race_id", "driver_id"]).any():
        raise ValueError("Duplicate race/driver: không thể tạo feature tin cậy")
    r["dnf"] = r.status.map(dnf)
    rows, coverage = [], []
    for race_id, group in q.groupby("race_id", sort=False):
        cutoff = group.start_utc.iloc[0]
        target = r[r.race_id == race_id].set_index("driver_id")
        n = len(group)
        q_ok = group.position.notna().all() and group.position.is_unique and (group.position > 0).all()
        # Không dùng race hiện tại dù results đã có trong CSDL.
        history = r[(r.start_utc + timedelta(hours=6) < cutoff) & r.position.notna()]
        target_ok = (set(group.driver_id) == set(target.index) and target.position.notna().all()
                     and set(target.position) == set(range(1, n + 1)))
        reason = "ready" if target_ok and q_ok else "awaiting_race" if target.empty and q_ok else "incomplete_roster_or_positions"
        coverage.append({"race_id": int(race_id), "race_name": group.race_name.iloc[0], "season": int(group.season.iloc[0]),
                         "q_entries": n, "r_entries": len(target), "status": reason})
        if not q_ok:
            continue
        q1_reference = group.q1_seconds.min()
        for _, item in group.iterrows():
            driver = history[history.driver_id == item.driver_id]
            # Tổng hợp đội theo race trước khi lấy 5 race, tránh 5 tay đua = 2.5 race.
            team = history[history.team_id == item.team_id].groupby(["start_utc", "race_id"], sort=True).agg(
                position=("position", "mean"), points=("points", "sum"))
            circuit = driver[driver.circuit_id == item.circuit_id]
            record = {"race_id": int(race_id), "driver_id": item.driver_id, "driver_name": item.driver_name,
                      "team_name": item.team_name, "race_name": item.race_name, "season": int(item.season),
                      "start_utc": cutoff, "cutoff_utc": cutoff, "version": VERSION,
                      "label": int(target.loc[item.driver_id, "position"]) if target_ok else np.nan,
                      "status": target.loc[item.driver_id, "status"] if item.driver_id in target.index else None,
                      "eligible": bool(target_ok),
                      "quali_position": float(item.position),
                      "q1_gap_pct": 100 * (item.q1_seconds / q1_reference - 1) if pd.notna(q1_reference) and q1_reference > 0 else np.nan,
                      "reached_q2": int(pd.notna(item.q2_seconds)), "reached_q3": int(pd.notna(item.q3_seconds)),
                      "driver_form5": _mean(driver, "position", 5), "driver_points5": _mean(driver, "points", 5),
                      "driver_dnf10": _mean(driver, "dnf", 10), "driver_history_count": len(driver),
                      "team_form5": _mean(team, "position", 5), "team_points5": _mean(team, "points", 5),
                      "circuit_form": _mean(circuit, "position"), "circuit_count": len(circuit),
                      "season_round": int(item.season_round), "field_size": n,
                      "team_id": item.team_id, "circuit_id": item.circuit_id}
            identity = {k: (None if pd.isna(v) else str(v)) for k, v in record.items()}
            record["snapshot_id"] = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            rows.append(record)
    return pd.DataFrame(rows), pd.DataFrame(coverage)


def build_and_save(db):
    frame, coverage = build_features(read_results(db, "Q"), read_results(db, "R"))
    if frame.empty:
        raise ValueError("Không có chặng Q hợp lệ")
    folder = ROOT / "data" / "processed"
    folder.mkdir(parents=True, exist_ok=True)
    frame.to_csv(folder / "features.csv", index=False)
    coverage.to_csv(folder / "coverage.csv", index=False)
    with Session(db) as session, session.begin():
        for row in frame.to_dict("records"):
            values = {k: (None if pd.isna(row[k]) else row[k]) for k in FEATURES}
            session.merge(FeatureSnapshot(id=row["snapshot_id"], race_id=row["race_id"], driver_id=row["driver_id"],
                                          cutoff_utc=row["cutoff_utc"].to_pydatetime(), version=VERSION, features=values,
                                          label=int(row["label"]) if pd.notna(row["label"]) else None))
    report = {"rows": len(frame), "races_with_q": int(frame.race_id.nunique()),
              "eligible_races": int(frame.loc[frame.eligible, "race_id"].nunique()),
              "coverage": coverage.status.value_counts().to_dict(),
              "missing_fraction": frame[FEATURES].isna().mean().to_dict(),
              "warning": "Retrospective snapshots: source revisions and Q publication times are not archived. Weather excluded from v1 models."}
    (folder / "quality.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return frame, report
