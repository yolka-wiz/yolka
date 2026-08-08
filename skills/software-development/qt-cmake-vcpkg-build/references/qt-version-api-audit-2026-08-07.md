# Qt-version API-compatibility audit — header token sweep (2026-08-07)

Used to answer: "does this vendored/foreign Qt code compile on Qt 6.8.2 when
upstream demands Qt 6.9+?" (albdf M12 WS2: PDF4QT v1.6.0.0 GUI layers vs
Debian system Qt 6.8.2). No build required; ran in seconds.

## Why not the obvious approaches

- **README/upstream claim** ("Download Qt 6.9 or higher") over-states risk:
  the code can be fully 6.8-compatible (it was).
- **Curated grep list from memory** misses APIs AND produces false alarms
  (e.g. `QComboBox::setPlaceholderText` was *suspected* 6.9-only; it is
  Qt 5.15, and the hit was a QLineEdit subclass anyway).

## The sweep (Python, stdlib only)

```python
import subprocess, re, os, collections

REPO = "<target-dir>"            # e.g. .../al-bdf-engine/src
GUIS = ["<dirs...>"]             # e.g. Pdf4QtLibGui, Pdf4QtLibWidgets, ...
QTINC = "/usr/include/x86_64-linux-gnu/qt6"   # triplet on Debian/Ubuntu amd64

# 1. all source files in target dirs
files = []
for g in GUIS:
    for root, _, fnames in os.walk(os.path.join(REPO, g)):
        for f in fnames:
            if f.endswith((".cpp", ".h")):
                files.append(os.path.join(root, f))

# 2. all QClass::method tokens used
tokens = set()
for f in files:
    txt = open(f, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r"\bQ([A-Z][A-Za-z0-9_]*?)::([a-zA-Z_][a-zA-Z0-9_]*)\b", txt):
        tokens.add((m.group(1), m.group(2)))

# 3. index EVERY identifier found in the installed Qt headers
method_index = collections.defaultdict(set)
for root, _, fnames in os.walk(QTINC):
    for f in fnames:
        if f.endswith(".h"):
            txt = open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
            for m in re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", txt):
                method_index[m.group(1)].add(f)

# 4. missing = real candidates (module-wide index resolves inherited methods)
missing = [(c, m) for c, m in sorted(tokens) if m not in method_index]
```

Result: **400 unique tokens → 3 missing** — `QTextToSpeech::availableEngines`,
`QVoice::ageName`, `QVoice::genderName`. All three are the TextToSpeech
MODULE (separate `qt6-speech-dev` package, deliberately not installed), NOT
Qt-6.9-version additions (the class exists in 6.8). All usage sites were
already behind `#if defined(QT_TEXTTOSPEECH_LIB)` compile-out guards.

## Qt 6.9-only members worth grepping by name (verified absent from 6.8.2 headers)

| API | since | 6.8.2 header? |
|---|---|---|
| `QColorSpace::primaryPoints()` | 6.9 | NO |
| `QColorSpace::TransferFunction::PerceptualQuantizer` | 6.9 | NO |
| `QColorSpace::TransferFunction::HybridLogGamma` | 6.9 | NO |
| `QColorSpace::Primaries::CinemaGamut` | 6.9 | NO |

Qt 6.8 additions that LOOK new but are fine on 6.8.2: `QColor::fromString`
(6.8), `QDateTime::fromISO8601`/`QDate::fromISO8601` (6.8),
`QImage::convertToColorSpace`/`setColorSpace` (6.4). Quick header check:
`grep -n '<method>' /usr/include/x86_64-linux-gnu/qt6/QtGui/qcolor.h`.

## Caveats

- Method-name sweep only. Enum VALUES added in newer Qt (new
  `QKeySequence::StandardKey`, `Qt::WindowType`, `QPainter::CompositionMode`
  members) need a separate spot-check of the values actually used — the ones
  used here (Delete/Cut/Copy/Paste, WA_DeleteOnClose,
  WA_TransparentForMouseEvents) are ancient.
- `.ui` files were checked separately for `<customwidget>` (none) — uic comes
  from the local Qt so unknown properties surface at uic time, not compile.

## Companion findings (same session)

- **Qt CMake guard macro:** `QT_<MODULE>_LIB` is defined as a compile
  definition only while `Qt6::<Module>` is linked → the compile-out switch
  for unprovisioned modules. Guards verified balanced:
  `grep -c '#if defined(QT_TEXTTOSPEECH_LIB)' <file>` → 2/3 per file, all
  `#include <QTextToSpeech>` sites guarded.
- **`.rc` on Linux:** scratch project in /tmp (`add_executable(t main.cpp
  icon.rc)`) — configure AND build succeed; CMake emits no rule without an RC
  compiler, so icon.rc is silently ignored. Not a Linux blocker.
- **`#elif` grep trap:** `grep -E "else"` does NOT match `#elif` → false
  "static_assert(false) in #else branch = Linux blocker" alarm in
  `pdfsendmail.cpp`. The chain was
  `#ifdef Q_OS_WIN ... #elif defined(Q_OS_UNIX) // TODO return false #else
  static_assert(false) #endif` — Q_OS_UNIX is defined on Linux, dead code.
  Grep `#if|#ifdef|#elif|#else|#endif` and read the block before flagging.
- **vcpkg dep audit:** vendored dirs had ZERO `find_package` calls — dep
  surface = core's. Upstream comparison via
  `git show v1.6.0.0:vcpkg.json` → upstream deps == our 9 core deps (ours
  adds harfbuzz + fribidi, the RTL additions). GUI adds only `TBB::tbb`
  (under `if(LINUX_GCC)`, already found by core) and `blend2d::blend2d`
  (already a core dep).
- **Upstream path-prefix trap:** upstream PDF4QT keeps the GUI at repo ROOT
  (`Pdf4QtLibGui/...`), the fork vendors into `src/Pdf4QtLibGui/...` — a
  plain `git diff <tag> -- src/...` shows everything as new. Compare content
  with `git show <tag>:<path> | tr -d '\r' | diff - <local>` (CRLF noise).
