"""Login lockout, closed self-registration, signup rate limit."""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.public_api import views as public_views

User = get_user_model()


class HardeningTests(APITestCase):
    def setUp(self):
        User.objects.create_user(username='m', email='m@t.local', password='Right-Pass-123', role='member')

    def login(self, pw, email='m@t.local', ip='1.1.1.1'):
        return self.client.post('/api/auth/login/', {'email': email, 'password': pw}, format='json',
                                HTTP_X_FORWARDED_FOR=ip)

    def test_five_wrong_passwords_lock_the_email(self):
        for _ in range(5):
            self.assertEqual(self.login('wrong').status_code, 401)
        self.assertEqual(self.login('Right-Pass-123').status_code, 429)          # locked even with the right one
        self.assertEqual(self.login('x', email='other@t.local').status_code, 401)  # other accounts unaffected

    def test_success_resets_the_counter(self):
        for _ in range(4):
            self.login('wrong')
        self.assertEqual(self.login('Right-Pass-123').status_code, 200)
        self.assertEqual(self.login('wrong').status_code, 401)

    def test_self_registration_is_closed(self):
        r = self.client.post('/api/auth/register/', {'email': 'x@t.local', 'username': 'x', 'password': 'Abc-12345!',
                                                      'password_confirm': 'Abc-12345!'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertFalse(User.objects.filter(email='x@t.local').exists())

    def test_signup_rate_limit(self):
        from apps.accounts import ratelimit
        for _ in range(public_views.SIGNUPS_PER_IP_HOUR):
            ratelimit.hit('signup_ip', '9.9.9.9')
        r = self.client.post('/api/public/register/', {}, HTTP_X_FORWARDED_FOR='9.9.9.9')
        self.assertEqual(r.status_code, 429)
