"""Slide-sized versions of the main charts (larger text, slide paper colour).

outputs in out/slides/: drying_map.png, global_lakes.png, mars_tests.png, route_map.png
AI disclosure: written with help from Claude (Anthropic AI assistant); run and checked by the team.
"""
import csv
import json
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
SO = os.path.join(OUT, 'slides')
os.makedirs(SO, exist_ok=True)
PAPER, INK, INK2, GRID = '#f5f2ea', '#10192a', '#4a5568', '#d9d3c4'
BLUE, DARK, CHANCE = '#3987e5', '#0d366b', '#c9c3b4'
RAMP = ['#cfe1f7', '#86b6ef', '#3987e5', '#1c5cab', '#0d366b']
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 16, 'axes.edgecolor': GRID,
                     'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK,
                     'text.color': INK, 'figure.facecolor': PAPER, 'axes.facecolor': PAPER,
                     'savefig.facecolor': PAPER})


def grid_and_meta():
    grid = np.load(os.path.join(OUT, 'retreat_grid.npy'))
    g = json.load(open(os.path.join(OUT, 'retreat_grid.json')))
    return grid, g


def base_map(ax, grid, g, show_reflood=True):
    year, refl, cls = grid[..., 0].astype(int), grid[..., 1].astype(int), grid[..., 2]
    H, W = year.shape
    ext = [g['x0'], g['x0'] + W * g['dx'], g['y0'] - H * g['dy'], g['y0']]
    rgb = np.ones((H, W, 3)) * np.array([0.961, 0.949, 0.918])
    rgb[cls == 2] = [0.89, 0.85, 0.77]          # basin, dried before 1984
    rgb[cls == 1] = [0.78, 0.87, 0.91]          # water 2021
    ax.imshow(rgb, extent=ext, interpolation='nearest')
    m = year > 0
    if show_reflood:
        rgb2 = np.zeros((H, W, 4))
        ax.imshow(np.ma.masked_where(~m, year), extent=ext, cmap=ListedColormap(RAMP),
                  norm=BoundaryNorm([1985, 1995, 2005, 2010, 2015, 2022], 5), interpolation='nearest')
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.set_xlabel('Longitude (°E)', fontsize=14)
    ax.set_ylabel('Latitude (°N)', fontsize=14)
    ax.tick_params(labelsize=13)
    return ext


def drying_map():
    grid, g = grid_and_meta()
    fig, ax = plt.subplots(figsize=(10.4, 6.6))
    base_map(ax, grid, g)
    handles = [Patch(color=c, label=l) for c, l in zip(RAMP, ['1985–94', '1995–2004', '2005–09', '2010–14', '2015–21'])]
    handles += [Patch(color=(0.89, 0.85, 0.77), label='dried before 1984'),
                Patch(color=(0.78, 0.87, 0.91), label='water in 2021')]
    ax.legend(handles=handles, loc='lower right', fontsize=13, title='Year the lake left', title_fontsize=13,
              frameon=True, facecolor=PAPER, edgecolor=GRID)
    fig.tight_layout()
    fig.savefig(os.path.join(SO, 'drying_map.png'), dpi=200, bbox_inches='tight', pad_inches=0.15)
    plt.close(fig)


def global_lakes():
    d = pd.read_csv('/home/claude/finder/datable_ground.csv')
    d['lake'] = d.lake.replace({'Lake Poopo': 'Lake Poopó', 'Colhue Huapi': 'Colhué Huapi',
                                'Lake Aksehir': 'Lake Akşehir'})
    d = d.sort_values('left_km2', ascending=False)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(16.6, 6.0), sharey=True)
    y = np.arange(len(d))[::-1]
    for ax, col, cap, title, color in ((a1, 'left_km2', 4000, 'Ground the lake left, 1985–2021', BLUE),
                                       (a2, 'stayed_dry_km2', 500, '…of which never flooded again', DARK)):
        v = d[col].values
        ax.barh(y, np.minimum(v, cap), height=0.64, color=color)
        for yi, val in zip(y, v):
            if val > cap:
                ax.text(cap * 0.98, yi, f'{val:,.0f} km² ▸', va='center', ha='right', color='white',
                        fontsize=14, fontweight='bold')
            else:
                ax.text(val + cap * 0.015, yi, f'{val:,.0f}', va='center', fontsize=13, color=INK2)
        ax.set_xlim(0, cap * 1.12)
        ax.set_title(title, loc='left', fontsize=17, color=INK)
        ax.grid(axis='x', color=GRID, lw=1)
        ax.set_axisbelow(True)
        for s in ('top', 'right', 'left'):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis='y', length=0, labelsize=14)
        ax.tick_params(axis='x', labelsize=12)
        ax.set_xlabel('km²', fontsize=13)
    a1.set_yticks(y)
    a1.set_yticklabels(d.lake)
    fig.tight_layout()
    fig.savefig(os.path.join(SO, 'global_lakes.png'), dpi=200)
    plt.close(fig)


