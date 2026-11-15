"""A field route across the dried Aral seabed, from the youngest to the oldest ground
that never flooded again, with what NASA EMIT sees at each stop.

Why: if the Aral is to be used to test instruments (orbital or on a rover) on an
evaporite sequence of known age, people need concrete places to go. Each stop is a
1 km x 1 km patch where at least 90% of the 60 m cells dried in one period and never
flooded again, chosen to have the most EMIT observations. The stops are chained so
each is within MAX_STEP_KM of the previous one, which keeps the route compact.

usage: python3 -I field_route.py [uploads folder]
outputs: out/field_route.csv, out/field_route.png, out/emit_cell_counts.npz

AI disclosure: written with help from Claude (Anthropic AI assistant); run and checked
by the team.
"""
import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emit_io import read_envi_header, read_envi_image
from emit_vs_retreat import family

UPLOADS = sys.argv[1] if len(sys.argv) > 1 else '/mnt/user-data/uploads/'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
FAMS = ['calcite/dolomite (core)', 'gypsum (core)', 'clays (core)',
        'Mg-perchlorate label (non-core)']
SHORT = ['carbonate', 'gypsum', 'clays', 'salt-type label']
PERIODS = [(2015, 2021), (2005, 2014), (1995, 2004), (1985, 1994)]   # young -> old
WIN = 17              # cells (17 x 60 m ~ 1 km)
MIN_PURE = 0.9
MAX_STEP_KM = 40.0


def load_grid():
    grid = np.load(os.path.join(OUT, 'retreat_grid.npy'))
    g = json.load(open(os.path.join(OUT, 'retreat_grid.json')))
    return grid, g


def emit_counts(grid, g):
    cache = os.path.join(OUT, 'emit_cell_counts.npz')
    if os.path.exists(cache):
        z = np.load(cache)
        return z['counts'], z['total']
    H, W = grid.shape[:2]
    counts = np.zeros((len(FAMS), H, W), np.uint16)
    total = np.zeros((H, W), np.uint16)
    for hdrp in sorted(glob.glob(os.path.join(UPLOADS, '*_min.hdr'))):
        gid = re.search(r'(EMIT_L2B_MIN_001_\w+?)_ortho', os.path.basename(hdrp)).group(1)
        imgs = glob.glob(os.path.join(UPLOADS, f'*{gid}_ortho_subset_aid0000_min.img'))
        if not imgs:
            continue
        h = read_envi_header(hdrp)
        a = read_envi_image(imgs[0], h)
        mid = a[..., 1]
        fam_of_id = np.array([family(h['lookup'].get(i, ('none', ''))[0])
                              for i in range(int(np.nanmax(mid)) + 2)], dtype=object)
        li, si = np.nonzero(mid != -9999)
        lon = h['x0'] + (si + 0.5) * h['dx']
        lat = h['y0'] - (li + 0.5) * h['dy']
        gc = np.floor((lon - g['x0']) / g['dx']).astype(int)
        gr = np.floor((g['y0'] - lat) / g['dy']).astype(int)
        ok = (gr >= 0) & (gr < H) & (gc >= 0) & (gc < W)
        li, si, gr, gc = li[ok], si[ok], gr[ok], gc[ok]
        fam = fam_of_id[np.clip(mid[li, si].astype(int), 0, len(fam_of_id) - 1)]
        np.add.at(total, (gr, gc), 1)
        for k, f in enumerate(FAMS):
            s = fam == f
            np.add.at(counts[k], (gr[s], gc[s]), 1)
        print('added', gid)
    np.savez_compressed(cache, counts=counts, total=total)
    return counts, total


