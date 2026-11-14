"""Figures for the Mars test.

1. out/mars_terra_sirenum_zones.png : Terra Sirenum. Every closed low (>= 100 km2) is
   coloured by the Aral drying zone each spot would fall in if that low dried like the
   Aral (one water level falling evenly). Chloride deposits are drawn on top, so you can
   see whether they sit in the last-to-dry (darkest) part.
2. out/mars_chloride_tests.png : the two tests on all 642 deposits
   (needs out/mars_chloride_F.csv and out/mars_chloride_test.json).

usage: python3 -I mars_figures.py <chloride csv>
AI disclosure: written with help from Claude (Anthropic AI assistant); run and checked
by the team.
"""
import csv
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource, ListedColormap
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mars_basin import OUT, R_MARS, ARAL_FRACTIONS

INK, INK2, GRID, SURF = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
ZONE_COLORS = ['#86b6ef', '#3987e5', '#1c5cab', '#0d366b']      # ordinal blue, validated
ZONE_NAMES = ['Dries first (0-7%): carbonate + clay on the Aral',
              'Next (7-53%): gypsum peak on the Aral', 'Then (53-77%): transition',
              'Dries last (77-100%): most soluble salts on the Aral']
ORANGE = '#eb6834'
CHANCE_GREY = '#c9c8c3'
NEWTON = (-40.8, 201.9)
DAVILA_LOW = (-32.89, 205.62)          # point inside the closed low under the big deposit
EXT = (199.0, 214.0, -41.5, -29.0)     # lon_w, lon_e, lat_s, lat_n
MIN_LOW = 100.0                        # km2

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'axes.edgecolor': GRID, 'axes.labelcolor': INK2,
                     'xtick.color': INK2, 'ytick.color': INK2, 'text.color': INK,
                     'figure.facecolor': SURF, 'axes.facecolor': SURF})


def load():
    z = np.load(os.path.join(OUT, 'mars_g_z.npy')).astype(np.float64)
    lab = np.load(os.path.join(OUT, 'mars_g_lab.npy'))
    depth = np.load(os.path.join(OUT, 'mars_g_depth.npy'))
    meta = json.load(open(os.path.join(OUT, 'mars_g_meta.json')))
    res, lat_max = meta['res'], meta['lat_max']
    lats = lat_max - (np.arange(z.shape[0]) + 0.5) / res
    A = np.broadcast_to(((R_MARS * np.radians(1 / res)) ** 2 *
                         np.cos(np.radians(lats)))[:, None], z.shape)
    return z, lab, depth, A, res, lat_max


def zones_in_window(z, lab, A, res, lat_max):
    """Aral zone (0-3) for every pixel of every closed low >= MIN_LOW that touches the window."""
    lon_w, lon_e, lat_s, lat_n = EXT
    r0, r1 = int((lat_max - lat_n) * res), int((lat_max - lat_s) * res)
    c0, c1 = int(lon_w * res), int(lon_e * res)
    win_lab = lab[r0:r1, c0:c1]
    zone = np.full(win_lab.shape, -1, int)
    for k in np.unique(win_lab[win_lab > 0]):
        m = lab == k
        a = A[m]
        if a.sum() < MIN_LOW:
            continue
        zz = z[m]
        # share of the low's area strictly higher than each pixel (ties split in half)
        o = np.argsort(zz)
        cum = np.cumsum(a[o])
        tot = cum[-1]
        zs = zz[o]
        lo = np.searchsorted(zs, zz, 'left'); hi = np.searchsorted(zs, zz, 'right')
        below = np.where(lo > 0, cum[np.maximum(lo - 1, 0)], 0.0)
        below_eq = cum[hi - 1]
        F = (tot - below_eq + 0.5 * (below_eq - below)) / tot
        zfull = np.full(lab.shape, -1, int)
        zfull[m] = np.digitize(F, ARAL_FRACTIONS)
        wm = win_lab == k
        zone[wm] = zfull[r0:r1, c0:c1][wm]
    return zone, (r0, r1, c0, c1)


