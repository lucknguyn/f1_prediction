"""Kiểm chứng dự đoán từng phiên không nhìn FP/Q của cuối tuần hiện tại."""
import json
from types import SimpleNamespace
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from f1lab.config import AppConfig
from f1lab.weekend import (FEATURES, WeekendCollector, WeekendFeatureBuilder,
                          WeekendFormModel, WeekendRegressionModel, WeekendTrainer,
                          WeekendPredictionService)


@pytest.fixture
def weekend_data():
    sessions, results = [], []
    for year in [2024, 2025, 2026]:
        for number in range(1, 6):
            cutoff = pd.Timestamp(datetime(year,2,1) + timedelta(days=number * 10))
            for offset, kind in enumerate(['FP1', 'Q', 'R']):
                sid = f'{year * 100 + number}-{kind}'
                meta = dict(id=sid, race_id=year*100+number, kind=kind, season=year,
                            season_round=number, circuit_id='track', race_name='Test', cutoff_utc=cutoff,
                            start_utc=pd.Timestamp(cutoff.to_pydatetime() + timedelta(hours=offset * 24 + 1)),
                            history_after_utc=pd.Timestamp(cutoff.to_pydatetime() + timedelta(hours=offset * 24 + 7)))
                sessions.append(meta)
                for driver in range(1, 5):
                    results.append(dict(session_id=sid, driver_id=f'd{driver}', driver_name=f'Driver {driver}',
                                        team_id=f't{(driver+1)//2}', team_name='Team', position=driver,
                                        **{k:v for k,v in meta.items() if k != 'id'}))
    return pd.DataFrame(sessions), pd.DataFrame(results)


def test_cutoff_excludes_current_weekend_and_future(weekend_data):
    sessions, results = weekend_data
    target = next(sessions[sessions.id == '202603-R'].itertuples())
    roster = results[results.session_id == target.id]
    builder = WeekendFeatureBuilder()
    before = builder.build_target(target, results, roster)
    changed = results.copy()
    changed.loc[changed.history_after_utc >= target.cutoff_utc, 'position'] = 99
    after = builder.build_target(target, changed, roster)
    pd.testing.assert_frame_equal(before[FEATURES], after[FEATURES])
    assert 'quali_position' not in FEATURES
    assert before.quali_position.eq(0).all()


@pytest.mark.parametrize('name',['baseline','Linear Regression','Random Forest','HistGradientBoosting'])
def test_each_model_handles_rookies_and_new_teams(name, weekend_data):
    sessions, results = weekend_data
    frame = WeekendFeatureBuilder().build(sessions, results)
    model = WeekendFormModel() if name == 'baseline' else WeekendRegressionModel(name)
    model.fit(frame[frame.season < 2026])
    holdout = frame.tail(4).copy()
    holdout['team_id'] = 'newteam'
    holdout['driver_session_form'] = np.nan
    assert np.isfinite(model.predict(holdout)).all()


def test_practice_deleted_lap_and_reserve_identity():
    results = pd.DataFrame([
        dict(DriverId='nan',TeamId='team',FullName='Reserve Driver',TeamName='Team',DriverNumber='99',Abbreviation='RES',Position=np.nan),
        dict(DriverId='regular',TeamId='team',FullName='Regular Driver',TeamName='Team',DriverNumber='1',Abbreviation='REG',Position=np.nan)])
    laps = pd.DataFrame(dict(DriverNumber=['99','99','1'], Deleted=[True,False,False],
                             LapTime=pd.to_timedelta([60,90,80],unit='s')))
    rows = WeekendCollector.normalize(SimpleNamespace(results=results,laps=laps),'FP1')
    assert rows[0]['driver_id'].startswith('live-')
    assert rows[0]['position'] == 2
    assert rows[0]['best_seconds'] == 90
    with pytest.raises(ValueError,match='Deleted'):
        WeekendCollector.normalize(SimpleNamespace(results=results,laps=laps.drop(columns='Deleted')),'FP1')


def test_sprint_quali_identity_from_source_abbreviation():
    results = pd.DataFrame([dict(DriverId='',TeamId='nan',FullName='Driver',TeamName='Team',DriverNumber='1',Abbreviation='REG',Position=1)])
    ids = results.assign(DriverId='regular',TeamId='team')
    rows = WeekendCollector.normalize(SimpleNamespace(results=results),'SQ',ids)
    assert rows[0]['driver_id'] == 'regular' and rows[0]['team_id'] == 'team'


def test_training_and_prediction_keep_separate_session_artifacts(tmp_path, weekend_data):
    sessions, results = weekend_data
    config = AppConfig(tmp_path)

    class Repository:
        def sessions(self): return sessions
        def results(self): return results
        def save_prediction(self,*args): return 'saved-run'

    trainer = WeekendTrainer(None, config)
    trainer.repository = Repository()
    summary = trainer.train()
    assert summary['sessions']['FP1']['status'] == 'ready'
    assert summary['sessions']['S']['status'] == 'insufficient_data'
    folder = config.artifacts_dir / 'weekend' / summary['experiment']
    for kind in ['FP1','Q','R']:
        assert json.loads((folder/f'{kind}-selection.json').read_text())['frozen_before_test']
    service = WeekendPredictionService(None, config)
    service.repository = Repository()
    prediction = service.predict('202605-R')
    assert set(prediction.predicted_rank) == {1,2,3,4}
    assert prediction.run_id.eq('saved-run').all()
    with pytest.raises(ValueError,match='không có trong lịch'):
        service.predict('202605-S')
    with pytest.raises(ValueError,match='đã học sau cutoff'):
        service.predict('202401-R')
    # Một phiên tương lai chưa có roster/nhãn: fallback chỉ lấy Race trước cutoff.
    future = sessions[sessions.id == '202605-R'].copy()
    future['id'] = '202606-R'; future['race_id']=202606; future['season_round']=6
    future['cutoff_utc'] += np.timedelta64(10, 'D')
    future['start_utc'] += np.timedelta64(10, 'D')
    future['history_after_utc'] += np.timedelta64(10, 'D')
    sessions = pd.concat([sessions,future],ignore_index=True)
    output = service.predict('202606-R')
    assert output.label.isna().all()
    assert output.roster_source.str.contains('gần nhất').all()
