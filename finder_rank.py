"""Rank drying closed-basin lakes worldwide from the Earth Engine export of
step4_global_drying_lakes.js, and draw the chart.

1. keep basins in dry climates (aridity index = rain / potential evaporation < 0.5)
2. join basins whose lost-water centres are within 150 km into one lake region
3. sum the area of permanent water that became land, 1984-2021
4. names are added by hand from the coordinates (listed in NAMES); regions that are
   reservoirs, river floodplains or deltas are left out (listed in EXCLUDED)

usage: python3 -I finder_rank.py global_drying_lakes.csv
outputs: finder_clusters.csv, finder_top_lakes.csv, finder_top_lakes.png

AI disclosure: written with help from Claude (Anthropic AI assistant); run and checked
by the team. Lake names were assigned from coordinates and should be checked on a map.
"""
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

R_EARTH = 6371.0
LINK_KM = 150.0
MAX_ARIDITY = 0.5


def cluster(d):
    lat, lon = np.radians(d.lat.values), np.radians(d.lon.values)
    parent = list(range(len(d)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(d)):
        c = np.sin(lat[i]) * np.sin(lat) + np.cos(lat[i]) * np.cos(lat) * np.cos(lon - lon[i])
        for j in np.nonzero(R_EARTH * np.arccos(np.clip(c, -1, 1)) < LINK_KM)[0]:
            if j > i:
                parent[find(j)] = find(i)
    roots = [find(i) for i in range(len(d))]
    d = d.assign(cluster=roots)
    g = d.groupby('cluster').apply(lambda x: pd.Series(dict(
        lost=x.lost_perm_km2.sum(), p2s=x.perm_to_seasonal_km2.sum(), perm84=x.perm_1984_km2.sum(),
        n_basins=len(x), endo_max=x.ENDO.max(),
        ai=np.average(x.aridity_index, weights=x.lost_perm_km2),
        lat=np.average(x.lat, weights=x.lost_perm_km2), lon=np.average(x.lon, weights=x.lost_perm_km2),
        first_id=x.sort_values('lost_perm_km2', ascending=False).HYBAS_ID.iloc[0],
        ids=' '.join(str(i) for i in x.HYBAS_ID))))
    g['share_lost'] = g.lost / g.perm84
    return g.sort_values('lost', ascending=False)


# keyed by the HydroBASINS ID of the basin that lost the most water in each region
NAMES = {
    4060255710: ('Aral Sea', 'Kazakhstan / Uzbekistan'),
    7060511880: ('Great Salt Lake', 'USA'),
    7060073780: ('NW Great Basin lakes (Malheur, Carson Sink, Goose, Abert...)', 'USA'),
    6060691260: ('Lake Poopó and Altiplano salt pans', 'Bolivia'),
    2060085820: ('Sistan Hamun lakes and Gowd-e-Zareh', 'Iran / Afghanistan'),
    6060960220: ('Southern Patagonia lakes (incl. Colhué Huapi)', 'Argentina'),
    2060692620: ('Lake Urmia', 'Iran'),
    7060073710: ('Laguna Salada (Salton trough)', 'Mexico'),
    4060050490: ('Torey lakes', 'Russia / Mongolia'),
    4060160150: ('Turgay and Irgiz lakes', 'Kazakhstan'),
    6060857460: ('Mar Chiquita (part)', 'Argentina'),
    2060086420: ('Lake Aksehir', 'Turkey'),
    4060481170: ('Dengizkul and Bukhara lakes', 'Uzbekistan'),
    1060695540: ('Lake Chad', 'Chad / Niger / Nigeria / Cameroon'),
    6060040690: ('Laguna Llancanelo', 'Argentina'),
    7060073650: ('Sevier Lake', 'USA'),
    2060085930: ('Fars lakes (Bakhtegan, Tashk)', 'Iran'),
}
REGION_NAMES = {   # regions whose biggest basin is not a single named lake
    (48.50, 51.29): ('West Kazakhstan steppe lakes', 'Kazakhstan'),
    (-35.61, 142.44): ('Western Victoria lakes', 'Australia'),
}
EXCLUDED = ['Iraq lakes and marshes (open basins, 32.4N 44.7E)', 'NE Brazil reservoirs',
            'NE China open basins', 'Indus river, Pakistan', 'Volga delta / Caspian coast',
            'Lake Mead and Lake Powell (reservoirs)', 'Manych, Russia (open basin)',
            'Northern Patagonia (-39.2, -67.7; mixed, not named)']


def main(path):
    d = pd.read_csv(path)
    g = cluster(d[d.aridity_index < MAX_ARIDITY].copy())
    g.to_csv('finder_clusters.csv')
    rows = []
    for _, r in g.iterrows():
        nm = NAMES.get(int(r.first_id))
        if nm is None:
            for (la, lo), v in REGION_NAMES.items():
                if abs(r.lat - la) < 0.05 and abs(r.lon - lo) < 0.05:
                    nm = v
        if nm is None:
            continue
        rows.append(dict(name=nm[0], country=nm[1], lost_perm_km2=round(r.lost),
                         became_seasonal_km2=round(r.p2s), permanent_1984_km2=round(r.perm84),
                         share_lost=round(r.share_lost, 2), aridity_index=round(r.ai, 2),
                         closed_basin='yes' if r.endo_max >= 1 else 'no',
                         lat=round(r.lat, 2), lon=round(r.lon, 2), hybas_ids=r.ids))
    t = pd.DataFrame(rows).sort_values('lost_perm_km2', ascending=False).reset_index(drop=True)
    t.index += 1
    t.to_csv('finder_top_lakes.csv', index_label='rank')
    print(t.drop(columns='hybas_ids').to_string())
    print(f'Aral vs next: {t.lost_perm_km2.iloc[0] / t.lost_perm_km2.iloc[1]:.1f} times')
    chart(t.head(15))


def chart(t):
    INK, INK2, GRID, SURF = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
    BLUE, DARK = '#3987e5', '#0d366b'
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.edgecolor': GRID,
                         'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK,
                         'text.color': INK, 'figure.facecolor': SURF, 'axes.facecolor': SURF})

    def arid(a):
        return 'hyper-arid' if a < 0.05 else ('arid' if a < 0.2 else 'semi-arid')
    labels = [f"{r['name'].split(' (')[0].replace(' and Gowd-e-Zareh', '').replace(' salt pans', '')}"
              f", {r.country}" for _, r in t.iterrows()]
    vals = t.lost_perm_km2.values
    XMAX = 2600
    fig, ax = plt.subplots(figsize=(10, 6.6))
    y = np.arange(len(t))[::-1]
    shown = np.minimum(vals, XMAX)
    ax.barh(y, shown, height=0.62, color=[DARK] + [BLUE] * (len(t) - 1))
    for yi, v, s, (_, r) in zip(y, vals, shown, t.iterrows()):
        tail = f"{int(round(r.share_lost * 100))}% of 1984 water · {arid(r.aridity_index)}"
        if v > XMAX:
            ax.text(XMAX - 30, yi, f"{v:,.0f} km² (bar cut)  ", va='center', ha='right',
                    color='white', fontsize=9.5, fontweight='bold')
            ax.text(XMAX + 40, yi, tail, va='center', fontsize=8.5, color=INK2)
        else:
            ax.text(s + 40, yi, f"{v:,.0f} km²  ·  " + tail, va='center', fontsize=8.5, color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9.5)
    ax.set_xlim(0, XMAX + 1900)
    ax.set_xticks([0, 500, 1000, 1500, 2000, 2500])
    ax.grid(axis='x', color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis='y', length=0)
    ax.set_xlabel('Permanent lake water that became dry land, 1984 to 2021 (km²)')
    fig.text(0.01, 0.985, 'Where else did a closed salt lake dry out while satellites watched?',
             fontsize=12.5, color=INK, ha='left', va='top')
    fig.text(0.01, 0.947, 'Closed basins in dry climates, 52°S to 52°N. The method puts the Aral '
             'first, 17 times ahead of the next.', fontsize=9, color=INK2, ha='left', va='top')
    fig.subplots_adjust(top=0.90, bottom=0.17, left=0.32, right=0.98)
    fig.text(0.01, 0.02, 'Data: JRC Global Surface Water v1.4 (Landsat, 30 m), transitions 1984 vs '
             '2021; HydroBASINS level 6; TerraClimate aridity (rain / potential evaporation).\n'
             'Lakes unusually high in 1984 (Great Salt Lake, Great Basin, Laguna Salada) look larger '
             'here. Lakes that dried before 1984 (Owens, Lop Nur) are missed.',
             fontsize=7.8, color=INK2, ha='left', va='bottom')
    fig.savefig('finder_top_lakes.png', dpi=150)


if __name__ == '__main__':
    main(sys.argv[1])
