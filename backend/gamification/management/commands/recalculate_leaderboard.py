from django.core.management.base import BaseCommand

from gamification.leaderboard_recalculation import changed_fields, proposed_rows
from gamification.models import LeaderboardEntry


class Command(BaseCommand):
    help = 'Preview or apply question-weighted path quiz scores for the current-knowledge leaderboard.'

    def add_arguments(self, parser):
        parser.add_argument('--organization-id', type=int)
        parser.add_argument('--apply', action='store_true', help='Write changes. Without this flag the command is read-only.')

    def handle(self, *args, **options):
        apply_changes = options['apply']
        changed = 0
        for row in proposed_rows(options['organization_id']):
            learner = row['learner']
            entry = row['entry']
            proposed = row['proposed']
            fields = changed_fields(entry, proposed)
            if not fields:
                continue
            changed += 1
            action = 'APPLY' if apply_changes else 'DRY-RUN'
            self.stdout.write(
                f'{action} organization={learner.organization_id} learner={learner.id} '
                f'email={learner.email} fields={",".join(fields)} '
                f'coverage={proposed["quizzes_completed"]}/{proposed["quizzes_required"]} '
                f'knowledge_score={proposed["knowledge_score"]}'
            )
            if apply_changes:
                LeaderboardEntry.objects.update_or_create(user=learner, defaults=proposed)
        mode = 'applied' if apply_changes else 'would change'
        self.stdout.write(self.style.SUCCESS(f'{changed} learner leaderboard rows {mode}.'))
