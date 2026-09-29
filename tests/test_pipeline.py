"""Kiểm thử các rủi ro thật: leakage, ranking, temporal split, persistence."""
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from f1lab.db import Base, Entry, Race, RaceSession, Result
from f1lab.features import FEATURES, build_features, dnf
from f1lab.ingest import import_year, seconds
from f1lab.ml import evaluate, pipeline, ranked, time_split


def frames():
    rows = []
    for index in range(1, 15):
        for driver in range(1, 5):
            rows.append(dict(race_id=202200 + index, season=2022, season_round=index,
                             race_name=f"Race {index}", start_utc=pd.Timestamp(datetime(2022, 1, 1) + timedelta(days=14 * index)),
                             circuit_id="circuit", driver_id=f"d{driver}", driver_name=f"Driver {driver}",
                             team_id="t1" if driver < 3 else "t2", team_name="Team", position=driver,
                             points=5 - driver, status="Finished", q1_seconds=90 + driver,
                             q2_seconds=90 + driver if driver < 4 else np.nan,
                             q3_seconds=90 + driver if driver < 3 else np.nan))
    q = pd.DataFrame(rows)
    r = q.copy()
    r["position"] = 5 - r.position
    return q, r


def test_current_and_future_labels_cannot_change_features():
    q, r = frames()
    before, _ = build_features(q, r)
    r.loc[r.race_id >= 202207, "position"] = 5 - r.loc[r.race_id >= 202207, "position"]
    r.loc[r.race_id >= 202207, "points"] = 100
    r.loc[r.race_id >= 202207, "status"] = "Engine"
    after, _ = build_features(q, r)
    pd.testing.assert_frame_equal(before.loc[before.race_id <= 202207, FEATURES], after.loc[after.race_id <= 202207, FEATURES])


def test_team_rolling_counts_races_not_drivers():
    q, r = frames()
    frame, _ = build_features(q, r)
    row = frame[(frame.race_id == 202207) & (frame.driver_id == "d1")].iloc[0]
    assert row.driver_history_count == 6
    assert row.team_form5 == pytest.approx(3.5)
    assert row.team_points5 == pytest.approx(7)
    assert frame.iloc[0].driver_history_count == 0
    assert np.isnan(frame.iloc[0].driver_form5)


def test_missing_roster_excludes_whole_race_from_metrics():
    q, r = frames()
    r = r[~((r.race_id == 202207) & (r.driver_id == "d4"))]
    frame, coverage = build_features(q, r)
    race = frame[frame.race_id == 202207]
    assert len(race) == 4
    assert not race.eligible.any()
    assert race.label.isna().all()
    assert coverage.loc[coverage.race_id == 202207, "status"].item() == "incomplete_roster_or_positions"


def test_future_race_q_generates_features_without_labels():
    q, r = frames()
    r = r[r.race_id < 202214]
    frame, coverage = build_features(q, r)
    assert frame[frame.race_id == 202214].label.isna().all()
    assert coverage.loc[coverage.race_id == 202214, "status"].item() == "awaiting_race"


def test_duplicate_driver_is_rejected():
    q, r = frames()
    with pytest.raises(ValueError, match="Duplicate"):
        build_features(pd.concat([q, q.iloc[:1]]), r)


@pytest.mark.parametrize("n", [4, 20, 22])
def test_rank_is_permutation_with_stable_ties(n):
    frame = pd.DataFrame(dict(race_id=[1] * n, quali_position=range(1, n + 1), driver_id=[str(i) for i in range(n)]))
    result = ranked(frame, np.ones(n))
    assert result.predicted_rank.to_list() == list(range(1, n + 1))
    assert result.quali_position.to_list() == list(range(1, n + 1))


def test_metrics_match_hand_calculation():
    frame = pd.DataFrame(dict(race_id=[1] * 4, driver_id=list("abcd"), quali_position=[1, 2, 3, 4], label=[1, 2, 3, 4]))
    output = ranked(frame, [2, 1, 3, 4])
    metrics, _ = evaluate(output)
    assert metrics["mae_rank"] == 0.5
    assert metrics["rmse_rank"] == pytest.approx(np.sqrt(0.5))
    assert metrics["winner_hit"] == 0
    assert metrics["podium_overlap"] == 1
    assert metrics["exact_podium"] == 0


