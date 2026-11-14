"""MOLA reader and first Terra Sirenum test.

Reads the MOLA MEGDR global topography (NASA PDS, MGS-M-MOLA-5-MEGDR-L3-V1.0) and lists
the connected regions below the 1,280 m contour of Davila et al. (2011) near Newton crater.
Result: at 16 px/deg the low ground below 1,280 m is not one closed basin; it connects to
the northern plains. The full closed-low analysis is in mars_depressions.py and
mars_fill_global.py; the chloride test is in mars_chloride_test.py.

The other scripts import read_megdr, pixel_area_km2, ARAL_FRACTIONS and OUT from here.

Aral fractions (EMIT analysis box, our data), share of the lake area already exposed:
   carbonate/clay zone   : first 6.9%     (dried 1985-1994)
   gypsum-peak zone      : 6.9-52.6%      (1995-2004)
   transition            : 52.6-77.4%     (2005-2014)
   salt-label zone       : last 22.6%     (2015-2021)

usage: python3 -I mars_basin.py megt90n000eb.img megt90n000eb.lbl
AI disclosure: written with help from Claude (Anthropic AI assistant); run and
checked by the team.
"""
import sys, os, re, glob, json
import numpy as np
from collections import deque

ARAL_FRACTIONS = [0.069, 0.526, 0.774]
ZONES = ['carbonate/clay zone (first 7%)', 'gypsum-peak zone (7-53%)',
         'transition (53-77%)', 'salt-label zone (last 23%)']
SPILL = 1280.0          # m, Davila et al. 2011
R_MARS = 3396.0         # km, mean radius
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')


def read_label(path):
    t = open(path, errors='replace').read()
    def val(key, cast=float):
        m = re.search(r'^\s*' + key + r'\s*=\s*"?([-\w.+]+)', t, re.M)
        return cast(m.group(1)) if m else None
    return dict(lines=val('LINES', int), samples=val('LINE_SAMPLES', int),
                bits=val('SAMPLE_BITS', int),
                stype=re.search(r'SAMPLE_TYPE\s*=\s*"?(\w+)', t).group(1),
                res=val('MAP_RESOLUTION'), maxlat=val('MAXIMUM_LATITUDE'),
                westlon=val('WESTERNMOST_LONGITUDE'),
                scale=val('SCALING_FACTOR') or 1.0, offset=val('OFFSET') or 0.0)


def read_megdr(img, lbl):
    L = read_label(lbl)
    dt = '>i2' if L['stype'].upper().startswith('MSB') else '<i2'
    z = np.fromfile(img, dtype=dt).reshape(L['lines'], L['samples']).astype(np.float32)
    z = z * L['scale'] + L['offset']
    return z, L


def pixel_area_km2(lat, res):
    d = np.radians(1.0 / res)
    return (R_MARS * d) ** 2 * np.cos(np.radians(lat))


def components_below(z, level):
    """4-connected components of z < level; returns label array and count."""
    mask = z < level
    lab = np.zeros(z.shape, dtype=np.int32)
    n = 0
    for r0, c0 in zip(*np.nonzero(mask)):
        if lab[r0, c0]:
            continue
        n += 1
        q = deque([(r0, c0)]); lab[r0, c0] = n
        while q:
            r, c = q.popleft()
            for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= rr < z.shape[0] and 0 <= cc < z.shape[1] and mask[rr, cc] and not lab[rr, cc]:
                    lab[rr, cc] = n; q.append((rr, cc))
    return lab, n


def lake_at(z, level, seed):
    """Region below `level` connected to `seed` (the basin's lowest point)."""
    lab, _ = components_below(z, level)
    return lab == lab[seed] if lab[seed] else np.zeros(z.shape, bool)


def main(img, lbl, box=(-45.0, -28.0, 198.0, 225.0)):
    z, L = read_megdr(img, lbl)
    res = L['res']
    lat_s, lat_n, lon_w, lon_e = box
    r0 = int((L['maxlat'] - lat_n) * res); r1 = int((L['maxlat'] - lat_s) * res)
    c0 = int((lon_w - L['westlon']) * res); c1 = int((lon_e - L['westlon']) * res)
    sub = z[r0:r1, c0:c1]
    lats = L['maxlat'] - (np.arange(r0, r1) + 0.5) / res
    lons = L['westlon'] + (np.arange(c0, c1) + 0.5) / res
    area = np.broadcast_to(pixel_area_km2(lats, res)[:, None], sub.shape)
    print(f'grid {L["lines"]}x{L["samples"]} at {res} px/deg; window {sub.shape}, '
          f'elevation {sub.min():.0f} to {sub.max():.0f} m')

    # candidate closed basins below the 1280 m contour
    lab, n = components_below(sub, SPILL)
    cands = []
    for k in range(1, n + 1):
        m = lab == k
        a = area[m].sum()
        if a < 5000:
            continue
        touches = m[0].any() or m[-1].any() or m[:, 0].any() or m[:, -1].any()
        rr, cc = np.nonzero(m)
        i = np.argmin(sub[m])
        cands.append(dict(id=k, area_km2=round(float(a)), floor_m=float(sub[m].min()),
                          depth_m=round(float(SPILL - sub[m].min())),
                          lat=round(float(lats[rr].mean()), 2), lon=round(float(lons[cc].mean()), 2),
                          seed=(int(rr[i]), int(cc[i])), touches_edge=bool(touches)))
    cands.sort(key=lambda d: -d['area_km2'])
    print('\nclosed regions below 1280 m (>= 5,000 km2):')
    for c in cands:
        print({k: v for k, v in c.items() if k != 'seed'})
    return sub, area, lats, lons, cands


def drying_order(sub, area, seed, spill=SPILL, step=5.0):
    full = lake_at(sub, spill, seed)
    A0 = area[full].sum()
    levels = np.arange(spill, sub[seed] - step, -step)
    exposed_level = np.full(sub.shape, np.nan)       # level at which each pixel dried
    curve = []
    prev = full
    for lv in levels:
        cur = lake_at(sub, lv, seed) if lv > sub[seed] else np.zeros(sub.shape, bool)
        newly = prev & ~cur
        exposed_level[newly] = lv
        curve.append((float(lv), float(1 - area[cur].sum() / A0)))
        prev = cur
    exposed_level[prev] = levels[-1]
    return full, exposed_level, np.array(curve), A0


if __name__ == '__main__':
    img, lbl = sys.argv[1], sys.argv[2]
    main(img, lbl)