def km_between(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    c = np.sin(p1) * np.sin(p2) + np.cos(p1) * np.cos(p2) * np.cos(np.radians(lon2 - lon1))
    return 6371.0 * np.arccos(np.clip(c, -1, 1))


def main():
    grid, g = load_grid()
    year, refl = grid[..., 0].astype(int), grid[..., 1].astype(int)
    counts, total = emit_counts(grid, g)
    H, W = year.shape
    lat_c = g['y0'] - (np.arange(H) + 0.5) * g['dy']
    lon_c = g['x0'] + (np.arange(W) + 0.5) * g['dx']
    LAT = np.broadcast_to(lat_c[:, None], (H, W))
    LON = np.broadcast_to(lon_c[None, :], (H, W))
    obs_density = uniform_filter(total.astype(float), WIN)
    stops, prev = [], None
    for lo, hi in PERIODS:
        pure = uniform_filter(((year >= lo) & (year <= hi) & (refl == 0)).astype(float), WIN)
        score = np.where(pure >= MIN_PURE, obs_density, -1.0)
        if prev is not None:
            score = np.where(km_between(prev[0], prev[1], LAT, LON) <= MAX_STEP_KM, score, -1.0)
        if score.max() <= 0:
            print('no patch for', lo, hi)
            continue
        r, c = np.unravel_index(np.argmax(score), score.shape)
        sl = (slice(max(0, r - WIN // 2), r + WIN // 2 + 1), slice(max(0, c - WIN // 2), c + WIN // 2 + 1))
        n = int(total[sl].sum())
        shares = [100.0 * counts[k][sl].sum() / max(n, 1) for k in range(len(FAMS))]
        yrs = year[sl][(year[sl] >= lo) & (year[sl] <= hi)]
        stop = dict(period=f'{lo}-{hi}', lat=round(float(lat_c[r]), 4), lon=round(float(lon_c[c]), 4),
                    median_drying_year=int(np.median(yrs)), share_pure=round(float(pure[r, c]), 2),
                    emit_observations=n)
        for s, v in zip(SHORT, shares):
            stop[f'{s}_%'] = round(v, 1)
        core = dict(zip(SHORT, shares))
        stop['most_common'] = max(core, key=core.get)
        if prev is not None:
            stop['km_from_previous'] = round(float(km_between(prev[0], prev[1], lat_c[r], lon_c[c])), 1)
        stops.append(stop)
        prev = (lat_c[r], lon_c[c])
    df = pd.DataFrame(stops)
    df.insert(0, 'stop', range(1, len(df) + 1))
    df.to_csv(os.path.join(OUT, 'field_route.csv'), index=False)
    print(df.to_string(index=False))
    return df, year, refl, g




def figure(df, year, refl, g):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, BoundaryNorm
    from matplotlib.patches import Patch
    INK, INK2, GRID, SURF = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
    grid = np.load(os.path.join(OUT, 'retreat_grid.npy'))
    cls = grid[..., 2]
    H, W = year.shape
    ext = [g['x0'], g['x0'] + W * g['dx'], g['y0'] - H * g['dy'], g['y0']]
    fig, ax = plt.subplots(figsize=(11, 5.6))
    base = np.full((H, W, 3), [0.988, 0.988, 0.984])
    base[cls == 1] = [0.80, 0.88, 0.92]                       # still water 2021
    base[(year > 0) & (refl > 0)] = [0.86, 0.86, 0.84]       # dried, flooded again later
    ax.imshow(base, extent=ext, interpolation='nearest')
    ramp = ['#cfe1f7', '#86b6ef', '#3987e5', '#1c5cab', '#0d366b']
    bounds = [1985, 1995, 2005, 2010, 2015, 2022]
    dry = np.ma.masked_where(~((year > 0) & (refl == 0)), year)
    ax.imshow(dry, extent=ext, cmap=ListedColormap(ramp), norm=BoundaryNorm(bounds, 5),
              interpolation='nearest')
    ax.plot(df.lon, df.lat, color=INK, lw=1.2, zorder=4)
    ax.scatter(df.lon, df.lat, s=140, color='#eb6834', edgecolor='white', linewidth=1.5, zorder=5)
    offsets = {1: (14, -2), 2: (14, -34), 3: (-30, -62), 4: (12, 14)}
    for _, r in df.iterrows():
        sh = {'carbonate': r['carbonate_%'], 'gypsum': r['gypsum_%'], 'clays': r['clays_%'],
              'salt-type label': r['salt-type label_%']}
        top = sorted(sh.items(), key=lambda kv: -kv[1])[:2]
        mins = ', '.join(f'{k} {v:.0f}%' for k, v in top if v >= 1)
        txt = f"Stop {r.stop}: dried {r.period}\n{mins}\n{r.lat:.3f}N {r.lon:.3f}E"
        ax.annotate(txt, (r.lon, r.lat), xytext=offsets.get(r.stop, (10, 8)), textcoords='offset points',
                    fontsize=8.5, color=INK, bbox=dict(boxstyle='round,pad=0.25', fc=SURF, ec=GRID, alpha=0.95),
                    zorder=6)
    handles = [Patch(color=c, label=l) for c, l in zip(ramp, ['1985-94', '1995-2004', '2005-09', '2010-14', '2015-21'])]
    handles += [Patch(color=(0.86, 0.86, 0.84), label='dried, then flooded again'),
                Patch(color=(0.80, 0.88, 0.92), label='water in 2021')]
    ax.legend(handles=handles, loc='lower left', fontsize=8, title='Never flooded again, dried in',
              title_fontsize=8.5, frameon=True, facecolor=SURF, edgecolor=GRID)
    ax.set_xlabel('Longitude (degrees E)')
    ax.set_ylabel('Latitude (degrees N)')
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.set_title('A 90 km field route across 36 years of drying, on ground that never flooded again',
                 loc='left', fontsize=12, color=INK, pad=14)
    ax.text(0, -0.16, 'Stops: 1 km patches where at least 90% of 60 m cells dried in one period and never '
            'flooded again; mineral shares from 12 NASA EMIT scenes (2023).', transform=ax.transAxes,
            fontsize=8.5, color=INK2)
    fig.savefig(os.path.join(OUT, 'field_route.png'), dpi=150, bbox_inches='tight')


if __name__ == '__main__':
    figure(*main())
