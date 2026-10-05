"""Schema dùng chung cho MySQL; SQLite chỉ dùng trong unit test."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import (JSON, CheckConstraint, Column, DateTime, Float, ForeignKey,
                        ForeignKeyConstraint, Integer, String, UniqueConstraint,
                        create_engine, text)
from sqlalchemy.orm import DeclarativeBase
from .config import AppConfig

ROOT = AppConfig().root


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Driver(Base):
    __tablename__ = "drivers"
    id = Column(String(80), primary_key=True)
    name = Column(String(160), nullable=False)
    code = Column(String(10))


class Team(Base):
    __tablename__ = "teams"
    id = Column(String(80), primary_key=True)
    name = Column(String(160), nullable=False)


class Circuit(Base):
    __tablename__ = "circuits"
    id = Column(String(80), primary_key=True)
    name = Column(String(160), nullable=False)
    country = Column(String(80))


class Race(Base):
    __tablename__ = "races"
    id = Column(Integer, primary_key=True)  # season * 100 + round
    season = Column(Integer, nullable=False, index=True)
    round = Column(Integer, nullable=False)
    name = Column(String(160), nullable=False)
    circuit_id = Column(String(80), ForeignKey("circuits.id"), nullable=False)
    start_utc = Column(DateTime, nullable=False, index=True)
    __table_args__ = (UniqueConstraint("season", "round"), CheckConstraint("round > 0"))


class Entry(Base):
    __tablename__ = "entries"
    race_id = Column(Integer, ForeignKey("races.id"), primary_key=True)
    driver_id = Column(String(80), ForeignKey("drivers.id"), primary_key=True)
    team_id = Column(String(80), ForeignKey("teams.id"), nullable=False)


class RaceSession(Base):
    __tablename__ = "sessions"
    id = Column(String(24), primary_key=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    kind = Column(String(4), nullable=False)
    exported_at = Column(DateTime, nullable=False)
    source = Column(String(120), nullable=False)
    __table_args__ = (UniqueConstraint("race_id", "kind"), UniqueConstraint("race_id", "id"))


class Result(Base):
    __tablename__ = "session_results"
    session_id = Column(String(24), primary_key=True)
    driver_id = Column(String(80), primary_key=True)
    race_id = Column(Integer, nullable=False, index=True)
    position = Column(Integer)
    q1_seconds = Column(Float)
    q2_seconds = Column(Float)
    q3_seconds = Column(Float)
    points = Column(Float)
    status = Column(String(120))
    __table_args__ = (
        ForeignKeyConstraint(["race_id", "session_id"], ["sessions.race_id", "sessions.id"]),
        ForeignKeyConstraint(["race_id", "driver_id"], ["entries.race_id", "entries.driver_id"]),
        CheckConstraint("position IS NULL OR position > 0"),
    )


class Weather(Base):
    __tablename__ = "weather_observations"
    session_id = Column(String(24), ForeignKey("sessions.id"), primary_key=True)
    elapsed_seconds = Column(Float, primary_key=True)
    air_temp = Column(Float)
    track_temp = Column(Float)
    humidity = Column(Float)
    wind_speed = Column(Float)
    rainfall = Column(Integer)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id = Column(String(36), primary_key=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    source = Column(String(120), nullable=False)
    status = Column(String(24), nullable=False)
    details = Column(JSON, nullable=False)


class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"
    id = Column(String(64), primary_key=True)  # hash of content + version
    race_id = Column(Integer, nullable=False, index=True)
    driver_id = Column(String(80), nullable=False)
    cutoff_utc = Column(DateTime, nullable=False)
    version = Column(String(32), nullable=False)
    features = Column(JSON, nullable=False)
    label = Column(Integer)
    __table_args__ = (ForeignKeyConstraint(["race_id", "driver_id"], ["entries.race_id", "entries.driver_id"]),)


class ModelRun(Base):
    __tablename__ = "model_runs"
    id = Column(String(36), primary_key=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    name = Column(String(80), nullable=False)
    train_through = Column(DateTime, nullable=False)
    split = Column(String(32), nullable=False)
    artifact = Column(String(512))
    details = Column(JSON, nullable=False)


class Prediction(Base):
    __tablename__ = "predictions"
    run_id = Column(String(36), ForeignKey("model_runs.id"), primary_key=True)
    snapshot_id = Column(String(64), ForeignKey("feature_snapshots.id"), primary_key=True)
    score = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False)
    __table_args__ = (CheckConstraint("`rank` > 0"),)


class EvaluationMetric(Base):
    __tablename__ = "evaluation_metrics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("model_runs.id"), nullable=False, index=True)
    race_id = Column(Integer, ForeignKey("races.id"))
    name = Column(String(64), nullable=False)
    value = Column(Float)


class Database:
    """Sở hữu engine; tạo kết nối khi cần và giải phóng pool bằng close()."""
    def __init__(self, url=None, config=None):
        self.config = config if config is not None else AppConfig()
        self.url = url
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            load_dotenv(self.config.root / ".env")
            url = self.url or os.getenv("DATABASE_URL")
            if not url:
                raise RuntimeError("Chưa cấu hình MySQL. Chạy: .venv/bin/python scripts/local_mysql.py start")
            self._engine = create_engine(url, pool_pre_ping=True)
        return self._engine

    def initialize(self):
        initialize(self.engine)

    def close(self):
        if self._engine is not None:
            self._engine.dispose()


def engine():
    """Compatibility adapter; ứng dụng mới sở hữu đối tượng Database."""
    return Database().engine


VIEW_SQL = """CREATE OR REPLACE VIEW prediction_comparison AS
        SELECT m.id AS run_id, m.name AS model, m.split, r.season, r.round,
               r.name AS race, d.name AS driver, t.name AS team,
               p.score, p.rank AS predicted_rank, f.label AS actual_rank
        FROM predictions p JOIN model_runs m ON m.id = p.run_id
        JOIN feature_snapshots f ON f.id = p.snapshot_id
        JOIN races r ON r.id = f.race_id JOIN drivers d ON d.id = f.driver_id
        JOIN entries e ON e.race_id = f.race_id AND e.driver_id = f.driver_id
        JOIN teams t ON t.id = e.team_id"""


def initialize(db):
    Base.metadata.create_all(db)
    with db.begin() as conn:
        conn.execute(text(VIEW_SQL))


class WeekendSession(Base):
    """Lịch thực tế từng phiên; tách khỏi schema Q/R v1 để giữ artifact cũ."""
    __tablename__ = "weekend_sessions"
    id = Column(String(24), primary_key=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False, index=True)
    kind = Column(String(4), nullable=False)
    start_utc = Column(DateTime, nullable=False)
    cutoff_utc = Column(DateTime, nullable=False)  # trước phiên đầu tiên cuối tuần
    history_after_utc = Column(DateTime, nullable=False)  # start + 6h bảo thủ
    collected_at = Column(DateTime, nullable=False, default=utcnow)
    status = Column(String(32), nullable=False, default="scheduled")
    source = Column(String(120), nullable=False)
    details = Column(JSON, nullable=False, default=dict)
    __table_args__ = (UniqueConstraint("race_id", "kind"),)


class WeekendResult(Base):
    __tablename__ = "weekend_results"
    session_id = Column(String(24), ForeignKey("weekend_sessions.id"), primary_key=True)
    driver_id = Column(String(80), ForeignKey("drivers.id"), primary_key=True)
    team_id = Column(String(80), ForeignKey("teams.id"), nullable=False)
    position = Column(Integer)
    best_seconds = Column(Float)
    __table_args__ = (CheckConstraint("position IS NULL OR position > 0"),)


class WeekendRun(Base):
    __tablename__ = "weekend_runs"
    id = Column(String(36), primary_key=True)
    session_id = Column(String(24), ForeignKey("weekend_sessions.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    cutoff_utc = Column(DateTime, nullable=False)
    model = Column(String(80), nullable=False)
    artifact = Column(String(512), nullable=False)
    details = Column(JSON, nullable=False)


class WeekendPrediction(Base):
    __tablename__ = "weekend_predictions"
    run_id = Column(String(36), ForeignKey("weekend_runs.id"), primary_key=True)
    driver_id = Column(String(80), ForeignKey("drivers.id"), primary_key=True)
    score = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False)
    actual_rank = Column(Integer)
    features = Column(JSON, nullable=False)
    __table_args__ = (CheckConstraint("`rank` > 0"),)
