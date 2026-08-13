#!/usr/bin/env python3
"""M14 form-fill RTL AP probe — replicate the tst_formsignaturetest embedded
fixture and byte-scan the form-fill output for /AP + /FontFile2.

Why this exists: the form fixture is EMBEDDED inline in
src/UnitTests/tst_formsignaturetest.cpp (object 8 = merged field+widget,
/T (name), /Rect [100 700 300 720]) — there is no fixture file on disk to
point the CLI at. This script regenerates that exact PDF and drives the real
binary, so a manual CLI probe (or a pre/post-GREEN verification) does not need
to hand-craft a PDF.

Usage:
    python3 scripts/form-fill-rtl-probe.py [albdf-binary] [outdir]
Defaults:
    albdf-binary = <repo>/src/build/bin/albdf (resolved from this script's path)
    outdir       = temp dir

Environment:
    QT_QPA_PLATFORM=offscreen is forced (headless contract).

Expected at baseline (pre-GREEN): exit code 1, stderr
"albdf: Unknown option 'font'." (QCommandLineParser::process bails on an
unregistered option — it never reaches execute()), NO output file.
Expected post-GREEN: exit 0, filled.pdf contains b"/AP" and b"/FontFile2".
"""
import os
import subprocess
import sys
import tempfile

# --- embedded fixture (byte-identical to tst_formsignaturetest.cpp) ---
FORM_PDF = (
    b"%PDF-1.5\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R /AcroForm 6 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [4 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    b"4 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
    b"/Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R /Annots [7 0 R 9 0 R] >>\nendobj\n"
    b"5 0 obj\n<< /Length 49 >>\nstream\n"
    b"BT /F1 12 Tf 1 0 0 1 72 740 Tm (Form test) Tj ET\n"
    b"endstream\nendobj\n"
    b"6 0 obj\n<< /Fields [8 0 R 10 0 R 12 0 R] /DA (/Helv 0 Tf 0 g) >>\nendobj\n"
    b"7 0 obj\n<< /Type /Annot /Subtype /Widget /Rect [100 700 300 720] /P 4 0 R /F 4 >>\nendobj\n"
    b"8 0 obj\n<< /FT /Tx /T (name) /V (John) /Type /Annot /Subtype /Widget "
    b"/Rect [100 700 300 720] /P 4 0 R /F 4 >>\nendobj\n"
    b"9 0 obj\n<< /Type /Annot /Subtype /Widget /Rect [100 600 115 615] /P 4 0 R /F 4 >>\nendobj\n"
    b"10 0 obj\n<< /FT /Btn /T (agree) /V /Off /Type /Annot /Subtype /Widget "
    b"/Rect [100 600 115 615] /P 4 0 R /F 4 >>\nendobj\n"
    b"11 0 obj\n<< /Type /Annot /Subtype /Widget /Rect [100 550 300 565] /P 4 0 R /F 4 >>\nendobj\n"
    b"12 0 obj\n<< /FT /Ch /T (country) /V (US) /Opt [(US) (UK) (DE)] /Type /Annot /Subtype /Widget "
    b"/Rect [100 550 300 565] /P 4 0 R /F 4 >>\nendobj\n"
    b"xref\n"
    b"0 13\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000074 00000 n \n"
    b"0000000131 00000 n \n"
    b"0000000201 00000 n \n"
    b"0000000349 00000 n \n"
    b"0000000447 00000 n \n"
    b"0000000519 00000 n \n"
    b"0000000608 00000 n \n"
    b"0000000725 00000 n \n"
    b"0000000814 00000 n \n"
    b"0000000932 00000 n \n"
    b"0000001022 00000 n \n"
    b"trailer << /Size 13 /Root 1 0 R >>\n"
    b"startxref\n"
    b"1163\n"
    b"%%EOF\n"
)


def main() -> int:
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    binary = sys.argv[1] if len(sys.argv) > 1 else os.path.join(repo, "src", "build", "bin", "albdf")
    outdir = sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp(prefix="m14probe")
    font = os.path.join(repo, "src", "tests", "fonts", "NotoNaskhArabic-Regular.ttf")

    form_path = os.path.join(outdir, "form.pdf")
    with open(form_path, "wb") as f:
        f.write(FORM_PDF)

    out_path = os.path.join(outdir, "filled.pdf")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(
        [binary, "form-fill", form_path, out_path,
         "--field", "name", "--value", "\u0633\u0644\u0627\u0645",  # سلام
         "--font", font],
        capture_output=True, env=env, timeout=120,
    )
    print("exit:", result.returncode)
    print("stdout:", result.stdout.decode("utf-8", "replace")[:300])
    print("stderr:", result.stderr.decode("utf-8", "replace")[:300])

    if os.path.exists(out_path):
        data = open(out_path, "rb").read()
        print("out size:", len(data))
        for token in (b"/AP", b"/FontFile2", b"/Type0", b"/Subtype /Form", b"/V"):
            print(f"{token.decode()} -> {token in data}")
    else:
        print("no output file")
    print("outdir:", outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