def test_temporal_split_never_splits_race():
    q, r = frames()
    frame, _ = build_features(q, r)
    frame.loc[frame.race_id >= 202212, "season"] = 2023
    train, valid = time_split(frame, 2023)
    assert not set(train.race_id) & set(valid.race_id)
    assert train.start_utc.max() < valid.start_utc.min()
    assert valid.groupby("race_id").size().eq(4).all()


def test_pipeline_new_category_missing_values_and_save_load(tmp_path):
    q, r = frames()
    frame, _ = build_features(q, r)
    model = pipeline("Random Forest").fit(frame[FEATURES], frame.label)
    holdout = frame.tail(4).copy()
    holdout["team_id"] = "rookie_team"
    holdout["driver_form5"] = np.nan
    predicted = model.predict(holdout[FEATURES])
    file = tmp_path / "model.joblib"
    joblib.dump(model, file)
    np.testing.assert_allclose(predicted, joblib.load(file).predict(holdout[FEATURES]))


@pytest.mark.parametrize("value, expected", [(None, None), ("", None), ("0:00.000", None), ("1:32.123", 92.123), ("bad", None)])
def test_lap_time_cleaning(value, expected):
    assert seconds(value) == (pytest.approx(expected) if expected is not None else None)


def test_dnf_definition():
    assert dnf("Finished") == 0
    assert dnf("+2 Laps") == 0
    assert dnf("Engine") == 1
    assert np.isnan(dnf("Disqualified"))


@pytest.fixture
def db():
    db = create_engine("sqlite://")
    @event.listens_for(db, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(db)
    return db


def payload():
    row = {"season": "2024", "round": "1", "raceName": "Sample", "date": "2024-03-02", "time": "15:00:00Z",
           "Circuit": {"circuitId": "bahrain", "circuitName": "Bahrain", "Location": {"country": "Bahrain"}}}
    driver = {"Driver": {"driverId": "driver", "givenName": "A", "familyName": "B"},
              "Constructor": {"constructorId": "team", "name": "Team"}, "position": "1"}
    return {"year": 2024, "source": "synthetic unit fixture", "exported_at": "2026-01-01T00:00:00",
            "schedule": [row], "qualifying": [dict(row, QualifyingResults=[dict(driver, Q1="1:30.000")])],
            "results": [dict(row, Results=[dict(driver, points="25", status="Finished")])]}


def test_import_idempotence_and_rollback(db):
    source = payload()
    import_year(db, source)
    import_year(db, source)
    with Session(db) as session:
        assert len(session.scalars(select(Result)).all()) == 2
        assert len(session.scalars(select(Entry)).all()) == 1
    source["results"][0]["Results"].append(source["results"][0]["Results"][0])
    with pytest.raises(ValueError, match="Duplicate"):
        import_year(db, source)
    with Session(db) as session:
        assert len(session.scalars(select(Result)).all()) == 2


def test_database_rejects_orphan_result(db):
    with pytest.raises(IntegrityError):
        with Session(db) as session, session.begin():
            session.add(Result(session_id="missing", race_id=1, driver_id="missing", position=1))


def test_backup_restore_roundtrip_and_nonempty_guard(db, tmp_path):
    from f1lab.delivery import backup_database, restore_database
    import_year(db, payload())
    backup = tmp_path / "database.json.gz"
    counts = backup_database(db, backup)
    restored = create_engine("sqlite://")
    Base.metadata.create_all(restored)
    assert restore_database(restored, backup) == counts
    with Session(restored) as session:
        assert len(session.scalars(select(Result)).all()) == 2
        race = session.get(Race, 202401)
        assert race.start_utc == datetime(2024, 3, 2, 15)
    with pytest.raises(ValueError, match="trống"):
        restore_database(restored, backup)
