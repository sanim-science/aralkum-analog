"""Step 3: do EMIT mineral labels change with the year the Aral seabed dried out?

Inputs : EMIT L2B MIN Group 2 scenes (AppEEARS ENVI output, orthorectified, 60 m)
         aral_retreat_for_emit_60m.tif (from Earth Engine, step 1)
Output : CSV tables in out/

AI disclosure: written with help from Claude (Anthropic AI assistant); run and
checked by the team.
"""
import sys, os, glob, json, re
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emit_io import read_envi_header, read_envi_image, read_geotiff

UPLOADS = sys.argv[1] if len(sys.argv) > 1 else '/mnt/user-data/uploads/'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
os.makedirs(OUT, exist_ok=True)

# ---- mineral families -------------------------------------------------------
# EMIT's 10 validated "core" minerals: calcite, chlorite, dolomite, goethite, gypsum,
# hematite, illite+muscovite, kaolinite, montmorillonite, vermiculite (README 6.7).
# Everything else is labelled "non-core" and needs further validation.
def family(name):
    n = name.lower()
    if n == 'none':
        return 'no match'
    if 'perchlorate' in n:
        return 'Mg-perchlorate label (non-core)'
    if 'gypsum' in n:
        return 'gypsum (core)'
    if re.search(r'calc|dolo|aragonite', n):
        return 'calcite/dolomite (core)'
    if re.search(r'montmor|beidellite|nontronite|kaol|halloysite|nacrite|'
                 r'muscov|illite|vermicul|chlorite', n) and 'prehnite' not in n:
        return 'clays (core)'
    if re.search(r'szomolnokite|kieserite|carnallite|niter', n):
        return 'other salts/sulfates (non-core)'
    if re.search(r'witherite|strontianite|rhodochrosite|azurite|malachite', n):
        return 'other carbonates (non-core)'
    if 'prehnite' in n:
        return 'prehnite label (non-core)'
    if 'portlandite' in n:
        return 'portlandite label (non-core)'
    if 'cronstedtite' in n:
        return 'cronstedtite label (non-core)'
    return 'other (non-core)'


def zone_labels(retreat, reflood, cls):
    z = np.full(retreat.shape, 'outside basin / other', dtype=object)
    z[cls == 2] = 'dried before 1984'
    for lo, hi in [(1985, 1994), (1995, 2004), (2005, 2014), (2015, 2021)]:
        z[(retreat >= lo) & (retreat <= hi)] = f'dried {lo}-{hi}'
    z[cls == 1] = 'still water 2021'
    r = np.full(retreat.shape, 'not exposed 1985-2021', dtype=object)
    r[reflood == 0] = 're-flooded 0 years'
    r[(reflood >= 1) & (reflood <= 2)] = 're-flooded 1-2 years'
    r[reflood >= 3] = 're-flooded 3+ years'
    return z, r


def main():
    grid, g = read_geotiff(glob.glob(os.path.join(UPLOADS, '*aral_retreat_for_emit_60m.tif'))[0])
    retreat_g, reflood_g, cls_g = grid[..., 0], grid[..., 1], grid[..., 2]
    rows = []
    for hdrp in sorted(glob.glob(os.path.join(UPLOADS, '*_min.hdr'))):
        gid = re.search(r'(EMIT_L2B_MIN_001_\w+?)_ortho', os.path.basename(hdrp)).group(1)
        img = glob.glob(os.path.join(UPLOADS, f'*{gid}_ortho_subset_aid0000_min.img'))
        if not img:
            print('missing image for', gid); continue
        h = read_envi_header(hdrp)
        a = read_envi_image(img[0], h)
        bd, mid = a[..., 0], a[..., 1]
        valid = mid != -9999
        li, si = np.nonzero(valid)
        lon = h['x0'] + (si + 0.5) * h['dx']
        lat = h['y0'] - (li + 0.5) * h['dy']
        gc = np.floor((lon - g['x0']) / g['dx']).astype(int)
        gr = np.floor((g['y0'] - lat) / g['dy']).astype(int)
        inside = (gr >= 0) & (gr < grid.shape[0]) & (gc >= 0) & (gc < grid.shape[1])
        li, si, gr, gc = li[inside], si[inside], gr[inside], gc[inside]
        ids = mid[li, si].astype(int)
        names = np.array([h['lookup'].get(i, ('none', 0))[0] if i != 0 else 'none' for i in ids])
        fam = np.array([family(n) for n in names])
        z, r = zone_labels(retreat_g[gr, gc], reflood_g[gr, gc], cls_g[gr, gc])
        date = re.search(r'_(\d{8})T', gid).group(1)
        rows.append(pd.DataFrame({
            'scene': gid, 'date': date, 'mineral_id': ids, 'mineral_name': names,
            'family': fam, 'band_depth': bd[li, si], 'zone': z, 'reflood_zone': r,
            'retreat_year': retreat_g[gr, gc], 'lon': lon[inside], 'lat': lat[inside]}))
        print(gid, 'pixels matched to grid:', inside.sum())
    df = pd.concat(rows, ignore_index=True)
    df.to_parquet(os.path.join(OUT, 'emit_pixels.parquet')) if False else None

    def table(by, sub=None):
        d = df if sub is None else df[sub]
        t = pd.crosstab(d[by], d['family'], normalize='index').mul(100).round(1)
        t.insert(0, 'n_pixels', d.groupby(by).size())
        return t

    zone_order = ['dried before 1984', 'dried 1985-1994', 'dried 1995-2004',
                  'dried 2005-2014', 'dried 2015-2021', 'outside basin / other']
    results = {}
    results['pooled_by_zone'] = table('zone').reindex(zone_order)
    for date in sorted(df['date'].unique()):
        results[f'{date}_by_zone'] = table('zone', df['date'] == date).reindex(zone_order)
    results['pooled_by_reflood'] = table('reflood_zone', df['retreat_year'] > 0)
    for k, t in results.items():
        t.to_csv(os.path.join(OUT, f'{k}.csv'))
    # scene-level family shares (consistency check)
    sc = pd.crosstab(df['date'], df['family'], normalize='index').mul(100).round(1)
    sc.insert(0, 'n_pixels', df.groupby('date').size())
    sc.to_csv(os.path.join(OUT, 'family_share_by_scene.csv'))
    df[['date', 'zone', 'reflood_zone', 'retreat_year', 'family', 'mineral_name',
        'band_depth']].to_csv(os.path.join(OUT, 'emit_pixels_sample.csv.gz'),
                              index=False, compression='gzip')
    pd.set_option('display.width', 250, 'display.max_columns', 30)
    print('\n=== family share by scene (%) ===\n', sc.T)
    for k in ['pooled_by_zone', '20230731_by_zone', '20230823_by_zone', 'pooled_by_reflood']:
        if k in results:
            print(f'\n=== {k} (% of pixels in each row) ===\n', results[k].T)


if __name__ == '__main__':
    main()
