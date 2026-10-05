"""Kiểm thử hợp đồng OOP, orchestration và tương thích artifact trước refactor."""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from f1lab.config import AppConfig
from f1lab.db import Database, ROOT
from f1lab.ingest import IngestionService
from f1lab.features import FEATURES, NUMERIC, VERSION
from f1lab.ml import ExperimentTrainer, PredictionService, RaceEvaluator
from f1lab.models import ModelFactory, RaceModel
from f1lab.repositories import ArtifactRepository


@pytest.fixture
def feature_data():
    rows = []
    for season in range(2023, 2027):
        for round_number in range(1, 13):
            for driver in range(1, 5):
                row = {name: float(driver) for name in NUMERIC}
                row.update(race_id=season * 100 + round_number, driver_id=f"d{driver}",
                           driver_name=f"Driver {driver}", race_name=f"Race {round_number}",
                           team_name="Team", team_id="team", circuit_id="circuit", season=season,
                           start_utc=pd.Timestamp(datetime(season, 1, 1) + timedelta(days=round_number)),
                           quali_position=float(driver), label=float(driver), eligible=True,
                           version=VERSION, snapshot_id=f"{season}-{round_number}-{driver}")
                rows.append(row)
    return pd.DataFrame(rows)


@pytest.mark.parametrize("name", ModelFactory.names)
def test_models_share_fit_predict_contract(name, feature_data):
    model = ModelFactory().create(name)
    assert isinstance(model, RaceModel)
    assert model.fit(feature_data) is model
    holdout = feature_data.tail(4).copy()
    holdout["driver_form5"] = np.nan
    holdout["team_id"] = "new_team"
    scores = model.predict(holdout)
    assert scores.shape == (4,)
    assert np.isfinite(scores).all()
    if name == "Baseline phong độ":
        np.testing.assert_array_equal(scores, holdout.quali_position)


def test_ingestion_source_can_be_replaced_without_network():
    calls = []

    class Source:
        def download_year(self, year, refresh):
            calls.append((year, refresh))
            return {"year": year}

    class Repository:
        def import_year(self, payload):
            return {"imported": payload["year"]}

    service = IngestionService(None, source=Source(), repository=Repository())
    assert service.ingest(2026, refresh=True) == {"imported": 2026}
    assert calls == [(2026, True)]


@pytest.fixture
def trained_experiment(tmp_path, feature_data):
    config = AppConfig(tmp_path)
    config.processed_dir.mkdir(parents=True)
    pd.DataFrame({"race_id": feature_data.race_id.unique(), "status": "ready"}).to_csv(
        config.processed_dir / "coverage.csv", index=False)

    class FeatureProvider:
        def build_and_save(self):
            return feature_data.copy(), {"rows": len(feature_data)}

    class TwoModels(ModelFactory):
        names = ("Baseline Q", "Linear Regression")

    class RunRepository:
        def __init__(self):
            self.evaluations = []
            self.inferences = []

        def save_evaluation(self, run_id, name, split, train, predictions, metrics, per_race,
                            artifact, experiment, fit_seconds):
            assert train.start_utc.max() < predictions.start_utc.min()
            if split == "test":
                choice = json.loads((artifact.parent / "selection.json").read_text())
                assert choice["frozen_before_test"] is True
                assert choice["folds"] == [2024, 2025]
            self.evaluations.append((name, split, run_id))

        def save_inference(self, *args):
            self.inferences.append(args)

    provider, runs = FeatureProvider(), RunRepository()
    trainer = ExperimentTrainer(None, config=config, features=provider, models=TwoModels(), runs=runs)
    summary = trainer.train(2026)
    return SimpleNamespace(config=config, summary=summary, provider=provider, runs=runs)


