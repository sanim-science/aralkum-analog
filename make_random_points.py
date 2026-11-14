"""Make 600 random points spread evenly over Mars between 60S and the equator.

Used to check mars_chloride_test.py: with no real effect, about 22.6% of points inside
closed lows should land in the Aral's last-to-dry band (we got 23%).
usage: python3 -I make_random_points.py random_pts.csv

AI disclosure: written with help from Claude (Anthropic AI assistant); run and checked
by the team.
"""
import csv
import sys

import numpy as np

rng = np.random.default_rng(1)
n = 600
lat = np.degrees(np.arcsin(rng.uniform(np.sin(np.radians(-60)), 0.0, n)))   # equal-area
lon = rng.uniform(0, 360, n)
with open(sys.argv[1], 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['FID', 'Lat', 'Lon'])
    for i, (a, b) in enumerate(zip(lat, lon)):
        w.writerow([i, a, b])