def fig_map(z, lab, depth, A, res, lat_max, chl):
    zone, (r0, r1, c0, c1) = zones_in_window(z, lab, A, res, lat_max)
    lon_w, lon_e, lat_s, lat_n = EXT
    sz = z[r0:r1, c0:c1]
    ext = [lon_w, lon_e, lat_s, lat_n]
    fig, ax = plt.subplots(figsize=(11, 8.6))
    ls = LightSource(azdeg=315, altdeg=35)
    ax.imshow(sz, extent=ext, cmap='gray', vmin=-3000, vmax=5000)
    ax.imshow(ls.hillshade(sz, vert_exag=0.02, dx=1, dy=1), extent=ext, cmap='gray', alpha=0.35)
    ax.imshow(np.ma.masked_less(zone, 0), extent=ext, cmap=ListedColormap(ZONE_COLORS),
              vmin=-0.5, vmax=3.5, interpolation='nearest', alpha=0.92)
    X = np.linspace(lon_w, lon_e, sz.shape[1]); Y = np.linspace(lat_n, lat_s, sz.shape[0])
    ax.contour(X, Y, sz, levels=[1280], colors=[INK], linewidths=0.6)
    ax.plot(NEWTON[1], NEWTON[0], marker='*', ms=13, color='white', mec=INK, mew=0.8)
    ax.annotate('Newton crater', (NEWTON[1], NEWTON[0]), xytext=(7, -4),
                textcoords='offset points', color='white', fontsize=10)
    ax.annotate('Closed low under the salt flats\nof Davila et al. (2011):\n3,600 km², rim 1,276 m, 254 m deep',
                (205.9, -32.6), xytext=(208.2, -30.2), fontsize=8.5, color=INK,
                bbox=dict(boxstyle='round,pad=0.3', fc=SURF, ec=GRID),
                arrowprops=dict(arrowstyle='-', color=INK, lw=0.8))
    la, lo = chl
    sel = (lo >= lon_w) & (lo <= lon_e) & (la >= lat_s) & (la <= lat_n)
    ax.scatter(lo[sel], la[sel], s=48, color=ORANGE, edgecolor='white', linewidth=1.2, zorder=5)
    handles = [Patch(color=c, label=n) for c, n in zip(ZONE_COLORS, ZONE_NAMES)]
    handles += [Line2D([], [], color=INK, lw=0.8, label='1,280 m contour'),
                Line2D([], [], marker='o', ls='', ms=7, color=ORANGE, mec='white',
                       label=f'Chloride deposits (Osterloo et al. 2010), {sel.sum()} in view')]
    ax.legend(handles=handles, loc='lower right', fontsize=8.3, frameon=True,
              facecolor=SURF, edgecolor=GRID, title='Closed lows coloured by Aral drying zone',
              title_fontsize=8.5)
    ax.set_xlim(lon_w, lon_e); ax.set_ylim(lat_s, lat_n)
    ax.set_xlabel('Longitude (degrees E)'); ax.set_ylabel('Latitude (degrees)')
    ax.set_title('Terra Sirenum, Mars: if each closed low dried like the Aral, where would salts end up?',
                 loc='left', fontsize=12, color=INK)
    ax.text(0.0, -0.09, 'NASA MOLA elevation, 16 px/deg. Zones per low: share of the low already dry when '
            'the water leaves a spot (limits 6.9%, 52.6%, 77.4% from our Aral data).',
            transform=ax.transAxes, fontsize=8.5, color=INK2)
    fig.savefig(os.path.join(OUT, 'mars_terra_sirenum_zones.png'), dpi=150, bbox_inches='tight')
    plt.close(fig)


def _bar_labels(ax, bars, vals):
    for bb, v in zip(bars, vals):
        ax.text(bb.get_x() + bb.get_width() / 2, v + 1.2, f'{v:.0f}%', ha='center',
                fontsize=9, color=INK)


def fig_tests():
    res = json.load(open(os.path.join(OUT, 'mars_chloride_test.json')))
    ins = res['inside_closed_depression']
    rows = [r for r in csv.DictReader(open(os.path.join(OUT, 'mars_chloride_F.csv')))
            if r['F_share_of_basin_dry_before'] and float(r['depression_area_km2']) >= MIN_LOW]
    F = np.array([float(r['F_share_of_basin_dry_before']) for r in rows])
    edges = [0.0] + ARAL_FRACTIONS + [1.0]
    obs = np.histogram(F, bins=edges)[0] / len(F) * 100
    exp = np.diff(edges) * 100

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw=dict(width_ratios=[1, 2.1]))
    for ax in (a1, a2):
        ax.grid(axis='y', color=GRID, lw=0.8); ax.set_axisbelow(True)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
        ax.set_ylim(0, 72)
    b = a1.bar([0, 1], [ins['expected_share'] * 100, ins['share'] * 100], 0.6,
               color=[CHANCE_GREY, ZONE_COLORS[2]])
    _bar_labels(a1, b, [ins['expected_share'] * 100, ins['share'] * 100])
    a1.set_xticks([0, 1]); a1.set_xticklabels(['Ground within\n150 km', 'Chloride\ndeposits'])
    a1.set_ylabel('In a closed low (%)')
    a1.set_title('1. Do salts sit in closed lows?  Yes', loc='left', fontsize=11, color=INK)

    x = np.arange(4)
    b1 = a2.bar(x - 0.2, exp, 0.38, color=CHANCE_GREY, label='If deposits were placed at random in the low')
    b2 = a2.bar(x + 0.2, obs, 0.38, color=ZONE_COLORS[2], label='Real chloride deposits')
    _bar_labels(a2, b1, exp); _bar_labels(a2, b2, obs)
    a2.set_xticks(x)
    a2.set_xticklabels(['Dries first\n0-7%', 'Gypsum peak\n7-53%', 'Transition\n53-77%',
                        'Dries last\n77-100%'])
    a2.set_ylabel('Share of deposits (%)')
    a2.legend(frameon=False, fontsize=9, loc='upper right')
    a2.set_title('2. Inside the low, are they where the Aral puts salts (dries last)?  No',
                 loc='left', fontsize=11, color=INK)
    fig.text(0.01, -0.04, f'642 chloride deposits (Osterloo et al. 2010, via Leask & Ehlmann 2021); '
             f'{len(F)} lie in closed lows of at least 100 km² (NASA MOLA, 16 px/deg). '
             'Zone limits fixed from our Aral data before looking at Mars.',
             fontsize=8.5, color=INK2)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, 'mars_chloride_tests.png'), dpi=150, bbox_inches='tight')
    plt.close(fig)


def main(chl_csv):
    from mars_chloride_test import load_points
    z, lab, depth, A, res, lat_max = load()
    la, lo, *_ = load_points(chl_csv)
    fig_map(z, lab, depth, A, res, lat_max, (la, lo))
    fig_tests()


if __name__ == '__main__':
    main(sys.argv[1])
