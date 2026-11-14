"""Step 3b: per-scene trend test of EMIT mineral labels against drying year.

For every EMIT scene separately:
  - match each 60 m EMIT pixel to the year the permanent lake left it (Earth Engine raster)
  - per drying year with enough pixels, compute
      share  = % of pixels carrying a mineral family
      bd_idx = mean band depth of that family over ALL pixels (0 where absent),
               an abundance-like proxy that also uses band depth
  - Spearman rank correlation between drying year and each measure
Then count in how many scenes the trend has the same sign (sign test).
Run twice: all exposed seabed, and only seabed that never re-flooded after the lake left.

AI disclosure: written with help from Claude (Anthropic AI assistant); run and
checked by the team.
"""
import sys, os, glob, re, math
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, binomtest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emit_io import read_envi_header, read_envi_image, read_geotiff
from emit_vs_retreat import family

UPLOADS = sys.argv[1] if len(sys.argv) > 1 else '/mnt/user-data/uploads/'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
MIN_PX_PER_YEAR = 300      # a drying year needs this many EMIT pixels in a scene
MIN_YEARS = 8              # a scene needs this many drying years to get a trend

FAMS = ['calcite/dolomite (core)', 'gypsum (core)', 'clays (core)',
        'Mg-perchlorate label (non-core)', 'other salts/sulfates (non-core)', 'no match']


def scene_rows(hdrp, grid, g, fam_of_id):
    gid = re.search(r'(EMIT_L2B_MIN_001_\w+?)_ortho', os.path.basename(hdrp)).group(1)
    img = glob.glob(os.path.join(UPLOADS, f'*{gid}_ortho_subset_aid0000_min.img'))[0]
    h = read_envi_header(hdrp)
    a = read_envi_image(img, h)
    bd, mid = a[..., 0], a[..., 1]
    li, si = np.nonzero(mid != -9999)
    lon = h['x0'] + (si + 0.5) * h['dx']
    lat = h['y0'] - (li + 0.5) * h['dy']
    gc = np.floor((lon - g['x0']) / g['dx']).astype(int)
    gr = np.floor((g['y0'] - lat) / g['dy']).astype(int)
    ok = (gr >= 0) & (gr < grid.shape[0]) & (gc >= 0) & (gc < grid.shape[1])
    li, si, gr, gc = li[ok], si[ok], gr[ok], gc[ok]
    year = grid[gr, gc, 0].astype(int)
    reflood = grid[gr, gc, 1].astype(int)
    keep = (year >= 1985) & (year <= 2021)
    ids = mid[li, si][keep].astype(int)
    depth = np.clip(np.nan_to_num(bd[li, si][keep], nan=0.0), 0, None)
    fam = fam_of_id[np.clip(ids, 0, len(fam_of_id) - 1)]
    return pd.DataFrame({'date': re.search(r'_(\d{8})T', gid).group(1),
                         'year': year[keep], 'reflood': reflood[keep],
                         'family': fam, 'depth': depth})


def trends(df, label):
    per_year, per_scene = [], []
    for date, d in df.groupby('date'):
        n = d.groupby('year').size()
        years = n[n >= MIN_PX_PER_YEAR].index
        d = d[d['year'].isin(years)]
        if len(years) < MIN_YEARS:
            continue
        for f in FAMS:
            is_f = (d['family'] == f)
            share = is_f.groupby(d['year']).mean() * 100
            bdi = (d['depth'].where(is_f, 0.0)).groupby(d['year']).mean()
            r_share = spearmanr(share.index, share.values)[0]
            r_bd = spearmanr(bdi.index, bdi.values)[0] if f != 'no match' else np.nan
            per_scene.append({'subset': label, 'date': date, 'family': f,
                              'n_years': len(years), 'n_pixels': len(d),
                              'rho_share': r_share, 'rho_banddepth': r_bd})
            for y in years:
                per_year.append({'subset': label, 'date': date, 'family': f, 'year': y,
                                 'share': share[y], 'bd_index': bdi[y], 'n': n[y]})
    return pd.DataFrame(per_scene), pd.DataFrame(per_year)


def summarize(ps):
    rows = []
    for (sub, f), d in ps.groupby(['subset', 'family'], sort=False):
        for col in ['rho_share', 'rho_banddepth']:
            v = d[col].dropna()
            if v.empty:
                continue
            pos, neg = int((v > 0).sum()), int((v < 0).sum())
            p = binomtest(max(pos, neg), pos + neg, 0.5).pvalue if pos + neg else np.nan
            rows.append({'subset': sub, 'family': f, 'measure': col, 'scenes': len(v),
                         'rising': pos, 'falling': neg, 'median_rho': round(v.median(), 2),
                         'sign_test_p': round(p, 4)})
    return pd.DataFrame(rows)


def main():
    grid, g = read_geotiff(glob.glob(os.path.join(UPLOADS, '*aral_retreat_for_emit_60m.tif'))[0])
    hdrs = sorted(glob.glob(os.path.join(UPLOADS, '*_min.hdr')))
    lookup = read_envi_header(hdrs[0])['lookup']
    fam_of_id = np.array(['no match'] + [family(lookup[i][0]) if i in lookup else 'other (non-core)'
                                         for i in range(1, max(lookup) + 1)], dtype=object)
    df = pd.concat([scene_rows(h, grid, g, fam_of_id) for h in hdrs], ignore_index=True)
    print('scenes:', df['date'].nunique(), '| exposed-seabed pixels:', len(df))
    print(df.groupby('date').size().rename('pixels').to_string())

    ps_all, py_all = trends(df, 'all exposed seabed')
    ps_nr, py_nr = trends(df[df['reflood'] == 0], 'never re-flooded')
    ps = pd.concat([ps_all, ps_nr]); py = pd.concat([py_all, py_nr])
    summ = summarize(ps)
    ps.round(3).to_csv(os.path.join(OUT, 'emit_trend_per_scene.csv'), index=False)
    py.round(4).to_csv(os.path.join(OUT, 'emit_share_per_scene_year.csv'), index=False)
    summ.to_csv(os.path.join(OUT, 'emit_trend_summary.csv'), index=False)
    pd.set_option('display.width', 200, 'display.max_rows', 200)
    print('\n', summ.to_string(index=False))
    print('\nper-scene rho (share), all exposed seabed:')
    print(ps_all.pivot(index='date', columns='family', values='rho_share').round(2)
          [FAMS[:4]].assign(years=ps_all.groupby('date')['n_years'].first()).to_string())


if __name__ == '__main__':
    main()
