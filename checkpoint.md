# checkpoint

- updated: 2026-10-10 20:20 local
- session: shipped PGExtension (e7c00a2) and pypostgres[timescale] (4c89e11..c671c46), tagged v0.0.2, verified integration on tsdb
- version: 0.0.3

## Goal

pypostgres[timescale] is shipped and tagged v0.0.2; integration tests verified against TimescaleDB 2.30.2 on branch `timescale-integration-tests`. Nothing open beyond the pyproject decision below.

## Todo

<!-- Owned by the orchestrator. One task per agent. -->
<!-- [ ] open   [~] in progress   [!] blocked -->

- [x] pg-extension feature, version 1 — worktree pg-ext-v1, mimo-v2.6-flash-free: unit 49 ✓, integration 23 ✓, full 72 ✓
- [x] pg-extension feature, version 2 — worktree pg-ext-v2, ling-3.1-flash-free: unit 48 ✓, integration 23 ✓, full 71 ✓
- [x] pg-extension feature, version 3 — worktree pg-ext-v3, step-5-preview-free: unit 49 ✓, integration not run
- [x] Chose v1, applied to main checkout uncommitted (README comment fixed 1.6 → 1.0), verified 49 + 23 green
- [x] Committed as e7c00a2 (6 files); pg-ext-v1/v2/v3 worktrees + branches removed (losing diffs kept at /tmp/opencode/pg-ext-v2.patch, pg-ext-v3.patch); pypostgres-pg container removed
- [x] pypostgres[timescale] feature — implemented inline per plan, commits 4c89e11..05b4cdd + review fixes c671c46; full suite green on TS 2.30.2 (83 passed, 1 skipped); reviews: style (approve-with-nits) + correctness (approve-with-nits) independent, spec/ponytail inline; accepted nits fixed, declined nits rationale in final report
- [ ] decide fate of pyproject WIP swept into 6372f11 (rewrite last commits to exclude, or leave)

## Leftovers

- Decide the fate of pgtable.py, notes.md, tests/todo-*.py (dead code or kept)
- Losing build diffs parked in /tmp/opencode/pg-ext-v2.patch and pg-ext-v3.patch
- Makefile edit uncommitted since before the feature; stopped at "left as WIP"

## Bugs

- inspector.py: partition loop logs `{index_name=}`, NameError when a parent is missing
- inspector.py: dead filter_tables line, hardcoded DSN in __main__, duplicate helper
- create_partitions_monthly steps 31 days, partition bounds drift on short months
- PGUtils.tables is a class-level dict shared across all instances
- pyproject claims requires-python >=3.8; runtime needs 3.10 (`str | None`)
- [all] extra names hammertime, which does not exist; dev deps declared twice

## Concerns

- AGENTS.md was removed from the repo; its Docker recipe is no longer on disk, local socket path used instead
- Integration tests need a tsdb container created per run; `caggtest` is a user-owned container, left running
- Subagent dispatch is degraded: opencode/* free models are rejected, only step-5-preview-free dispatched
- The three pg-ext OpenChamber sessions point at worktree dirs that no longer exist

## Key Facts

- v0.0.2 tagged on df3e1cc; version is dynamic via hatch-vcs, scheme no-guess-dev
- timescale module is flat (src/pypostgres/timescale.py); TimescaleDB(cur) mirrors PGUtils
- TS 2.30 drift: hypertables dropped is_distributed/replication_factor; job_stats.last_start is now last_run_started_at
- uv sync does not install pypostgres; uv pip install -e . does
- checkpoint format is fixed by the /checkpoint command spec (skill-version 0.0.3)
- git add with explicit paths does not protect against a stale index; check git status before commit

## Key files

- src/pypostgres/timescale.py — TimescaleDB facade plus TS* dataclasses
- src/pypostgres/inspector.py — introspection, holds the pg_extension query
- src/pypostgres/models/__init__.py — PGExtension, PGDatabase.extensions
- tests/test-timescale.py, tests/test-psycopg2.py, tests/test-models.py — unit and integration coverage
- docs/superpowers/{specs,plans}/2026-10-10-timescale*.md — design record
- CHANGELOG.md — release notes for v0.0.1 and v0.0.2
- checkpoint.md — this file, holds the orchestrator's task queue

## Time Tracking

| Date       | Task                       | Description                                                  | Memory               | Owner                      | Time |
| ---------- | -------------------------- | ------------------------------------------------------------ | -------------------- | -------------------------- | ---- |
| 2026-10-10 | PGExtension introspection  | 3 parallel builds compared, v1 applied and committed e7c00a2 | memory/2026-10-10.md | Big Pickle + 3 free models | 105  |
| 2026-10-10 | timescale design           | brainstorm, spec, plan, skeleton                             | memory/2026-10-10.md | Big Pickle                 | 30   |
| 2026-10-10 | timescale implementation   | 5 tasks, commits 4c89e11..05b4cdd                            | memory/2026-10-10.md | Big Pickle                 | 15   |
| 2026-10-10 | timescale review and fixes | 2 independent reviews, fixes in c671c46                      | memory/2026-10-10.md | step-5-preview-free ×2     | 30   |
| 2026-10-10 | versioning and changelog   | hatch-vcs, CHANGELOG, tag v0.0.2                             | memory/2026-10-10.md | Big Pickle                 | 15   |
| 2026-10-10 | tsdb integration run       | container recreated, 25 passed / 1 skipped on branch         | memory/2026-10-10.md | Big Pickle                 | 15   |
| 2026-10-10 | checkpoint fix             | corrected time tracker to /checkpoint spec                   | memory/2026-10-10.md | Big Pickle                 | 15   |
