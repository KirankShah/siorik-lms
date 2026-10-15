Attempting to perform the InitializeDefaultDrives operation on the 'FileSystem' provider failed.
# Siorik LMS — contributor guide

## Architecture map

This is a two-part monorepo. `backend/` is Django 5 and Django REST Framework; `frontend/` is a React 19, Vite, TypeScript SPA. They communicate through JSON APIs under `/api/`. The backend uses PostgreSQL by default and has a MySQL option for the hosting environment. There is no Docker workflow.

### Backend modules

- `core/` — settings, root URL routing, JWT/session API defaults, shared role permissions, and subscription middleware.
- `accounts/` — custom `User` and `Organization` models, role-based login, password flows, user provisioning/imports, and queued staff invitations.
- `org_settings/` — organization-level subscription dates, active learner seat caps, quiz attempt caps, and pass thresholds.
- `courses/` — course curriculum (`Course → Module → Lesson → Slide`), content elements, enrollments, slide progress, learning paths, permissions, media/video endpoints, and reporting.
- `assessments/` — quizzes, questions, answer choices, attempts, grading, answer-key filtering, and quiz feedback.
- `assignments/` — assignment prompts and learner submissions; one assignment per slide.
- `scenarios/` — branching scenario nodes, choices, and attempts.
- `levelassessments/` — placement assessments, learner attempts, level assignment, and the assessment gates used by learning paths.
- `certificates/` — certificate eligibility and issuance, templates, PDF rendering, and public token-based verification.
- `gamification/` — badges, learner awards, leaderboard records, and score recalculation.
- `audit/` — audit events and the shared logging helper.
- `dialogue/` — reusable characters and scenes for course interactions.
- `narration/` — slide narration data and generation integrations.
- `resources/` — downloadable/viewable learning resources.
- Each app owns its models, migrations, serializers, views, URL configuration, and related services or permissions. `core/urls.py` mounts the app APIs under `/api/`; authentication routes are mounted under `/api/auth/`.

### Frontend modules

- `src/main.tsx`, `App.tsx`, and `routes/` bootstrap the SPA, route users, and gate pages by authentication and role.
- `context/AuthContext.tsx` owns login state, session restoration, and scheduled token refresh. `lib/apiClient.ts` adds bearer tokens, retries after refresh, and handles JSON, multipart, and blob requests. `lib/tokenStorage.ts` stores JWTs.
- `pages/` contains learner pages; `pages/admin/` contains platform, organization, and instructor workflows.
- `components/player/` coordinates course and slide playback; `components/admin/` contains course and content-authoring UI; shared interactive answer widgets live in `components/`.
- `lib/*Api.ts` are app-specific API wrappers; `types/` mirrors serialized API data. Keep endpoint payloads and TypeScript types aligned with DRF serializers.
- `index.css` defines Tailwind v4 theme tokens and shared styles. Vite is configured for the supported older-browser syntax/CSS baseline.

## Dependency map

```text
accounts ───────────────┐
  └─ organization/user  ├─ org_settings (subscription, seats, quiz/pass policy)
                        └─ courses (tenant content, access, enrollments, progress)
                               ├─ assessments (quiz payloads, attempts, grading)
                               ├─ assignments (submission payloads)
                               ├─ scenarios (branching interactions and attempts)
                               ├─ levelassessments (placement and path eligibility)
                               ├─ certificates (eligibility, issuance, PDF)
                               ├─ gamification (progress and achievement totals)
                               ├─ dialogue / narration (course interaction media)
                               └─ resources (learning materials)
audit is called by account, course, and certificate workflows.

frontend routes/pages → app API wrappers → shared apiClient → Django API
frontend player → courses progress endpoint + slide-type API endpoints
```

Course content lives in separate models for each slide type, linked to a `Slide`; slide progress is shared across types. Keep the existing slide type boundaries and API request pattern. `courses/permissions.py` is the canonical place for course visibility/editability scoping. Check `CLAUDE.md` for the detailed content hierarchy and established authoring/player conventions.

## Protected areas: extra care required

- **Authentication and account lifecycle:** `accounts/models.py`, `accounts/views.py`, `accounts/services.py`, `core/settings.py`, and frontend `AuthContext`/`apiClient`/`tokenStorage`. Preserve role checks, token refresh behavior, password-reset protections, and forced-reset rules.
- **Permissions and tenant isolation:** `core/permissions.py`, `courses/permissions.py`, and every DRF view queryset/action. Preserve organization scoping and distinguish platform content visibility from edit rights. Never rely on frontend route hiding as authorization.
- **Subscription and seat limits:** `core/subscription_middleware.py`, `org_settings/`, and `accounts/services.py::ensure_learner_seat_available`. Seat usage includes active learners and the check is transaction/row-lock based; keep every create/reactivate path covered and preserve lock ordering.
- **Certificate issuing:** `certificates/services.py`, certificate views/models, and course/quiz/level completion triggers. Eligibility spans course completion, quiz averages, organization policy, learning-path state, expiry, PDF storage, and audit/gamification side effects. Preserve idempotency and verification behavior.
- **Database migrations:** every app's `migrations/`, especially custom SQL, data migrations, cross-app dependencies, and PostgreSQL/MySQL compatibility. Do not edit an already-applied migration to change history; add a new migration and check both supported engines where practical.
- **Assessment answer confidentiality:** assessment serializers and grading/submission views strip answer keys before submission and expose scoped feedback after submission. Preserve every question type's grading and reveal rules.
- **Uploads and media:** file validators, video chunk upload/streaming, static/media storage settings, and user-provided rich text/URLs need careful validation and access checks.

## Commands

Run from the repository root in PowerShell. Activate the backend virtual environment first when preferred; explicit paths below avoid depending on activation.

```powershell
# Full backend test suite (requires the configured database and PostgreSQL/MySQL service)
cd backend
..\backend\venv\Scripts\python.exe manage.py test --keepdb

# Django checks and migration drift check
..\backend\venv\Scripts\python.exe manage.py check
..\backend\venv\Scripts\python.exe manage.py makemigrations --check --dry-run

# Full frontend test suite
cd ..\frontend
npm test

# Production build (includes TypeScript project build/type checks)
npm run build

# Lint (Oxlint)
npm run lint
```

The repository also documents `python manage.py test`, `npm run dev`, and other workflows in `CLAUDE.md` and `README.md`. `--keepdb` reuses Django's test database; it does not discard or recreate an existing test database.

## Working rules

1. Make the smallest change that fixes the requested behavior. Do not refactor, rename, or broaden scope unless asked.
2. Add a regression test for every behavior fix. Run the focused test, then the relevant full suite; record environment or database limitations accurately.
3. Keep frontend API wrappers/types consistent with backend serializers and preserve tenant/role checks server-side.
4. Treat migrations and data changes as compatibility work. Review migration dependencies and reversibility; never rewrite applied migration history.
5. Do not deploy. Deployment is outside the development task; do not run deployment scripts or publish changes.
6. Do not put secrets, local database credentials, tokens, or learner data into code, logs, or documentation.

## Canonical branch

- `main` is the production deployment branch and the only base for future integration and feature work.
- Create review branches from the intended `origin/main` commit. Do not base new work on `fresh-start`; it is obsolete and must not be merged into `main`.

