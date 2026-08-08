# Compile-out recipe — Qt6::TextToSpeech from vendored PDF4QT LibGui

Hit 2026-08-07 during M12 GUI restore. User direction: "patch the
texttospeech library" (chose fork patch over provisioning the module).

## Why

The aqt/Qt-online Qt 6.8.3 prebuilt needs ICU 73 (see qt-cmake-vcpkg-build
pitfall 15), and this box has NO `qt6-texttospeech-dev` — the vendored LibGui
links `Qt6::TextToSpeech` unconditionally, so any configure that includes
LibGui aborts for the WHOLE tree. Two paths: install the module (needs apt
repo access, not in cache) or compile it out (fork divergence, tracked).

## Change set (commit 48d58fd8, 4 files)

### 1. `src/Pdf4QtLibGui/pdftexttospeech.cpp` — no-op stub (511-line rewrite)

- Same class API: constructor, `isValid()`, `setDocument`, `setSettings`,
  `setProxy`, `initializeUI`, all private slots/methods.
- `m_textToSpeech = nullptr`; `isValid() { return false; }` — this makes the
  sidebar Speech page auto-hide via the existing
  `case Speech: return !m_textToSpeech->isValid();` gate in
  `pdfsidebarwidget.cpp` (no UI code change needed to hide it).
- `initializeUI(...)` fills controls in a disabled "Unavailable" state
  (`setEnabled(false)`, label "Text to speech is not available in this build.").
- Header `pdftexttospeech.h` is UNCHANGED: it only forward-declares
  `class QTextToSpeech;` and holds `QTextToSpeech* m_textToSpeech;` — a
  pointer to a forward-declared class compiles without the module.
- Top comment documents the fork divergence + restore-from-upstream note.

### 2. `src/Pdf4QtLibGui/pdfsidebarwidget.cpp` — guard include + call site

```cpp
#include <QPainter>
// albdf: text-to-speech not provisioned (fork divergence, see pdftexttospeech.cpp)
#if defined(QT_TEXTTOSPEECH_LIB)
#include <QTextToSpeech>
#endif
```

Call site (~line 396, `showPage` case Speech):
```cpp
#if defined(QT_TEXTTOSPEECH_LIB)
        QStringList speechEngines = QTextToSpeech::availableEngines();
        ...original two-branch QMessageBox logic...
#else
        Q_UNUSED(ui)
        QMessageBox::critical(this, tr("Error"), tr("Speech feature is unavailable in this build."));
#endif
```

### 3. `src/Pdf4QtLibGui/pdfviewersettingsdialog.cpp` — guard include + 2 sites

- Include guarded same as sidebar.
- Ctor: `m_textToSpeechEngines = QTextToSpeech::availableEngines();` →
  `#if defined(QT_TEXTTOSPEECH_LIB) ... #else m_textToSpeechEngines = QStringList(); #endif`
  (the `for (const QString& engine : m_textToSpeechEngines)` loop later just
  finds nothing — no further guarding needed there).
- `setSpeechEngine(...)` whole body → `#if` original body / `#else`
  `Q_UNUSED(engine) Q_UNUSED(locale)` stub / `#endif`.

### 4. `src/Pdf4QtLibGui/CMakeLists.txt` — drop module from link

```
target_link_libraries(Pdf4QtLibGui PRIVATE Pdf4QtLibCore Pdf4QtLibWidgets
  Qt6::Core Qt6::Gui Qt6::Widgets Qt6::PrintSupport Qt6::Xml Qt6::Svg)
  # albdf: Qt6::TextToSpeech dropped (fork divergence — see pdftexttospeech.cpp)
```

## Verification (before wiring GUI into root CMake)

```bash
grep -rn "#include <QTextToSpeech>" src/Pdf4QtLibGui/   # all inside #if guards
grep -c "#if defined(QT_TEXTTOSPEECH_LIB)" src/Pdf4QtLibGui/pdfsidebarwidget.cpp src/Pdf4QtLibGui/pdfviewersettingsdialog.cpp
# sidebar: 2 (include + call site), settings: 3 (include + ctor + setSpeechEngine)
grep -n "TextToSpeech" src/Pdf4QtLibGui/CMakeLists.txt  # only the albdf comment
```

`QT_TEXTTOSPEECH_LIB` is defined ONLY when the module is linked — so the
guarded code is dead by default and auto-restores if the module is later
provisioned. Guard macro choice matters: `QT_CONFIG(texttospeech)` would NOT
work for an add-on module absent from the build (qtbase config macro), the
per-module `QT_<MODULE>_LIB` define is the reliable one.

## Gotchas

- The user's OOB message read "0atch the texttospeech library" — a typo for
  "Patch" (leading zero from the OOB marker framing). Context made the intent
  unambiguous: patch the vendored code, don't install the module.
- First patch attempt duplicated the include instead of guarding the original
  (added a second `#include <QTextToSpeech>` inside a guard while the
  unguarded original remained) — after every guard edit, re-grep the file to
  confirm exactly ONE guarded include and no unguarded copy.
- `Q_UNUSED(ui)` needed in the sidebar `#else` branch because `ui` is only
  referenced inside the guarded block.
