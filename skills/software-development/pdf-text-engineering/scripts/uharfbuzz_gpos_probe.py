#!/usr/bin/env python3
"""Shape Arabic/Hebrew text with HarfBuzz and print per-glyph GPOS data.

Replicates the albdf engine buffer setup (pdfrtltextengine.cpp:128-256):
direction RTL, script arab, language fa, cluster level MONOTONE_CHARACTERS,
no features. Prints advances, GPOS x/y offsets, clusters, and glyph ink
extents (font units).

IMPORTANT: run with the SYSTEM python3, which has uharfbuzz installed
(`pip install --user --break-system-packages uharfbuzz`). The Hermes
`execute_code` sandbox interpreter is a different python and will NOT see
it — write/run this via terminal instead.

Usage:
    python3 uharfbuzz_gpos_probe.py <font.ttf> "مَا" "بِسْم" ...
"""
import sys

import uharfbuzz as hb


def shape(font, text, direction="rtl", script="Arab", lang="fa"):
    buf = hb.Buffer()
    buf.add_str(text)
    buf.direction = direction
    # uharfbuzz 0.56: ot_tag_to_script takes str (bytes -> TypeError);
    # hb.Script / hb.script_from_string do not exist in this version.
    buf.script = hb.ot_tag_to_script(script)
    buf.language = lang
    hb.shape(font, buf)
    return [
        (info.codepoint, info.cluster, pos.x_advance, pos.x_offset, pos.y_offset)
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions)
    ]


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    blob = hb.Blob.from_file_path(sys.argv[1])
    face = hb.Face(blob)
    font = hb.Font(face)
    print("upem:", face.upem, "glyph_count:", face.glyph_count)
    for text in sys.argv[2:]:
        print(f"--- {text} ---")
        for gid, cluster, x_adv, x_off, y_off in shape(font, text):
            ext = font.get_glyph_extents(gid)  # height negative = ink extends downward
            print(
                f"  gid={gid:4d} 0x{gid:04x} x_adv={x_adv:6d} x_off={x_off:6d} "
                f"y_off={y_off:6d} cluster={cluster} "
                f"extents=({ext.x_bearing},{ext.y_bearing},{ext.width},{ext.height})"
            )


if __name__ == "__main__":
    main()
