"""Test the Aral drying prediction against real Martian chloride deposits.

Prediction (fixed from our Aral data BEFORE looking at the Mars deposits):
in a closed basin that dries by evaporation, the most soluble salts end up in the
LAST 22.6% of the lake area to dry (Aral: area exposed after 77.4% of the lake was
already dry, i.e. the 2015-2021 seabed in our EMIT box).

For each chloride deposit (Osterloo et al. 2010, via Leask & Ehlmann 2021, CC0)
that lies inside a closed depression in today's MOLA topography, we compute
    F = share of the depression's area that lies HIGHER than the deposit
      = how much of the lake would already be dry when the water left this spot,
assuming one water level falling through the basin.
If deposits were placed at random inside depressions, F would be uniform on 0..1,
so 22.6% of deposits would have F > 0.774. The prediction says: many more.

Two tests:
  1. deposit level: binomial test, share with F > 0.774 vs 0.226;
  2. depression level (deposits cluster, so they are not independent): one value per
     depression (the median F of its deposits), compared with simulated random
     placement (Monte Carlo, 20,000 runs).
Also reported: share of deposits that sit in a closed depression at all, compared with
the share of ground within 150 km of each deposit that is in a closed depression.

usage: python3 -I mars_chloride_test.py <chloride csv>
AI disclosure: written with help from Claude (Anthropic AI assistant); run and checked
by the team.
"""
import csv
import json
import os
import sys

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mars_basin import OUT, R_MARS

ARAL_LAST = 0.774          # F threshold from the Aral (fixed in advance)
MIN_AREAS = [100.0, 1000.0, 10000.0]   # km2, sensitivity
RNG = np.random.default_rng(42)


def load_points(path):
    rows = list(csv.DictReader(open(path, newline='', encoding='utf-8-sig')))
    cols = rows[0].keys()
    def pick(keys):
        for c in cols:
            if any(k == c.lower().strip() for k in keys):
                return c
        for c in cols:
            if any(k in c.lower() for k in keys):
                return c
        raise KeyError(keys)
    clat = pick(['lat', 'latitude', 'centroid_lat', 'y'])
    clon = pick(['lon', 'long', 'longitude', 'centroid_lon', 'x'])
    lat = np.array([float(r[clat]) for r in rows])
    lon = np.array([float(r[clon]) for r in rows]) % 360.0
    return lat, lon, rows, clat, clon


