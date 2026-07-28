# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A multi-tenant Learning Management System for compliance/AML training. Django 5 + DRF backend (`/backend`), React + Vite + TypeScript + Tailwind CSS v4 frontend (`/frontend`). Native local setup, no Docker — needs Python 3.11+, Node 20+, and a local PostgreSQL server.

## Commands

### Backend (`/backend`, with `venv` activated)

```powershell
venv\Scripts\Activate.ps1          # source venv/bin/activate on macOS/Linux
python manage.py runserver         # http://localhost:8000
python manage.py test              # full suite (also see backend/test_api_flows.py — most
                                    # end-to-end API flow tests live in this one file, not
                                    # spread across per-app tests.py)
python manage.py test assessments.SomeTestCase.test_something   # single test
python manage.py test --keepdb     # reuse the test DB between runs (much faster iteration)
python manage.py makemigrations
python manage.py makemigrations --check --dry-run   # verify no missing migrations
python manage.py check
```

### Frontend (`/frontend`)

```powershell
npm run dev       # http://localhost:5173, proxies API calls to VITE_API_BASE_URL
npm run build      # tsc -b && vite build — the tsc project-build step catches some
                    # cross-file type errors that `tsc --noEmit` alone misses
npm run lint        # oxlint (not eslint — there is no eslint.config.js)
npm run preview
npx tsc --noEmit    # fast typecheck without a full build
```

Run both dev servers side by side in separate terminals; the frontend proxies to the backend via `VITE_API_BASE_URL` (`frontend/.env`, defaults to `http://localhost:8000/api`).

## Architecture

### Content hierarchy

`Course → Module → Lesson → Slide`. A `Slide` has a `slide_type` (`CONTENT`, `QUIZ`, `ASSIGNMENT`, `SCENARIO`) and is otherwise a pure metadata/ordering row — **it has no type-specific payload field itself**. Each slide type's content lives in a separate model/app with its own FK back to `Slide`, and is fetched by the frontend as a **separate follow-up request** filtered by `?slide=<id>`, never nested inside the Slide serializer:

