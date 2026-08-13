// qt_rtl_probe.cpp — empirically verify Qt 6.8 QTextLayout/QRawFont RTL shaping facts.
//
// Answers, per loaded TTF:
//   1. Does QTextLayout produce the same GIDs as direct hb_shape?   (shaping on/off)
//   2. Does QGlyphRun::positions() include GPOS mark y-offsets?     (fatha displacement)
//   3. Is QGlyphRun::stringIndexes() filled?                        (cluster mapping; try
//      with AND without the Retrieve* flags — default call returns EMPTY, verified 6.8.2)
//   4. RTL run glyph order: LOGICAL order w/ descending x, only RUNS are visual.
//   5. QRawFont::advancesForGlyphIndexes == hb hmtx (byte-parity -> /W stays identical).
//   6. QRawFont::glyphIndexesForString is UNSHAPED cmap lookup (no joining/ligatures).
//
// Build:  g++ -std=c++17 qt_rtl_probe.cpp -o probe $(pkg-config --cflags --libs Qt6Gui Qt6Core)
// Run:    QT_QPA_PLATFORM=offscreen ./probe <font.ttf>
//
// REQUIRED: QGuiApplication (offscreen) before QFontDatabase::addApplicationFontFromData —
// scratch probes segfault without it. For 1 font unit = 1 device unit, set
// QRawFont pixelSize = unitsPerEm() (same convention as hb_font_set_scale(upem,upem)).
// HarfBuzz ground-truth cross-check: python3 + uharfbuzz (SYSTEM python, not the
// execute_code sandbox venv) with hb.BufferClusterLevel.MONOTONE_CHARACTERS.
#include <QGuiApplication>
#include <QFile>
#include <QFontDatabase>
#include <QRawFont>
#include <QTextLayout>
#include <QTextLine>
#include <cstdio>

static void dump(const QString& label, const QTextLayout& layout)
{
    fprintf(stderr, "=== %s\n", qPrintable(label)); fflush(stderr);
    for (int li = 0; li < layout.lineCount(); ++li)
    {
        QTextLine line = layout.lineAt(li);
        fprintf(stderr, "line %d textStart %d textLength %d naturalTextWidth %g\n",
                li, line.textStart(), line.textLength(), double(line.naturalTextWidth()));
        const auto runs = line.glyphRuns(); // NOTE: default flags -> stringIndexes() EMPTY
        fprintf(stderr, "  runCount %d\n", int(runs.size()));
        for (const QGlyphRun& run : runs)
        {
            const auto idxs = run.glyphIndexes();
            const auto pos = run.positions();
            const auto sidx = run.stringIndexes();
            fprintf(stderr, "  run: rtl=%d nGlyphs=%d rawFontValid=%d stringIndexesFilled=%d\n",
                    int(run.isRightToLeft()), int(idxs.size()),
                    int(run.rawFont().isValid()), int(!sidx.isEmpty()));
            for (int g = 0; g < idxs.size() && g < 12; ++g)
            {
                double x = pos.value(g).x(), y = pos.value(g).y();
                double adv = (g + 1 < pos.size()) ? pos.value(g + 1).x() - x : 0.0;
                fprintf(stderr, "    g %d gid %u pos %g %g adv %g srcIdx %d\n", g, idxs.value(g),
                        x, y, adv, g < sidx.size() ? int(sidx.value(g)) : -1);
            }
        }
    }
    fflush(stderr);
}

int main(int argc, char** argv)
{
    qputenv("QT_QPA_PLATFORM", "offscreen");
    QGuiApplication app(argc, argv);
    if (argc < 2) { fprintf(stderr, "usage: %s <font.ttf>\n", argv[0]); return 2; }
    QFile f(QString::fromLocal8Bit(argv[1]));
    if (!f.open(QIODevice::ReadOnly)) { fprintf(stderr, "cannot open font\n"); return 1; }
    const QByteArray data = f.readAll();

    const int fid = QFontDatabase::addApplicationFontFromData(data);
    const QString fam = QFontDatabase::applicationFontFamilies(fid).value(0);
    fprintf(stderr, "family: %s\n", qPrintable(fam));
    QFont font(fam, 12);

    auto shape = [&](const char* utf8, Qt::LayoutDirection dir) {
        QTextLayout layout(QString::fromUtf8(utf8), font);
        QTextOption opt; opt.setTextDirection(dir); layout.setTextOption(opt);
        layout.beginLayout();
        QTextLine line = layout.createLine(); line.setLineWidth(10000); layout.endLayout();
        dump(QString::fromUtf8(utf8) + (dir == Qt::RightToLeft ? " (base RTL)" : " (auto)"), layout);
    };
    shape("سلام", Qt::RightToLeft);      // pure RTL word
    shape("مَا", Qt::RightToLeft);       // fatha mark: watch for y displacement in pos
    shape("abc سلام def", Qt::LeftToRight); // mixed: runs must be visual L->R

    QRawFont raw;
    raw.loadFromData(data, 12.0, QFont::PreferNoHinting);
    fprintf(stderr, "=== QRawFont: upem %g valid %d ascent %g descent %g\n",
            double(raw.unitsPerEm()), int(raw.isValid()), double(raw.ascent()), double(raw.descent()));
    const QList<quint32> gids = raw.glyphIndexesForString(QString::fromUtf8("سلام"));
    fprintf(stderr, "glyphIndexesForString(سلام) UNSHAPED (%d):", int(gids.size()));
    for (quint32 g : gids) fprintf(stderr, " %u", g);
    fprintf(stderr, "  <- compare vs shaped GIDs above\n");
    const QList<QPointF> advs = raw.advancesForGlyphIndexes(gids);
    for (int i = 0; i < gids.size(); ++i)
        fprintf(stderr, "  gid %u hmtx advance %g px = %g font-units\n", gids[i],
                double(advs[i].x()), double(advs[i].x()) * 1000.0 / 12.0);
    const QList<quint32> mark = raw.glyphIndexesForString(QString::fromUtf8("\xD9\x8E")); // fatha
    if (!mark.isEmpty())
        fprintf(stderr, "fatha gid %u boundingRect %s (ink-above-origin check)\n", mark.first(),
                qPrintable(raw.boundingRect(mark.first()).toString()));
    return 0;
}
