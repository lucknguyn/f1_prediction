import json
import joblib
import numpy as np
from ..config import AppConfig
from ..ml import RaceEvaluator
from .common import FEATURES, VERSION
from .repository import WeekendRepository
from .features import WeekendFeatureBuilder
from .training import WeekendFormModel, WeekendRegressionModel


class WeekendPredictionService:
    def __init__(self, db, config=None):
        self.config = config or AppConfig()
        self.repository = WeekendRepository(db)

    def predict(self, session_id):
        sessions = self.repository.sessions()
        target_rows = sessions[sessions.id == session_id]
        if target_rows.empty:
            raise ValueError("Phiên này không có trong lịch của chặng")
        target = next(target_rows.itertuples())
        summary_path = self.config.artifacts_dir / "weekend" / "latest.json"
        if not summary_path.exists():
            raise ValueError("Cần huấn luyện mô hình từng phiên trước")
        summary = json.loads(summary_path.read_text())
        info = summary["sessions"].get(target.kind, {})
        if info.get("status") != "ready":
            raise ValueError("Chưa đủ dữ liệu lịch sử để huấn luyện phiên này")
        artifact = self.config.root / info["artifact"]
        bundle = joblib.load(artifact)
        if bundle["version"] != VERSION or bundle["features"] != FEATURES:
            raise ValueError("Phiên bản mô hình không tương thích")
        if not bundle["train_through"] < target.cutoff_utc:
            raise ValueError("Mô hình đã học sau cutoff; chỉ demo các mùa sau training")
        history = self.repository.results()
        roster = history[history.session_id == session_id]
        roster_source = "Danh sách tham gia phiên từ nguồn hồi cứu"
        if roster.empty:
            # Chưa có roster phiên: chỉ dùng danh sách phiên R gần nhất trước cutoff.
            candidates = history[(history.kind == "R") & (history.history_after_utc < target.cutoff_utc)]
            if candidates.empty:
                raise ValueError("Chưa có danh sách tay đua để dự đoán")
            roster = candidates[candidates.session_id == candidates.sort_values("start_utc").session_id.iloc[-1]].copy()
            roster["position"] = np.nan
            roster_source = "Tạm dùng danh sách Race gần nhất trước cutoff; cần xác nhận thay đổi tay đua/đội"
        frame = WeekendFeatureBuilder().build_target(target, history, roster)
        output = RaceEvaluator().rank(frame, bundle["model"].predict(frame))
        output["score"] = 1 + output.score * (output.field_size - 1)
        output["roster_source"] = roster_source
        output["run_id"] = self.repository.save_prediction(target, output, bundle, artifact.relative_to(self.config.root))
        return output

