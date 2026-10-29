"""The "must change password" lock on temporary-password accounts."""
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core import mail
from rest_framework.test import APITestCase

from apps.members.models import MembershipRegistration as R
from apps.members.services import approve_registration

from .test_payments import PaymentTestBase, SIGNUP_PASSWORD
from .faces import one_face

# Test photos have no real face — stub the detector to find one well-placed face.
_faces = one_face()


def setUpModule():
    _faces.start()


def tearDownModule():
    _faces.stop()

User = get_user_model()
NEW_PASSWORD = 'My-Own-Strong-Pass-42'


class PasswordLockTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='m', email='m@test.local', password='Temp-Pass-123', must_change_password=True,
        )

    def login(self, password='Temp-Pass-123'):
        r = self.client.post('/api/auth/login/', {'email': 'm@test.local', 'password': password}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return r

    def change(self, old='Temp-Pass-123', new=NEW_PASSWORD, confirm=None):
        return self.client.post('/api/auth/change-password/', {
            'old_password': old, 'new_password': new, 'new_password_confirm': confirm or new,
        }, format='json')

    def test_login_still_works_and_reports_the_flag(self):
        r = self.login()
        self.assertTrue(r.data['user']['must_change_password'])

    def test_other_endpoints_are_locked_with_a_clear_code(self):
        self.login()
        for path in ('/api/members/membership/', '/api/workouts/', '/api/notifications/', '/api/dashboard/'):
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 403)
                self.assertEqual(r.json()['code'], 'password_change_required')
                self.assertIn('temporary password', r.json()['detail'])

    def test_me_change_password_and_logout_stay_open(self):
        r = self.login()
        me = self.client.get('/api/auth/me/')
        self.assertEqual(me.status_code, 200)
        self.assertTrue(me.data['must_change_password'])
        self.assertEqual(self.client.post('/api/auth/logout/', {'refresh': r.data['refresh']}, format='json').status_code, 200)

    def test_changing_the_password_clears_the_lock(self):
        self.login()
        self.assertEqual(self.change().status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertEqual(self.client.get('/api/members/membership/').status_code, 404)   # unlocked (no membership here)
        self.assertEqual(self.client.get('/api/auth/me/').data['must_change_password'], False)

    def test_cannot_keep_the_temporary_password(self):
        self.login()
        r = self.change(new='Temp-Pass-123')
        self.assertEqual(r.status_code, 400)
        self.assertIn('new_password', r.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)

    def test_wrong_current_password_keeps_the_lock(self):
        self.login()
        self.assertEqual(self.change(old='nope').status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)

    def test_unflagged_users_are_unaffected(self):
        User.objects.create_user(username='x', email='x@test.local', password='Normal-Pass-77')
        r = self.client.post('/api/auth/login/', {'email': 'x@test.local', 'password': 'Normal-Pass-77'}, format='json')
        self.assertFalse(r.data['user']['must_change_password'])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.assertNotEqual(self.client.get('/api/workouts/').status_code, 403)

    def test_public_endpoints_need_no_token(self):
        self.assertEqual(self.client.get('/api/public/plans/').status_code, 200)


class ApprovalLockTests(PaymentTestBase):
    def approve(self, reg_id):
        with self.captureOnCommitCallbacks(execute=True):
            return approve_registration(self.reg(reg_id))

    def test_normal_signup_is_not_locked(self):
        user = self.approve(self.registered_and_paid())
        self.assertFalse(user.must_change_password)
        r = self.client.post('/api/auth/login/', {'email': user.email, 'password': SIGNUP_PASSWORD}, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.assertEqual(self.client.get('/api/members/membership/').status_code, 200)

    def test_legacy_signup_without_password_is_locked_until_changed(self):
        reg_id = self.registered_and_paid()
        R.objects.filter(id=reg_id).update(password_hash=make_password(None))
        user = self.approve(reg_id)
        self.assertTrue(user.must_change_password)
        temp = re.search(r'Temporary password: (\S+)', mail.outbox[0].body).group(1)
        r = self.client.post('/api/auth/login/', {'email': user.email, 'password': temp}, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.assertEqual(self.client.get('/api/members/membership/').status_code, 403)
        self.client.post('/api/auth/change-password/', {
            'old_password': temp, 'new_password': NEW_PASSWORD, 'new_password_confirm': NEW_PASSWORD,
        }, format='json')
        self.assertEqual(self.client.get('/api/members/membership/').status_code, 200)
