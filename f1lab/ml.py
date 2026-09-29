"""So sánh trên validation; khóa lựa chọn trước khi đọc metric test."""
from __future__ import annotations

import hashlib
import json
import time
import uuid

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from scipy.stats import spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy.orm import Session

from .db import ROOT, EvaluationMetric, ModelRun, Prediction, utcnow
from .features import CATEGORICAL, FEATURES, NUMERIC, VERSION, build_and_save

NAMES = ["Baseline Q", "Baseline phong độ", "Linear Regression", "Random Forest", "HistGradientBoosting", "CatBoost"]


def pipeline(name):
    numeric = Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
                        ("scale", StandardScaler())])
    category = Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                         ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False))])
    preprocessing = ColumnTransformer([("num", numeric, NUMERIC), ("cat", category, CATEGORICAL)])
    models = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(n_estimators=250, max_depth=9, min_samples_leaf=5, max_features=0.8, random_state=42, n_jobs=2),
        "HistGradientBoosting": HistGradientBoostingRegressor(max_iter=180, max_leaf_nodes=15, l2_regularization=2, early_stopping=False, random_state=42),
        "CatBoost": CatBoostRegressor(iterations=350, depth=5, learning_rate=0.04, loss_function="RMSE", random_seed=42, thread_count=2, verbose=False, allow_writing_files=False),
    }
    return Pipeline([("preprocess", preprocessing), ("model", models[name])])


def score_model(name, model, frame):
    if name == "Baseline Q":
        return frame.quali_position.to_numpy(float)
    if name == "Baseline phong độ":
        return frame.driver_form5.fillna(frame.quali_position).to_numpy(float)
    return model.predict(frame[FEATURES])


def ranked(frame, scores):
    if len(frame) != len(scores) or not np.isfinite(scores).all():
        raise ValueError("Prediction không hữu hạn hoặc sai số lượng")
    out = frame.copy()
    out["score"] = np.asarray(scores)
    out = out.sort_values(["race_id", "score", "quali_position", "driver_id"], kind="stable")
    out["predicted_rank"] = out.groupby("race_id").cumcount() + 1
    return out


def evaluate(predictions):
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


def time_split(frame, eval_year):
    eligible = frame[frame.eligible & frame.label.notna()]
    train = eligible[eligible.season < eval_year].copy()
    valid = eligible[eligible.season == eval_year].copy()
    if train.race_id.nunique() < 10 or valid.race_id.nunique() < 1:
        raise ValueError(f"Không đủ race train/evaluate năm {eval_year}")
    if not train.start_utc.max() < valid.start_utc.min() or set(train.race_id) & set(valid.race_id):
        raise ValueError("Temporal split bị rò rỉ")
    return train, valid


def persist_run(db, run_id, name, split, train, predictions, metrics, per_race, artifact, experiment, fit_seconds):
    with Session(db) as session, session.begin():
        session.add(ModelRun(id=run_id, name=name, train_through=train.start_utc.max().to_pydatetime(), split=split,
                             artifact=str(artifact) if artifact else None,
                             details={"experiment": experiment, "feature_version": VERSION, "features": FEATURES,
                                      "seed": 42, "train_races": int(train.race_id.nunique()), "fit_seconds": fit_seconds,
                                      "parameters": "Fixed configurations in f1lab/ml.py; no test tuning"}))
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


