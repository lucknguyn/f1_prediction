"""Trang phân tích chỉ gọi service, không chứa truy vấn SQL."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from .service import AnalysisService, RadarComparison, NUMERIC, PROFILE


@st.cache_data(ttl=300)
def analysis_frame(_engine):
    return AnalysisService(_engine).results()


@st.cache_data
def cluster_profiles(profiles):
    return AnalysisService.cluster(profiles)


def render_analysis(engine):
    st.title('Hiểu dữ liệu trước khi dự đoán.')
    frame = analysis_frame(engine)
    if frame.empty:
        st.info('Chưa có dữ liệu Q/R trong MySQL.'); return
    season = st.selectbox('Mùa phân tích', sorted(frame.season.unique(), reverse=True),
                          index=1 if len(frame.season.unique()) > 1 else 0, key='analysis_season')
    data = frame[frame.season == season]
    stats, clusters, radar = st.tabs(['Thống kê', 'Nhóm tay đua', 'So sánh radar'])
    with stats:
        team = st.selectbox('Đội', ['Tất cả'] + sorted(data.team_name.dropna().unique()), key='analysis_team')
        selected = data if team == 'Tất cả' else data[data.team_name == team]
        col = st.selectbox('Thuộc tính', NUMERIC, key='analysis_attribute')
        a, b, c = st.columns(3)
        a.metric('Mẫu có giá trị', int(selected[col].count()))
        b.metric('Trung bình', f'{selected[col].mean():.2f}')
        c.metric('Thiếu', int(selected[col].isna().sum()))
        st.plotly_chart(px.histogram(selected, x=col, nbins=20, title=f'{season} · {team}'), width='stretch')
        st.caption('Một mẫu = tay đua/chặng. Thời gian tính bằng giây; vị trí tính bằng bậc. Histogram bỏ giá trị thiếu; độ lệch chuẩn dùng ddof=1.')
        st.dataframe(AnalysisService.statistics(selected).query("group_type == 'all'").drop(columns=['group_type','group_id','season']), hide_index=True)
        with st.expander('Ba giá trị cao nhất và thấp nhất'):
            columns = ['driver_name', 'race_name', 'season', col]
            st.dataframe(pd.concat([selected.nlargest(3, col)[columns].assign(nhom='Cao nhất'), selected.nsmallest(3, col)[columns].assign(nhom='Thấp nhất')]), hide_index=True)
        teams = data[data.race_position.notna()].groupby('team_name', as_index=False).agg(
            points_mean=('points','mean'), race_mean=('race_position','mean'), dnf_rate=('dnf','mean'), observations=('race_position','count'))
        st.subheader('Thành tích đội trong mùa')
        st.dataframe(teams.sort_values('points_mean', ascending=False), hide_index=True)
        st.caption('Điểm cao hơn tốt hơn; hạng trung bình và tỷ lệ DNF thấp hơn tốt hơn. Đây là thành tích đội và tay đua kết hợp, không đo riêng sức mạnh xe. Điểm chỉ gồm Race.')
        st.download_button('Tải dữ liệu đang lọc', selected.to_csv(index=False, na_rep='N/a').encode('utf-8-sig'), 'results.csv')
    profiles = AnalysisService.profiles(frame, season)
    with clusters:
        st.caption('KMeans mô tả hồ sơ tay đua của mùa đã chọn. Nhãn cụm không phải xếp hạng; dữ liệu mùa đang diễn ra chỉ phản ánh các chặng đã có kết quả.')
        try:
            grouped, scores, centers, summary = cluster_profiles(profiles)
            st.metric('Số cụm theo silhouette', summary['selected_k'])
            st.plotly_chart(px.scatter(grouped, x='PC1', y='PC2', color=grouped.cluster.astype(str), hover_name='driver_name', labels={'color':'Cụm'}), width='stretch')
            st.caption(f"Hai trục PCA giải thích {sum(summary['explained_variance_ratio']):.1%} phương sai sau chuẩn hóa. Chỉ {len(profiles)} tay đua: phân cụm mang tính khám phá.")
            st.plotly_chart(px.line(scores, x='k', y='silhouette', markers=True), width='stretch')
            with st.expander('Elbow, tâm cụm và hồ sơ tay đua'):
                st.plotly_chart(px.line(scores, x='k', y='inertia', markers=True), width='stretch')
                st.dataframe(centers, hide_index=True)
                st.dataframe(grouped, hide_index=True)
            st.caption('Các thuộc tính: Q trung bình, Race trung bình, điểm trung bình, DNF và số chặng. Điền thiếu bằng median, StandardScaler, seed 42. Chọn k tốt nhất trong 2–6 nếu đủ mẫu. Thành tích tổng kết mùa này không được đưa vào đầu vào dự đoán quá khứ.')
        except ValueError as exc:
            st.info(str(exc))
    with radar:
        if len(profiles) < 2:
            st.info('Cần ít nhất hai tay đua.'); return
        ids, names = profiles.driver_id.tolist(), profiles.set_index('driver_id').driver_name.to_dict()
        a, b = st.columns(2)
        p1 = a.selectbox('Tay đua thứ nhất', ids, format_func=names.get, key='radar_p1')
        p2 = b.selectbox('Tay đua thứ hai', ids, index=1, format_func=names.get, key='radar_p2')
        attributes = st.multiselect('Trục radar', PROFILE, default=PROFILE)
        try:
            values = RadarComparison().normalize(profiles, [p1,p2], attributes)
            fig = go.Figure()
            for driver, row in values.iterrows():
                fig.add_trace(go.Scatterpolar(r=row.tolist()+[row.iloc[0]], theta=attributes+[attributes[0]], fill='toself', name=names[driver]))
            fig.update_layout(polar=dict(radialaxis=dict(range=[0,1])))
            st.plotly_chart(fig, width='stretch')
            st.caption('Chuẩn hóa min–max theo toàn bộ tay đua cùng mùa. Đảo chiều Q, Race và DNF để phía ngoài tốt hơn; n_races chỉ là độ phủ, không phải kỹ năng. Trục không biến thiên = 0,5; thiếu dữ liệu để trống.')
            st.dataframe(profiles[profiles.driver_id.isin([p1,p2])], hide_index=True)
        except ValueError as exc:
            st.info(str(exc))
