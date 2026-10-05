import numpy as np
import pandas as pd


class WeekendFeatureBuilder:
    """Đầu vào chỉ gồm lịch sử kết thúc trước cutoff của phiên đầu cuối tuần."""
    def build_target(self, target, history, roster):
        if roster.empty or roster.driver_id.duplicated().any():
            raise ValueError("Danh sách tay đua thiếu hoặc trùng")
        sizes = history.groupby("session_id").driver_id.transform("size")
        history = history.assign(relative_rank=(history.position - 1) / (sizes - 1).clip(lower=1))
        past = history[(history.history_after_utc < target.cutoff_utc) & history.position.notna()].sort_values("start_utc")
        labels = roster.set_index("driver_id").position if "position" in roster else pd.Series(dtype=float)
        eligible = len(labels) == len(roster) and set(labels.dropna()) == set(range(1, len(roster) + 1))
        rows = []
        for item in roster.itertuples():
            same = past[past.kind == target.kind]
            race = past[past.kind == "R"]
            driver = same[same.driver_id == item.driver_id]
            team = same[same.team_id == item.team_id].groupby("session_id", sort=False).relative_rank.mean()
            race_driver = race[race.driver_id == item.driver_id]
            race_team = race[race.team_id == item.team_id].groupby("session_id", sort=False).relative_rank.mean()
            circuit = driver[driver.circuit_id == target.circuit_id]
            rows.append(dict(race_id=int(target.race_id), session_id=target.id, kind=target.kind,
                season=int(target.season), season_round=int(target.season_round), race_name=target.race_name,
                cutoff_utc=target.cutoff_utc, start_utc=target.start_utc, driver_id=item.driver_id,
                driver_name=item.driver_name, team_id=item.team_id, team_name=item.team_name,
                circuit_id=target.circuit_id, field_size=len(roster), label=labels.get(item.driver_id, np.nan),
                eligible=eligible, quali_position=0.0,  # phá hòa bằng ID, tuyệt đối không Q hiện tại
                driver_session_form=driver.relative_rank.tail(5).mean() if len(driver) else np.nan,
                team_session_form=team.tail(5).mean(), driver_race_form=race_driver.relative_rank.tail(5).mean() if len(race_driver) else np.nan,
                team_race_form=race_team.tail(5).mean(), circuit_session_form=circuit.relative_rank.mean() if len(circuit) else np.nan,
                session_history_count=len(driver), race_history_count=len(race_driver)))
        return pd.DataFrame(rows)

    def build(self, sessions, results):
        frames = []
        for target in sessions.itertuples():
            roster = results[results.session_id == target.id]
            if not roster.empty:
                frames.append(self.build_target(target, results, roster))
        if not frames:
            raise ValueError("Chưa có kết quả phiên; chạy weekend-data")
        return pd.concat(frames, ignore_index=True)

