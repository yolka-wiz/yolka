---
name: open-source-triage
description: "Systematic codebase archaeology and fix design for unfamiliar open-source projects — read, trace, build, document, and design a fix without writing code."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [oss, triage, codebase-archaeology, upstream, fix-design, research]
    related_skills: [systematic-debugging, plan, spike, github-pr-workflow]
---

# Open-Source Triage

## When to Use

Use this skill when given a task that involves **understanding an unfamiliar open-source project** to design a fix — without necessarily writing the fix code yet. Signals:

- Bug report with reproduction steps, the user wants you to understand the codebase and design the approach
- A detailed research plan is provided (markdown with architecture tables, phases, prior art)
- Task says "research" or "analyze" or "investigate" before "implement"
- You need to trace a feature or bug through multiple architectural layers in an unfamiliar codebase
- You're preparing to contribute upstream (the fix will be submitted as a PR/MR)

**Do NOT use this for:** debugging code you already know well (use `systematic-debugging`), throwaway feasibility experiments (use `spike`), or implementing a well-understood fix (use `test-driven-development` + `github-pr-workflow`).

## Core Method

```
read context → understand architecture → set up build → trace data flow → build & test → document findings → design fix
```

Each step builds on the previous one. Do not skip steps.

---

## Step 1: Read and Understand the Context

Start with whatever the user provides — a bug report, a research plan, a feature request. Extract the key facts before touching any code:

- **What breaks?** (exact symptom, steps to reproduce)
- **Who uses it?** (target users, locale, use case)
- **What's the fix scope?** (what files/areas are expected to change)
- **Prior art?** (previous MRs/PRs, attempted fixes, related commits)
- **Success criteria?** (what passing means)

If nothing is provided, ask. Do not start cloning repos until you know where to look.

## Step 2: Map the Architecture

Before reading source code, build a mental model of the architecture. Look for:

- **Component table** — what are the major modules and how do they relate?
- **Data flow direction** — what calls what? What data moves between layers?
- **Plugin/generator pattern** — many OSS projects use modular backends (e.g., Okular's generators for PDF/DJVU/EPUB)

Use the project's README, docs, and directory structure:

```bash
ls -la src/        # top-level modules
ls -la plugins/    # plugin patterns
cat README.md      # project overview
```

**Key question:** which component does the bug live in? If there's a plugin/generator architecture, the fix likely lives in one specific plugin, not the core.

## Step 3: Set Up the Build Environment

### Choose the right machine

- **Prefer a Linux/macOS machine** for C++/Qt projects (Windows builds for KDE are painful — require WSL2, Craft, or MSYS2)
- **Use a remote server** if one is available and the local machine isn't suitable
- **Check SSH access** before cloning anything

### Install build dependencies

Check systematically:

```bash
cmake --version
pkg-config --modversion poppler-qt6  # or whatever the project uses
dpkg -l | grep -iE 'kf6|qt6|poppler|fribidi|harfbuzz'
g++ --version
```

For missing packages:

```bash
sudo apt-get install -y cmake extra-cmake-modules qt6-base-dev \
  libpoppler-qt6-dev libkf6coreaddons-dev [etc.]
```

**Pitfall:** Many KDE/Qt packages list OPTIONAL features as REQUIRED in CMakeLists.txt. Use `-DFORCE_NOT_REQUIRED_DEPENDENCIES='Pkg1;Pkg2'` to skip what you don't need instead of installing every optional dep. Check CMakeLists.txt for the variable name.

**Pitfall:** SUDO_PASSWORD in the Hermes .env only works for **local** sudo, not for sudo inside an `ssh` session. Set up NOPASSWD sudo on remote machines, or have the user install packages.

### Clone and build just the relevant target

```bash
git clone <repo-url>
cd <repo>
cmake -B build -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON
cmake --build build --target <specific-target> --parallel $(nproc)
```

**Always build only the target you need**, not the whole project (saves significant time on large projects like Okular).

## Step 4: Trace the Data Flow

This is the core investigative work. Systematically trace how data moves from input to output:

### 4a. Find the entry point and exit point

- **Entry point:** where does the input enter the system? (e.g., PDF file → Poppler::Page::textList())
- **Exit point:** where does the output get consumed? (e.g., TextPage::findText(), TextPage::text())
- The bug lives somewhere between these two points.

### 4b. Use grep/search to find key code

```bash
# Find the function creating the output data structure
grep -n 'TextPage\b' generators/poppler/generator_pdf.cpp

# Find BiDi-related code (or confirm absence)
grep -rn 'bidi\|fribidi\|raqm\|harfbuzz' . --include='*.cpp' --include='*.h'

# Find where the core function is called in the pipeline
grep -rn 'correctTextOrder\|setTextPage' core/
```

### 4c. Read the critical functions completely

Read the full functions — not just the signatures. Skimming misses the bug.

```bash
sed -n '1441,1480p' generators/poppler/generator_pdf.cpp  # textPage()
sed -n '1829,1900p' generators/poppler/generator_pdf.cpp  # abstractTextPage()
```

### 4d. Draw the data flow

For each step in the pipeline, note:
- What data structure is produced?
- What order is the data in? (visual/logical, rendered/source)
- Is any processing applied? (normalization, reordering, filtering)
- Where could RTL/BiDi/script-specific handling be inserted?

### 4e. Check prior art

```bash
git log --all --oneline --grep='bidi\|rtl\|persian\|arabic\|hebrew' 2>/dev/null
git show <commit-hash> --stat       # check what files changed in a prior fix
git log --all --oneline | head -30  # recent activity
git show <commit-hash>              # view the full prior art diff
```

## Step 5: Build and Run Tests

### Build the test target

```bash
cmake --build build --target <test-name> --parallel $(nproc)
```

### Run tests (headless-friendly)

```bash
# For Qt apps on headless servers
QT_QPA_PLATFORM=offscreen ./build/bin/<test-name>
```

**Pitfall:** Qt tests fail with `could not connect to display` on headless machines. Use `QT_QPA_PLATFORM=offscreen` or `QT_QPA_PLATFORM=minimal`.

### Check for existing related tests

```bash
grep -n 'persian\|arabic\|hebrew\|rtl\|bidi\|RTL\|BiDi' autotests/searchtest.cpp
```

If no tests exist for the bug's domain, that's a finding — new tests will need to be written.

## Step 6: Document Findings

Produce a clear report covering:

- **Architecture model** — the data flow diagram
- **Root cause** — exactly where and why the bug occurs
- **Prior art** — what was tried before and why it didn't work (or what succeeded that's applicable)
- **Fix design** — which files need to change, what library to use, the approach
- **Test plan** — what tests to write and how to run them
- **Risks** — potential blockers (e.g., library not available, upstream bug not fixed)

