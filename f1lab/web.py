"""Chạy: streamlit run app.py — web học và demo trên dữ liệu thật."""
from __future__ import annotations

import logging

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


class DashboardApp:
    def __init__(self, artifacts=None, database=None, overview_loader=None, experiment_loader=None, table_loader=None):
        self.artifacts = artifacts if artifacts is not None else ArtifactRepository()
        self.database = database if database is not None else dashboard_database()
        self.overview_loader = overview_loader if overview_loader is not None else db_overview
        self.experiment_loader = experiment_loader if experiment_loader is not None else experiment_files
        self.table_loader = table_loader if table_loader is not None else read_table
        self.pages = {
            "Tổng quan": self.render_overview,
            "Dự đoán & đối chiếu": self.render_predictions,
            "So sánh mô hình": self.render_models,
            "Dữ liệu & MySQL": self.render_data,
            "Học & bảo vệ": self.render_learning,
        }

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
        page = st.sidebar.radio("Không gian làm việc", ["Tổng quan", "Dự đoán & đối chiếu", "So sánh mô hình", "Dữ liệu & MySQL", "Học & bảo vệ"], label_visibility="collapsed", key="navigation")
        st.sidebar.markdown("---")
        st.sidebar.caption("Dự đoán sau phân hạng Q, trước Race. Kết quả lịch sử được đánh giá ngoài mẫu theo thời gian.")

        self.db_ok = True
        try:
            self.db_version, self.counts, self.schedule = self.overview_loader()
            st.sidebar.success("MySQL đã kết nối")
        except Exception:
            logging.getLogger(__name__).exception("Không kết nối/đọc được MySQL")
            self.db_ok, self.counts, self.schedule = False, {}, pd.DataFrame()
            st.sidebar.warning("MySQL chưa kết nối. Đang xem artifact đã lưu.")

        latest_path = self.artifacts.config.artifacts_dir / "latest.json"
        if not latest_path.exists():
            st.title("Bắt đầu với dữ liệu thật")
            st.info("Chưa có thí nghiệm hoàn chỉnh. Chạy các lệnh bên dưới theo thứ tự.")
            st.code(".venv/bin/python scripts/local_mysql.py start\n.venv/bin/python -m f1lab ingest --years 2022 2023 2024 2025 2026\n.venv/bin/python -m f1lab train --test-year 2026\n.venv/bin/python -m streamlit run app.py", language="bash")
            st.stop()

        self.summary = self.artifacts.load_latest()
        self.data = self.experiment_loader(self.summary["experiment"])
        self.features, self.predictions, self.metrics = self.data["features"], self.data["predictions"], self.data["metrics"]
        self.selected = self.summary["selected"]
        self.test_year = self.summary["test_year"]
        test = self.metrics[(self.metrics.split == "test") & (self.metrics.model == self.selected)]
        self.best_test = test.iloc[0] if not test.empty else None
        st.sidebar.caption(f"Thí nghiệm: {self.summary['experiment']}\n\nNguồn: FastF1 / Jolpica")
        self.pages[page]()
        st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
        st.caption("F1 LAB / Đồ án học tập · Dữ liệu FastF1 & Jolpica · Kết quả thực nghiệm, không phải đảm bảo thứ hạng tương lai.")

    def render_race(self, race):
        race = race.sort_values("predicted_rank")
        a, b = st.columns([1.35, 1])
        with a:
            st.subheader("Thứ tự dự đoán")
            cols = ["predicted_rank", "driver_name", "team_name", "quali_position", "label"]
            shown = race[cols].rename(columns={"predicted_rank": "Dự đoán", "driver_name": "Tay đua", "team_name": "Đội", "quali_position": "Hạng Q", "label": "Thực tế"})
            st.dataframe(shown, hide_index=True, use_container_width=True, height=540)
            st.download_button("Tải kết quả CSV", race.to_csv(index=False).encode("utf-8-sig"), file_name=f"prediction-{int(race.race_id.iloc[0])}.csv", mime="text/csv")
        with b:
            st.subheader("Dự đoán lệch bao nhiêu?")
            if race.label.notna().all():
                plot = race.copy()
                plot["Sai lệch tuyệt đối (bậc)"] = (plot.predicted_rank - plot.label).abs()
                fig = px.bar(plot, x="Sai lệch tuyệt đối (bậc)", y="driver_name", orientation="h", color_discrete_sequence=[ACCENT],
                             labels={"driver_name": "Tay đua"}, hover_data=["predicted_rank", "label"])
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(chart_style(fig, 500), use_container_width=True)
                st.caption("Nguồn: prediction ngoài mẫu và kết quả FastF1/Jolpica của chặng đang chọn. 0 bậc = đúng thứ hạng.")
            else:
                st.info("Chưa có đầy đủ kết quả Race để đối chiếu. Thứ hạng dự đoán không phải xác suất thắng.")

    def render_overview(self):
        st.markdown('<div class="eyebrow">FORMULA 1 / SEASON 2026</div>', unsafe_allow_html=True)
        st.title("Đọc quá khứ.\nKiểm chứng dự đoán.")
        st.markdown('<p class="intro">Một phòng thực nghiệm nhỏ để tìm hiểu dữ liệu đường đua, so sánh mô hình học máy và giải thích từng dự đoán — từ MySQL đến vạch đích.</p>', unsafe_allow_html=True)
        st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Chặng có feature Q", self.features.race_id.nunique())
        c2.metric("Mẫu tay đua / chặng", f"{len(self.features):,}")
        c3.metric("Mô hình + baseline", self.metrics.model.nunique())
        c4.metric(f"MAE test {self.test_year}", f"{self.best_test.mae_rank:.2f} bậc" if self.best_test is not None else "Chưa có")
        st.caption(f"Model chọn bằng validation: {self.selected}. MAE là sai số trung bình thứ hạng sau sắp xếp, mỗi chặng có trọng số bằng nhau.")
        left, right = st.columns([1.6, 1], gap="large")
        with left:
            st.subheader("Mô hình có hơn quy tắc đơn giản?")
            board = self.data["validation_leaderboard"].sort_values("mae_rank", ascending=False)
            fig = px.bar(board, x="mae_rank", y="model", orientation="h", color="model",
                         color_discrete_map={name: ACCENT if name == self.selected else MUTED for name in board.model},
                         labels={"mae_rank": "MAE validation (bậc) — thấp hơn tốt hơn", "model": "Mô hình"})
            fig.update_layout(showlegend=False)
            st.plotly_chart(chart_style(fig), use_container_width=True)
            st.caption(f"Validation {self.summary['validation_years']}; tổng hợp theo chặng. Lựa chọn được lưu trước khi tính metric test.")
        with right:
            st.subheader("Một dự đoán đi qua đâu?")
            for number, title, desc in [
                ("01", "Dữ liệu nguồn", "Q, kết quả lịch sử, đội và đường đua từ FastF1 / Jolpica."),
                ("02", "MySQL & đặc trưng", "Khóa liên kết rõ ràng. Phong độ chỉ tính từ các race trước."),
                ("03", "Học & kiểm chứng", "4 mô hình, 2 baseline. Kiểm tra theo thứ tự thời gian."),
            ]:
                st.markdown(f"**{number} · {title}**")
                st.caption(desc)
            st.info("Mô hình không biết trước tai nạn, chiến thuật hay thời tiết Race thực tế.")
        st.warning("Đây là backtest hồi cứu: nguồn có thể sửa kết quả Q sau sự kiện. Chưa có snapshot lịch sử chứng minh chính xác thời điểm mỗi thông tin được công bố. Thời tiết Q được khám phá riêng, chưa đưa vào model v1.")

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
                st.dataframe(race[["driver_name"] + FEATURES], hide_index=True, use_container_width=True)
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
        st.markdown('<div class="eyebrow">MODEL BENCHMARK</div>', unsafe_allow_html=True)
        st.title("Chọn bằng bằng chứng.")
        st.info(f"Đã chọn {self.selected} bằng MAE validation {self.summary['validation_years']}. Test {self.test_year} dùng để báo cáo, không dùng để chọn lại model.")
        st.dataframe(self.metrics[["model", "split", "year", "n_races", "mae_rank", "rmse_rank", "spearman", "winner_hit", "podium_overlap", "r2_raw", "fit_seconds"]], hide_index=True, use_container_width=True)
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
                st.plotly_chart(chart_style(fig), use_container_width=True)
                st.caption(f"Nguồn: test {self.test_year}, các chặng đủ danh sách và nhãn. Không nối với dữ liệu giả cho chặng bị loại.")
        with right:
            st.subheader("Feature nào ảnh hưởng đến model?")
            importance = self.data["importance"].sort_values("mae_increase").tail(8)
            fig = px.bar(importance, x="mae_increase", y="feature", orientation="h", error_x="std", color_discrete_sequence=[ACCENT],
                         labels={"mae_increase": "MAE tăng khi hoán vị (bậc)", "feature": "Đặc trưng"})
            st.plotly_chart(chart_style(fig), use_container_width=True)
            st.caption(f"Permutation importance của {self.selected} trên validation {self.summary['validation_years'][-1]}, 3 lần lặp. Đây không phải bằng chứng nhân quả.")
        with st.expander("Đọc các chỉ số như thế nào?", expanded=True):
            st.markdown("**MAE:** lệch trung bình bao nhiêu bậc; thấp hơn tốt hơn. **RMSE:** phạt nặng sai số lớn. **Spearman:** mức giống nhau của hai thứ tự. **Winner hit:** tỷ lệ đúng người thắng. **Podium overlap:** tỷ lệ người trùng trong nhóm ba người đứng đầu. **R² raw:** chất lượng đầu ra hồi quy liên tục; có thể âm, không phải % đúng. F1-score cần bài toán phân loại riêng; bản v1 chưa dự đoán xác suất podium.")

    def render_data(self):
        st.markdown('<div class="eyebrow">DATA WORKBENCH</div>', unsafe_allow_html=True)
        st.title("Biết dữ liệu trước khi học.")
        tab1, tab2, tab3 = st.tabs(["Chất lượng & phong độ", "MySQL", "Thời tiết Q"])
        with tab1:
            coverage_file = self.artifacts.experiment_folder(self.summary["experiment"]) / "coverage.csv"
            if coverage_file.exists():
                coverage = pd.read_csv(coverage_file)
                st.caption("ready = đủ Q/R và thứ hạng 1..N; awaiting_race = đã có Q, chưa có Race; incomplete = lệch danh sách hoặc thiếu hạng. Không âm thầm tính metric trên một phần tay đua.")
                st.dataframe(coverage, hide_index=True, use_container_width=True, height=230)
            a, b = st.columns(2)
            with a:
                missing = self.features[FEATURES].isna().mean().mul(100).sort_values(ascending=False).reset_index()
                missing.columns = ["Đặc trưng", "Thiếu (%)"]
                fig = px.bar(missing[missing["Thiếu (%)"] > 0], x="Thiếu (%)", y="Đặc trưng", orientation="h", color_discrete_sequence=[MUTED])
                st.plotly_chart(chart_style(fig), use_container_width=True)
                st.caption("Nguồn: snapshot feature hiện tại, trước imputation. Thiếu lịch sử được giữ lại và xử lý trong training pipeline.")
            with b:
                driver = st.selectbox("Xem phong độ tay đua", sorted(self.features.driver_name.unique()))
                history = self.features[self.features.driver_name == driver].sort_values("start_utc")
                fig = px.line(history, x="start_utc", y="driver_form5", markers=True, color_discrete_sequence=[ACCENT],
                              labels={"start_utc": "Ngày race (UTC)", "driver_form5": "Hạng TB 5 race trước (bậc)"})
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(chart_style(fig), use_container_width=True)
                st.caption("Mỗi điểm chỉ dùng lịch sử trước race đó; hạng thấp hơn tốt hơn.")
        with tab2:
            if self.db_ok:
                st.caption(f"Kết nối thực: MySQL {self.db_version}. Dữ liệu bên dưới được truy vấn từ CSDL.")
                st.dataframe(pd.DataFrame(self.counts.items(), columns=["Bảng", "Số dòng"]), hide_index=True)
                st.subheader("View prediction_comparison")
                st.dataframe(self.table_loader("comparison"), hide_index=True, use_container_width=True)
                st.subheader("Nhật ký thu thập")
                st.dataframe(self.table_loader("ingestion"), hide_index=True, use_container_width=True)
            else:
                st.warning("Bật MySQL: .venv/bin/python scripts/local_mysql.py start")
            st.code("SELECT race, driver, team, model, predicted_rank, actual_rank\nFROM prediction_comparison\nWHERE season = 2026\nORDER BY `round`, predicted_rank;", language="sql")
        with tab3:
            if self.db_ok:
                weather = self.table_loader("weather")
                if not weather.empty:
                    sid = st.selectbox("Phiên thời tiết", weather.session_id.unique())
                    subset = weather[weather.session_id == sid].copy()
                    subset["Phút từ đầu phiên"] = subset.elapsed_seconds / 60
                    fig = px.line(subset, x="Phút từ đầu phiên", y=["air_temp", "track_temp"],
                                  labels={"value": "Nhiệt độ (°C)", "variable": "Đại lượng"}, color_discrete_sequence=[MUTED, ACCENT])
                    st.plotly_chart(chart_style(fig), use_container_width=True)
                    st.caption(f"Nguồn FastF1 · {subset['name'].iloc[0]} {subset.season.iloc[0]} · Q. air_temp: không khí; track_temp: mặt đường. Thời tiết Q không phải dự báo thời tiết Race.")
                else:
                    st.info("Chưa thu thập thời tiết. Chạy python -m f1lab weather --year 2024 --round 1")
            st.warning("Thời tiết được lưu để khám phá, chưa dùng làm feature v1 vì độ phủ còn hạn chế. Không dùng thời tiết Race đã xảy ra để dự đoán trước Race.")

    def render_learning(self):
        st.markdown('<div class="eyebrow">LEARNING NOTES</div>', unsafe_allow_html=True)
        st.title("Hiểu để tự bảo vệ đồ án.")
        with st.expander("Kiến trúc OOP của dự án", expanded=True):
            st.write("DashboardApp phụ trách giao diện; các service phụ trách nghiệp vụ; repository phụ trách SQL và artifact. ExperimentTrainer dùng ModelFactory để lấy một RaceModel và gọi fit/predict giống nhau cho baseline lẫn hồi quy.")
            st.write("Đóng gói: Database giữ engine bên trong. Trừu tượng: RaceModel định nghĩa hợp đồng. Kế thừa: các chiến lược triển khai RaceModel. Đa hình: cùng lời gọi predict tạo kết quả theo từng chiến lược. Các service ghép với nhau qua constructor để dễ kiểm thử.")
            st.caption("Xem docs/OOP.md để đọc sơ đồ lớp, ví dụ sử dụng và cách mở rộng.")
        for title, body in [
            ("1 · Một mẫu học là gì?", "Một tay đua tại một chặng. X gồm hạng Q và thống kê trước race; y là thứ hạng Race. ID dùng liên kết bảng. Tên không phải điểm kỹ năng."),
            ("2 · Tại sao cần MySQL?", "Quản lý tay đua, đội, phiên, kết quả và lịch sử mô hình bằng khóa liên kết; import trong transaction, chạy lại không nhân đôi kết quả. Feature snapshot ghi đúng bộ đầu vào đã dùng."),
            ("3 · Vì sao không chia random?", "Các tay đua cùng race có quan hệ với nhau. Giữ nguyên race và dùng mùa trước học, mùa sau kiểm tra để tránh thông tin tương lai."),
            ("4 · Mô hình hoạt động ra sao?", "Linear Regression cộng đóng góp tuyến tính. Random Forest trung bình nhiều cây. Boosting học tuần tự để sửa sai. Tất cả dùng cùng feature và cùng tập chia; cấu hình cố định để kiểm chứng ban đầu."),
            ("5 · Vì sao kết quả là thứ tự duy nhất?", "Model tạo điểm hạng liên tục. Sắp các điểm trong cùng race để có 1..N; phá hòa bằng Q rồi ID. Không làm tròn từng người và không gọi điểm đó là xác suất."),
            ("6 · Điểm yếu nào phải nói rõ?", "Thay đổi luật 2026; thiếu snapshot công bố trong quá khứ; DNF khó dự đoán; loại race thiếu nhãn có thể gây thiên lệch; chưa có dự báo thời tiết lưu tại cutoff. Feature importance không chứng minh nhân quả."),
        ]:
            with st.expander(title, expanded=True):
                st.write(body)
        st.subheader("Kịch bản demo 8–10 phút")
        st.write("Giới thiệu cutoff → mở chất lượng dữ liệu → giải thích khóa MySQL → chọn chặng backtest → đối chiếu thực tế → so sánh baseline → phân tích chặng sai nhiều → trình bày giới hạn.")
        st.caption("Tài liệu trong dự án: README.md, docs/DE_CUONG.md, docs/BAI_01.md, docs/HUONG_DAN.md và docs/BAO_CAO_THUC_NGHIEM.md.")