def test_training_writes_consistent_artifacts_and_freezes_selection(trained_experiment):
    result = trained_experiment
    artifacts = ArtifactRepository(result.config)
    assert artifacts.load_latest() == result.summary
    assert len(result.runs.evaluations) == 6
    files = artifacts.load_experiment(result.summary["experiment"])
    assert files["metrics"].shape[0] == 6
    assert set(files["metrics"].split) == {"validation", "test"}
    assert result.summary["selected"] in ModelFactory.names
    assert result.summary["test_year"] == 2026


def test_prediction_guards_and_saved_output_with_injected_dependencies(trained_experiment):
    result = trained_experiment
    service = PredictionService(None, config=result.config, features=result.provider, runs=result.runs)
    with pytest.raises(ValueError, match="đã học sau"):
        service.predict(202401)
    with pytest.raises(ValueError, match="chưa có Q"):
        service.predict(202699)
    assert not result.runs.inferences
    predicted = service.predict(202601)
    assert sorted(predicted.predicted_rank) == [1, 2, 3, 4]
    assert len(result.runs.inferences) == 1


def test_database_engine_is_lazy_and_reused():
    database = Database("sqlite://")
    assert database._engine is None
    first = database.engine
    assert database.engine is first
    database.close()


@pytest.mark.skipif(not (ROOT / "artifacts/latest.json").exists(), reason="Cần artifact trước refactor")
def test_saved_models_keep_identical_scores_and_ranks():
    artifacts = ArtifactRepository()
    latest = artifacts.load_latest()
    predictions = artifacts.load_experiment(latest["experiment"])["predictions"]
    factory, evaluator = ModelFactory(), RaceEvaluator()
    for run_id, original in predictions.groupby("run_id"):
        bundle = artifacts.load_model(artifacts.experiment_folder(latest["experiment"]) / f"{run_id}.joblib")
        rebuilt = evaluator.rank(original, factory.from_bundle(bundle).predict(original))
        # Identity comparison prevents a sort-order coincidence from hiding changed predictions.
        keys = ["race_id", "driver_id"]
        expected = original.set_index(keys).sort_index()
        actual = rebuilt.set_index(keys).sort_index()
        np.testing.assert_allclose(actual.score, expected.score, rtol=1e-10, atol=1e-10)
        np.testing.assert_array_equal(actual.predicted_rank, expected.predicted_rank)


def test_session_collector_preserves_partial_data_manifest(tmp_path):
    from scripts.collect_session import SessionCollector

    class DataNotLoadedError(Exception):
        pass

    class Session:
        event = {"EventName": "Sample"}
        results = pd.DataFrame({"driver": ["A"]})
        weather_data = pd.DataFrame()

        def load(self, **options):
            assert options == dict(laps=True, telemetry=False, weather=True, messages=False)

        @property
        def laps(self):
            raise DataNotLoadedError("laps unavailable")

    api = SimpleNamespace(Cache=SimpleNamespace(enable_cache=lambda path: None),
                          get_session=lambda *args: Session(),
                          core=SimpleNamespace(DataNotLoadedError=DataNotLoadedError))
    collector = SessionCollector(tmp_path / "raw", tmp_path / "cache", api)
    folder, report = collector.collect(2026, 1, "Q")
    assert report["status"] == "partial"
    assert report["datasets"]["results"]["status"] == "exported"
    assert report["datasets"]["laps"]["status"] == "unavailable"
    assert report["datasets"]["weather_data"]["status"] == "empty"
    assert json.loads((folder / "manifest.json").read_text()) == report
    assert (folder / "results.csv").exists()


def test_mysql_manager_stops_only_pid_from_its_own_directory(tmp_path, monkeypatch):
    from scripts.local_mysql import LocalMySQLManager
    import signal

    calls = []
    monkeypatch.setattr("scripts.local_mysql.os.kill", lambda pid, sig: calls.append((pid, sig)))
    manager = LocalMySQLManager(tmp_path)
    manager.local.mkdir()
    manager.pid.write_text("12345")
    manager.stop()
    assert calls == [(12345, signal.SIGTERM)]