def train_experiment(db, test_year=2026):
    frame, quality = build_and_save(db)
    experiment = utcnow().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    folder = ROOT / "artifacts" / experiment
    folder.mkdir(parents=True)
    fingerprint = hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()
    metric_rows, all_predictions, all_per_race, runs = [], [], [], {}
    folds = [test_year - 2, test_year - 1]
    # Không âm thầm đổi năm test để lấy một kết quả đẹp khi 2026 thiếu dữ liệu.
    for year in folds:
        time_split(frame, year)

    def run_fold(name, year, split):
        train, valid = time_split(frame, year)
        model, start = None, time.perf_counter()
        if not name.startswith("Baseline"):
            model = pipeline(name)
            model.fit(train[FEATURES], train.label)
        elapsed = time.perf_counter() - start
        output = ranked(valid, score_model(name, model, valid))
        metrics, per_race = evaluate(output)
        rid = str(uuid.uuid4())
        artifact = folder / f"{rid}.joblib"
        joblib.dump({"name": name, "model": model, "train_through": train.start_utc.max(),
                     "version": VERSION, "features": FEATURES, "data_sha256": fingerprint}, artifact)
        persist_run(db, rid, name, split, train, output, metrics, per_race, artifact, experiment, elapsed)
        metric_rows.append(dict(model=name, split=split, year=year, run_id=rid, fit_seconds=elapsed, **metrics))
        output["model"], output["split"], output["run_id"] = name, split, rid
        per_race["model"], per_race["split"], per_race["year"] = name, split, year
        all_predictions.append(output)
        all_per_race.append(per_race)
        runs[(name, year)] = artifact
        print(f"{split} {year} | {name}: MAE rank={metrics['mae_rank']:.3f}, races={metrics['n_races']}", flush=True)
        return model, output, artifact, rid

    for year in folds:
        for name in NAMES:
            run_fold(name, year, "validation")
    # Chọn theo trung bình mỗi race của toàn bộ validation, rồi Spearman.
    cv = pd.concat(all_per_race)
    board = cv.groupby("model").agg(mae_rank=("mae_rank", "mean"), spearman=("spearman", "mean"),
                                    n_races=("race_id", "size")).reset_index()
    board = board.sort_values(["mae_rank", "spearman", "model"], ascending=[True, False, True])
    selected = board.iloc[0].model
    board.to_csv(folder / "validation_leaderboard.csv", index=False)
    (folder / "selection.json").write_text(json.dumps({"selected": selected, "reason": "Lowest race-macro validation MAE; Spearman tie-break",
                                                        "frozen_before_test": True, "folds": folds}, indent=2))
    # Giải thích trên validation, không chọn feature từ test.
    last_train, last_valid = time_split(frame, folds[-1])
    bundle = joblib.load(runs[(selected, folds[-1])])
    base_mae = evaluate(ranked(last_valid, score_model(selected, bundle["model"], last_valid)))[0]["mae_rank"]
    rng, importance = np.random.default_rng(42), []
    for column in FEATURES:
        increases = []
        for _ in range(3):
            shuffled = last_valid.copy()
            shuffled[column] = rng.permutation(shuffled[column].to_numpy())
            error = evaluate(ranked(shuffled, score_model(selected, bundle["model"], shuffled)))[0]["mae_rank"]
            increases.append(error - base_mae)
        importance.append({"feature": column, "mae_increase": float(np.mean(increases)), "std": float(np.std(increases))})
    pd.DataFrame(importance).sort_values("mae_increase", ascending=False).to_csv(folder / "importance.csv", index=False)

    test_available = bool(((frame.season == test_year) & frame.eligible).any())
    selected_artifact, selected_run = None, None
    if test_available:
        for name in NAMES:
            _, _, artifact, run_id = run_fold(name, test_year, "test")
            if name == selected:
                selected_artifact, selected_run = artifact, run_id
    else:
        # Train cho tương lai dù chưa có nhãn test. Không bịa test metric.
        train = frame[(frame.season < test_year) & frame.eligible]
        model = None if selected.startswith("Baseline") else pipeline(selected).fit(train[FEATURES], train.label)
        selected_artifact = folder / "forecast.joblib"
        joblib.dump({"name": selected, "model": model, "train_through": train.start_utc.max(), "version": VERSION,
                     "features": FEATURES, "data_sha256": fingerprint}, selected_artifact)
    pd.DataFrame(metric_rows).to_csv(folder / "metrics.csv", index=False)
    pd.concat(all_predictions).to_csv(folder / "predictions.csv", index=False)
    pd.concat(all_per_race).to_csv(folder / "race_metrics.csv", index=False)
    frame.to_csv(folder / "features.csv", index=False)
    (folder / "coverage.csv").write_text((ROOT / "data" / "processed" / "coverage.csv").read_text())
    summary = {"experiment": experiment, "created_at": utcnow().isoformat(), "selected": selected,
               "selected_artifact": str(selected_artifact.relative_to(ROOT)), "selected_run": selected_run,
               "test_year": test_year, "test_available": test_available,
               "validation_years": folds, "data_sha256": fingerprint, "quality": quality,
               "protocol": "Frozen model / rolling past results; retrospective Q; race-macro metrics; no hyperparameter search"}
    (folder / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    latest = ROOT / "artifacts" / "latest.json"
    temp = latest.with_suffix(".tmp")
    temp.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    temp.replace(latest)
    return summary


def predict_race(db, race_id):
    latest = json.loads((ROOT / "artifacts" / "latest.json").read_text())
    artifact = ROOT / latest["selected_artifact"]
    bundle = joblib.load(artifact)  # Chỉ artifact do dự án tạo, không nhận file upload.
    frame, _ = build_and_save(db)
    race = frame[frame.race_id == race_id]
    if race.empty:
        raise ValueError("Chặng chưa có Q hợp lệ. Chạy ingest --refresh sau Q.")
    if bundle["version"] != VERSION or bundle["features"] != FEATURES:
        raise ValueError("Model không cùng phiên bản feature; cần train lại")
    if not pd.Timestamp(bundle["train_through"]) < race.start_utc.min():
        raise ValueError("Model đã học sau chặng này. Hãy xem prediction backtest đã lưu.")
    output = ranked(race, score_model(bundle["name"], bundle["model"], race))
    rid = str(uuid.uuid4())
    with Session(db) as session, session.begin():
        session.add(ModelRun(id=rid, name=bundle["name"], split="inference",
                             train_through=pd.Timestamp(bundle["train_through"]).to_pydatetime(), artifact=str(artifact),
                             details={"experiment": latest["experiment"], "retrospective": bool(race.label.notna().all()),
                                      "feature_version": VERSION, "features": FEATURES}))
        session.flush()
        for row in output.to_dict("records"):
            session.add(Prediction(run_id=rid, snapshot_id=row["snapshot_id"], score=float(row["score"]), rank=int(row["predicted_rank"])))
    return output
