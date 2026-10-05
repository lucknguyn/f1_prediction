"""Constantes và chuyển đổi thời gian dùng chung, không chứa nghiệp vụ."""
import pandas as pd

KINDS = {"Practice 1": "FP1", "Practice 2": "FP2", "Practice 3": "FP3",
         "Qualifying": "Q", "Sprint": "S", "Sprint Qualifying": "SQ", "Sprint Shootout": "SQ", "Race": "R"}
LABELS = {"FP1": "FP1", "FP2": "FP2", "FP3": "FP3", "Q": "Qualifying", "SQ": "Sprint Qualifying", "S": "Sprint", "R": "Race"}
NUMERIC = ["driver_session_form", "team_session_form", "driver_race_form", "team_race_form",
           "circuit_session_form", "session_history_count", "race_history_count", "season_round", "field_size"]
CATEGORICAL = ["team_id", "circuit_id"]
FEATURES = NUMERIC + CATEGORICAL
VERSION = "preweekend-v1"


def utc_timestamp(value):
    stamp = pd.Timestamp(value)
    return stamp.tz_convert("UTC").tz_localize(None) if stamp.tzinfo else stamp
