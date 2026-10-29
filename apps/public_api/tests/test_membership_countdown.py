"""Membership countdown — starts at approval, shown as calendar months + days."""
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.members.models import Membership, MembershipPlan
from apps.members.services import approve_registration

from .test_payments import PaymentTestBase
from .faces import one_face

# Test photos have no real face — stub the detector to find one well-placed face.
_faces = one_face()


def setUpModule():
    _faces.start()


def tearDownModule():
    _faces.stop()

User = get_user_model()


class TimeRemainingTests(APITestCase):
    def setUp(self):
        self.plan = MembershipPlan.objects.create(name='pro', display_name='Pro', price_monthly=79, price_annual=790)
        self.user = User.objects.create_user(username='m', email='m@test.local', password='x')

    def membership(self, start, expiry):
        return Membership.objects.create(member=self.user, plan=self.plan, start_date=start, expiry_date=expiry)

    def test_fresh_three_month_plan(self):
        today = date.today()
        t = self.membership(today, today + relativedelta(months=3)).time_remaining
        self.assertEqual((t['months'], t['days']), (3, 0))
        self.assertEqual(t['percent_used'], 0)
        self.assertFalse(t['expired'])
        self.assertEqual(t['total_days_remaining'], t['plan_total_days'])

    def test_part_way_through(self):
        today = date.today()
        start = today - timedelta(days=10)
        expiry = start + relativedelta(months=3)
        t = self.membership(start, expiry).time_remaining
        rd = relativedelta(expiry, today)
        self.assertEqual((t['months'], t['days']), (rd.months + 12 * rd.years, rd.days))
        self.assertEqual(t['total_days_remaining'], (expiry - today).days)
        self.assertEqual(t['percent_used'], round(100 * 10 / (expiry - start).days))

    def test_one_year_plan_counts_twelve_months(self):
        today = date.today()
        t = self.membership(today, today + relativedelta(months=12)).time_remaining
        self.assertEqual((t['months'], t['days']), (12, 0))

    def test_expired(self):
        today = date.today()
        t = self.membership(today - relativedelta(months=2), today - timedelta(days=1)).time_remaining
        self.assertEqual((t['months'], t['days'], t['total_days_remaining']), (0, 0, 0))
        self.assertTrue(t['expired'])
        self.assertEqual(t['percent_used'], 100)

    def test_member_api_returns_the_countdown(self):
        today = date.today()
        self.membership(today, today + relativedelta(months=1))
        self.client.force_authenticate(self.user)
        data = self.client.get('/api/members/membership/').data
        self.assertEqual(data['time_remaining']['months'], 1)
        self.assertEqual(data['start_date'], today.isoformat())

    def test_dashboard_returns_the_countdown(self):
        today = date.today()
        self.membership(today, today + relativedelta(months=2))
        self.client.force_authenticate(self.user)
        m = self.client.get('/api/dashboard/').data['membership']
        self.assertEqual(m['start_date'], today.isoformat())
        self.assertEqual((m['time_remaining']['months'], m['time_remaining']['days']), (2, 0))


class CountdownStartsAtApprovalTests(PaymentTestBase):
    def staff_client(self):
        staff = User.objects.create_user(username='s', email='s@t.local', password='x', is_staff=True)
        self.client.force_authenticate(staff)

    def test_approval_starts_the_full_plan_period_today(self):
        reg_id = self.registered_and_paid()          # 3-month signup
        user = approve_registration(self.reg(reg_id))
        m = Membership.objects.get(member=user)
        self.assertEqual(m.start_date, date.today())
        self.assertEqual((m.time_remaining['months'], m.time_remaining['days']), (3, 0))

    def test_admin_registrations_show_the_countdown_for_approved_only(self):
        approved_id = self.registered_and_paid()
        approve_registration(self.reg(approved_id))
        pending_id = self.register(iqama_number='2888777666', email='other@example.com', full_name='Other Person').data['id']
        self.staff_client()
        rows = {r['id']: r for r in self.client.get('/api/admin/registrations-api/registrations/').data['results']}
        self.assertEqual(rows[approved_id]['membership']['time_remaining']['months'], 3)
        self.assertEqual(rows[approved_id]['membership']['start_date'], date.today())
        self.assertIsNone(rows[pending_id]['membership'])

    def test_registrations_list_has_no_per_row_membership_queries(self):
        self.staff_client()
        approve_registration(self.reg(self.registered_and_paid()))
        # 2 = the count + one select that joins plan, approver, user and membership
        with self.assertNumQueries(2):
            self.client.get('/api/admin/registrations-api/registrations/')
        second = self.register(iqama_number='2777666555', email='b@example.com', full_name='Second Person').data['id']
        self.pay('pay_b', second, 23700)
        self.verify('pay_b')
        approve_registration(self.reg(second))
        with self.assertNumQueries(2):   # still 2 with two approved rows: no per-row lookups
            self.client.get('/api/admin/registrations-api/registrations/')
