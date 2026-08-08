#!/usr/bin/env python3
"""Probe an albdf-emitted PDF's CIDToGIDMap stream + PNG ink bbox (P6 checks).

CIDToGIDMap (PDF 32000-1 §9.7.4.3): must be a stream of 65536 2-byte big-endian
entries (entry[code] = gid, entry[0] = 0 = .notdef). A short ARRAY is invalid —
Ghostscript and PDF4QT's own parser (pdffont.cpp, stream-only read) ignore it
and fall back to /Identity (code 1 -> .null invisible, code 2 -> Latin 'A').

Examples:
  python3 cidtogidmap_probe.py out.pdf --expect "1:681 2:1173 3:728 4:1266"
  python3 cidtogidmap_probe.py --ink render.png --expect-bbox 2x16 --expect-ink 32

Exit 0 = pass, 1 = fail. Needs Pillow only for --ink.
"""
import argparse
import re
import sys
import zlib


def cidtogidmap_stream(pdf_path):
    """Return decoded stream bytes, or None if not an indirect Flate stream."""
    data = open(pdf_path, "rb").read()
    m = re.search(rb"/CIDToGIDMap\s+(\d+)\s+0\s+R", data)
    if not m:
        return None
    om = re.search(rb"(?m)^%s 0 obj\s*$" % m.group(1), data)
    if not om:
        return None
    sm = re.search(rb"stream\r?\n", data[om.end():])
    if not sm:
        return None
    s = om.end() + sm.end()
    e = data.find(b"endstream", s)
    return zlib.decompress(data[s:e].strip(b"\r\n"))


def nonzero_entries(dec):
    return {i: (dec[2 * i] << 8) | dec[2 * i + 1]
            for i in range(1, len(dec) // 2) if dec[2 * i] or dec[2 * i + 1]}


def ink_bbox(png_path, threshold=64):
    from PIL import Image
    im = Image.open(png_path).convert("L")
    px = im.load()
    w, h = im.size
    coords = [(x, y) for y in range(h) for x in range(w) if px[x, y] < threshold]
    if not coords:
        return None, 0
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1), len(coords)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", nargs="?", help="PDF produced by albdf add-text")
    ap.add_argument("--expect", default="", help="space-separated 'code:gid' pairs, e.g. '1:681 2:1173'")
    ap.add_argument("--ink", help="PNG to measure (Ghostscript or albdf render)")
    ap.add_argument("--expect-bbox", default="", help="e.g. '2x16'")
    ap.add_argument("--expect-ink", type=int, default=None)
    a = ap.parse_args()
    ok = True

    if a.pdf:
        try:
            dec = cidtogidmap_stream(a.pdf)
        except zlib.error:
            dec = None
        if dec is None:
            print(f"{a.pdf}: CIDToGIDMap is NOT an indirect Flate stream -> FAIL")
            ok = False
        else:
            nz = nonzero_entries(dec)
            good = len(dec) == 131072 and dec[0] == 0 and dec[1] == 0
            print(f"{a.pdf}: decoded {len(dec)}B; nonzero entries: {nz}; "
                  f"spec-size+notdef={'OK' if good else 'FAIL'}")
            ok = ok and good
            if a.expect:
                exp = {int(k): int(v) for k, v in (p.split(":") for p in a.expect.split())}
                good = nz == exp
                print(f"  expected {exp}: {'OK' if good else 'FAIL'}")
                ok = ok and good

    if a.ink:
        sz, n = ink_bbox(a.ink)
        good = sz is not None
        print(f"{a.ink}: ink bbox={sz} px, {n} ink px"
              + ("" if good else " (BLANK) -> FAIL"))
        ok = ok and good
        if a.expect_bbox:
            w, h = a.expect_bbox.lower().split("x")
            good = sz == (int(w), int(h))
            print(f"  expected bbox {a.expect_bbox}: {'OK' if good else 'FAIL'}")
            ok = ok and good
        if a.expect_ink is not None:
            good = abs(n - a.expect_ink) <= 3
            print(f"  expected ink ~{a.expect_ink}: {'OK' if good else 'FAIL'}")
            ok = ok and good

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
