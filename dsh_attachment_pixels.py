#!/usr/bin/env python3
"""dsh_attachment_pixels.py - inspect a DSH attachment blob as measurable pixel data.

DSH stores attachments content-addressed:
    ${DSH_HOME:-~/.dsh}/attachments/v1/objects/<first-2-hex>/<full-sha256>
so the sha256 shown in an "[image omitted ...]" placeholder maps directly to a file.

Usage:  python3 dsh_attachment_pixels.py <sha256-or-prefix-or-path>
        python3 dsh_attachment_pixels.py -            # read image bytes on stdin
        cat shot.jpg | python3 dsh_attachment_pixels.py -

Accepts a path (with U+202F/U+00A0 normalised, as macOS screenshot names use a
narrow no-break space), a bare sha256 or any unambiguous prefix of one, or raw
image bytes on stdin. Prints only measured values: dimensions, dominant colours,
a downsampled mean-colour grid, and coarse structural statistics. No
interpretation is added.
"""
import glob
import hashlib
import io
import os
import sys

import numpy as np
from PIL import Image

STORE = os.path.join(os.environ.get("DSH_HOME", os.path.expanduser("~/.dsh")),
                     "attachments", "v1", "objects")

# macOS writes U+202F NARROW NO-BREAK SPACE before AM/PM in screenshot names.
# Shells, editors and chat transports silently mangle it, so normalise it back.
EXOTIC_SPACE = {0x202F: " ", 0x00A0: " ", 0x2007: " ", 0x2009: " ", 0x3000: " "}


def normalise(s):
    return s.translate(EXOTIC_SPACE)


def find_on_disk(arg):
    """Path lookup that survives an invisible-space mangled filename."""
    for cand in (arg, normalise(arg)):
        if os.path.isfile(cand):
            return cand
    if os.sep in normalise(arg):
        hits = glob.glob(normalise(arg))
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise SystemExit("ambiguous path %r matches:\n  %s"
                             % (arg, "\n  ".join(sorted(hits))))
    return None


def describe(arg):
    return "".join(c if 0x20 <= ord(c) <= 0x7E else "<U+%04X>" % ord(c) for c in arg)


def resolve(arg):
    on_disk = find_on_disk(arg)
    if on_disk is not None:
        return on_disk, None

    prefix = normalise(arg).lower()
    for tag in ("sha256:", "attach_sha256:", "blob:", "objects/"):
        if tag in prefix:
            prefix = prefix.split(tag, 1)[1]
    prefix = prefix.strip()
    if not all(c in "0123456789abcdef" for c in prefix) or len(prefix) < 2:
        raise SystemExit(
            "not a path and not a hex sha256: %s\n"
            "  (if this came from a shell, the name may contain U+202F; "
            "pass the sha256 or use stdin: '-')" % describe(arg))

    for d in sorted(os.listdir(STORE)):
        full = os.path.join(STORE, d)
        if not os.path.isdir(full):
            continue
        for name in sorted(os.listdir(full)):
            if name.startswith(prefix):
                return os.path.join(full, name), None

    raise SystemExit(
        "no blob matching %r under %s\n"
        "  the file exists on disk but was never stored as a DSH attachment;\n"
        "  run it by path, or pipe it: cat <file> | %s -"
        % (describe(arg), STORE, os.path.basename(sys.argv[0])))


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__.strip())

    arg = sys.argv[1]
    if arg == "-":
        raw = sys.stdin.buffer.read()
        if not raw:
            raise SystemExit("stdin was empty: nothing to measure")
        path, source = "<stdin>", io.BytesIO(raw)
    else:
        path, _ = resolve(arg)
        raw = open(path, "rb").read()
        source = path

    digest = hashlib.sha256(raw).hexdigest()

    im = Image.open(source)
    fmt, mode = im.format, im.mode
    im = im.convert("RGB")
    w, h = im.size
    a = np.asarray(im).astype(np.uint16)

    print("file            %s" % path)
    print("bytes           %d" % len(raw))
    print("sha256          %s" % digest)
    print("name==sha256    %s"
          % (digest == os.path.basename(path) if path != "<stdin>" else "n/a (stdin)"))
    print("format/mode     %s / %s" % (fmt, mode))
    print("dimensions      %dx%d  (aspect %.3f)" % (w, h, w / h))

    # ---- dominant colours (16-level bins, JPEG-noise tolerant) ----
    flat = ((a // 24) * 24 + 12).reshape(-1, 3)
    uniq, counts = np.unique(flat, axis=0, return_counts=True)
    order = np.argsort(-counts)
    print("\ntop colours (quantised to 24-level bins):")
    for i in order[:12]:
        r, g, b = (int(v) for v in uniq[i])
        pct = 100.0 * counts[i] / len(flat)
        print("  #%02x%02x%02x  %5.2f%%   rgb(%3d,%3d,%3d)" % (r, g, b, pct, r, g, b))

    # ---- coarse spatial layout: mean colour of each cell ----
    gw, gh = 8, 12
    print("\nmean-colour grid %dx%d (row 0 = top):" % (gw, gh))
    for gy in range(gh):
        y0, y1 = h * gy // gh, h * (gy + 1) // gh
        row = []
        for gx in range(gw):
            x0, x1 = w * gx // gw, w * (gx + 1) // gw
            cell = a[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0)
            row.append("#%02x%02x%02x" % tuple(int(v) for v in cell))
        print("  " + " ".join(row))

    # ---- coarse structural stats ----
    lum = (0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2])
    r, g, b = a[..., 0].astype(int), a[..., 1].astype(int), a[..., 2].astype(int)
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)

    skin = ((r > 95) & (g > 40) & (b > 20) & ((mx - mn) > 15)
            & (abs(r - g) > 15) & (r > g) & (r > b))
    near_black = lum < 25
    near_white = lum > 230

    # horizontal banding: low-variance rows signal flat UI chrome / letterboxing
    row_std = lum.std(axis=1)
    flat_rows = row_std < 6

    print("\nstatistics (fractions of pixels/rows):")
    print("  mean luminance      %.1f / 255" % lum.mean())
    print("  mean saturation     %.3f" % sat.mean())
    print("  near-black          %5.2f%%" % (100 * near_black.mean()))
    print("  near-white          %5.2f%%" % (100 * near_white.mean()))
    print("  skin-tone heuristic %5.2f%%" % (100 * skin.mean()))
    print("  low-variance rows   %5.2f%%  (flat horizontal bands)" % (100 * flat_rows.mean()))

    # ---- column/row transition profile, to locate distinct bands ----
    seg = lum.mean(axis=1)
    jumps = np.where(np.abs(np.diff(seg)) > 22)[0]
    print("  strong row transitions (>22 luma step) at y = %s"
          % (", ".join(str(int(y)) for y in jumps[:24]) or "none"))


if __name__ == "__main__":
    main()
