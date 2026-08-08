# QFlags 32-bit overflow — 64-bit flags class fix (albdf, 2026-08-06)

Case study of a fork-made build break and the drop-in replacement that fixed
it, including the ADL shadowing trap that the first fix attempt hit.

## Symptom

```
/usr/include/.../qt6/QtCore/qflags.h:54:33: error: static assertion failed:
QFlags uses an int as storage, so an enum with underlying long long will overflow.
   54 |     static_assert((sizeof(Enum) <= sizeof(int)),
      |                   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      |                   (8 <= 4)
```

Fires in `Q_DECLARE_OPERATORS_FOR_FLAGS(pdftool::PDFToolAbstractApplication::Options)`.

## Root cause

Wave-1 page-ops commit `4402b1c` added three flags to the enum:

```cpp
Sign        = 0x40000000,
Rotate      = 0x80000000,      // bit 31 — last value QFlags int can hold
MovePage    = 0x100000000,     // bit 32 — OVERFLOW
DeletePage  = 0x200000000,     // bit 33 — OVERFLOW
```

`QFlags` is 32-bit-only before Qt 6.9. Both the dev container (Debian 13 apt
Qt 6.8.2) and CI (pins `6.8.*`) reject it. The author's env must have been Qt
≥ 6.9 or the page-ops branch never actually rebuilt on 6.8 — the merge
landed with a build that never compiled on the toolchain.

## Critical diagnosis: the stale baseline

The main checkout's `src/build/bin/albdf` was dated **Aug 5 20:48**; the
breaking commit was **Aug 6**. `ctest` on the stale binary reported 11/11
green — a FALSE baseline. Three parallel subagents all independently hit the
build error, which is what exposed the truth.

Lesson: before trusting "baseline green", compare
`stat -c %y build/bin/<binary>` against `git log -1 --format=%ci HEAD`.
Binary older than the suspect commit = stale; rebuild from clean first.

## The fix: 64-bit Options class

Replace `Q_DECLARE_FLAGS(Options, Option)` + the file-bottom
`Q_DECLARE_OPERATORS_FOR_FLAGS(...)` with a class keeping the QFlags API
surface the CLI actually uses (`testFlag`, `operator|`):

```cpp
class Options
{
public:
    constexpr Options() noexcept = default;
    constexpr Options(Option flag) noexcept : m_flags(static_cast<quint64>(flag)) {}

    constexpr bool testFlag(Option flag) const noexcept
    {
        return (m_flags & static_cast<quint64>(flag)) != 0;
    }
    constexpr bool operator==(const Options& other) const noexcept { return m_flags == other.m_flags; }
    constexpr bool operator!=(const Options& other) const noexcept { return !(*this == other); }
    constexpr Options operator|(Option flag) const noexcept { return Options(m_flags | static_cast<quint64>(flag)); }
    constexpr Options operator|(const Options& other) const noexcept { return Options(m_flags | other.m_flags); }
    constexpr Options& operator|=(Option flag) noexcept { m_flags |= static_cast<quint64>(flag); return *this; }
    constexpr Options& operator|=(const Options& other) noexcept { m_flags |= other.m_flags; return *this; }

private:
    constexpr explicit Options(quint64 flags) noexcept : m_flags(flags) {}
    quint64 m_flags = 0;
};
```

Enum values untouched — this is a drop-in for the ~10 call sites that do
`return ConsoleFormat | OpenDocument | Rotate;` and the two
`optionFlags.testFlag(X)` loops.

## ADL shadowing trap (the fix's own pitfall)

First attempt declared the free operators INSIDE `namespace pdftool`:

```cpp
namespace pdftool {
inline constexpr ...::Options operator|(...::Option left, ...::Option right) { ... }
}
```

Result: the Options fix compiled, but an UNRELATED line broke:

```
pdftooldeletepage.cpp:147:76: error: invalid conversion from 'int' to
'pdf::PDFOptimizer::OptimizationFlag' [-fpermissive]
  147 |  pdf::PDFOptimizer optimizer(pdf::PDFOptimizer::RemoveUnusedObjects | pdf::PDFOptimizer::ShrinkObjectStorage,
```

Why: unqualified lookup from inside `namespace pdftool` finds the FIRST scope
declaring `operator|` and stops. My pdftool-scope `operator|` SHADOWED the
QFlags `operator|` declarations Qt emits at GLOBAL scope (that's where
`Q_DECLARE_OPERATORS_FOR_FLAGS` puts them). So
`PDFOptimizer::A | PDFOptimizer::B` no longer found the QFlags operator and
fell back to built-in `int|int`, which then can't convert to the enum.

Minimal repro (compile both):

```cpp
// global scope: COMPILES
pdf::PDFOptimizer optimizer(pdf::PDFOptimizer::RemoveUnusedObjects |
                            pdf::PDFOptimizer::ShrinkObjectStorage, nullptr);

// inside namespace pdftool: FAILS with int→OptimizationFlag error
namespace pdftool { struct T { int f() { /* same expression */ } }; }
```

## The correct placement

Free operators at **global scope**, fully qualified:

```cpp
// after: } // namespace pdftool
inline constexpr pdftool::PDFToolAbstractApplication::Options operator|(
    pdftool::PDFToolAbstractApplication::Option left,
    pdftool::PDFToolAbstractApplication::Option right)
{
    return pdftool::PDFToolAbstractApplication::Options(left) | right;
}
```

At global scope both coexist: Qt's QFlags operators and our Options operators,
and overload resolution picks the exact match. Comment in the header explains
the WHY so nobody "fixes" it back into the namespace.

## Verification

- Fresh configure + build: `cmake --build build -j$(nproc)` clean
- `QT_QPA_PLATFORM=offscreen ctest --test-dir src/build --output-on-failure`
  → 12/12 green (11 prior + UnitTestsPageOps)
- Commits: `4bb644f` (main), same content propagated to 3 worktrees
  (copied file + committed per-branch — cherry-pick was finicky when the
  worktrees carried the agents' own uncommitted fix variants)

## Follow-up

Recorded the trap in `docs/PROBLEMS.md` (vcpkg/toolchain traps section):
Qt QFlags 32-bit limit + the stale-baseline warning. Also DB task #31 closed
with ref `4bb644f`. All three M10 agents found the same root cause
independently — a strong signal the orchestrator's stale baseline was wrong.
