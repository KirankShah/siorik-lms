from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Organization, User

from .models import Badge, UserBadge


class UserBadgeCelebrationTests(APITestCase):
    def setUp(self):
        organization = Organization.objects.create(name='Celebration Bank', slug='celebration-bank')
        self.learner = User.objects.create_user(
            email='learner@celebration.test',
            password='test-password',
            role=User.Role.LEARNER,
            organization=organization,
        )
        self.other_learner = User.objects.create_user(
            email='other@celebration.test',
            password='test-password',
            role=User.Role.LEARNER,
            organization=organization,
        )
        self.badge = Badge.objects.create(
            key='celebration-test',
            name='First Strike',
            description='Answered your first assessment question correctly.',
            icon='⚡',
        )

    def test_new_award_is_returned_as_uncelebrated(self):
        award = UserBadge.objects.create(user=self.learner, badge=self.badge)
        self.client.force_authenticate(self.learner)

        response = self.client.get('/api/user-badges/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['id'], award.id)
        self.assertIsNone(response.data[0]['celebration_seen_at'])

    def test_learner_can_acknowledge_own_celebration_idempotently(self):
        award = UserBadge.objects.create(user=self.learner, badge=self.badge)
        self.client.force_authenticate(self.learner)
        url = f'/api/user-badges/{award.id}/acknowledge-celebration/'

        first_response = self.client.post(url)
        award.refresh_from_db()
        first_seen_at = award.celebration_seen_at
        second_response = self.client.post(url)
        award.refresh_from_db()

        self.assertEqual(first_response.status_code, 200)
        self.assertIsNotNone(first_seen_at)
        self.assertLessEqual(first_seen_at, timezone.now())
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(award.celebration_seen_at, first_seen_at)

    def test_learner_cannot_acknowledge_another_learners_award(self):
        award = UserBadge.objects.create(user=self.other_learner, badge=self.badge)
        self.client.force_authenticate(self.learner)

        response = self.client.post(f'/api/user-badges/{award.id}/acknowledge-celebration/')

        self.assertEqual(response.status_code, 404)
        award.refresh_from_db()
        self.assertIsNone(award.celebration_seen_at)

    def test_acknowledgement_requires_authentication(self):
        award = UserBadge.objects.create(user=self.learner, badge=self.badge)

        response = self.client.post(f'/api/user-badges/{award.id}/acknowledge-celebration/')

        self.assertEqual(response.status_code, 401)
