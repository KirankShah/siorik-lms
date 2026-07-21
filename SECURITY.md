# Security Review — Bank LMS

This document summarizes a security pass across the backend (Django + DRF) and
frontend (React), what changed, why, and what's still a known limitation.

## 1. HTTPS-only cookies and transport security (production)

`backend/core/settings.py` — a new block runs only when `DEBUG=False`:

- `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True` — session/CSRF
  cookies (used by the Django admin and the DRF browsable API session login;
  the React app itself uses JWTs, not cookies) are never sent over plain HTTP.
- `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = 'Lax'`,
  `CSRF_COOKIE_SAMESITE = 'Lax'`.
- `SECURE_SSL_REDIRECT = True` — forces HTTP → HTTPS redirect.
- `SECURE_HSTS_SECONDS = 2592000` (30 days) + `SECURE_HSTS_INCLUDE_SUBDOMAINS`
  + `SECURE_HSTS_PRELOAD` — browsers refuse to fall back to HTTP once they've
  seen the header once. Start at 30 days and raise it once the HTTPS rollout
  is confirmed stable (a wrong HSTS setting is hard to undo for users who've
  already cached it).
- `SECURE_PROXY_SSL_HEADER` — trusts `X-Forwarded-Proto` from the reverse
  proxy/load balancer so Django knows the original request was HTTPS even
  though the proxy talks plain HTTP to the app server. **Only correct if your
  proxy actually sets this header and strips any client-supplied one** —
  otherwise this becomes a spoofing vector.
- `SECURE_CONTENT_TYPE_NOSNIFF = True`, `SECURE_BROWSER_XSS_FILTER = True`.

All of this is skipped under `DEBUG=True` so local `http://localhost` dev
keeps working. `ALLOWED_HOSTS` is now read from the `ALLOWED_HOSTS` env var
(comma-separated) instead of being hardcoded — it defaults to empty, which
Django only auto-permits for `localhost`/`127.0.0.1` while `DEBUG=True`; a
production deploy **must** set this or every request will be rejected
(fail-closed, by design).

Also added: `CSRF_TRUSTED_ORIGINS`, sourced from the same origins as the CORS
allowlist below — required by Django for cross-origin POSTs (admin,
browsable API) once served over HTTPS with a real domain.

## 2. Rate limiting

`backend/core/settings.py` `REST_FRAMEWORK`:

```python
'DEFAULT_THROTTLE_CLASSES': ('rest_framework.throttling.ScopedRateThrottle',),
'DEFAULT_THROTTLE_RATES': {'login': '10/min', 'quiz-submit': '20/min'},
```

