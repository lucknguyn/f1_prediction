"""So sánh trên validation; khóa lựa chọn trước khi đọc metric test."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .db import utcnow
from .features import FEATURES, VERSION, FeatureService
from .config import AppConfig
from .models import ModelFactory
from .repositories import ArtifactRepository, ModelRunRepository
from dataclasses import dataclass, field

NAMES = list(ModelFactory.names)


class RaceEvaluator:
    """Chuyển điểm sang thứ hạng và đánh giá toàn bộ tay đua mỗi race."""
    def rank(self, frame, scores):
        if len(frame) != len(scores) or not np.isfinite(scores).all():
            raise ValueError("Prediction không hữu hạn hoặc sai số lượng")
        out = frame.copy()
        out["score"] = np.asarray(scores)
        out = out.sort_values(["race_id", "score", "quali_position", "driver_id"], kind="stable")
        out["predicted_rank"] = out.groupby("race_id").cumcount() + 1
        return out

    def evaluate(self, predictions):
        rows = []
        for race_id, race in predictions.groupby("race_id"):
            y, rank = race.label.to_numpy(float), race.predicted_rank.to_numpy(float)
            if not np.isfinite(y).all() or set(y) != set(range(1, len(y) + 1)):
                raise ValueError("Metric full-grid cần đủ nhãn 1..N")
            actual_order = race.sort_values("label").driver_id.to_list()
            predicted_order = race.sort_values("predicted_rank").driver_id.to_list()
            k = min(3, len(race))
            top = min(10, len(race))
            rows.append({"race_id": int(race_id), "n_drivers": len(race),
                         "mae_rank": mean_absolute_error(y, rank),
                         "rmse_rank": float(np.sqrt(mean_squared_error(y, rank))),
                         "spearman": float(spearmanr(y, rank).statistic),
                         "winner_hit": float(actual_order[0] == predicted_order[0]),
                         "podium_overlap": len(set(actual_order[:k]) & set(predicted_order[:k])) / k,
                         "exact_podium": float(actual_order[:k] == predicted_order[:k]),
                         "top10_overlap": len(set(actual_order[:top]) & set(predicted_order[:top])) / top,
                         "mae_raw": mean_absolute_error(y, race.score),
                         "rmse_raw": float(np.sqrt(mean_squared_error(y, race.score))),
                         "r2_raw": r2_score(y, race.score)})
        per_race = pd.DataFrame(rows)
        if per_race.empty:
            raise ValueError("Không có race hợp lệ để đánh giá")
        metrics = per_race.drop(columns=["race_id", "n_drivers"]).mean().to_dict()
        metrics.update(n_races=len(per_race), n_drivers=len(predictions))
        return metrics, per_race

class TemporalSplitter:
    def split(self, frame, eval_year):
        eligible = frame[frame.eligible & frame.label.notna()]
        train = eligible[eligible.season < eval_year].copy()
        valid = eligible[eligible.season == eval_year].copy()
        if train.race_id.nunique() < 10 or valid.race_id.nunique() < 1:
            raise ValueError(f"Không đủ race train/evaluate năm {eval_year}")
        if not train.start_utc.max() < valid.start_utc.min() or set(train.race_id) & set(valid.race_id):
            raise ValueError("Temporal split bị rò rỉ")
        return train, valid

@dataclass
class TrainingContext:
    frame: pd.DataFrame
    folder: Path
    fingerprint: str
    experiment: str
    metric_rows: list = field(default_factory=list)
    all_predictions: list = field(default_factory=list)
    all_per_race: list = field(default_factory=list)
    runs: dict = field(default_factory=dict)


class ExperimentTrainer:
    """Điều phối validation, khóa lựa chọn và kiểm thử theo thời gian."""
    def __init__(self, db, config=None, features=None, artifacts=None, models=None, evaluator=None, splitter=None, runs=None):
        self.config = config if config is not None else AppConfig()
        self.features = features if features is not None else FeatureService(db, self.config)
        self.artifacts = artifacts if artifacts is not None else ArtifactRepository(self.config)
        self.models = models if models is not None else ModelFactory()
        self.evaluator = evaluator if evaluator is not None else RaceEvaluator()
        self.splitter = splitter if splitter is not None else TemporalSplitter()
        self.runs = runs if runs is not None else ModelRunRepository(db, VERSION, FEATURES)

    def _run_fold(self, context, name, year, split):
        train, valid = self.splitter.split(context.frame, year)
        start = time.perf_counter()
        strategy = self.models.create(name)
        strategy.fit(train)
        model = strategy.estimator
        elapsed = time.perf_counter() - start
        output = self.evaluator.rank(valid, strategy.predict(valid))
        metrics, per_race = self.evaluator.evaluate(output)
        rid = str(uuid.uuid4())
        artifact = context.folder / f"{rid}.joblib"
        self.artifacts.save_model({"name": name, "model": model, "train_through": train.start_utc.max(),
                     "version": VERSION, "features": FEATURES, "data_sha256": context.fingerprint}, artifact)
        self.runs.save_evaluation(rid, name, split, train, output, metrics, per_race, artifact, context.experiment, elapsed)
        context.metric_rows.append(dict(model=name, split=split, year=year, run_id=rid, fit_seconds=elapsed, **metrics))
        output["model"], output["split"], output["run_id"] = name, split, rid
        per_race["model"], per_race["split"], per_race["year"] = name, split, year
        context.all_predictions.append(output)
        context.all_per_race.append(per_race)
        context.runs[(name, year)] = artifact
        print(f"{split} {year} | {name}: MAE rank={metrics['mae_rank']:.3f}, races={metrics['n_races']}", flush=True)
        return model, output, artifact, rid

    def train(self, test_year=2026):
        frame, quality = self.features.build_and_save()
        experiment = utcnow().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
        folder = self.artifacts.experiment_folder(experiment)
        folder.mkdir(parents=True)
        fingerprint = hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()
        context = TrainingContext(frame, folder, fingerprint, experiment)
        folds = [test_year - 2, test_year - 1]
        # Không âm thầm đổi năm test để lấy một kết quả đẹp khi 2026 thiếu dữ liệu.
        for year in folds:
            self.splitter.split(frame, year)
        for year in folds:
            for name in self.models.names:
                self._run_fold(context, name, year, "validation")
        # Chọn theo trung bình mỗi race của toàn bộ validation, rồi Spearman.
        cv = pd.concat(context.all_per_race)
        board = cv.groupby("model").agg(mae_rank=("mae_rank", "mean"), spearman=("spearman", "mean"),
                                        n_races=("race_id", "size")).reset_index()
        board = board.sort_values(["mae_rank", "spearman", "model"], ascending=[True, False, True])
        selected = board.iloc[0].model
        board.to_csv(folder / "validation_leaderboard.csv", index=False)
        (folder / "selection.json").write_text(json.dumps({"selected": selected, "reason": "Lowest race-macro validation MAE; Spearman tie-break",
                                                            "frozen_before_test": True, "folds": folds}, indent=2))
        # Giải thích trên validation, không chọn feature từ test.
        _, last_valid = self.splitter.split(frame, folds[-1])
        bundle = self.artifacts.load_model(context.runs[(selected, folds[-1])])
        base_mae = self.evaluator.evaluate(self.evaluator.rank(last_valid, self.models.from_bundle(bundle).predict(last_valid)))[0]["mae_rank"]
        rng, importance = np.random.default_rng(42), []
        for column in FEATURES:
            increases = []
            for _ in range(3):
                shuffled = last_valid.copy()
                shuffled[column] = rng.permutation(shuffled[column].to_numpy())
                error = self.evaluator.evaluate(self.evaluator.rank(shuffled, self.models.from_bundle(bundle).predict(shuffled)))[0]["mae_rank"]
                increases.append(error - base_mae)
            importance.append({"feature": column, "mae_increase": float(np.mean(increases)), "std": float(np.std(increases))})
        pd.DataFrame(importance).sort_values("mae_increase", ascending=False).to_csv(folder / "importance.csv", index=False)

        test_available = bool(((frame.season == test_year) & frame.eligible).any())
        selected_artifact, selected_run = None, None
        if test_available:
            for name in self.models.names:
                _, _, artifact, run_id = self._run_fold(context, name, test_year, "test")
                if name == selected:
                    selected_artifact, selected_run = artifact, run_id
        else:
            # Train cho tương lai dù chưa có nhãn test. Không bịa test metric.
            train = frame[(frame.season < test_year) & frame.eligible]
            strategy = self.models.create(selected).fit(train)
            model = strategy.estimator
            selected_artifact = folder / "forecast.joblib"
            self.artifacts.save_model({"name": selected, "model": model, "train_through": train.start_utc.max(), "version": VERSION,
                         "features": FEATURES, "data_sha256": fingerprint}, selected_artifact)
        pd.DataFrame(context.metric_rows).to_csv(folder / "metrics.csv", index=False)
        pd.concat(context.all_predictions).to_csv(folder / "predictions.csv", index=False)
        pd.concat(context.all_per_race).to_csv(folder / "race_metrics.csv", index=False)
        frame.to_csv(folder / "features.csv", index=False)
        (folder / "coverage.csv").write_text((self.config.root / "data" / "processed" / "coverage.csv").read_text())
        summary = {"experiment": experiment, "created_at": utcnow().isoformat(), "selected": selected,
                   "selected_artifact": str(selected_artifact.relative_to(self.config.root)), "selected_run": selected_run,
                   "test_year": test_year, "test_available": test_available,
                   "validation_years": folds, "data_sha256": fingerprint, "quality": quality,
                   "protocol": "Frozen model / rolling past results; retrospective Q; race-macro metrics; no hyperparameter search"}
        (folder / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        self.artifacts.save_latest(summary)
        return summary

class PredictionService:
    """Dự đoán với artifact hiện hành và lưu bằng chứng đầu vào/đầu ra."""
    def __init__(self, db, config=None, features=None, artifacts=None, models=None, evaluator=None, runs=None):
        self.config = config if config is not None else AppConfig()
        self.features = features if features is not None else FeatureService(db, self.config)
        self.artifacts = artifacts if artifacts is not None else ArtifactRepository(self.config)
        self.models = models if models is not None else ModelFactory()
        self.evaluator = evaluator if evaluator is not None else RaceEvaluator()
        self.runs = runs if runs is not None else ModelRunRepository(db, VERSION, FEATURES)

    def predict(self, race_id):
        latest = self.artifacts.load_latest()
        artifact = self.config.root / latest["selected_artifact"]
        bundle = self.artifacts.load_model(artifact)  # Chỉ artifact do dự án tạo, không nhận file upload.
        frame, _ = self.features.build_and_save()
        race = frame[frame.race_id == race_id]
        if race.empty:
            raise ValueError("Chặng chưa có Q hợp lệ. Chạy ingest --refresh sau Q.")
        if bundle["version"] != VERSION or bundle["features"] != FEATURES:
            raise ValueError("Model không cùng phiên bản feature; cần train lại")
        if not pd.Timestamp(bundle["train_through"]) < race.start_utc.min():
            raise ValueError("Model đã học sau chặng này. Hãy xem prediction backtest đã lưu.")
        output = self.evaluator.rank(race, self.models.from_bundle(bundle).predict(race))
        rid = str(uuid.uuid4())
        self.runs.save_inference(rid, bundle, artifact, latest["experiment"], race, output)
        return output

# Compatibility adapters for previous scripts/notebooks.
def pipeline(name):
    return ModelFactory().create(name).estimator


def score_model(name, model, frame):
    return ModelFactory().create(name, model).predict(frame)


def ranked(frame, scores):
    return RaceEvaluator().rank(frame, scores)


def evaluate(predictions):
    return RaceEvaluator().evaluate(predictions)


def time_split(frame, eval_year):
    return TemporalSplitter().split(frame, eval_year)


def persist_run(db, *args):
    return ModelRunRepository(db, VERSION, FEATURES).save_evaluation(*args)


def train_experiment(db, test_year=2026):
    return ExperimentTrainer(db).train(test_year)


def predict_race(db, race_id):
    return PredictionService(db).predict(race_id)
