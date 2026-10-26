from collections import defaultdict

from accounts.models import User

from .models import LeaderboardEntry
from .services import current_knowledge_defaults


CURRENT_KNOWLEDGE_FIELDS = (
    'organization_id',
    'current_course_quiz_average',
    'latest_periodic_exam_score',
    'knowledge_score',
    'last_assessed_at',
    'quizzes_completed',
    'quizzes_required',
)


def eligible_learners(organization_id=None):
    queryset = User.objects.filter(
        role=User.Role.LEARNER,
        is_active=True,
        organization_id__isnull=False,
    ).select_related('organization', 'leaderboard_entry')
    if organization_id is not None:
        queryset = queryset.filter(organization_id=organization_id)
    return queryset.order_by('organization_id', 'assessment_level', 'id')


def proposed_rows(organization_id=None):
    rows = []
    for learner in eligible_learners(organization_id):
        try:
            entry = learner.leaderboard_entry
        except LeaderboardEntry.DoesNotExist:
            entry = None
        proposed = current_knowledge_defaults(learner)
        rows.append({'learner': learner, 'entry': entry, 'proposed': proposed})
    _attach_ranks(rows, source='old')
    _attach_ranks(rows, source='new')
    return rows


def _attach_ranks(rows, source):
    grouped = defaultdict(list)
    for row in rows:
        learner = row['learner']
        if source == 'old':
            entry = row['entry']
            knowledge_score = entry.knowledge_score if entry else None
            quiz_average = entry.current_course_quiz_average if entry else None
            last_assessed_at = entry.last_assessed_at if entry else None
        else:
            proposed = row['proposed']
            knowledge_score = proposed['knowledge_score']
            quiz_average = proposed['current_course_quiz_average']
            last_assessed_at = proposed['last_assessed_at']
        row[f'{source}_rank'] = None
        if knowledge_score is not None:
            grouped[learner.organization_id].append(
                (row, knowledge_score, quiz_average, last_assessed_at)
            )

    for values in grouped.values():
        values.sort(
            key=lambda value: (
                value[1],
                value[2] if value[2] is not None else -1,
                value[3].timestamp() if value[3] is not None else -1,
                -value[0]['learner'].id,
            ),
            reverse=True,
        )
        for rank, (row, *_rest) in enumerate(values, start=1):
            row[f'{source}_rank'] = rank


def changed_fields(entry, proposed):
    if entry is None:
        return list(CURRENT_KNOWLEDGE_FIELDS)
    return [field for field in CURRENT_KNOWLEDGE_FIELDS if getattr(entry, field) != proposed[field]]