## Step 7: Present to User

Before moving to implementation, present:
1. Architecture understanding (confirms you're looking at the right place)
2. Root cause finding
3. Proposed fix design
4. Ask: "Proceed to implementation?"

## Pitfalls

1. **Don't build the whole project** — build only the target you need. On large C++ projects, a full build takes 30+ minutes.
2. **KDE/Qt projects have many optional deps marked REQUIRED** — check CMakeLists.txt for `FORCE_NOT_REQUIRED_DEPENDENCIES`.
3. **Headless Qt tests** — always use `QT_QPA_PLATFORM=offscreen`.
4. **SSH sudo** — SUDO_PASSWORD from .env doesn't flow through SSH. Set up NOPASSWD sudo or have the user run install commands.
5. **BiDi/RTL in PDF renderers** — Poppler returns text in visual order for RTL scripts; the application must reorder it using Fribidi or similar. This is a common pattern across PDF tools.
6. **Generator/plugin pattern** — when there are multiple generators (PDF, XPS, DJVU, EPUB), a fix in one generator's BiDi handling doesn't automatically apply to others. Each generator builds its own TextPage independently.
7. **Distinguish text extraction from rendering** — when a bug report mentions multiple symptoms (e.g., "search is broken" AND "annotations look wrong"), check if they're in the same code path. Text extraction (search/copy) and text rendering (display/annotations) are often different code paths. Fix one doesn't fix the other.
8. **Qt6 BiDi detection is built-in** — use `QChar::direction()` (returns `DirR` or `DirAL` for RTL) or `QString::isRightToLeft()` instead of pulling in Fribidi. Qt6 already implements the Unicode BiDi algorithm internally. Only reach for Fribidi if you need Arabic shaping/joining, not just direction detection.
9. **RTL fix location: centralize in core, not per-generator** — when multiple generators (PDF, DJVU, EPUB) share a common TextPage class, applying BiDi reordering in `correctTextOrder()` (called once via `Page::setTextPage()`) fixes all generators simultaneously. Don't patch each generator separately.
10. **Verify LTR safety before implementing RTL fixes** — write a minimal C++ test that calls `containsRTL("Hello World")` → false and `containsRTL("متن")` → true. This proves the fix won't regress existing English/LTR functionality before you touch production code.
11. **Poppler Qt6 backend vs glib backend divergence** — Poppler may fix RTL in the glib backend (TextSelectionDumper) without fixing the Qt6 backend (Page::textList()). Always check which backend your application uses before assuming an upstream fix applies to you.
12. **Test PDFs with RTL text need proper formatting** — When creating test PDFs with fpdf2, characters are stored in LOGICAL order (not visual). For proper RTL testing, need PDFs with characters in VISUAL order (right-to-left). Verify by checking x-coordinates: ascending = LTR visual, descending = RTL visual. See `references/okular-rtl-triage.md` for verification code.
13. **Arabic presentation forms (0xFExx) have joining rules** — Professional PDFs use Unicode presentation forms (INITIAL, FINAL, MEDIAL, ISOLATED) for Arabic text. These forms have specific joining rules. Reversing them directly breaks ligatures. For production fixes, convert to base characters first, reverse, then let font apply correct forms. For text extraction (search/copy), reversing presentation forms works but may affect rendering.
14. **Real PDF testing is essential** — Test PDFs created with fpdf2 may not match real-world PDFs. Always test with a real PDF from the target domain. Compare output with `pdftotext` to verify correctness.
15. **Word grouping may differ between tools** — Poppler and pdftotext may group characters into words differently. This is normal. Focus on verifying individual word correctness rather than exact matching.
16. **Poppler-style BiDi algorithm for mixed LTR/RTL** — For text containing both LTR and RTL characters, reverse only the RTL runs while keeping LTR runs as-is. This algorithm (from Poppler's `reorderText()`) identifies LTR and RTL sections, then reverses only RTL sections to convert from visual to logical order. Use `QChar::direction()` to detect character direction.
17. **Verify fix with pdftotext comparison** — After implementing a BiDi fix, compare the output with `pdftotext` to verify correctness. The first word of a Persian PDF should match between your fix and pdftotext output.

## Related Skills

- **`systematic-debugging`** — use when you need a tight repro loop on a running system
- **`spike`** — use for throwaway feasibility experiments
- **`plan`** — use to write a formal implementation plan after triage
- **`github-pr-workflow`** — use to submit the fix as a PR/MR

## Session References

- `references/okular-rtl-triage.md` — Full triage details for Okular RTL text fix (architecture, prior art, proposed design)
