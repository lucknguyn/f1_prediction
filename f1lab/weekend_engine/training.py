"""Dự đoán riêng từng phiên từ lịch sử trước cuối tuần, không dùng Q hiện tại."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import fastf1
import joblib
import numpy as np
import pandas as pd
from sqlalchemy import delete, text
from sqlalchemy.orm import Session
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ..config import AppConfig
from ..db import (Driver, Team, WeekendSession, WeekendResult, WeekendRun,
                 WeekendPrediction, utcnow)
from ..ingest import FastF1DataSource
from ..ml import RaceEvaluator
from ..models import RaceModel
from ..repositories import ResultRepository

from .common import NUMERIC, CATEGORICAL, FEATURES, LABELS, VERSION
from .repository import WeekendRepository
from .features import WeekendFeatureBuilder


class WeekendFormModel(RaceModel):
    name = "Baseline lịch sử phiên"

    def fit(self, frame):
        return self

    def predict(self, frame):
        return frame.driver_session_form.fillna(frame.driver_race_form).fillna(0.5).to_numpy(float)



class WeekendRegressionModel(RaceModel):
    def __init__(self, name):
        self.name = name
        estimators = {"Linear Regression": LinearRegression(),
            "Random Forest": RandomForestRegressor(n_estimators=100, max_depth=7, min_samples_leaf=4, random_state=42, n_jobs=2),
            "HistGradientBoosting": HistGradientBoostingRegressor(max_iter=100, max_leaf_nodes=12, early_stopping=False, random_state=42)}
        self.estimator = Pipeline([("preprocess", ColumnTransformer([
            ("numeric", Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
                                   ("scale", StandardScaler())]), NUMERIC),
            ("category", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL)])),
            ("model", estimators[name])])

    def fit(self, frame):
        self.estimator.fit(frame[FEATURES], (frame.label - 1) / (frame.field_size - 1).clip(lower=1))
        return self

    def predict(self, frame):
        return self.estimator.predict(frame[FEATURES])



class WeekendTrainer:
    names = ("Baseline lịch sử phiên", "Linear Regression", "Random Forest", "HistGradientBoosting")

    def __init__(self, db, config=None):
        self.config = config or AppConfig()
        self.repository = WeekendRepository(db)
        self.builder = WeekendFeatureBuilder()

    def train(self, test_year=2026):
        frame = self.builder.build(self.repository.sessions(), self.repository.results())
        experiment = utcnow().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
        folder = self.config.artifacts_dir / "weekend" / experiment
        folder.mkdir(parents=True)
        frame.to_csv(folder / "features.csv", index=False)
        summaries, metrics, predictions = {}, [], []
        for kind in LABELS:
            data = frame[(frame.kind == kind) & frame.eligible]
            train = data[data.season < test_year - 1]
            valid = data[data.season == test_year - 1]
            test = data[data.season == test_year]
            if train.race_id.nunique() < 3 or valid.race_id.nunique() < 2:
                summaries[kind] = {"status": "insufficient_data", "train_sessions": int(train.race_id.nunique()), "validation_sessions": int(valid.race_id.nunique())}
                continue
            board = []
            for name in self.names:
                model = WeekendFormModel() if name == self.names[0] else WeekendRegressionModel(name)
                model.fit(train)
                output = RaceEvaluator().rank(valid, model.predict(valid))
                # Điểm là tỷ lệ vị trí, metric raw đổi về đơn vị hạng trước khi đánh giá.
                output["score"] = 1 + output.score * (output.field_size - 1)
                metric, _ = RaceEvaluator().evaluate(output)
                board.append({"model": name, **metric})
                metrics.append(dict(kind=kind, split="validation", model=name, **metric))
            board.sort(key=lambda x: (x["mae_rank"], -x["spearman"], x["model"]))
            name = board[0]["model"]
            selection = {"kind": kind, "selected": name, "validation": board, "frozen_before_test": True}
            (folder / f"{kind}-selection.json").write_text(json.dumps(selection, indent=2))
            final_train = data[data.season < test_year]
            model = WeekendFormModel() if name == self.names[0] else WeekendRegressionModel(name)
            model.fit(final_train)
            artifact = folder / f"{kind}.joblib"
            bundle = {"model": model, "name": name, "kind": kind, "features": FEATURES, "version": VERSION,
                      "train_through": final_train.start_utc.max(), "test_year": test_year,
                      "data_sha256": hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()}
            joblib.dump(bundle, artifact)
            summaries[kind] = {"status": "ready", "selected": name, "artifact": str(artifact.relative_to(self.config.root)),
                               "train_sessions": int(final_train.race_id.nunique()), "validation_sessions": int(valid.race_id.nunique())}
            if not test.empty:
                output = RaceEvaluator().rank(test, model.predict(test))
                output["score"] = 1 + output.score * (output.field_size - 1)
                metric, _ = RaceEvaluator().evaluate(output)
                metrics.append(dict(kind=kind, split="test", model=name, **metric))
                output["model"] = name
                predictions.append(output)
                summaries[kind]["test_sessions"] = int(test.race_id.nunique())
            print(kind, summaries[kind], flush=True)
        pd.DataFrame(metrics).to_csv(folder / "metrics.csv", index=False)
        if predictions:
            pd.concat(predictions).to_csv(folder / "predictions.csv", index=False)
        summary = {"experiment": experiment, "created_at": utcnow().isoformat(), "sessions": summaries,
                   "mode": "preweekend", "test_year": test_year, "validation_year": test_year - 1,
                   "limitations": "Retrospective participant lists and revised sources; no historical publication snapshots; FP fastest lap is not race pace; 2026 is exploratory after previous test exposure."}
        temp = self.config.artifacts_dir / "weekend" / "latest.tmp"
        temp.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        temp.replace(temp.with_suffix(".json"))
        return summary

