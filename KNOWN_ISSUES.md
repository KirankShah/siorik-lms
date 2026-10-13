# Known issues

| date | symptom | root cause | files changed | test added |
|---|---|---|---|---|
| 2026-10-13 | Leaderboard showed no own metrics, omitted learners outside the Top 5, and had no clear unassessed state. | The API excluded null Knowledge Scores, while the widget sliced the response to five rows and rendered missing own metrics as dashes. | `backend/gamification/views.py`; `backend/test_api_flows.py`; `frontend/src/components/LeaderboardWidget.tsx`; `frontend/src/components/LeaderboardWidget.test.tsx`; `frontend/src/types/gamification.ts` | `CurrentKnowledgeLeaderboardTests.test_endpoint_includes_unassessed_same_org_learner_but_never_another_organization`; two `LeaderboardWidget` regression tests |
