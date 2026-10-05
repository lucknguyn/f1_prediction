"""Biểu đồ xuất PNG cho báo cáo, cùng phép chuẩn hóa với web."""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .service import NUMERIC, RadarComparison


def radar_figure(profiles, drivers, attributes=None):
    values = RadarComparison().normalize(profiles, drivers, attributes)
    if values.isna().any().any():
        raise ValueError('Tay đua thiếu thuộc tính radar; chọn thuộc tính hoặc tay đua khác.')
    labels = values.columns.tolist()
    theta = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
    fig, ax = plt.subplots(figsize=(8, 6), subplot_kw={'projection': 'polar'})
    names = profiles.set_index('driver_id').driver_name.to_dict()
    for driver, row in values.iterrows():
        points = row.tolist()
        ax.plot(theta+[theta[0]], points+[points[0]], label=names[driver])
        ax.fill(theta+[theta[0]], points+[points[0]], alpha=.1)
    ax.set_xticks(theta, labels)
    ax.set_ylim(0, 1)
    ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.15))
    ax.set_title('Same-season min–max; higher = better / more races', pad=30)
    fig.tight_layout()
    return fig


def export_plots(frame, clustered, scores, profiles, folder):
    period = f'{int(frame.season.min())}–{int(frame.season.max())}'
    for col in NUMERIC:
        fig, ax = plt.subplots(figsize=(7, 4))
        values = frame[col].dropna()
        bins = np.arange(values.min() - .5, values.max() + 1.5) if col in ('quali_position', 'race_position', 'dnf') else 20
        ax.hist(values, bins=bins, color='#d94b43', edgecolor='white', linewidth=.4)
        ax.set(xlabel=col, ylabel='Driver-race observations',
               title=f'{period} · all teams · n={frame[col].count()} · missing omitted')
        fig.tight_layout(); fig.savefig(folder/f'histogram-{col}.png', dpi=150); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(scores.k, scores.inertia, marker='o'); axes[0].set(xlabel='k', ylabel='Inertia (elbow)')
    axes[1].plot(scores.k, scores.silhouette, marker='o'); axes[1].set(xlabel='k', ylabel='Silhouette')
    fig.tight_layout(); fig.savefig(folder/'cluster-selection.png', dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 6))
    for label, group in clustered.groupby('cluster'):
        ax.scatter(group.PC1, group.PC2, label=f'Cluster {label} (n={len(group)})', alpha=.8)
    # Chỉ chú thích cực trị; tên của các điểm sát nhau xem bằng hover trên web.
    for index in {clustered.PC1.idxmin(), clustered.PC1.idxmax(), clustered.PC2.idxmin()}:
        row = clustered.loc[index]
        ax.annotate(row.driver_name, (row.PC1, row.PC2), xytext=(-5, 10),
                    textcoords='offset points', ha='right', fontsize=8)
    ax.legend(loc='lower left')
    ax.margins(.12)
    ax.set(xlabel='PC1', ylabel='PC2', title='Driver-season profiles · PCA projection; clusters are not ranks')
    fig.tight_layout(); fig.savefig(folder/'clusters-pca.png', dpi=150); plt.close(fig)
    candidates = profiles.dropna(subset=['quali_mean', 'race_mean', 'points_mean', 'dnf_rate']).sort_values('n_races', ascending=False)
    if len(candidates) >= 2:
        fig = radar_figure(profiles, candidates.driver_id.iloc[:2].tolist())
        fig.savefig(folder/'radar-example.png', dpi=150); plt.close(fig)
