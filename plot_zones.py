"""Small-multiple chart: share of EMIT mineral labels by drying zone, two dates.
AI disclosure: written with help from Claude (Anthropic AI assistant); run and checked by the team.
"""
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
zones = ['dried 1985-1994', 'dried 1995-2004', 'dried 2005-2014', 'dried 2015-2021']
xlab = ['1985–94', '1995–2004', '2005–14', '2015–21']
panels = [('calcite/dolomite (core)', 'Calcite / dolomite (validated)'),
          ('gypsum (core)', 'Gypsum (validated)'),
          ('clays (core)', 'Clays (validated)'),
          ('Mg-perchlorate label (non-core)', '"Mg-perchlorate" label (NOT validated)')]
scenes = [('20230731', '31 Jul 2023', '#2a78d6'), ('20230823', '23 Aug 2023', '#eb6834')]
MIN_N = 5000   # zones with fewer pixels than this are drawn hollow

ink, ink2, grid = '#0b0b0b', '#52514e', '#e4e3df'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'axes.edgecolor': grid, 'axes.labelcolor': ink2,
                     'xtick.color': ink2, 'ytick.color': ink2})
fig, axes = plt.subplots(1, 4, figsize=(13, 3.9), facecolor='#fcfcfb')
for ax, (fam, title) in zip(axes, panels):
    ax.set_facecolor('#fcfcfb')
    for date, label, color in scenes:
        t = pd.read_csv(os.path.join(OUT, f'{date}_by_zone.csv'), index_col=0).reindex(zones)
        y, n = t[fam].values, t['n_pixels'].values
        x = range(len(zones))
        ax.plot(x, y, color=color, lw=2, zorder=2)
        for xi, yi, ni in zip(x, y, n):
            hollow = ni < MIN_N
            ax.scatter([xi], [yi], s=55, zorder=3, linewidths=2,
                       facecolors='#fcfcfb' if hollow else color, edgecolors=color)
        if fam == panels[-1][0]:   # direct labels on the last panel only
            ax.annotate(label, (len(zones) - 1, y[-1]), xytext=(6, 0),
                        textcoords='offset points', va='center', color=ink2, fontsize=9)
    ax.set_title(title, color=ink, fontsize=10.5, loc='left')
    ax.set_xticks(range(len(zones)), xlab, fontsize=8.5)
    ax.set_ylim(bottom=0)
    ax.grid(axis='y', color=grid, lw=0.8)
    ax.set_axisbelow(True)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
axes[0].set_ylabel('% of EMIT pixels in zone')
fig.text(0.01, 0.985, 'EMIT mineral labels vs. the year the Aral seabed dried (eastern basin, 60 m)',
         color=ink, fontsize=13, fontweight='bold', va='top')
fig.text(0.01, 0.915, 'Each panel has its own y-scale. Hollow points: fewer than 5,000 pixels in that zone. '
         'Source: NASA EMIT L2B MIN (Group 2) + drying year from JRC/Landsat (our analysis).',
         color=ink2, fontsize=9, va='top')
h = [plt.Line2D([], [], color=c, lw=2, marker='o', label=l) for _, l, c in scenes]
fig.legend(handles=h, loc='upper right', frameon=False, ncol=2, bbox_to_anchor=(0.995, 0.995))
fig.tight_layout(rect=(0, 0, 0.97, 0.86))
fig.savefig(os.path.join(OUT, 'emit_minerals_by_drying_zone.png'), dpi=200)
print('saved')