def mars_tests():
    res = json.load(open(os.path.join(OUT, 'mars_chloride_test.json')))
    ins = res['inside_closed_depression']
    rows = [r for r in csv.DictReader(open(os.path.join(OUT, 'mars_chloride_F.csv')))
            if r['F_share_of_basin_dry_before'] and float(r['depression_area_km2']) >= 100]
    F = np.array([float(r['F_share_of_basin_dry_before']) for r in rows])
    edges = [0.0, 0.069, 0.526, 0.774, 1.0]
    obs = np.histogram(F, bins=edges)[0] / len(F) * 100
    exp = np.diff(edges) * 100
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(16.6, 5.6), gridspec_kw=dict(width_ratios=[1, 2.2]))
    for ax in (a1, a2):
        ax.grid(axis='y', color=GRID, lw=1)
        ax.set_axisbelow(True)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
        ax.set_ylim(0, 75)
        ax.tick_params(labelsize=13)
    vals = [ins['expected_share'] * 100, ins['share'] * 100]
    b = a1.bar([0, 1], vals, 0.62, color=[CHANCE, DARK])
    for bb, v in zip(b, vals):
        a1.text(bb.get_x() + bb.get_width() / 2, v + 1.5, f'{v:.0f}%', ha='center', fontsize=16, color=INK)
    a1.set_xticks([0, 1])
    a1.set_xticklabels(['Ground nearby', 'Salt deposits'], fontsize=14)
    a1.set_title('1. In closed lows?  Yes', loc='left', fontsize=17)
    x = np.arange(4)
    b1 = a2.bar(x - 0.2, exp, 0.38, color=CHANCE, label='Random placement')
    b2 = a2.bar(x + 0.2, obs, 0.38, color=DARK, label='Real Martian deposits')
    for bars, vv in ((b1, exp), (b2, obs)):
        for bb, v in zip(bars, vv):
            a2.text(bb.get_x() + bb.get_width() / 2, v + 1.5, f'{v:.0f}%', ha='center', fontsize=14, color=INK)
    a2.set_xticks(x)
    a2.set_xticklabels(['Dries first', 'Gypsum peak', 'Transition', 'Dries last'], fontsize=14)
    a2.legend(frameon=False, fontsize=14, loc='upper right')
    a2.set_title('2. Where the Aral puts salts (dries last)?  No', loc='left', fontsize=17)
    a1.set_ylabel('% of deposits', fontsize=14)
    fig.tight_layout()
    fig.savefig(os.path.join(SO, 'mars_tests.png'), dpi=200)
    plt.close(fig)


def route_map():
    grid, g = grid_and_meta()
    df = pd.read_csv(os.path.join(OUT, 'field_route.csv'))
    fig, ax = plt.subplots(figsize=(10.4, 6.6))
    base_map(ax, grid, g)
    ax.plot(df.lon, df.lat, color=INK, lw=2, zorder=4)
    ax.scatter(df.lon, df.lat, s=260, color='#eb6834', edgecolor='white', linewidth=2, zorder=5)
    labels = {1: 'salts', 2: 'gypsum + clay', 3: 'clay', 4: 'clay + carbonate'}
    offs = {1: (16, 0), 2: (16, -30), 3: (-40, -52), 4: (14, 16)}
    for _, r in df.iterrows():
        ax.annotate(f"{r.stop}  {r.period}\n{labels[r.stop]}", (r.lon, r.lat), xytext=offs[r.stop],
                    textcoords='offset points', fontsize=14, color=INK, zorder=6,
                    bbox=dict(boxstyle='round,pad=0.3', fc=PAPER, ec=GRID, alpha=0.95))
    fig.tight_layout()
    fig.savefig(os.path.join(SO, 'route_map.png'), dpi=200, bbox_inches='tight', pad_inches=0.15)
    plt.close(fig)


if __name__ == '__main__':
    drying_map()
    global_lakes()
    mars_tests()
    route_map()
    print(os.listdir(SO))
