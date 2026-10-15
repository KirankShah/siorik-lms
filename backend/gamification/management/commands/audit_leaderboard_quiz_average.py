import csv

from django.core.management.base import BaseCommand

from gamification.leaderboard_recalculation import proposed_rows


class Command(BaseCommand):
    help = 'Read-only comparison of stored leaderboard scores with complete quiz-coverage scoring.'

    def add_arguments(self, parser):
        parser.add_argument('--organization-id', type=int)

    def handle(self, *args, **options):
        writer = csv.writer(self.stdout)
        writer.writerow([
            'organization_id', 'organization', 'learner_id', 'email', 'completed', 'required',
            'old_average', 'new_average', 'old_knowledge_score', 'new_knowledge_score',
            'old_status', 'new_status', 'old_rank', 'new_rank',
        ])
        rows = proposed_rows(options['organization_id'])
        for row in rows:
            learner = row['learner']
            entry = row['entry']
            proposed = row['proposed']
            completed = proposed['quizzes_completed']
            required = proposed['quizzes_required']
            writer.writerow([
                learner.organization_id,
                learner.organization.name,
                learner.id,
                learner.email,
                completed,
                required,
                entry.current_course_quiz_average if entry else '',
                proposed['current_course_quiz_average'] if proposed['current_course_quiz_average'] is not None else '',
                entry.knowledge_score if entry else '',
                proposed['knowledge_score'] if proposed['knowledge_score'] is not None else '',
                'Ranked' if entry and entry.knowledge_score is not None else 'In progress',
                'Ranked' if proposed['knowledge_score'] is not None else f'In progress ({completed} of {required} quizzes)',
                row['old_rank'] or '',
                row['new_rank'] or '',
            ])
        self.stderr.write(f'Audited {len(rows)} active learners; no data was changed.')
