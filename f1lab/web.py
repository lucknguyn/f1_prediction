"""Chạy: streamlit run app.py — web học và demo trên dữ liệu thật."""
from __future__ import annotations

import logging
import os
import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from f1lab.db import Database
from f1lab.repositories import ArtifactRepository, DashboardRepository
from f1lab.features import FEATURES

ACCENT = "#f45145"
MUTED = "#8497ad"

def chart_style(fig, height=360):
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Arial", size=12), margin=dict(l=16, r=16, t=40, b=20), height=height,
                      legend=dict(orientation="h", y=1.15))
    fig.update_xaxes(gridcolor="#253040")
    fig.update_yaxes(gridcolor="#253040")
    return fig

@st.cache_data
def experiment_files(experiment):
    return ArtifactRepository().load_experiment(experiment)


@st.cache_resource
def dashboard_database():
    return Database()


@st.cache_data(ttl=30)
def db_overview():
    return DashboardRepository(dashboard_database().engine).overview()


@st.cache_data(ttl=30)
def read_table(name):
    return DashboardRepository(dashboard_database().engine).read_table(name)


@st.cache_resource
def source_worker():
    from .sync import SyncWorker
    return SyncWorker()


@st.fragment(run_every="60s")
def render_sync_status(engine):
    from .sync import SyncService
    state = SyncService(engine).status()
    stamp = state.get("last_calendar_success")
    revision = state.get("finished_at")
    known_revision = "source_revision" in st.session_state
    previous = st.session_state.get("source_revision")
    st.session_state["source_revision"] = revision
    if revision and revision != previous:
        db_overview.clear()
        read_table.clear()
        from .analysis.web import analysis_frame
        analysis_frame.clear()
        if known_revision:
            st.rerun()
    with st.sidebar:
        st.caption("Tự đồng bộ 15 phút/lần khi ứng dụng đang chạy. Lịch lấy từ nguồn, không cố định tên chặng.")
        if stamp:
            local = pd.Timestamp(stamp).tz_convert("Asia/Ho_Chi_Minh")
            st.caption(f"Lịch cập nhật: {local:%d/%m/%Y %H:%M} (Việt Nam)")
        if state.get("status") == "running":
            st.caption("Đang kiểm tra dữ liệu mới…")
        elif state.get("status") in ("error", "partial"):
            st.caption("Một phần nguồn chưa tải được; đang dùng dữ liệu đã lưu và sẽ thử lại.")
        if st.button("Xem dữ liệu mới", key="reload_source"):
            db_overview.clear()
            read_table.clear()
            from .analysis.web import analysis_frame
            analysis_frame.clear()
            st.rerun()


