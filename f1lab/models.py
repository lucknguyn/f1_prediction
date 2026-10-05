"""Các chiến lược dự đoán có cùng giao diện fit/predict."""
from abc import ABC, abstractmethod

from catboost import CatBoostRegressor
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .features import CATEGORICAL, FEATURES, NUMERIC


def _regression_pipeline(name):
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

class RaceModel(ABC):
    """Hợp đồng chung; baseline và hồi quy đều trả điểm để xếp hạng."""
    estimator = None

    @abstractmethod
    def fit(self, frame):
        """Học từ frame gồm FEATURES và label; trả về chính đối tượng."""

    @abstractmethod
    def predict(self, frame):
        """Trả một điểm liên tục cho mỗi tay đua."""


class QualifyingBaseline(RaceModel):
    name = "Baseline Q"

    def fit(self, frame):
        return self

    def predict(self, frame):
        return frame.quali_position.to_numpy(float)


class FormBaseline(RaceModel):
    name = "Baseline phong độ"

    def fit(self, frame):
        return self

    def predict(self, frame):
        return frame.driver_form5.fillna(frame.quali_position).to_numpy(float)


class RegressionModel(RaceModel):
    def __init__(self, name, estimator=None):
        self.name = name
        self.estimator = estimator if estimator is not None else _regression_pipeline(name)

    def fit(self, frame):
        self.estimator.fit(frame[FEATURES], frame.label)
        return self

    def predict(self, frame):
        return self.estimator.predict(frame[FEATURES])


class ModelFactory:
    names = ("Baseline Q", "Baseline phong độ", "Linear Regression", "Random Forest", "HistGradientBoosting", "CatBoost")

    def create(self, name, estimator=None):
        if name == "Baseline Q":
            return QualifyingBaseline()
        if name == "Baseline phong độ":
            return FormBaseline()
        if name not in self.names:
            raise ValueError(f"Mô hình không được hỗ trợ: {name}")
        return RegressionModel(name, estimator)

    def from_bundle(self, bundle):
        return self.create(bundle["name"], bundle["model"])
