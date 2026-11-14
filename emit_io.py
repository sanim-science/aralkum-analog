"""Readers for AppEEARS ENVI output (EMIT L2B MIN) and the Earth Engine GeoTIFF export.

AI disclosure: written with help from Claude (Anthropic AI assistant); run and
checked by the team.
"""
import re
import numpy as np
import tifffile

ENVI_DTYPES = {1: np.uint8, 2: np.int16, 3: np.int32, 4: np.float32,
               5: np.float64, 12: np.uint16}


def _braced_list(text, key):
    m = re.search(r'^' + re.escape(key) + r'\s*=\s*\{(.*?)\}\s*$', text,
                  re.MULTILINE | re.DOTALL)
    if not m:
        return None
    return [v.strip() for v in m.group(1).split(',')]


def read_envi_header(path):
    text = open(path, encoding='utf-8', errors='replace').read()
    def num(key):
        return int(re.search(r'^' + key + r'\s*=\s*(\d+)', text, re.M).group(1))
    hdr = {
        'samples': num('samples'), 'lines': num('lines'), 'bands': num('bands'),
        'dtype': ENVI_DTYPES[num('data type')],
        'interleave': re.search(r'^interleave\s*=\s*(\w+)', text, re.M).group(1).lower(),
        'byte_order': num('byte order'),
    }
    mi = _braced_list(text, 'map info')
    # ENVI map info: projection, ref px x, ref px y, map x, map y, dx, dy, ...
    # reference pixel (1,1) = upper-left corner of the upper-left pixel
    hdr['x0'] = float(mi[3]) - (float(mi[1]) - 1) * float(mi[5])
    hdr['y0'] = float(mi[4]) + (float(mi[2]) - 1) * float(mi[6])
    hdr['dx'], hdr['dy'] = float(mi[5]), float(mi[6])
    hdr['band_names'] = _braced_list(text, 'band names')
    m = re.search(r'^data ignore value\s*=\s*([-\d.eE]+)', text, re.M)
    hdr['nodata'] = float(m.group(1)) if m else None
    # mineral lookup table (present in EMIT L2B MIN headers)
    idx, names, groups = (_braced_list(text, k) for k in ('index', 'name', 'group'))
    if idx and names and groups:
        hdr['lookup'] = {int(i): (n, int(g)) for i, n, g in zip(idx, names, groups)}
    return hdr


def read_envi_image(img_path, hdr):
    dt = np.dtype(hdr['dtype']).newbyteorder('>' if hdr['byte_order'] else '<')
    a = np.fromfile(img_path, dtype=dt)
    s, l, b = hdr['samples'], hdr['lines'], hdr['bands']
    if a.size != s * l * b:
        raise ValueError(f'size mismatch: {a.size} vs {s*l*b}')
    if hdr['interleave'] == 'bip':
        a = a.reshape(l, s, b)
    elif hdr['interleave'] == 'bsq':
        a = a.reshape(b, l, s).transpose(1, 2, 0)
    elif hdr['interleave'] == 'bil':
        a = a.reshape(l, b, s).transpose(0, 2, 1)
    return a.astype(np.float32)  # (lines, samples, bands)


def lzw_decode(data):
    """Pure-Python TIFF LZW decoder (MSB-first, early change).
    Needed because the 'imagecodecs' package is not available here."""
    out = bytearray()
    table = [bytes([i]) for i in range(256)] + [b'', b'']
    nbits, bitpos, total = 9, 0, len(data) * 8
    prev = None
    data = bytes(data) + b'\x00\x00\x00'
    while bitpos + nbits <= total:
        i = bitpos >> 3
        chunk = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
        code = (chunk >> (24 - (bitpos & 7) - nbits)) & ((1 << nbits) - 1)
        bitpos += nbits
        if code == 256:                       # clear
            del table[258:]
            nbits, prev = 9, None
            continue
        if code == 257:                       # end of information
            break
        if prev is None:
            entry = table[code]
        else:
            entry = table[code] if code < len(table) else prev + prev[:1]
            table.append(prev + entry[:1])
        out += entry
        prev = entry
        if len(table) >= (1 << nbits) - 1 and nbits < 12:
            nbits += 1
    return bytes(out)


def _read_tiled_lzw(tf, page):
    th, tw = page.tilelength, page.tilewidth
    rows, cols = page.imagelength, page.imagewidth
    spp = page.samplesperpixel
    dt = np.dtype(page.dtype).newbyteorder(tf.byteorder)
    out = np.zeros((rows, cols, spp), dtype=page.dtype)
    ntx = (cols + tw - 1) // tw
    fh = tf.filehandle
    for k, (off, cnt) in enumerate(zip(page.dataoffsets, page.databytecounts)):
        fh.seek(off)
        raw = lzw_decode(fh.read(cnt))
        tile = np.frombuffer(raw[:th * tw * spp * dt.itemsize], dtype=dt)
        tile = tile.reshape(th, tw, spp)
        r0, c0 = (k // ntx) * th, (k % ntx) * tw
        h, w = min(th, rows - r0), min(tw, cols - c0)
        out[r0:r0 + h, c0:c0 + w] = tile[:h, :w]
    return out


def read_geotiff(path):
    with tifffile.TiffFile(path) as tf:
        page = tf.pages[0]
        if page.compression == 5 and page.is_tiled and page.predictor == 1 \
                and page.planarconfig == 1:
            data = _read_tiled_lzw(tf, page)
        else:
            data = tf.asarray()
        tags = page.tags
        scale = tags['ModelPixelScaleTag'].value
        tie = tags['ModelTiepointTag'].value
        nodata = tags['GDAL_NODATA'].value if 'GDAL_NODATA' in tags else None
    # tiepoint: (i, j, k, x, y, z); assume PixelIsArea (corner), as Earth Engine writes
    x0 = tie[3] - tie[0] * scale[0]
    y0 = tie[4] + tie[1] * scale[1]
    if data.ndim == 3 and data.shape[0] < data.shape[-1] and data.shape[0] <= 4:
        data = np.moveaxis(data, 0, -1)       # (bands, rows, cols) -> (rows, cols, bands)
    return data, dict(x0=x0, y0=y0, dx=scale[0], dy=scale[1], nodata=nodata)
