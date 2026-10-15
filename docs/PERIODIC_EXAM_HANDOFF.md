# Periodic Exam handoff

## Delivered work

| Phase | Commit | Delivered |
|---|---|---|
| Base reconciliation | `b673c07`, `c488602`, `f6b0b5b`, `6172549` | Main-base baseline, reviewed certificate/categorize tests, and fresh-database gamification migration fix. |
| Phase 1 | `60cd2a8` | Settings/cycle schema, verified calendar adapter, on-demand cycles, settings/toggle/availability APIs, platform toggle and org settings UI. |
| Phase 2 | `55ba42f` | Frozen cycle question pools and participant snapshots, readiness API, idempotent materialisation. |
| Phase 3 | `954d596` | Attempt papers, lifetime no-repeat/LRU selection, server-authoritative timer, grading and learner APIs. |
| Phase 4 | `ab478cf` | Learner availability, navigation/card, introduction, exam/resume/timeout flow and score-only result UI. |
| Phase 5 | `c80662c` | Snapshot report API/UI, search/filter/pagination, CSV/XLSX exports and admin readiness display. |
| Phase 6 | `5d86844` | Separate reminder command, delivery ledger, Kathmandu due dates, retryable branded email and dry run. |

Phase 7 adds the scale tests, final design reconciliation and this handoff. Record its final commit hash in the review or release record after commit.

## Manual QA checklist

- [ ] For Lumbini and a second organisation, verify disabled means no learner sidebar/card/routes and no org-admin settings/report links.
- [ ] Enable each test organisation; confirm the first cycle begins only at the next full configured boundary and tenant data never crosses.
- [ ] Verify monthly, quarterly, half-yearly and yearly displayed dates after the Patro checklist is signed.
- [ ] Start an exam and verify one-question display, server countdown, automatic lock/advance/submit, and no previous navigation.
- [ ] Close and reopen the browser; verify the open attempt resumes and elapsed questions catch up exactly once.
- [ ] Start immediately before cycle end; verify it can finish afterward while no new attempt can start after the boundary.
- [ ] Compare two learners and a retake: different randomized papers, unused-in-cycle first, then least-recently-used fallback.
- [ ] Hand-calculate report rows for Not attempted, In progress, Failed and Passed; confirm all 11 columns and multiple attempts.
- [ ] Download CSV and XLSX, open both in Excel, and verify Nepali text, formulas as text, filters/data and row parity.
- [ ] Send one reminder to a safe mailbox; verify branding, end date, login link, exact due day, retry and no mail after pass.
- [ ] Expire a test subscription; verify learner/admin locks and reminder suppression while platform reporting remains read-only.
- [ ] Smoke-test Level Assessment, certificates, leaderboard, Knowledge Score and the inactivity reminder command unchanged.

## Remaining deployment gates

- [ ] Follow `docs/MYSQL_MIGRATION_TEST_PLAN.md` on a disposable copy of production MySQL; record apply/reverse results, charset and index checks.
- [ ] Complete `docs/CALENDAR_VERIFICATION.md` against an official Patro with reviewer initials/date; library/table agreement is not independent verification.
- [ ] Record real Lumbini unique single-/multiple-choice question counts for every level and identify levels below 30.
- [ ] Take and verify a production backup; record the exact pre-deploy `main` commit hash and rollback owner.
- [ ] Merge the reviewed fresh-database fix first, then `integration/main-2026-10`; rebase this feature branch on that updated `main`, dropping equivalent commits, rerun all checks, and merge the Periodic Exam review last.
- [ ] Install the pinned Python dependencies before migration, schedule `send_periodic_exam_reminders` daily, and perform a disabled-state smoke test before enabling any tenant.

## Enable exactly one organisation

Run from `backend/` only after deployment gates pass. Replace both placeholders with verified values. The actor must be a real platform admin; first enablement starts at the next full cycle.

```powershell
..\backend\venv\Scripts\python.exe manage.py shell -c "from accounts.models import Organization, User; from periodic_exams.services import set_feature_enabled; org=Organization.objects.get(slug='<organisation-slug>'); actor=User.objects.get(email='<platform-admin-email>', role=User.Role.PLATFORM_ADMIN); row=set_feature_enabled(org, True, actor); print({'organization_id': org.id, 'enabled': row.enabled, 'enabled_from': row.enabled_from})"
```

Confirm without exposing tenant data:

```powershell
..\backend\venv\Scripts\python.exe manage.py shell -c "from periodic_exams.models import PeriodicExamSettings; print(PeriodicExamSettings.objects.values('organization_id','enabled','enabled_from').get(organization__slug='<organisation-slug>'))"
```

Disable the same organisation if QA fails (this hides the feature, blocks new starts and stops reminders without deleting attempts):

```powershell
..\backend\venv\Scripts\python.exe manage.py shell -c "from accounts.models import Organization, User; from periodic_exams.services import set_feature_enabled; org=Organization.objects.get(slug='<organisation-slug>'); actor=User.objects.get(email='<platform-admin-email>', role=User.Role.PLATFORM_ADMIN); set_feature_enabled(org, False, actor); print('Periodic Exam disabled for organization', org.id)"
```
