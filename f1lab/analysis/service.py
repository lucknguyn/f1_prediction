from __future__ import annotations
import json
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from ..config import AppConfig
from ..features import dnf
from ..repositories import ResultRepository

NUMERIC = ['quali_position', 'race_position', 'points', 'q1_seconds', 'q2_seconds', 'q3_seconds', 'dnf']
PROFILE = ['quali_mean', 'race_mean', 'points_mean', 'dnf_rate', 'n_races']
LOWER = {'quali_mean', 'race_mean', 'dnf_rate'}


class RadarComparison:
    def normalize(self, population, drivers, attributes=None):
        attributes = attributes or PROFILE
        if len(drivers) != 2 or any(d not in population.driver_id.values for d in drivers):
            raise ValueError('Chọn đúng hai driver_id có trong mùa đã chọn.')
        if len(attributes) < 3 or len(set(attributes)) != len(attributes) or not set(attributes) <= set(PROFILE):
            raise ValueError('Radar cần ít nhất 3 thuộc tính khác nhau: ' + ', '.join(PROFILE))
        values = population.set_index('driver_id')[attributes].astype(float)
        low, high = values.min(), values.max()
        norm = (values - low) / (high - low).replace(0, np.nan)
        norm = norm.mask(values.notna() & (high == low), 0.5)
        for column in LOWER.intersection(attributes):
            norm[column] = 1 - norm[column]
        return norm.loc[drivers]


