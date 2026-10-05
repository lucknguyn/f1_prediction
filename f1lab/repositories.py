"""Repository chứa truy vấn SQL và thao tác artifact, nhận dependency từ ngoài."""
import json
import joblib
import numpy as np
import pandas as pd
from sqlalchemy import text, select, func
from sqlalchemy.orm import Session
from .config import AppConfig
from .db import Base, FeatureSnapshot, ModelRun, Prediction, EvaluationMetric


class ResultRepository:
    def __init__(self, db):
        self.db = db

    def read(self, kind):
        sql = text("""SELECT r.id AS race_id, r.season, r.round AS season_round,
               r.name AS race_name, r.start_utc, r.circuit_id, z.driver_id,
               d.name AS driver_name, e.team_id, t.name AS team_name,
               z.position, z.points, z.status, z.q1_seconds, z.q2_seconds, z.q3_seconds
            FROM session_results z JOIN sessions s ON z.session_id = s.id
            JOIN races r ON r.id = z.race_id JOIN drivers d ON d.id = z.driver_id
            JOIN entries e ON e.race_id = z.race_id AND e.driver_id = z.driver_id
            JOIN teams t ON t.id = e.team_id
            WHERE s.kind = :kind ORDER BY r.start_utc, z.position, z.driver_id""")
        with self.db.connect() as conn:
            return pd.read_sql(sql, conn, params={"kind": kind}, parse_dates=["start_utc"])

class FeatureSnapshotRepository:
    def __init__(self, db, version, features):
        self.db, self.version, self.features = db, version, tuple(features)

    def save(self, frame):
        with Session(self.db) as session, session.begin():
            for row in frame.to_dict("records"):
                values = {k: (None if pd.isna(row[k]) else row[k]) for k in self.features}
                session.merge(FeatureSnapshot(id=row["snapshot_id"], race_id=row["race_id"], driver_id=row["driver_id"],
                                              cutoff_utc=row["cutoff_utc"].to_pydatetime(), version=self.version, features=values,
                                              label=int(row["label"]) if pd.notna(row["label"]) else None))


class ModelRunRepository:
    def __init__(self, db, version, features):
        self.db, self.version, self.features = db, version, list(features)

    def save_evaluation(self, run_id, name, split, train, predictions, metrics, per_race, artifact, experiment, fit_seconds):
        with Session(self.db) as session, session.begin():
            session.add(ModelRun(id=run_id, name=name, train_through=train.start_utc.max().to_pydatetime(), split=split,
                                 artifact=str(artifact) if artifact else None,
                                 details={"experiment": experiment, "feature_version": self.version, "features": self.features,
                                          "seed": 42, "train_races": int(train.race_id.nunique()), "fit_seconds": fit_seconds,
                                      "parameters": "Fixed configurations in f1lab/models.py; no test tuning"}))
            session.flush()
            for row in predictions.to_dict("records"):
                session.add(Prediction(run_id=run_id, snapshot_id=row["snapshot_id"], score=float(row["score"]), rank=int(row["predicted_rank"])))
            for key, value in metrics.items():
                session.add(EvaluationMetric(run_id=run_id, name=key, value=float(value) if np.isfinite(value) else None))
            for row in per_race.to_dict("records"):
                for key, value in row.items():
                    if key != "race_id":
                        session.add(EvaluationMetric(run_id=run_id, race_id=row["race_id"], name=key,
                                                     value=float(value) if np.isfinite(value) else None))

    def save_inference(self, run_id, bundle, artifact, experiment, race, output):
        with Session(self.db) as session, session.begin():
            session.add(ModelRun(id=run_id, name=bundle["name"], split="inference",
                                 train_through=pd.Timestamp(bundle["train_through"]).to_pydatetime(), artifact=str(artifact),
                                 details={"experiment": experiment, "retrospective": bool(race.label.notna().all()),
                                          "feature_version": self.version, "features": self.features}))
            session.flush()
            for row in output.to_dict("records"):
                session.add(Prediction(run_id=run_id, snapshot_id=row["snapshot_id"],
                                       score=float(row["score"]), rank=int(row["predicted_rank"])))


class ArtifactRepository:
    csv_names = ("metrics", "predictions", "race_metrics", "features", "validation_leaderboard", "importance")

    def __init__(self, config=None):
        self.config = config if config is not None else AppConfig()

    def experiment_folder(self, experiment):
        return self.config.artifacts_dir / experiment

    def load_latest(self):
        return json.loads((self.config.artifacts_dir / "latest.json").read_text())

    def load_experiment(self, experiment):
        folder = self.experiment_folder(experiment)
        return {name: pd.read_csv(folder / f"{name}.csv") for name in self.csv_names}

    def load_model(self, path):
        # Chỉ artifact nội bộ; không nhận model upload từ web.
        return joblib.load(path)

    def save_model(self, bundle, path):
        joblib.dump(bundle, path)

    def save_latest(self, summary):
        self.config.artifacts_dir.mkdir(parents=True, exist_ok=True)
        latest = self.config.artifacts_dir / "latest.json"
        temporary = latest.with_suffix(".tmp")
        temporary.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        temporary.replace(latest)


class DashboardRepository:
    queries = {
        "ingestion": "SELECT created_at, source, status, details FROM ingestion_runs ORDER BY created_at DESC LIMIT 30",
        "weather": "SELECT w.*, r.name, r.season, r.`round` FROM weather_observations w JOIN sessions s ON s.id=w.session_id JOIN races r ON r.id=s.race_id ORDER BY session_id, elapsed_seconds",
        "comparison": "SELECT * FROM prediction_comparison ORDER BY season DESC, `round` DESC LIMIT 100",
    }
    table_names = ("drivers", "teams", "races", "entries", "session_results", "weather_observations", "feature_snapshots", "model_runs", "predictions")

    def __init__(self, db):
        self.db = db

    def overview(self):
        with self.db.connect() as conn:
            version = conn.execute(text("SELECT VERSION()")).scalar()
            counts = {name: conn.execute(select(func.count()).select_from(Base.metadata.tables[name])).scalar()
                      for name in self.table_names}
            schedule = pd.read_sql(text("SELECT id, season, `round`, name, start_utc FROM races ORDER BY start_utc"), conn)
        return version, counts, schedule

    def read_table(self, name):
        with self.db.connect() as conn:
            return pd.read_sql(text(self.queries[name]), conn)

    def diagnostics(self):
        with self.db.connect() as conn:
            version = conn.execute(text("SELECT VERSION()")).scalar()
            counts = {table.name: conn.execute(select(func.count()).select_from(table)).scalar()
                      for table in Base.metadata.sorted_tables}
            rows = conn.execute(text("SELECT COUNT(*) FROM prediction_comparison")).scalar()
        return version, counts, rows
