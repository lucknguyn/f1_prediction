import json
import uuid
import pandas as pd
from sqlalchemy import delete, text
from sqlalchemy.orm import Session
from ..db import Driver, Team, WeekendSession, WeekendResult, WeekendRun, WeekendPrediction
from .common import FEATURES, VERSION


class WeekendRepository:
    def __init__(self, db):
        self.db = db

    def sessions(self):
        with self.db.connect() as conn:
            return pd.read_sql(text("""SELECT s.*, r.season, r.`round` AS season_round,
                r.name AS race_name, r.circuit_id FROM weekend_sessions s
                JOIN races r ON r.id=s.race_id ORDER BY s.start_utc"""), conn,
                parse_dates=["start_utc", "cutoff_utc", "history_after_utc"])

    def results(self):
        with self.db.connect() as conn:
            return pd.read_sql(text("""SELECT z.*, s.kind, s.race_id, s.start_utc,
                s.cutoff_utc, s.history_after_utc, r.season, r.`round` AS season_round,
                r.circuit_id, r.name AS race_name, d.name AS driver_name, t.name AS team_name
                FROM weekend_results z JOIN weekend_sessions s ON z.session_id=s.id
                JOIN races r ON r.id=s.race_id JOIN drivers d ON d.id=z.driver_id
                JOIN teams t ON t.id=z.team_id ORDER BY s.start_utc, z.driver_id"""), conn,
                parse_dates=["start_utc", "cutoff_utc", "history_after_utc"])

    def save_session(self, values, rows=None):
        with Session(self.db) as session, session.begin():
            session.merge(WeekendSession(**values))
            session.flush()
            if rows is not None:
                session.execute(delete(WeekendResult).where(WeekendResult.session_id == values["id"]))
                for row in rows:
                    session.merge(Driver(id=row["driver_id"], name=row["driver_name"]))
                    session.merge(Team(id=row["team_id"], name=row["team_name"]))
                session.flush()
                for row in rows:
                    session.add(WeekendResult(session_id=values["id"], **{k: row.get(k) for k in
                                ("driver_id", "team_id", "position", "best_seconds")}))

    def save_prediction(self, target, output, bundle, artifact):
        run_id = str(uuid.uuid4())
        with Session(self.db) as session, session.begin():
            session.add(WeekendRun(id=run_id, session_id=target.id,
                cutoff_utc=target.cutoff_utc.to_pydatetime(), model=bundle["name"], artifact=str(artifact),
                details={"version": VERSION, "mode": "preweekend", "retrospective_roster": True,
                         "train_through": str(bundle["train_through"]), "roster_source": output.roster_source.iloc[0]}))
            session.flush()
            for row in output.to_dict("records"):
                session.add(WeekendPrediction(run_id=run_id, driver_id=row["driver_id"], score=float(row["score"]),
                    rank=int(row["predicted_rank"]), actual_rank=int(row["label"]) if pd.notna(row["label"]) else None,
                    features={k: None if pd.isna(row[k]) else row[k] for k in FEATURES}))
        return run_id

