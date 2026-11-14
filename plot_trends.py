"""Charts for the 12-scene EMIT trend test.
AI disclosure: written with help from Claude (Anthropic AI assistant); run and checked by the team.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
ps = pd.read_csv(os.path.join(OUT, 'emit_trend_per_scene.csv'))
py = pd.read_csv(os.path.join(OUT, 'emit_share_per_scene_year.csv'))

FAMS = [('calcite/dolomite (core)', 'Calcite / dolomite (validated)'),
        ('gypsum (core)', 'Gypsum (validated)'),
        ('clays (core)', 'Clays (validated)'),
        ('Mg-perchlorate label (non-core)', '"Mg-perchlorate" label (not validated)')]
BLUE, INK, INK2, GRID, SURF = '#2a78d6', '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.edgecolor': GRID,
                     'xtick.color': INK2, 'ytick.color': INK2, 'axes.labelcolor': INK2})

# ---- Figure 1: per-scene rank correlation, two subsets ----
fig, axes = plt.subplots(1, 2, figsize=(13, 4.4), facecolor=SURF, sharey=True)
for ax, sub in zip(axes, ['all exposed seabed', 'never re-flooded']):
    ax.set_facecolor(SURF)
    d = ps[ps.subset == sub]
    for i, (f, label) in enumerate(FAMS):
        v = d[d.family == f]['rho_share'].dropna().values
        y = len(FAMS) - 1 - i
        jitter = (np.arange(len(v)) - (len(v) - 1) / 2) * 0.035
        ax.scatter(v, y + jitter, s=46, color=BLUE, edgecolors=SURF, linewidths=1.5, zorder=3)
        ax.plot([np.median(v)] * 2, [y - 0.32, y + 0.32], color=INK, lw=2.2, zorder=4)
        pos, neg = int((v > 0).sum()), int((v < 0).sum())
        txt = f'{neg} of {len(v)} falling' if neg >= pos else f'{pos} of {len(v)} rising'
        ax.text(1.04, y, txt, va='center', fontsize=9.5, color=INK2, transform=ax.get_yaxis_transform())
    ax.axvline(0, color=INK2, lw=1)
    ax.set_xlim(-1.05, 1.05)
    ax.set_yticks(range(len(FAMS)), [l for _, l in FAMS][::-1])
    ax.set_xlabel('Rank correlation with drying year')
    ax.set_title(f'{sub.capitalize()}', loc='left', color=INK, fontsize=11)
    ax.grid(axis='x', color=GRID, lw=0.8); ax.set_axisbelow(True)
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
fig.text(0.01, 0.98, 'The same trends appear scene after scene: 12 EMIT scenes, April-October 2023',
         color=INK, fontsize=13, fontweight='bold', va='top')
fig.text(0.01, 0.915, 'Each dot is one EMIT scene; the black bar is the median. '
         'Source: NASA EMIT L2B MIN (Group 2), drying year from JRC/Landsat (our analysis).',
         color=INK2, fontsize=9, va='top')
fig.text(0.01, 0.015, 'Negative: less of it on ground that dried later. Positive: more of it.', color=INK2, fontsize=9)
fig.tight_layout(rect=(0, 0.04, 0.93, 0.87), w_pad=8)
fig.savefig(os.path.join(OUT, 'emit_trends_per_scene.png'), dpi=200)

# ---- Figure 2: median share by drying period across scenes, with interquartile range ----
a = py[py.subset == 'all exposed seabed'].copy()
a['period'] = pd.cut(a.year, [1984, 1994, 2004, 2014, 2021],
                     labels=['1985–94', '1995–2004', '2005–14', '2015–21'])
fig, axes = plt.subplots(1, 4, figsize=(13, 3.9), facecolor=SURF)
for ax, (f, label) in zip(axes, FAMS):
    ax.set_facecolor(SURF)
    m = (a[a.family == f].groupby(['date', 'period'], observed=True)
         .apply(lambda d: np.average(d.share, weights=d.n)).unstack())
    x = range(m.shape[1])
    med, q1, q3 = m.median(), m.quantile(0.25), m.quantile(0.75)
    ax.fill_between(x, q1.values, q3.values, color=BLUE, alpha=0.18, lw=0)
    ax.plot(x, med.values, color=BLUE, lw=2, marker='o', ms=7, mec=SURF, mew=1.5)
    for xi, (c, val) in enumerate(zip(m.count().values, med.values)):
        ax.annotate(f'{val:.1f}%', (xi, val), xytext=(0, 9), textcoords='offset points',
                    ha='center', fontsize=8.5, color=INK2)
    ax.set_xticks(list(x), m.columns, fontsize=8.5)
    ax.set_ylim(bottom=0, top=max(q3.max(), med.max()) * 1.25)
    ax.set_title(label, loc='left', color=INK, fontsize=10.5)
    ax.grid(axis='y', color=GRID, lw=0.8); ax.set_axisbelow(True)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
axes[0].set_ylabel('% of EMIT pixels (median of scenes)')
fig.text(0.01, 0.985, 'Carbonate and clay where the sea left first, gypsum in the middle, salt labels last',
         color=INK, fontsize=13, fontweight='bold', va='top')
fig.text(0.01, 0.915, 'Line: median of 12 EMIT scenes (2023). Shaded: middle half of scenes. '
         'Each panel has its own y-scale. Drying year from JRC/Landsat (our analysis).',
         color=INK2, fontsize=9, va='top')
fig.tight_layout(rect=(0, 0, 1, 0.86))
fig.savefig(os.path.join(OUT, 'emit_minerals_by_period_12scenes.png'), dpi=200)
print('saved')
