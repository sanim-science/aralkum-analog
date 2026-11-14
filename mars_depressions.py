"""Find closed depressions in MOLA MEGDR topography with a priority-flood fill.

A depression is a set of connected pixels whose filled level is above the
ground. Its spill level is the filled level (the lowest rim point water would
overflow). This does not assume a contour in advance, so it tests whether the
1,280 m contour of Davila et al. (2011) closes in the MOLA data.

usage: python3 -I mars_depressions.py megt90n000eb.img megt90n000eb.lbl
AI disclosure: written with help from Claude (Anthropic AI assistant); run and checked
by the team.
"""
import heapq
import sys
import json
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mars_basin import read_megdr, pixel_area_km2, OUT

BOX = (-50.0, -25.0, 190.0, 230.0)   # lat_min, lat_max, lon_min, lon_max
NEWTON = (-40.8, 201.9)


def priority_flood(z):
    """Fill depressions; edges drain out. Returns the filled surface."""
    h, w = z.shape
    filled = z.astype(np.float64).copy()
    done = np.zeros((h, w), bool)
    heap = []
    for i in range(h):
        for j in (0, w - 1):
            heapq.heappush(heap, (filled[i, j], i, j)); done[i, j] = True
    for j in range(1, w - 1):
        for i in (0, h - 1):
            heapq.heappush(heap, (filled[i, j], i, j)); done[i, j] = True
    while heap:
        v, i, j = heapq.heappop(heap)
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1),
                       (1, 1), (1, -1), (-1, 1), (-1, -1)):
            a, b = i + di, j + dj
            if 0 <= a < h and 0 <= b < w and not done[a, b]:
                done[a, b] = True
                if filled[a, b] < v:
                    filled[a, b] = v
                heapq.heappush(heap, (filled[a, b], a, b))
    return filled


def label(mask):
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    n = 0
    for i in range(h):
        for j in range(w):
            if mask[i, j] and lab[i, j] == 0:
                n += 1
                stack = [(i, j)]
                lab[i, j] = n
                while stack:
                    a, b = stack.pop()
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1),
                                   (1, 1), (1, -1), (-1, 1), (-1, -1)):
                        x, y = a + da, b + db
                        if 0 <= x < h and 0 <= y < w and mask[x, y] and lab[x, y] == 0:
                            lab[x, y] = n
                            stack.append((x, y))
    return lab, n


def gc_km(lat1, lon1, lat2, lon2, r=3396.0):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    c = np.sin(p1) * np.sin(p2) + np.cos(p1) * np.cos(p2) * np.cos(dl)
    return r * np.arccos(np.clip(c, -1, 1))


def bearing(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    x = np.sin(dl) * np.cos(p2)
    y = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dl)
    return (np.degrees(np.arctan2(x, y)) + 360) % 360


def main(img, lbl, min_area=3000.0):
    z, meta = read_megdr(img, lbl)
    res = meta['res']
    lat_min, lat_max, lon_min, lon_max = BOX
    r0 = int(round((90 - lat_max) * res)); r1 = int(round((90 - lat_min) * res))
    c0 = int(round(lon_min * res)); c1 = int(round(lon_max * res))
    sub = z[r0:r1, c0:c1].astype(np.float64)
    lats = 90 - (np.arange(r0, r1) + 0.5) / res
    lons = (np.arange(c0, c1) + 0.5) / res
    area = pixel_area_km2(lats, res)[:, None] * np.ones((1, sub.shape[1]))

    filled = priority_flood(sub)
    depth = filled - sub
    lab, n = label(depth > 0)
    out = []
    for k in range(1, n + 1):
        m = lab == k
        a = float(area[m].sum())
        if a < min_area:
            continue
        ii, jj = np.nonzero(m)
        spill = float(filled[m].max())
        floor = float(sub[m].min())
        w = area[m]
        clat = float((lats[ii] * w).sum() / w.sum())
        clon = float((lons[jj] * w).sum() / w.sum())
        out.append(dict(id=k, area_km2=round(a), spill_m=spill, floor_m=floor,
                        depth_m=spill - floor, lat=round(clat, 2), lon=round(clon, 2),
                        km_from_newton=round(float(gc_km(*NEWTON, clat, clon))),
                        bearing_deg=round(float(bearing(*NEWTON, clat, clon))),
                        touches_edge=bool(ii.min() == 0 or jj.min() == 0 or
                                          ii.max() == sub.shape[0] - 1 or
                                          jj.max() == sub.shape[1] - 1)))
    out.sort(key=lambda d: -d['area_km2'])
    for d in out:
        print(d)
    os.makedirs(OUT, exist_ok=True)
    np.save(os.path.join(OUT, 'mars_sub.npy'), sub)
    np.save(os.path.join(OUT, 'mars_filled.npy'), filled)
    np.save(os.path.join(OUT, 'mars_labels.npy'), lab)
    with open(os.path.join(OUT, 'mars_window.json'), 'w') as f:
        json.dump(dict(box=BOX, res=res, r0=r0, c0=c0), f)
    with open(os.path.join(OUT, 'mars_depressions.json'), 'w') as f:
        json.dump(out, f, indent=1)
    return out


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
