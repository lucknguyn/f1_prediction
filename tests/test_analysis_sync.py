import json
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from f1lab.analysis.service import AnalysisService, RadarComparison, NUMERIC, PROFILE
from f1lab.config import AppConfig
from f1lab.sync import SyncService


def test_statistics_uses_sample_std_and_excludes_missing():
    frame = pd.DataFrame({col: [1., 3., np.nan] for col in NUMERIC})
    frame['team_id'], frame['season'] = ['a']*3, [2025]*3
    result = AnalysisService.statistics(frame)
    row = result.query("group_type == 'all' and attribute == 'points'").iloc[0]
    assert row['count'] == 2 and row['mean'] == 2 and row['median'] == 2
    assert row['std'] == pytest.approx(2**.5)
    assert set(result.group_type) == {'all','season','team','team_season'}


def profiles():
    frame = pd.DataFrame({key: [1.,2.,5.,8.,9.,12.] for key in PROFILE})
    frame['driver_id'] = list('abcdef')
    frame['driver_name'] = list('ABCDEF')
    return frame


def test_radar_uses_entire_population_and_reverses_low_is_good():
    result = RadarComparison().normalize(profiles(), ['a','b'])
    assert result.loc['b','points_mean'] == pytest.approx(1/11)
    assert result.loc['b','race_mean'] == pytest.approx(10/11)
    data = profiles(); data['n_races'] = 24
    assert RadarComparison().normalize(data, ['a','b']).n_races.tolist() == [.5,.5]
    with pytest.raises(ValueError): RadarComparison().normalize(data,['a','unknown'])


def test_cluster_reproducible_with_three_candidates_and_pca():
    first = AnalysisService.cluster(profiles())
    second = AnalysisService.cluster(profiles())
    assert len(first[1]) >= 3
    assert first[0].cluster.tolist() == second[0].cluster.tolist()
    assert first[3]['selected_k'] == int(first[1].sort_values(['silhouette','k'],ascending=[False,True]).iloc[0].k)
    assert sum(first[3]['explained_variance_ratio']) <= 1.0000001
    with pytest.raises(ValueError): AnalysisService.cluster(profiles().head(3))


def test_profiles_exclude_future_q_only_and_report_coverage():
    frame = pd.DataFrame(dict(season=[2025]*3,driver_id=['a']*3, driver_name=['A']*3,
        race_id=[1,2,3],race_position=[2,4,np.nan],quali_position=[1,np.nan,3],points=[18,12,np.nan],dnf=[0,1,np.nan]))
    result=AnalysisService.profiles(frame,2025).iloc[0]
    assert result.n_races == 2 and result.race_mean == 3 and result.quali_count == 1


def test_sync_ttl_failure_preserves_success_and_retries(tmp_path):
    clock=[datetime(2026,10,6,tzinfo=timezone.utc)]
    calls=[]
    class Ingest:
        fail=False
        def ingest(self, year, refresh):
            calls.append(year)
            if self.fail: raise RuntimeError('network unavailable')
    source=Ingest()
    class Collector:
        repository=SimpleNamespace(sessions=lambda: pd.DataFrame(dict(season=[2026],start_utc=[pd.Timestamp('2026-10-04')],race_id=[202616],season_round=[16])))
        def collect(self,*args,**kwargs): return [{'session':'202616-R','status':'ready'}]
    service=SyncService(None,AppConfig(tmp_path),source,Collector(),clock=lambda:clock[0])
    good=service.run(); assert good['status']=='ok' and calls==[2026]
    assert service.run()==good and calls==[2026]
    clock[0]+=timedelta(minutes=16);source.fail=True
    bad=service.run();assert bad['status']=='error' and bad['last_success']==good['last_success']
    assert bad['last_calendar_success']==good['last_calendar_success']
    source.fail=False;clock[0]+=timedelta(minutes=16)
    assert service.run()['status']=='ok' and len(calls)==3


def test_sync_cross_process_lock_skips_work(tmp_path):
    import fcntl
    service=SyncService(None,AppConfig(tmp_path))
    service.folder.mkdir(parents=True)
    with (service.folder/'sync.lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert service.run(force=True)=={'status':'running'}
