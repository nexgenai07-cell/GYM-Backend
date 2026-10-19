"""Approval → temporary password + welcome email."""
import re

from django.core import mail
from django.test import SimpleTestCase, override_settings

from apps.members import services
from apps.members.models import MembershipRegistration as R
from apps.members.services import approve_registration, generate_temp_password, member_portal_url

from .test_payments import PaymentTestBase

PROD_FRONTEND_URL = 'http://localhost:5173,https://gym-member-and-admin.vercel.app'
SIGNUP_PASSWORD = 'Str0ng-Passw0rd!'   # what PaymentTestBase.register() submits


def temp_password_in(body):
    return re.search(r'Temporary password: (\S+)', body).group(1)


@override_settings(FRONTEND_URL=PROD_FRONTEND_URL)
class WelcomeEmailTests(PaymentTestBase):
    def approve(self):
        reg_id = self.registered_and_paid()
        with self.captureOnCommitCallbacks(execute=True):
            user = approve_registration(self.reg(reg_id))
        return user

    def test_user_gets_a_working_temporary_password(self):
        user = self.approve()
        self.assertEqual(len(mail.outbox), 1)
        password = temp_password_in(mail.outbox[0].body)
        user.refresh_from_db()
        self.assertTrue(user.check_password(password))
        self.assertFalse(user.check_password(SIGNUP_PASSWORD))
        r = self.client.post('/api/auth/login/', {'email': user.email, 'password': password}, format='json')
        self.assertEqual(r.status_code, 200)

    def test_email_has_single_login_url_email_and_change_warning(self):
        user = self.approve()
        msg = mail.outbox[0]
        self.assertEqual(msg.to, [user.email])
        self.assertIn('Login page:         https://gym-member-and-admin.vercel.app/login', msg.body)
        self.assertNotIn('localhost', msg.body)
        self.assertNotIn(',https', msg.body)
        self.assertIn(f'Email:              {user.email}', msg.body)
        self.assertIn('Change it as soon as you log in', msg.body)

    def test_password_is_never_logged(self):
        with self.assertLogs('apps.members.services', 'INFO') as logs:
            self.approve()
        password = temp_password_in(mail.outbox[0].body)
        self.assertFalse(any(password in line for line in logs.output))

    @override_settings(EMAIL_BACKEND=services.CONSOLE_EMAIL_BACKEND, DEBUG=False)
    def test_console_backend_in_production_does_not_send_or_print_password(self):
        with self.assertLogs('apps.members.services', 'ERROR') as logs:
            user = self.approve()
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('NOT sent', logs.output[0])
        self.assertEqual(self.reg(R.objects.get(created_user=user).id).status, R.STATUS_APPROVED)

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