class DashboardApp:
    def __init__(self, artifacts=None, database=None, overview_loader=None, experiment_loader=None, table_loader=None):
        self.artifacts = artifacts if artifacts is not None else ArtifactRepository()
        self.database = database if database is not None else dashboard_database()
        self.overview_loader = overview_loader if overview_loader is not None else db_overview
        self.experiment_loader = experiment_loader if experiment_loader is not None else experiment_files
        self.table_loader = table_loader if table_loader is not None else read_table
        self.pages = {
            "Dự đoán": self.render_forecasts,
            "Phân tích": self.render_analysis,
            "Mô hình": self.render_models,
            "Dữ liệu": self.render_data,
        }

    def render_forecasts(self):
        scope = st.radio("Thời điểm dự đoán", ["Trước cuối tuần", "Q → Race (đối chứng)"],
                         horizontal=True, key="prediction_scope")
        if scope == "Trước cuối tuần":
            self.render_weekend()
        elif hasattr(self, "summary"):
            self.render_predictions()
        else:
            st.info("Chưa huấn luyện thí nghiệm Q → Race.")

    def render_analysis(self):
        if self.db_ok:
            from .analysis.web import render_analysis
            render_analysis(self.database.engine)
        else:
            st.warning("Cần kết nối MySQL để phân tích dữ liệu.")


    def run(self):
        st.set_page_config(page_title="F1 Lab · Race intelligence", page_icon="🏁", layout="wide")
        st.markdown("""<style>
        .block-container {max-width:1360px;padding-top:2.2rem;padding-bottom:3rem}
        h1 {font-size:2.8rem!important;letter-spacing:-.06em;line-height:1.08!important}
        h2 {letter-spacing:-.03em} [data-testid="stMetricValue"]{font-variant-numeric:tabular-nums}
        .eyebrow {color:#f45145;font-size:.76rem;letter-spacing:.2em;font-weight:700;margin-bottom:1.15rem}
        .intro {color:#aab6c6;font-size:1.03rem;max-width:700px;line-height:1.65}
        .rule {height:1px;background:#2a3442;margin:1.6rem 0}
        .small-note {color:#aab6c6;font-size:.82rem;line-height:1.55}
        .brand {font-size:1.65rem;font-weight:800;letter-spacing:-.08em;margin-bottom:.25rem}
        .brand span {color:#f45145}.number {font-size:2rem;font-weight:700;color:#f45145}
        </style>""", unsafe_allow_html=True)
        st.sidebar.markdown('<div class="brand">F1<span> / </span>LAB</div>', unsafe_allow_html=True)
        st.sidebar.caption("MACHINE LEARNING · MYSQL · PYTHON")
        st.sidebar.markdown("---")
        page = st.sidebar.radio("Không gian làm việc", list(self.pages), label_visibility="collapsed", key="navigation", index=0)
        st.sidebar.markdown("---")
        st.sidebar.caption("Toàn bộ cuối tuần: dự đoán trước FP1, không dùng Q hiện tại. Q → Race là thí nghiệm riêng để so sánh.")

        self.db_ok = True
        try:
            self.db_version, self.counts, self.schedule = self.overview_loader()
            st.sidebar.success("MySQL đã kết nối")
        except Exception:
            logging.getLogger(__name__).exception("Không kết nối/đọc được MySQL")
            self.db_ok, self.counts, self.schedule = False, {}, pd.DataFrame()
            st.sidebar.warning("MySQL chưa kết nối. Đang xem artifact đã lưu.")

        if self.db_ok:
            if os.getenv("F1_AUTO_SYNC", "1") != "0":
                source_worker()
            render_sync_status(self.database.engine)
        latest_path = self.artifacts.config.artifacts_dir / "latest.json"
        if latest_path.exists():
            self.summary = self.artifacts.load_latest()
            self.data = self.experiment_loader(self.summary["experiment"])
            self.features, self.predictions, self.metrics = self.data["features"], self.data["predictions"], self.data["metrics"]
            self.selected = self.summary["selected"]
            self.test_year = self.summary["test_year"]
            test = self.metrics[(self.metrics.split == "test") & (self.metrics.model == self.selected)]
            self.best_test = test.iloc[0] if not test.empty else None
        elif page == "Mô hình":
            st.info("Chưa có thí nghiệm. Chạy python -m f1lab train --test-year 2026.")
            return
        self.pages[page]()
        st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
        st.caption("F1 LAB / Đồ án học tập · Dữ liệu FastF1 & Jolpica · Kết quả thực nghiệm, không phải đảm bảo thứ hạng tương lai.")

    def render_weekend(self):
        from f1lab.weekend import WeekendRepository, WeekendPredictionService, LABELS
        st.title("Dự đoán trước khi cuối tuần bắt đầu.")
        st.caption("FP1 · FP2 · FP3 · Qualifying · Sprint Qualifying · Sprint · Race. Chỉ hiển thị các phiên có trong lịch thực tế.")
        if not self.db_ok:
            st.warning("Cần MySQL để đọc lịch phiên và lưu dự đoán.")
            return
        repo = WeekendRepository(self.database.engine)
        sessions = repo.sessions()
        if sessions.empty:
            st.info("Chưa tải lịch phiên. Chạy python -m f1lab weekend-data --years 2024 2025 2026.")
            return
        current = pd.Timestamp.now(tz="UTC").tz_localize(None)
        upcoming = sessions[(sessions.kind == "R") & (sessions.start_utc >= current)].head(1)
        past = sessions[(sessions.kind == "R") & (sessions.start_utc < current)].tail(1)
        if not past.empty:
            row = past.iloc[0]
            st.caption(f"Chặng vừa qua: {row.race_name} · {row.start_utc:%d/%m/%Y} · {row.circuit_id}")
        if not upcoming.empty:
            row = upcoming.iloc[0]
            st.info(f"Sắp tới: {row.race_name} · {row.start_utc:%d/%m/%Y} · {row.circuit_id}")
        years = sorted(sessions.season.unique(), reverse=True)
        year = st.selectbox("Mùa của cuối tuần", years, key="weekend_year")
        choices = sessions[sessions.season == year].drop_duplicates("race_id")
        names = choices.set_index("race_id").race_name.to_dict()
        # Mặc định mở chặng gần nhất đã bắt đầu, kể cả chưa nằm trong backtest cũ.
        started = choices[choices.cutoff_utc <= pd.Timestamp.now(tz="UTC").tz_localize(None)]
        coming = choices[(choices.cutoff_utc >= current) & (choices.cutoff_utc <= current + pd.Timedelta(days=7))]
        default = coming.race_id.iloc[0] if not coming.empty else started.race_id.iloc[-1] if not started.empty else choices.race_id.iloc[0]
        ids = choices.race_id.tolist()
        if st.session_state.get("weekend_race") not in ids:
            st.session_state["weekend_race"] = default
        race_id = st.selectbox("Chặng cuối tuần", ids,
                              format_func=lambda x: f"R{x % 100:02d} · {names[x]}", key="weekend_race")
        weekend = sessions[sessions.race_id == race_id]
        st.dataframe(weekend[["kind", "start_utc", "cutoff_utc", "status"]].rename(columns={
            "kind": "Phiên", "start_utc": "Bắt đầu UTC", "cutoff_utc": "Mốc dự đoán UTC", "status": "Dữ liệu"}),
            hide_index=True, width='stretch')
        available_sessions = weekend.id.tolist()
        if st.session_state.get("weekend_session") not in available_sessions:
            st.session_state["weekend_session"] = available_sessions[0]
        sid = st.selectbox("Phiên cần dự đoán", available_sessions,
                           format_func=lambda x: LABELS[x.split("-")[-1]], key="weekend_session")
        target = weekend[weekend.id == sid].iloc[0]
        cutoff = target.cutoff_utc.tz_localize("UTC").tz_convert("Asia/Ho_Chi_Minh")
        st.info(f"Mọi dự đoán ở đây dùng lịch sử trước {cutoff:%d/%m/%Y %H:%M:%S} giờ Việt Nam, trước phiên đầu tiên. Không dùng FP hay Q của chính chặng này.")
        if target.kind.startswith("FP"):
            st.caption("Mục tiêu FP: xếp hạng vòng nhanh nhất hợp lệ. Đây không phải tốc độ chạy dài hay thứ hạng Race; chương trình thử xe và lượng nhiên liệu làm FP khó dự đoán.")
        summary_path = self.artifacts.config.artifacts_dir / "weekend/latest.json"
        info = {}
        if summary_path.exists():
            summary = json.loads(summary_path.read_text())
            info = summary["sessions"].get(target.kind, {})
            st.caption(f"Mô hình phiên: {info.get('selected', 'chưa đủ dữ liệu')} · validation {summary['validation_year']} · huấn luyện trước {summary['test_year']}.")
        if st.button("Dự đoán và lưu phiên", key="predict_weekend", type="primary", disabled=info.get("status") != "ready"):
            try:
                st.session_state["weekend_output"] = WeekendPredictionService(self.database.engine).predict(sid)
            except ValueError as exc:
                st.warning(str(exc))
            except Exception:
                logging.getLogger(__name__).exception("Weekend prediction failed")
                st.error("Không lưu được dự đoán. Kiểm tra MySQL và nhật ký.")
        output = st.session_state.get("weekend_output")
        if output is not None and output.session_id.iloc[0] == sid:
            st.warning(output.roster_source.iloc[0] + ". Nguồn hồi cứu chưa có snapshot xác minh danh sách đã biết trước cutoff.")
            st.dataframe(output[["predicted_rank", "driver_name", "team_name", "label"]].rename(columns={
                "predicted_rank": "Dự đoán", "driver_name": "Tay đua", "team_name": "Đội", "label": "Thực tế"}), hide_index=True, width='stretch')
            if output.eligible.all():
                from f1lab.ml import RaceEvaluator
                metrics, _ = RaceEvaluator().evaluate(output)
                a, b, c = st.columns(3)
                a.metric("MAE hạng phiên", f"{metrics['mae_rank']:.2f}")
                b.metric("Spearman", f"{metrics['spearman']:.3f}")
                c.metric("Trùng top 3", f"{metrics['podium_overlap']:.0%}")
                st.caption("Đây là đối chiếu hồi cứu, không phải dự đoán được lưu từ trước lúc phiên diễn ra.")
            with st.expander("Đầu vào chỉ gồm lịch sử trước cuối tuần"):
                from f1lab.weekend import FEATURES as WEEKEND_FEATURES
                st.dataframe(output[["driver_name"] + WEEKEND_FEATURES], hide_index=True, width='stretch')
        results = repo.results()
        actual = results[results.session_id == sid].sort_values("position")
        with st.expander("Kết quả thật của phiên", expanded=output is None):
            if actual.empty:
                st.info("Chưa có kết quả phiên trong MySQL; không tạo kết quả giả.")
            else:
                st.dataframe(actual[["position", "driver_name", "team_name", "best_seconds"]], hide_index=True, width='stretch')
        if info.get("status") != "ready":
            st.warning("Chưa đủ dữ liệu lịch sử để huấn luyện phiên này. Chạy weekend-data rồi weekend-train; không dùng model Race giả làm model FP.")
        if summary_path.exists():
            with st.expander("Đánh giá riêng từng phiên và độ phủ"):
                folder = summary_path.parent / summary["experiment"]
                st.dataframe(pd.read_csv(folder / "metrics.csv"), hide_index=True, width='stretch')
                st.json(summary["sessions"])

    def render_race(self, race):
        race = race.sort_values("predicted_rank")
        a, b = st.columns([1.35, 1])
        with a:
            st.subheader("Thứ tự dự đoán")
            cols = ["predicted_rank", "driver_name", "team_name", "quali_position", "label"]
            shown = race[cols].rename(columns={"predicted_rank": "Dự đoán", "driver_name": "Tay đua", "team_name": "Đội", "quali_position": "Hạng Q", "label": "Thực tế"})
            st.dataframe(shown, hide_index=True, width="stretch", height=540)
            st.download_button("Tải kết quả CSV", race.to_csv(index=False).encode("utf-8-sig"), file_name=f"prediction-{int(race.race_id.iloc[0])}.csv", mime="text/csv")
        with b:
            st.subheader("Dự đoán lệch bao nhiêu?")
            if race.label.notna().all():
                plot = race.copy()
                plot["Sai lệch tuyệt đối (bậc)"] = (plot.predicted_rank - plot.label).abs()
                fig = px.bar(plot, x="Sai lệch tuyệt đối (bậc)", y="driver_name", orientation="h", color_discrete_sequence=[ACCENT],
                             labels={"driver_name": "Tay đua"}, hover_data=["predicted_rank", "label"])
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(chart_style(fig, 500), width="stretch")
                st.caption("Nguồn: prediction ngoài mẫu và kết quả FastF1/Jolpica của chặng đang chọn. 0 bậc = đúng thứ hạng.")
            else:
                st.info("Chưa có đầy đủ kết quả Race để đối chiếu. Thứ hạng dự đoán không phải xác suất thắng.")


    def render_predictions(self):
        st.markdown('<div class="eyebrow">RACE EXPLORER</div>', unsafe_allow_html=True)
        st.title("Đặt dự đoán cạnh thực tế.")
        mode = st.radio("Chế độ", ["Backtest đã lưu", "Chạy dự đoán từ Q hiện có"], horizontal=True, key="prediction_mode")
        if mode == "Backtest đã lưu":
            col1, col2 = st.columns(2)
            year = col1.selectbox("Mùa", sorted(self.predictions.season.unique(), reverse=True))
            model = col2.selectbox("Mô hình", list(self.data["validation_leaderboard"].model), index=list(self.data["validation_leaderboard"].model).index(self.selected))
            subset = self.predictions[(self.predictions.season == year) & (self.predictions.model == model)]
            names = subset.drop_duplicates("race_id").set_index("race_id").race_name.to_dict()
            race_id = st.selectbox("Chặng đua", sorted(names), format_func=lambda x: f"R{x % 100:02d} · {names[x]}")
            race = subset[subset.race_id == race_id]
            st.caption(f"{race.split.iloc[0].upper()} · Mô hình chỉ được huấn luyện với các mùa trước {year}. Rolling feature có thể dùng những race đã kết thúc trước chặng này.")
            rm = self.data["race_metrics"]
            row = rm[(rm.race_id == race_id) & (rm.model == model)].iloc[0]
            m1, m2, m3 = st.columns(3)
            m1.metric("MAE thứ hạng", f"{row.mae_rank:.2f} bậc")
            m2.metric("Spearman", f"{row.spearman:.3f}")
            m3.metric("Trùng người podium", f"{row.podium_overlap:.0%}")
            self.render_race(race)
            with st.expander("Xem đầu vào mô hình — không chứa kết quả Race hiện tại"):
                st.dataframe(race[["driver_name"] + FEATURES], hide_index=True, width="stretch")
        elif not self.db_ok:
            st.error("Cần bật MySQL để tạo snapshot và lưu dự đoán mới.")
        else:
            options = self.schedule[self.schedule.season >= self.test_year]
            names = options.set_index("id").name.to_dict()
            race_id = st.selectbox("Chặng cần dự đoán", options.id.to_list(), format_func=lambda x: f"{x // 100} / R{x % 100:02d} · {names[x]}", key="forecast_race")
            st.caption("Lệnh tải dữ liệu: python -m f1lab ingest --years 2026 --refresh. Nếu chưa có Q, hệ thống sẽ từ chối dự đoán. Model vẫn được đóng băng trước mùa test.")
            if st.button("Tạo và lưu dự đoán", type="primary"):
                try:
                    from f1lab.ml import PredictionService
                    with st.spinner("Đọc MySQL, tạo feature và lưu snapshot…"):
                        st.session_state["forecast"] = PredictionService(self.database.engine).predict(race_id)
                except ValueError as exc:
                    st.warning(str(exc))
                except Exception:
                    st.error("Không thể tạo dự đoán. Kiểm tra MySQL và chạy lệnh CLI để xem nhật ký.")
            forecast = st.session_state.get("forecast")
            if forecast is not None and int(forecast.race_id.iloc[0]) == race_id:
                st.info("Dự đoán hồi cứu: Race đã có kết quả." if forecast.label.notna().all() else "Dự đoán trước khi có đầy đủ nhãn Race; chưa tính metric.")
                self.render_race(forecast)

    def render_models(self):
        latest = self.artifacts.config.artifacts_dir / "weekend/latest.json"
        if latest.exists():
            summary = json.loads(latest.read_text())
            st.subheader("Mô hình dự đoán trước cuối tuần")
            rows = [{"Phiên":kind, "Mô hình":info.get("selected", "Chưa đủ dữ liệu"),
                     "Phiên train":info.get("train_sessions", 0), "Phiên validation":info.get("validation_sessions", 0),
                     "Phiên test":info.get("test_sessions", 0)} for kind, info in summary["sessions"].items()]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            st.caption("Chọn theo validation, không chọn theo điểm test. FP/Sprint có ít mẫu; độ tin cậy còn hạn chế. Mô hình được giữ cố định khi lịch và kết quả mới cập nhật.")
            with st.expander("Các chỉ số từng phiên"):
                st.dataframe(pd.read_csv(latest.parent / summary["experiment"] / "metrics.csv"), hide_index=True)
        st.markdown('<div class="eyebrow">MODEL BENCHMARK</div>', unsafe_allow_html=True)
        st.title("Chọn bằng bằng chứng.")
        st.info(f"Đã chọn {self.selected} bằng MAE validation {self.summary['validation_years']}. Test {self.test_year} dùng để báo cáo, không dùng để chọn lại model.")
        st.dataframe(self.metrics[["model", "split", "year", "n_races", "mae_rank", "rmse_rank", "spearman", "winner_hit", "podium_overlap", "r2_raw", "fit_seconds"]], hide_index=True, width="stretch")
        st.download_button("Tải toàn bộ metric", self.metrics.to_csv(index=False).encode(), "model-metrics.csv", "text/csv")
        left, right = st.columns(2)
        with left:
            st.subheader("Sai số thay đổi theo chặng")
            rm = self.data["race_metrics"]
            curve = rm[(rm.model.isin([self.selected, "Baseline Q"])) & (rm.split == "test")].copy()
            if not curve.empty:
                curve["Vòng"] = curve.race_id % 100
                fig = px.line(curve, x="Vòng", y="mae_rank", color="model", markers=True,
                              labels={"mae_rank": "MAE thứ hạng (bậc)", "model": "Mô hình"}, color_discrete_sequence=[ACCENT, MUTED])
                st.plotly_chart(chart_style(fig), width="stretch")
                st.caption(f"Nguồn: test {self.test_year}, các chặng đủ danh sách và nhãn. Không nối với dữ liệu giả cho chặng bị loại.")
        with right:
            st.subheader("Feature nào ảnh hưởng đến model?")
            importance = self.data["importance"].sort_values("mae_increase").tail(8)
            fig = px.bar(importance, x="mae_increase", y="feature", orientation="h", error_x="std", color_discrete_sequence=[ACCENT],
                         labels={"mae_increase": "MAE tăng khi hoán vị (bậc)", "feature": "Đặc trưng"})
            st.plotly_chart(chart_style(fig), width="stretch")
            st.caption(f"Permutation importance của {self.selected} trên validation {self.summary['validation_years'][-1]}, 3 lần lặp. Đây không phải bằng chứng nhân quả.")
        with st.expander("Đọc các chỉ số như thế nào?", expanded=True):
            st.markdown("**MAE:** lệch trung bình bao nhiêu bậc; thấp hơn tốt hơn. **RMSE:** phạt nặng sai số lớn. **Spearman:** mức giống nhau của hai thứ tự. **Winner hit:** tỷ lệ đúng người thắng. **Podium overlap:** tỷ lệ người trùng trong nhóm ba người đứng đầu. **R² raw:** chất lượng đầu ra hồi quy liên tục; có thể âm, không phải % đúng. F1-score cần bài toán phân loại riêng; bản v1 chưa dự đoán xác suất podium.")

    def render_data(self):
        st.markdown('<div class="eyebrow">DATA WORKBENCH</div>', unsafe_allow_html=True)
        st.title("Biết dữ liệu trước khi học.")
        tab1, tab2, tab3 = st.tabs(["Chất lượng nguồn", "MySQL", "Thời tiết Q"])
        with tab1:
            if self.db_ok:
                from .analysis.web import analysis_frame
                frame = analysis_frame(self.database.engine)
                st.caption("Dữ liệu nguồn hiện tại trong MySQL; không phụ thuộc ngày huấn luyện model.")
                missing = frame.isna().sum().rename("Thiếu").rename_axis("Trường").reset_index()
                st.dataframe(missing, hide_index=True)
                st.caption("Q2/Q3 thiếu có thể do không vào vòng; không điền 0. Giữ DNF và giá trị cực trị hợp lệ; không tự bịa nhãn còn thiếu.")
                st.download_button("Tải toàn bộ kết quả Q/R", frame.to_csv(index=False, na_rep="N/a").encode("utf-8-sig"), "results.csv")
            else:
                st.info("Cần MySQL để xem chất lượng nguồn hiện tại.")
        with tab2:
            if self.db_ok:
                st.caption(f"Kết nối thực: MySQL {self.db_version}. Dữ liệu bên dưới được truy vấn từ CSDL.")
                st.dataframe(pd.DataFrame(self.counts.items(), columns=["Bảng", "Số dòng"]), hide_index=True)
                st.subheader("View prediction_comparison")
                st.dataframe(self.table_loader("comparison"), hide_index=True, width="stretch")
                st.subheader("Nhật ký thu thập")
                st.dataframe(self.table_loader("ingestion"), hide_index=True, width="stretch")
            else:
                st.warning("Bật MySQL: .venv/bin/python scripts/local_mysql.py start")

        with tab3:
            if self.db_ok:
                weather = self.table_loader("weather")
                if not weather.empty:
                    sid = st.selectbox("Phiên thời tiết", weather.session_id.unique())
                    subset = weather[weather.session_id == sid].copy()
                    subset["Phút từ đầu phiên"] = subset.elapsed_seconds / 60
                    fig = px.line(subset, x="Phút từ đầu phiên", y=["air_temp", "track_temp"],
                                  labels={"value": "Nhiệt độ (°C)", "variable": "Đại lượng"}, color_discrete_sequence=[MUTED, ACCENT])
                    st.plotly_chart(chart_style(fig), width="stretch")
                    st.caption(f"Nguồn FastF1 · {subset['name'].iloc[0]} {subset.season.iloc[0]} · Q. air_temp: không khí; track_temp: mặt đường. Thời tiết Q không phải dự báo thời tiết Race.")
                else:
                    st.info("Chưa thu thập thời tiết. Chạy python -m f1lab weather --year 2024 --round 1")
            st.warning("Thời tiết được lưu để khám phá, chưa dùng làm feature v1 vì độ phủ còn hạn chế. Không dùng thời tiết Race đã xảy ra để dự đoán trước Race.")

