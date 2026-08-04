---
name: codebase-architecture-research
description: Deep-dive a codebase for extension points, deps, headless.
---

# Codebase Architecture Research

Use when a task asks to research a foreign (vendor/upstream) codebase to find extension points, write-back paths, dependencies, determinism properties, or headless capability — e.g. "how do I add a new CLI command to X", "can I build Y without the GUI", "document how Z saves".

## Workflow

1. **Orient cheaply.** List the top-level dirs and the module the task names (CLI dir, core lib dir). Read that module's `CMakeLists.txt` and its entry point (`main.cpp`) first — they reveal the target/registration structure immediately.
2. **Find the extension pattern.** Look for a base class + registry: singleton storage, `registerApplication`-style calls from constructors, static per-command instances, and a `getStandardString(Command)`-style dispatch key. Then read ONE concrete command end-to-end (smallest one available) as the skeleton template.
3. **Verify the task's premises BEFORE deep-diving.** If the task asserts a behavior ("trace how an edited text flow is written back"), grep the whole repo for *consumers* of that API first. Premises are often wrong — in PDF4QT the text-flow editor's edited output is consumed only by the audiobook plugin; there is NO write-back path (see references/pdf4qt-architecture.md §2). Report the correction explicitly rather than forcing a trace down a nonexistent path.
4. **Batch independent searches in one turn.** Grep for class/function names (targeted) rather than reading whole files. Multiple `search_files`/`read_file` calls with no interdependencies go in a single assistant turn.
5. **Trace save/write-back paths to the serialization layer.** Find: content-stream parser → editable element model → content-stream builder (how resources/fonts/XObjects get into the page Resources dict) → document builder/modifier → final writer. Note which orchestration lives in GUI plugins vs core (QMessageBox/QGraphicsScene usage marks GUI-only glue; the building blocks may still be core-safe).
6. **Dependencies: enumerate exactly.** CMake target name, linked libraries (and PUBLIC vs PRIVATE), `vcpkg.json` deps, `find_package` calls with REQUIRED flags. Check for existing build options that already do what a fork wants (e.g. `PDF4QT_BUILD_ONLY_CORE_LIBRARY`). Distinguish *build-required* deps from *runtime-optional* ones (blend2d is REQUIRED in CMake but has a QPainter fallback in the rasterizer).
7. **Determinism: check the writer, then the periphery.** Timestamps/random IDs hide in: document writer (trailer `/ID` preserved vs regenerated, date strings), encryption IVs (`QRandomGenerator::securelySeeded`), signature code (`QDateTime::currentDateTime`), and new-blank-document trailer construction. Check each.
8. **Headless: check main() and the platform.** Note the QApplication class used (QGuiApplication needs `QT_QPA_PLATFORM=offscreen` headless), and whether the path under study touches widgets.
9. **Tag every claim.** `[V] verified in source` + `file:line`. Flag anything not fully traced as `[unverified]` explicitly — never let unverified items masquerade as verified.
10. **Write the deliverable INCREMENTALLY.** Dense research sessions can hit tool-iteration caps; the deliverable file was lost once because it was only written at the end. After each major section is traced, append it to the output file.

## Pitfalls

- Task premises about a library's behavior are hypotheses, not facts — find call sites before tracing.
- GUI-plugin code often contains the ONLY working example of a write-back pipeline; the core classes it uses are reusable headless even though the example isn't.
- "Optional" deps: check both CMake REQUIRED status and runtime fallback branches — they disagree.
- Keep findings in a `references/` file under this skill when the research will be reused by an ongoing fork/integration effort, so future sessions don't re-derive them.

## Support files

- `references/pdf4qt-architecture.md` — verified deep-dive of PDF4QT (PdfTool CLI extension pattern, content-stream write-back, font embedding, deps, determinism, headless status) with file:line refs.
