"""Chart for step 6: ground left by each lake's permanent water (1985-2021) that never
flooded again, i.e. ground whose drying year is the age of the surface.
usage: python3 -I datable_chart.py datable_ground.csv
AI disclosure: written with help from Claude (Anthropic AI assistant); run and checked by the team.
"""
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

INK, INK2, GRID, SURF = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
DARK, LIGHT = '#0d366b', '#b9d4f5'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.edgecolor': GRID,
                     'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK,
                     'text.color': INK, 'figure.facecolor': SURF, 'axes.facecolor': SURF})
NAMES = {'Lake Poopo': 'Lake Poopó', 'Colhue Huapi': 'Colhué Huapi', 'Lake Aksehir': 'Lake Akşehir'}
d = pd.read_csv(sys.argv[1]).sort_values('stayed_dry_km2', ascending=False)
d['lake'] = d.lake.replace(NAMES)
XMAX = 1500
fig, ax = plt.subplots(figsize=(10, 5.4))
y = np.arange(len(d))[::-1]
dry = d.stayed_dry_km2.values
ax.barh(y, np.minimum(dry, XMAX), height=0.62, color=DARK)
for yi, (_, r) in zip(y, d.iterrows()):
    share = f"{r.stayed_dry_share * 100:.0f}% of {r.left_km2:,.0f} km² left by the lake"
    if r.stayed_dry_km2 > XMAX:
        ax.text(XMAX - 25, yi, f"{r.stayed_dry_km2:,.0f} km² (bar cut)  ", va='center', ha='right',
                color='white', fontsize=9.5, fontweight='bold')
        ax.text(XMAX + 25, yi, share, va='center', fontsize=8.5, color=INK2)
    else:
        ax.text(r.stayed_dry_km2 + 25, yi, f"{r.stayed_dry_km2:,.0f} km²  ·  {share}", va='center',
                fontsize=8.5, color=INK2)
ax.set_yticks(y)
ax.set_yticklabels(d.lake, fontsize=9.5)
ax.set_xlim(0, XMAX + 1000)
ax.set_xticks([0, 250, 500, 750, 1000, 1250, 1500])
ax.grid(axis='x', color=GRID, lw=0.8)
ax.set_axisbelow(True)
for s in ('top', 'right', 'left'):
    ax.spines[s].set_visible(False)
ax.tick_params(axis='y', length=0)
ax.set_xlabel('Ground the lake left that never flooded again, 1985–2021 (km²)')
fig.text(0.01, 0.985, 'Only the Aral leaves a large surface of known age', fontsize=12.5,
         color=INK, ha='left', va='top')
fig.text(0.01, 0.945, 'Most drying lakes are seasonal salt flats that flood again, so their drying '
         'year is not the age of the surface.', fontsize=9, color=INK2, ha='left', va='top')
fig.subplots_adjust(top=0.88, bottom=0.15, left=0.2, right=0.98)
fig.text(0.01, 0.02, 'Data: JRC Global Surface Water v1.4 Yearly History (Landsat, 30 m), 1984–2021. '
         'Ground counted if it was permanent water, then land, and never water again up to 2021.',
         fontsize=7.8, color=INK2, ha='left', va='bottom')
fig.savefig('datable_ground.png', dpi=150)