- `CONTENT` → `courses.Element` (rich text/image/video/embed/etc. blocks, ordered, many per slide). `Element.save()`/`delete()` auto-write a `SlideRevision` snapshot (`courses.models.Slide.snapshot_elements`) — CONTENT-only versioning, not shared by other slide types.
- `QUIZ` → `assessments` app: `Quiz` (plain FK to Slide, treated as 0-or-1 in practice) → `Question` → `Choice`. One `Choice` row is reused across question types with different meaning per type (documented in `Choice`'s own docstring) rather than one table per question type. Question types: SINGLE_CHOICE, MULTIPLE_CHOICE, MULTIPLE_ANSWER, TRUE_FALSE, FILL_BLANK, MATCHING, ORDERING, CATEGORIZE, HOTSPOT, SHORT_ANSWER, ESSAY. Matching/Categorize/Hotspot each also have their own small supporting models (`Choice.match_text`, `CategoryBucket`/`CategorizeItem`, `HotspotRegion`) — see `assessments/models.py` docstrings and `assessments/serializers.py` for how each type's answer-key fields are stripped from the API for learners and only revealed once an attempt exists.
- `ASSIGNMENT` → `assignments` app: `Assignment` (**OneToOne** to Slide, strictly one per slide) + `AssignmentSubmission`.
- `SCENARIO` → `scenarios` app: `ScenarioNode` (FK to Slide, rich-text prompt, `node_key` unique per slide, `is_start` marks the entry point) → `ScenarioChoice` (`next_node` FK nullable — null ends the scenario) → `ScenarioAttempt` (records the path taken, for reporting). Authoring UI is a capped flat list, not a graph canvas.

Quiz grading (`assessments.views.QuizViewSet.submit`) is mostly generic set-equality (`selected_ids == correct_choice_ids`) shared across question types, with two scoped exceptions where set equality can't express the answer: ORDERING compares the submitted sequence positionally, and MATCHING relies on the frontend only submitting a pairing's id once it's self-consistently correct (see the long comment in that method for the reasoning — this is a real architectural constraint, not an oversight).

### Progress tracking is slide-type-agnostic and frontend-driven

`courses.models.SlideProgress` (enrollment FK, slide FK, `time_spent_seconds`, `completed_at`) has no per-type payload and no `mark_complete()` method. Completion is set imperatively by **one shared endpoint**: `POST /api/enrollments/<id>/slide-progress/` (`courses.views.EnrollmentViewSet.slide_progress`), driven entirely by whether the caller sends `completed: true`. Neither `assessments`, `assignments`, nor `scenarios` ever write to `SlideProgress` themselves — grading/submission in those apps is fully decoupled from progress. On the frontend, `components/player/SlidePlayer.tsx` owns the dwell timer and is the single choke point that calls this endpoint: CONTENT slides auto-complete once a dwell-time threshold (`Slide.estimated_minutes`) is met; QUIZ/ASSIGNMENT/SCENARIO slides only complete when their type-specific player calls the `onSubmitted` callback it's passed. Any new slide type should follow this same pattern rather than inventing new progress plumbing.

### Multi-tenant authorization

Two roles-and-organization-aware helper functions in `courses/permissions.py` — `visible_courses_for_user(user)` and `editable_courses_for_user(user)` — are the authorization backbone used by nearly every ViewSet across `courses`, `assessments`, `assignments`, and `scenarios` (queryset filtering is always `...course__in=editable_courses_for_user(request.user)` or `visible_courses_for_user(...)`, chosen per-action). `Course.content_owner` is `PLATFORM` or `ORGANIZATION`; an org can see platform-owned courses only via an explicit `CourseAccess` grant, and can never edit them. `accounts.User.Role` is `LEARNER` / `INSTRUCTOR` / `ORG_ADMIN` / `PLATFORM_ADMIN` — `core.permissions.IsAdminRole`/`ADMIN_ROLES` gates everything but LEARNER. When adding a new content-owning app, mirror this exact `editable_courses_for_user`/`visible_courses_for_user` scoping rather than rolling new logic.

### Auth

JWT via `rest_framework_simplejwt` (`DEFAULT_AUTHENTICATION_CLASSES` also includes `SessionAuthentication` for the Django admin/browsable API). Access tokens are short-lived (30 min) with rotating refresh tokens (7 days) — see `SIMPLE_JWT` in `backend/core/settings.py`.

### Frontend conventions

- `frontend/src/components/admin/` — instructor authoring UI. `frontend/src/components/player/` — learner-facing slide player. Plain `frontend/src/components/` holds shared/type-specific interactive widgets (e.g. `QuizPlayer.tsx`, `MatchingAnswer.tsx`, `ScenarioPlayer.tsx`).
- `frontend/src/lib/*Api.ts` — one file per backend app, thin wrappers around `apiFetch` (`lib/apiClient.ts`). Convention: `fetchXForSlide(slideId)` (GET `?slide=`, `[0] ?? null` for 0-or-1 relationships), `createX`/`updateX` (conditionally build `FormData` when an optional file field is a `File` instance, otherwise send plain JSON — `apiClient.ts` auto-detects `body instanceof FormData` to skip setting `Content-Type`).
- `frontend/src/types/*.ts` — one file per backend app's serialized shapes, generally mirroring the DRF serializer fields 1:1, including doc comments about which fields get stripped for non-privileged roles.
- Drag-and-drop uses `@dnd-kit/core` + `@dnd-kit/sortable` throughout. Convention: a single `PointerSensor` with `activationConstraint: { distance: 4 }`, `closestCenter` collision detection, no `KeyboardSensor`. Plain list reordering (module/lesson/slide/element/choice lists) uses `SortableContext`/`useSortable`/`arrayMove` with no `DragOverlay` — the dragged item just gets `opacity: 0.5` in place. Cross-container drag (dragging an item *into* a distinct drop target, e.g. `MatchingAnswer.tsx`, `CategorizeAnswer.tsx`, `HotspotEditor`) uses plain `useDraggable`/`useDroppable` with a `DragOverlay`, since that's a different interaction pattern from in-place reordering.
- `RichTextField` (`components/admin/RichTextField.tsx`) is a Quill-based **uncontrolled** editor — it only reads `initialHtml` on mount, so every usage needs `key={<record>.id}` to force a remount when switching which record it's editing.
- Tailwind v4, CSS-native theming — no `tailwind.config.js`; brand tokens (`brand-navy`, `brand-navy-light`, `brand-gold`, custom `neutral-50..900` scale, not Tailwind's default slate/gray) are defined via an `@theme` block in `frontend/src/index.css`.

### Answer-key data exposure pattern

Any field that reveals a correct answer before submission (`Choice.is_correct`, `Choice.match_text` for MATCHING, `Choice.order` for ORDERING, `CategorizeItem.correct_bucket`, `HotspotRegion.is_correct`, `ScenarioChoice.is_recommended`, `Question.explanation`/`feedback_correct`/`feedback_incorrect`) is stripped in the serializer's `to_representation` for any request where `request.user.role not in PRIVILEGED_ROLES`, and only re-exposed scoped to a specific already-submitted attempt/answer (e.g. `QuizAnswerSerializer.correct_choice_ids`/`correct_order`/`correct_placements`/`correct_region_ids`). When adding a new gradable question/interaction type, follow this same strip-then-reveal-post-submission shape rather than inventing a new one.