`ScopedRateThrottle` only throttles a view that declares a `throttle_scope` —
every other view is unaffected (confirmed: `SimpleRateThrottle.allow_request`
returns `True` immediately when `throttle_scope` isn't set), so this is safe
to set as the global default without touching unrelated endpoints.

- **Login** (`accounts/views.py: ThrottledTokenObtainPairView`): a thin
  subclass of simplejwt's `TokenObtainPairView` with
  `throttle_scope = 'login'`. Wired in at `accounts/urls.py`. Brute-force
  defense — 10 attempts/minute per client IP (anonymous requests are keyed by
  IP; see the residual-risk note below).
- **Quiz submit** (`assessments/views.py: QuizViewSet.submit`): the `@action`
  decorator now passes `throttle_classes=[ScopedRateThrottle],
  throttle_scope='quiz-submit'`. 20 attempts/minute per authenticated user.
  (Note: `QuizViewSet` needed an explicit `throttle_scope = None` class
  attribute added — DRF's router validates `@action` kwargs via `hasattr()`
  at URL-registration time, and `throttle_scope` isn't a `APIView` default
  attribute the way `permission_classes` is, so it needs to exist somewhere
  in the class before the per-action override can apply.)

**Verified live**: hammered `/api/auth/login/` 12x — first 10 returned 401,
11th and 12th returned 429. Hammered `/api/quizzes/<id>/submit/` 22x — first
20 returned 201, remainder returned 429.

**Residual risk / known limitation**: the throttle cache is Django's default
(`LocMemCache` — in-process memory) unless a `CACHES` backend is configured.
That's fine for a single-process dev server, but in a multi-worker/multi-
instance production deployment each process has its own counter, so the
*effective* rate limit is `configured_rate × worker_count`. Point `CACHES` at
a shared backend (Redis/Memcached) before relying on this for real abuse
protection in production.

## 3. Input validation on upload/text fields

| Field | Model | Validation added |
|---|---|---|
| `Lesson.content_file` | `courses` | *(already present)* size cap + extension allowlist per `lesson_type` in `Lesson.clean()`, called explicitly from `LessonWriteSerializer.validate()` since `ModelSerializer` doesn't call `full_clean()` automatically |
| `Organization.logo` | `accounts` | **new**: `validate_image_size` (5MB cap) — Pillow (via `ImageField`) already rejects non-image content regardless of extension |
| `Course.cover_image` | `courses` | **new**: same 5MB `validate_image_size` |
| `User.phone_number` | `accounts` | **new**: `validate_phone_number` (regex — digits, spaces, `+`, `-`, parentheses, 7–20 chars) |
| `Course.description` | `courses` | **new**: `MaxLengthValidator(10_000)` — was an unbounded `TextField` |
| `Question.question_text` | `assessments` | **new**: `MaxLengthValidator(5_000)` — was an unbounded `TextField` |
| `Lesson.content_url` | `courses` | *(already present)* Django's built-in `URLField` validator |
| All `CharField`s (titles, slugs, choice text, etc.) | all apps | *(already present)* bounded `max_length` |
| Enrollment report CSV export | `courses/views.py: EnrollmentReportView` | **new**: `_csv_safe()` prefixes any cell starting with `=`, `+`, `-`, or `@` with a `'` — prevents CSV/formula-injection (a malicious `first_name` like `=HYPERLINK(...)` executing when the export is opened in Excel) |
| Bulk-enroll CSV upload | `courses/views.py: CourseViewSet.bulk_enroll` | *(already present)* parsed via `csv.reader`, never `eval`/`exec`; tolerant of a header row (skips any cell without `@`) |

New model field migrations: `accounts/migrations/0002_...`,
`courses/migrations/0004_...`, `assessments/migrations/0002_...`.

**Known limitation**: file-type validation is extension-based (plus Pillow's
real-image-content check for images). A `.pdf`-named file containing embedded
HTML/JS isn't independently verified against its magic bytes for non-image
uploads (`Lesson.content_file`). Mitigated by: (a) `SECURE_CONTENT_TYPE_NOSNIFF`
forcing browsers not to sniff-and-execute a different content type than what's
served, and (b) the extension allowlist itself. A deeper fix (e.g.
`python-magic` signature checks) was left out of this pass — it needs
`libmagic`, which complicates Windows dev-environment portability — but is a
reasonable next step before handling untrusted uploads at scale.

## 4. Explicit `permission_classes` on every view

An audit of every DRF view/route (`accounts`, `courses`, `assessments`,
`certificates`, plus `core/urls.py`) found **no accidental anonymous access**
— the global `DEFAULT_PERMISSION_CLASSES = (IsAuthenticated,)` was already
catching everything. Three views relied on that implicit default rather than
declaring it themselves:

- `accounts/views.py: MeView` → now `permission_classes = [IsAuthenticated]`
- `courses/views.py: EnrollmentViewSet` → now `permission_classes =
  [IsAuthenticated]`, with a comment explaining why it's deliberately *not*
  `IsAdminRole` (learners must be able to self-enroll and mark their own
  lesson progress; `RoleScopedQuerysetMixin` already restricts which rows
  they can see/touch)
- `certificates/views.py: CertificateViewSet` → now `permission_classes =
  [IsAuthenticated]`

The only two intentionally public endpoints in the entire backend:

- `GET /verify/<uuid:token>/` (`certificates/views.py: verify_certificate`) —
  a plain Django view (not DRF), documented in-line as intentionally public.
  Looks up a certificate by its opaque UUID token and returns only
  non-sensitive summary fields (never the PDF, never internal IDs) — this is
  the "share this link so an employer can verify it" endpoint.
- `POST /api/auth/login/` and `POST /api/auth/refresh/` — must be public to
  issue/refresh tokens in the first place; simplejwt already declares
  `permission_classes = ()` on these explicitly (not relying on our global
  default), and login is now also throttled (see §2).

## 5. CORS allowlist

`backend/core/settings.py`:

```python
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = <CORS_ALLOWED_ORIGINS env, comma-separated> or [local Vite dev ports]
```

`CORS_ALLOW_ALL_ORIGINS` is explicitly set to `False` (defense in depth —
it's django-cors-headers' own default, but a wildcard here is exactly the
kind of thing that gets silently flipped on during debugging and forgotten).
Production origins come from the `CORS_ALLOWED_ORIGINS` env var; local dev
falls back to `http://localhost:5173`/`5174`. `CSRF_TRUSTED_ORIGINS` reuses
the same env-driven list (see §1).

## 6. `AuditLog` model

New `audit` app — `AuditLog(user, action, object_type, object_id, timestamp)`,
`user` nullable (`SET_NULL`) so a deleted user's history isn't lost, `action`
a bounded `TextChoices` set. A single `log_action(user, action, obj)` helper
in `audit/services.py` is the one call site every trigger uses, so the
recording logic itself isn't duplicated. Registered read-only in the Django
admin (`has_add_permission`/`has_change_permission` return `False` — logs are
observed, not edited).

Triggered on exactly the four events requested:

| Action | Where | Note |
|---|---|---|
| `LOGIN` | `accounts/views.py: ThrottledTokenObtainPairView.post` | Only on a *successful* login — verified a failed attempt does **not** create a log row |
| `COURSE_CREATED` | `courses/views.py: CourseViewSet.perform_create` | |
| `CERTIFICATE_GENERATED` | `certificates/services.py: generate_certificate` | Only on actual creation, not on the idempotent "return the existing still-valid certificate" path |
| `ENROLLMENT_CREATED` / `ENROLLMENT_UPDATED` | `courses/views.py: EnrollmentViewSet.perform_create` / `perform_update` / `complete_lesson` | Covers self-enrollment, a `PATCH` status/progress change, and the lesson-completion flow |

**Verified live** end-to-end (real HTTP requests, not just unit tests): login
→ 1 `LOGIN` row; course creation → 1 `COURSE_CREATED` row; enroll + patch →
`ENROLLMENT_CREATED` + `ENROLLMENT_UPDATED` rows; certificate issue →
`CERTIFICATE_GENERATED` row. Also covered by 5 new automated tests in
`test_api_flows.py::AuditLogTests`.

**Known limitation**: audit logging isn't yet wired into Module/Lesson/Quiz
CRUD or certificate downloads/revocation — only the four events explicitly
in scope for this pass. Extending `log_action()` calls to those is
straightforward if broader coverage is wanted later.

## 7. Frontend

No `dangerouslySetInnerHTML`/raw-HTML injection points exist anywhere in
`frontend/src` (grepped and confirmed) — React's default JSX escaping covers
all user-supplied text (course descriptions, question text, learner names,
etc.).

JWTs are kept in `localStorage` (this was flagged with its own tradeoff
comment when auth was first built — XSS exposure vs. simplicity; see
`frontend/src/lib/tokenStorage.ts`). The backend's HTTPS/cookie hardening in
§1 governs the Django session/CSRF cookies (admin + browsable API only) and
is independent of this — the JWT flow doesn't use cookies at all, so those
settings don't change frontend behavior.

`VITE_API_BASE_URL` defaults to `http://localhost:8000/api` for local dev
only (`frontend/src/lib/apiClient.ts` fallback); a production build must set
this env var to an `https://` URL — there is no code path that hardcodes an
insecure production URL.

## Summary of files changed

- `backend/core/settings.py` — HTTPS/cookie hardening, `ALLOWED_HOSTS` +
  `CORS_ALLOWED_ORIGINS` + `CSRF_TRUSTED_ORIGINS` env-driven, throttle config,
  `audit` app registration
- `backend/audit/` — new app (`models.py`, `services.py`, `admin.py`,
  migration)
- `backend/accounts/views.py` — `ThrottledTokenObtainPairView`, explicit
  `permission_classes` on `MeView`
- `backend/accounts/urls.py` — use the throttled login view
- `backend/accounts/models.py`, `accounts/validators.py` — phone number regex,
  image size validator
- `backend/courses/models.py` — cover image size validator, description
  length cap
- `backend/courses/views.py` — course/enrollment audit logging, CSV
  formula-injection guard, explicit `EnrollmentViewSet` permissions
- `backend/assessments/models.py` — question text length cap
- `backend/assessments/views.py` — quiz-submit throttle scope
- `backend/certificates/views.py` — explicit `CertificateViewSet`
  permissions, public-endpoint doc comment
- `backend/certificates/services.py` — certificate-generation audit logging
- `backend/.env`, `backend/.env.example` — new `ALLOWED_HOSTS`,
  `CORS_ALLOWED_ORIGINS` variables
- `backend/test_api_flows.py` — 12 new tests (rate limiting ×2, audit
  logging ×5, CSV injection ×1, plus assertions folded into existing tests)
- New migrations: `accounts/0002`, `courses/0004`, `assessments/0002`,
  `audit/0001`
