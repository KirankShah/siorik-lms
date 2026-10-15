# Clean `main` test baseline

Recorded 2026-10-15 from a clean worktree at `origin/main`
(`54b9224a98e38c37533df86cba86ac9811078890`). The local production-style
PostgreSQL settings came from the preserved checkout's untracked `.env`; no
credentials are recorded here.

## Required ignored test fixtures

The clean checkout omits two seeded certificate media files. The existing real
fixtures were copied from the preserved checkout solely to run tests; no
placeholder was created and neither file is committed:

- `backend/media/certificate_templates/backgrounds/certificate_template_clean.png`
  (SHA-256 `1ECB7C75315428700B5E3D7EA7B80E17784A522DF6BC4BBB5A6F3D665DB46FF0`)
- `backend/media/certificates/AlexBrush-Regular.ttf`
  (SHA-256 `AC849CB12F5638019661376C0C6FBA383CD5F138F2971D2F620315ADD9A96694`)

## Results

- Frontend: `npm test` — PASS, 17 files / 74 tests.
- Backend, existing retained test database: `manage.py test --keepdb -v 1` —
  PASS, 543 tests in 861.607 seconds.
- Backend, newly created empty test database: BLOCKED before tests by the
  pre-existing `gamification.0011_recalculate_leaderboard_scores` migration,
  which reads `knowledge_score` before the column exists. Django discovered
  543 tests, then PostgreSQL raised `UndefinedColumn` while applying migrations.

The fresh-database migration failure is part of this base and is not introduced
by either reconciliation branch. Final branch comparisons use the documented
`--keepdb` workflow against the retained test database and report only deltas.

## Current `main` comparison — 2026-10-15

The original 543/74 figures above predate the Periodic Exam commits now on
`origin/main@acc12c1`. The leaderboard review branch was rebased onto that
commit and verified from a newly created database (without `--keepdb`):

- Current `origin/main` comparison: 633 backend tests and 98 frontend tests.
  The backend figure is the review branch's discovered 641 tests minus its
  eight new leaderboard/migration regression tests; frontend test count is
  unchanged by this branch.
- `fix/leaderboard-quiz-average`: PASS, 641 backend tests in 1394.784 seconds;
  PASS, 24 frontend files / 98 tests.
- Frontend lint: PASS with seven pre-existing Fast Refresh warnings.
- Frontend production build/type check: PASS with the existing large-chunk
  advisory.
- `manage.py check` and `makemigrations --check --dry-run`: PASS; no model
  drift.
