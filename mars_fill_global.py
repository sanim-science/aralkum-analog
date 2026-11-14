"""Fill every closed depression on Mars between 70S and 20N (MOLA MEGDR 16 px/deg).

Uses morphological reconstruction by erosion (scikit-image), which gives the same
filled surface as a priority-flood: water poured anywhere fills each closed low up to
its lowest rim point, and anything that touches the window edge drains away.
Longitude wraps around, so the window is padded 30 degrees on each side.

Outputs (out/): mars_g_z.npy (int16 elevation), mars_g_depth.npy (float32, filled - z),
mars_g_lab.npy (int32 depression id, 0 = not in a closed depression),
mars_g_meta.json (lat_max, res).

AI disclosure: written with help from Claude (Anthropic AI assistant); run and checked
by the team.
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage
from skimage.morphology import reconstruction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mars_basin import read_megdr, OUT

LAT_MAX, LAT_MIN, PAD_DEG = 20.0, -70.0, 30


def main(img, lbl):
    z, L = read_megdr(img, lbl)
    res = L['res']
    r0, r1 = int((90 - LAT_MAX) * res), int((90 - LAT_MIN) * res)
    band = z[r0:r1]
    pad = int(PAD_DEG * res)
    big = np.hstack([band[:, -pad:], band, band[:, :pad]]).astype(np.float64)
    seed = big.copy()
    seed[1:-1, 1:-1] = big.max()
    filled = reconstruction(seed, big, method='erosion')
    filled = filled[:, pad:-pad]
    depth = (filled - band).astype(np.float32)
    lab, n = ndimage.label(depth > 0, structure=np.ones((3, 3)))
    # join depressions that wrap across 0/360 E
    for i in np.nonzero((lab[:, 0] > 0) & (lab[:, -1] > 0))[0]:
        a, b = lab[i, 0], lab[i, -1]
        if a != b:
            lab[lab == b] = a
    os.makedirs(OUT, exist_ok=True)
    np.save(os.path.join(OUT, 'mars_g_z.npy'), band.astype(np.int16))
    np.save(os.path.join(OUT, 'mars_g_depth.npy'), depth)
    np.save(os.path.join(OUT, 'mars_g_lab.npy'), lab.astype(np.int32))
    json.dump(dict(lat_max=LAT_MAX, lat_min=LAT_MIN, res=res),
              open(os.path.join(OUT, 'mars_g_meta.json'), 'w'))
    print(f'band {band.shape}, {n} depressions, '
          f'{(depth > 0).mean() * 100:.1f}% of pixels inside a closed depression')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
