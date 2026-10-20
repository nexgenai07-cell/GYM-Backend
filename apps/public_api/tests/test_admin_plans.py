"""Membership plans managed from the admin portal."""
from decimal import Decimal

from django.contrib.auth import get_user_model

from apps.members.models import MembershipPlan

from .test_site_content import ContentTestBase

User = get_user_model()
ADMIN = '/api/admin/site-content/plans'


class AdminPlanTests(ContentTestBase):
    def setUp(self):
        super().setUp()
        self.basic = MembershipPlan.objects.create(name='basic', display_name='Basic', price_monthly=29, price_annual=290)
        self.as_admin()

    def new_plan(self, **over):
        body = {'name': 'Student Plan', 'display_name': 'Student', 'display_name_ar': 'طالب',
                'price_monthly': '19.00', 'price_annual': '190.00',
                'features': ['Gym floor', ' '], 'features_ar': ['صالة الأجهزة'], **over}
        return self.client.post(f'{ADMIN}/', body, format='json')

    def test_create_with_arabic_and_it_shows_publicly(self):
        r = self.new_plan()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['name'], 'student-plan')                 # slugified code
        self.assertEqual(r.data['features'], ['Gym floor'])              # blanks dropped
        self.client.force_authenticate(None)
        public = {p['name']: p for p in self.client.get('/api/public/plans/').data}
        self.assertEqual(public['student-plan']['display_name_ar'], 'طالب')
        self.assertEqual(public['student-plan']['features_ar'], ['صالة الأجهزة'])

    def test_validation(self):
        self.assertEqual(self.new_plan(price_monthly='0').status_code, 400)
        self.assertEqual(self.new_plan(name='basic').status_code, 400)           # duplicate code
        self.assertEqual(self.new_plan(features='not a list').status_code, 400)

    def test_deactivate_takes_it_off_the_site_but_admin_still_sees_it(self):
        r = self.client.patch(f'{ADMIN}/{self.basic.pk}/', {'is_active': False, 'price_monthly': '35.00'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(MembershipPlan.objects.get(pk=self.basic.pk).price_monthly, Decimal('35.00'))
        self.assertIn(self.basic.pk, [p['id'] for p in self.client.get(f'{ADMIN}/').data])
        self.client.force_authenticate(None)
        self.assertNotIn(self.basic.pk, [p['id'] for p in self.client.get('/api/public/plans/').data])

    def test_no_delete_and_members_cannot_edit(self):
        self.assertEqual(self.client.delete(f'{ADMIN}/{self.basic.pk}/').status_code, 405)
        self.client.force_authenticate(User.objects.create_user(username='m', email='m@t.local', password='x'))
        self.assertEqual(self.client.patch(f'{ADMIN}/{self.basic.pk}/', {'is_active': False}, format='json').status_code, 403)
