"""Approval → login with the signup password + welcome email (temporary-password fallback for legacy signups)."""
import re

from django.contrib.auth.hashers import make_password
from django.core import mail
from django.test import SimpleTestCase, override_settings

from apps.members import services
from apps.members.models import MembershipRegistration as R
from apps.members.services import approve_registration, generate_temp_password, member_portal_url

from .test_payments import PaymentTestBase, SIGNUP_PASSWORD
from .faces import one_face

# Test photos have no real face — stub the detector to find one well-placed face.
_faces = one_face()


def setUpModule():
    _faces.start()


def tearDownModule():
    _faces.stop()

PROD_FRONTEND_URL = 'http://localhost:5173,https://gym-member-and-admin.vercel.app'
APPROVED_LINE = 'You can now log in with the email and password you created during signup.'


def temp_password_in(body):
    return re.search(r'Temporary password: (\S+)', body).group(1)


@override_settings(FRONTEND_URL=PROD_FRONTEND_URL)
class WelcomeEmailTests(PaymentTestBase):
    def approve(self, legacy=False):
        """legacy=True: a signup made while the site had no password field (unusable hash)."""
        reg_id = self.registered_and_paid()
        if legacy:
            R.objects.filter(id=reg_id).update(password_hash=make_password(None))
        with self.captureOnCommitCallbacks(execute=True):
            user = approve_registration(self.reg(reg_id))
        user.refresh_from_db()
        return user

    def login(self, email, password):
        return self.client.post('/api/auth/login/', {'email': email, 'password': password}, format='json')

    # ---------- normal signup: the member's own password ----------
    def test_member_logs_in_with_the_signup_password(self):
        user = self.approve()
        self.assertTrue(user.check_password(SIGNUP_PASSWORD))
        self.assertFalse(user.must_change_password)
        self.assertEqual(self.login(user.email, SIGNUP_PASSWORD).status_code, 200)

    def test_email_confirms_approval_without_any_password(self):
        user = self.approve()
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, [user.email])
        self.assertIn('Your registration is approved!', msg.body)
        self.assertIn(APPROVED_LINE, msg.body)
        self.assertIn('Login page:  https://gym-member-and-admin.vercel.app/login', msg.body)
        self.assertIn(f'Email:       {user.email}', msg.body)
        self.assertNotIn('Temporary password', msg.body)
        self.assertNotIn(SIGNUP_PASSWORD, msg.body)
        self.assertNotIn('localhost', msg.body)

    # ---------- legacy signup (no password): temporary password + lock ----------
    def test_legacy_signup_gets_a_working_temporary_password_and_the_lock(self):
        user = self.approve(legacy=True)
        body = mail.outbox[0].body
        password = temp_password_in(body)
        self.assertTrue(user.check_password(password))
        self.assertTrue(user.must_change_password)
        self.assertNotIn(APPROVED_LINE, body)
        self.assertIn('You will be asked to choose your own', body)
        self.assertEqual(self.login(user.email, password).status_code, 200)

    def test_temporary_password_is_never_logged(self):
        with self.assertLogs('apps.members.services', 'INFO') as logs:
            self.approve(legacy=True)
        password = temp_password_in(mail.outbox[0].body)
        self.assertFalse(any(password in line for line in logs.output))

    # ---------- delivery ----------
    @override_settings(EMAIL_BACKEND=services.CONSOLE_EMAIL_BACKEND, DEBUG=False)
    def test_console_backend_in_production_does_not_send(self):
        with self.assertLogs('apps.members.services', 'ERROR') as logs:
            user = self.approve()
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('NOT sent', logs.output[0])
        self.assertEqual(R.objects.get(created_user=user).status, R.STATUS_APPROVED)

    def test_no_email_when_approval_rolls_back(self):
        reg_id = self.register().data['id']   # unpaid → approval refused
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(ValueError):
                approve_registration(self.reg(reg_id))
        self.assertEqual(len(mail.outbox), 0)


class HelperTests(SimpleTestCase):
    def test_temp_password_shape(self):
        pw = generate_temp_password()
        self.assertEqual(len(pw), 12)
        self.assertTrue(set(pw) <= set(services.TEMP_PASSWORD_CHARS))
        self.assertNotEqual(pw, generate_temp_password())

    def test_portal_url(self):
        cases = {
            PROD_FRONTEND_URL: 'https://gym-member-and-admin.vercel.app',
            'http://localhost:5173': 'http://localhost:5173',
            ' https://a.example/ , https://b.example ': 'https://a.example',
            '': services.DEFAULT_MEMBER_PORTAL,
        }
        for value, expected in cases.items():
            with self.subTest(value=value), override_settings(FRONTEND_URL=value):
                self.assertEqual(member_portal_url(), expected)
