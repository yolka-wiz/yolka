---
name: lo-writer-cluster-ops
description: "Run the LO Writer fix cluster: conductor, DBs, standards."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [libreoffice, cluster, conductor, autonomous, writer, sw, agno]
    related_skills: [agno-agent-playground, mcp-server-verification, bug-tracker-triage]
---

# LibreOffice Writer Cluster Ops

Operate the autonomous agent cluster that finds and fixes small problems in
LibreOffice **Writer (sw/)**, crossing into core/editeng/vcl when needed.
Located at `/home/agent/workspace/playground/cluster/`.

## Topology

| Piece | Path / role |
|---|---|
| Conductor | `cluster/conductor.py` — one iteration per run (cron every ~45 min) |
| Tracker | `cluster/tracker.py` — renders `cluster/status.md` + publishes to results repo |
| History DB | `data/cluster_history.db` — tasks/actions/commits/reverts (append-only) |
| Knowledge DB | `data/lo_memory.db` — sql-vec shared memory |
| Standard | `cluster/standards.md` — the formal process (read it first) |
| Read-only clone | `/home/agent/workspace/libreoffice-core` (index source) |
| Writable clone | `/home/agent/workspace/lo-writer` (edits; origin=yolka-wiz/libreoffice-work) |

## Loop (per iteration)

1. `conductor.py` picks next pending task (smallest first).
2. **Upstream check** (searcher): `bugzilla_check` + `gerrit_check` → skip if
   already upstream.
3. **Investigate** (inspector_a): root cause + exact proposal, file:line evidence.
4. **Implement** (inspector_b): branch `writer/<bug-id>-<slug>` in lo-writer,
   smallest change, verify (V0–V3), commit PR-quality, push, back to master.
5. **Record**: conductor writes commit SHA/branch into history DB; task →
   `pr_ready`; tracker updates status.md.
6. Agents publish summaries to the results repo (publish_results tool).

## Key commands

```bash
cd /home/agent/workspace/playground
.venv/bin/python cluster/conductor.py        # one iteration (silent if no task)
.venv/bin/python cluster/tracker.py          # regenerate + publish status
.venv/bin/python scripts/seed_tasks.py       # add queue entries (idempotent)
.venv/bin/python scripts/memory_maintenance.py  # prune duplicates/noise
.venv/bin/python cluster/history_db.py       # DB stats
```

Cron: `hermes cron` job runs the conductor; silent on no-op (empty stdout),
prints a line per task event.

## Verification levels (record on every commit)

- V0 unverified (needs upstream CI — MUST state why)
- V1 static/format validated (xmllint, script, regex)
- V2 script/unit tested
- V3 compiled (module build)

Full LO build = hours; the cluster never runs it. Upstream Gerrit CI is the
final gate — always noted in PR-ready summaries.

## Commit format

```
tdf#<bugid> <summary ≤72 chars>
<what / why / how verified — verification level stated>
```

Only on `writer/*` branches; one problem per branch.

## Pitfalls

- Never edit the read-only index clone — lo-writer only.
- Never touch `workdir/`, `external/`, `config_host/`, `solenv/`.
- History DB is append-only; reverts are recorded, never deleted.
- Agents run as subprocesses (isolation); conductor owns all DB writes.
- If a task has an open/merged Gerrit change → skip (never duplicate upstream).
- Searcher's context7 MCP requires the async `run_searcher` path.