class AnalysisService:
    def __init__(self, db=None, config=None):
        self.db, self.config = db, config or AppConfig()

    def results(self):
        repository = ResultRepository(self.db)
        q, r = repository.read('Q'), repository.read('R')
        keys = ['race_id', 'driver_id']
        metadata = ['season', 'season_round', 'race_name', 'start_utc', 'circuit_id', 'driver_name', 'team_id', 'team_name']
        q = q[keys + metadata + ['position', 'q1_seconds', 'q2_seconds', 'q3_seconds']].rename(columns={'position': 'quali_position'})
        r = r[keys + metadata + ['position', 'points', 'status']].rename(columns={'position': 'race_position'})
        frame = q.merge(r, on=keys, how='outer', suffixes=('', '_race'), validate='one_to_one')
        for col in metadata:
            frame[col] = frame[col].combine_first(frame.pop(col + '_race'))
        frame['dnf'] = frame.status.map(dnf)
        return frame.sort_values(['season', 'season_round', 'driver_id']).reset_index(drop=True)

    @staticmethod
    def statistics(frame):
        rows = []
        groups = [('all', 'all', None, frame)]
        groups += [('team', key, None, value) for key, value in frame.groupby('team_id')]
        groups += [('season', str(key), key, value) for key, value in frame.groupby('season')]
        groups += [('team_season', team, year, value) for (team, year), value in frame.groupby(['team_id', 'season'])]
        for kind, key, season, group in groups:
            for attribute in NUMERIC:
                values = group[attribute].dropna()
                rows.append(dict(group_type=kind, group_id=key, season=season, attribute=attribute,
                    count=len(values), mean=values.mean(), median=values.median(), std=values.std(ddof=1)))
        return pd.DataFrame(rows)

    @staticmethod
    def profiles(frame, season):
        # Chỉ những hàng thực sự có Race, không biến Q của chặng tương lai thành thành tích mùa.
        complete = frame[(frame.season == season) & frame.race_position.notna()]
        return complete.groupby(['driver_id', 'driver_name'], as_index=False).agg(
            quali_mean=('quali_position', 'mean'), race_mean=('race_position', 'mean'),
            points_mean=('points', 'mean'), dnf_rate=('dnf', 'mean'), n_races=('race_id', 'nunique'),
            quali_count=('quali_position', 'count'), dnf_count=('dnf', 'count'))

    @staticmethod
    def cluster(profiles):
        if len(profiles) < 5:
            raise ValueError('Cần ít nhất 5 tay đua để so sánh ba giá trị k.')
        values = SimpleImputer(strategy='median', keep_empty_features=True).fit_transform(profiles[PROFILE])
        scaler = StandardScaler()
        x = scaler.fit_transform(values)
        max_k = min(6, len(x) - 1, len(np.unique(x, axis=0)) - 1)
        if max_k < 4:
            raise ValueError('Chưa đủ hồ sơ khác nhau để so sánh ít nhất ba giá trị k.')
        board, models = [], {}
        for k in range(2, max_k + 1):
            model = KMeans(n_clusters=k, random_state=42, n_init=20).fit(x)
            board.append(dict(k=k, inertia=model.inertia_, silhouette=silhouette_score(x, model.labels_)))
            models[k] = model
        scores = pd.DataFrame(board)
        selected = int(scores.sort_values(['silhouette', 'k'], ascending=[False, True]).iloc[0].k)
        model, pca = models[selected], PCA(n_components=2, random_state=42)
        result = profiles.copy()
        result[['PC1', 'PC2']] = pca.fit_transform(x)
        result['cluster'] = model.labels_
        centers = pd.DataFrame(scaler.inverse_transform(model.cluster_centers_), columns=PROFILE)
        centers.index.name = 'cluster'
        return result, scores, centers.reset_index(), {'selected_k': selected,
            'explained_variance_ratio': pca.explained_variance_ratio_.tolist(), 'seed': 42,
            'features': PROFILE, 'n_drivers': len(profiles), 'selection': 'maximum silhouette; smaller k breaks ties'}

    def export(self, season=2025):
        from .plots import export_plots
        folder = self.config.processed_dir / 'analysis'
        folder.mkdir(parents=True, exist_ok=True)
        frame = self.results()
        stats, profiles = self.statistics(frame), self.profiles(frame, season)
        clustered, scores, centers, summary = self.cluster(profiles)
        summary['season'] = season
        outputs = {'results': frame, 'results2': stats, 'driver_season': profiles,
                   'clusters': clustered, 'cluster_scores': scores, 'cluster_centers': centers}
        extremes = []
        for col in NUMERIC:
            for label, subset in [('lowest', frame.nsmallest(3, col)), ('highest', frame.nlargest(3, col))]:
                extremes.append(subset.assign(attribute=col, extreme=label))
        outputs['extremes'] = pd.concat(extremes)
        for name, data in outputs.items():
            data.to_csv(folder / f'{name}.csv', index=False, na_rep='N/a')
        dictionary = []
        for col in frame:
            unit = 'seconds' if col.endswith('_seconds') else 'rank' if 'position' in col else 'points' if col == 'points' else '0/1' if col == 'dnf' else 'UTC' if col == 'start_utc' else 'identifier/text'
            dictionary.append(dict(attribute=col, dtype=str(frame[col].dtype), unit=unit,
                                   missing='N/a in CSV; NULL in MySQL; never impute target'))
        pd.DataFrame(dictionary).to_csv(folder / 'data_dictionary.csv', index=False)
        quality = {'rows': len(frame), 'duplicate_driver_race': int(frame.duplicated(['race_id', 'driver_id']).sum()),
                   'missing': frame.isna().sum().to_dict(), 'iqr_outliers': {},
                   'policy': 'Keep valid extremes and DNF; inspect IQR flags, do not delete automatically. Q2/Q3 missing can mean elimination; do not replace with zero.'}
        for col in NUMERIC:
            q1, q3 = frame[col].quantile([.25, .75]); spread=q3-q1
            quality['iqr_outliers'][col] = int(((frame[col] < q1-1.5*spread) | (frame[col] > q3+1.5*spread)).sum())
        (folder/'quality_report.json').write_text(json.dumps(quality, indent=2, ensure_ascii=False))
        (folder/'summary.json').write_text(json.dumps(summary, indent=2))
        export_plots(frame, clustered, scores, profiles, folder)
        return summary