def main(path):
    z = np.load(os.path.join(OUT, 'mars_g_z.npy')).astype(np.float64)
    depth = np.load(os.path.join(OUT, 'mars_g_depth.npy'))
    lab = np.load(os.path.join(OUT, 'mars_g_lab.npy'))
    meta = json.load(open(os.path.join(OUT, 'mars_g_meta.json')))
    res, lat_max = meta['res'], meta['lat_max']
    h, w = z.shape
    lats = lat_max - (np.arange(h) + 0.5) / res
    px_area = (R_MARS * np.radians(1 / res)) ** 2 * np.cos(np.radians(lats))
    A = np.broadcast_to(px_area[:, None], z.shape)

    lat, lon, rows, clat, clon = load_points(path)
    print(f'{len(lat)} deposits; columns used: {clat}, {clon}; '
          f'lat {lat.min():.1f}..{lat.max():.1f}, lon {lon.min():.1f}..{lon.max():.1f}')
    ii = np.floor((lat_max - lat) * res).astype(int)
    jj = np.floor(lon * res).astype(int) % w
    ok = (ii >= 0) & (ii < h)
    ii, jj = ii[ok], jj[ok]
    k_pt = lab[ii, jj]
    z_pt = z[ii, jj]

    # depression areas and per-depression sorted elevations (only those with deposits)
    ids = np.unique(k_pt[k_pt > 0])
    dep_area = {}
    dep_sorted = {}
    flat_lab = lab.ravel()
    order = np.argsort(flat_lab, kind='stable')
    sl = flat_lab[order]
    starts = np.searchsorted(sl, ids, 'left'); ends = np.searchsorted(sl, ids, 'right')
    zr, ar = z.ravel(), A.ravel()
    for k, s, e in zip(ids, starts, ends):
        idx = order[s:e]
        zz, aa = zr[idx], ar[idx]
        o = np.argsort(zz)
        dep_sorted[k] = (zz[o], np.cumsum(aa[o]))
        dep_area[k] = aa.sum()

    def F_of(k, zp):
        zz, cum = dep_sorted[k]
        tot = cum[-1]
        below_or_eq = cum[np.searchsorted(zz, zp, 'right') - 1] if zp >= zz[0] else 0.0
        below = cum[np.searchsorted(zz, zp, 'left') - 1] if zp > zz[0] else 0.0
        above = tot - below_or_eq
        tie = below_or_eq - below
        return (above + 0.5 * tie) / tot

    F = np.array([F_of(k, zp) if k > 0 else np.nan for k, zp in zip(k_pt, z_pt)])
    area_pt = np.array([dep_area.get(k, 0.0) for k in k_pt])

    # local null for "inside a closed depression": share of ground within 150 km
    in_dep = lab > 0
    rad = 150.0
    local_share = []
    for i, j in zip(ii, jj):
        dl = int(np.ceil(rad / (R_MARS * np.radians(1 / res))))
        i0, i1 = max(0, i - dl), min(h, i + dl + 1)
        cosl = max(np.cos(np.radians(lats[i])), 0.05)
        dj = int(np.ceil(dl / cosl))
        cols = np.arange(j - dj, j + dj + 1) % w
        sub_in = in_dep[i0:i1][:, cols]
        sub_a = A[i0:i1][:, cols]
        la = np.radians(lats[i0:i1])[:, None]
        lo = np.radians((cols + 0.5) / res)[None, :]
        p1, l1 = np.radians(lats[i]), np.radians((j + 0.5) / res)
        c = np.sin(p1) * np.sin(la) + np.cos(p1) * np.cos(la) * np.cos(lo - l1)
        disc = R_MARS * np.arccos(np.clip(c, -1, 1)) <= rad
        local_share.append((sub_in & disc).astype(float).__mul__(sub_a).sum() /
                           (disc * sub_a).sum())
    local_share = np.array(local_share)

    results = dict(n_deposits=int(len(lat)), n_in_band=int(ok.sum()))
    obs_in = int((k_pt > 0).sum())
    exp_in = float(local_share.sum())
    sd_in = float(np.sqrt((local_share * (1 - local_share)).sum()))
    results['inside_closed_depression'] = dict(
        observed=obs_in, share=obs_in / len(k_pt), expected_local=exp_in,
        expected_share=exp_in / len(k_pt), z=(obs_in - exp_in) / sd_in)
    print(f"\ninside a closed depression: {obs_in}/{len(k_pt)} = {obs_in/len(k_pt):.1%}; "
          f"expected from ground within 150 km: {exp_in/len(k_pt):.1%} (z = {(obs_in-exp_in)/sd_in:.1f})")

    results['F_tests'] = []
    for amin in MIN_AREAS:
        sel = (k_pt > 0) & (area_pt >= amin)
        f = F[sel]
        n = len(f); hits = int((f > ARAL_LAST).sum())
        bt = stats.binomtest(hits, n, 1 - ARAL_LAST, alternative='greater')
        # depression-level test
        ks = k_pt[sel]
        uniq, counts = np.unique(ks, return_counts=True)
        med = np.array([np.median(f[ks == k]) for k in uniq])
        obs_dep = int((med > ARAL_LAST).sum())
        sims = np.array([(np.median(RNG.random((20000, c)), axis=1) > ARAL_LAST) for c in counts]).sum(axis=0)
        p_dep = float((sims >= obs_dep).mean())
        r = dict(min_area_km2=amin, n_deposits=n, hits=hits, share=hits / n,
                 p_binomial=bt.pvalue, median_F=float(np.median(f)),
                 ks_p_vs_uniform=float(stats.kstest(f, 'uniform').pvalue),
                 n_depressions=int(len(uniq)), dep_hits=obs_dep,
                 dep_expected=float(sims.mean()), p_depression_level=p_dep)
        results['F_tests'].append(r)
        print(f"\nmin depression area {amin:,.0f} km2: {n} deposits in {len(uniq)} depressions")
        print(f"  deposits in the Aral 'last 22.6%' band: {hits}/{n} = {hits/n:.1%} "
              f"(chance 22.6%), binomial p = {bt.pvalue:.2g}; median F = {np.median(f):.2f}")
        print(f"  depressions whose median deposit is in that band: {obs_dep}/{len(uniq)} "
              f"(random placement gives {sims.mean():.1f}); p = {p_dep:.2g}")

    # write per-deposit table
    with open(os.path.join(OUT, 'mars_chloride_F.csv'), 'w', newline='') as fh:
        wr = csv.writer(fh)
        wr.writerow(['lat', 'lon_E', 'elev_m', 'depression_id', 'depression_area_km2',
                     'F_share_of_basin_dry_before', 'in_aral_last_band', 'local_share_in_depressions'])
        for a, b, c, d, e, f_, g in zip(lat[ok], lon[ok], z_pt, k_pt, area_pt, F, local_share):
            wr.writerow([f'{a:.3f}', f'{b:.3f}', int(c), int(d), round(float(e)),
                         '' if np.isnan(f_) else round(float(f_), 3),
                         '' if np.isnan(f_) else int(f_ > ARAL_LAST), round(float(g), 3)])
    json.dump(results, open(os.path.join(OUT, 'mars_chloride_test.json'), 'w'), indent=1)
    return results


if __name__ == '__main__':
    main(sys.argv[1])
