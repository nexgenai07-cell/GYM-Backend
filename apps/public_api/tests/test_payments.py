"""Registration + Moyasar payment flow: verification, tampering, webhook, approval gate."""
import io
import shutil
import tempfile
import urllib.error
from decimal import Decimal
from unittest import mock

from django.contrib.auth.hashers import check_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from PIL import Image
from rest_framework.test import APITestCase

from apps.members.models import Membership, MembershipPlan, MembershipRegistration as R
from apps.members.services import approve_registration
from apps.public_api import moyasar

WEBHOOK_SECRET = 'whsec_test'
SIGNUP_PASSWORD = 'Str0ng-Passw0rd!'
IQAMA = '2999888777'


def clear_image(size=320):
    """A sharp, evenly lit picture that passes the signup photo check (checkerboard)."""
    img = Image.new('L', (size, size), 90)
    px = img.load()
    for y in range(size):
        for x in range(size):
            if (x // 8 + y // 8) % 2:
                px[x, y] = 170
    return img.convert('RGB')


def photo():
    buf = io.BytesIO()
    clear_image().save(buf, 'JPEG', quality=92)
    return SimpleUploadedFile('live.jpg', buf.getvalue(), content_type='image/jpeg')


@override_settings(
    MOYASAR_SECRET_KEY='sk_test_dummy',
    MOYASAR_PUBLISHABLE_KEY='pk_test_dummy',
    MOYASAR_WEBHOOK_SECRET=WEBHOOK_SECRET,
)
class PaymentTestBase(APITestCase):
    def setUp(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        media_override = override_settings(MEDIA_ROOT=media)
        media_override.enable()
        self.addCleanup(media_override.disable)

        # In-memory stand-in for Moyasar's GET /payments/<id>.
        self.payments = {}
        patcher = mock.patch.object(moyasar, 'fetch_payment', side_effect=self.fake_fetch)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.plan = MembershipPlan.objects.create(
            name='pro', display_name='Pro', price_monthly=Decimal('79.00'), price_annual=Decimal('790.00'),
        )

    # ---------- helpers ----------
    def fake_fetch(self, pid):
        if pid not in self.payments:
            raise moyasar.MoyasarError('Payment not found.')
        return self.payments[pid]

    def register(self, **overrides):
        """POST /public/register/. Pass a field as None to leave it out."""
        data = dict(iqama_number=IQAMA, full_name='Test User', email='Test@Example.com', phone='0500000000',
                    age=30, gender='male', plan=self.plan.id, duration_months=3,
                    password=SIGNUP_PASSWORD, photo=photo())
        data.update(overrides)
        data = {k: v for k, v in data.items() if v is not None}
        return self.client.post('/api/public/register/', data, format='multipart')

    def reg(self, reg_id):
        return R.objects.get(id=reg_id)

    def pay(self, pid, reg_id, amount, status='paid', currency='SAR', msg=None, attempt=None, refunded=0):
        if attempt is None:
            existing = R.objects.filter(id=reg_id).first()
            attempt = existing.payment_attempt_token if existing else 'x'
        self.payments[pid] = {
            'id': pid, 'status': status, 'amount': amount, 'currency': currency, 'refunded': refunded,
            'metadata': {'registration_id': str(reg_id), 'attempt': attempt},
            'source': {'type': 'creditcard', 'company': 'mada', 'message': msg,
                       'name': 'CARD HOLDER', 'number': '4201-32XX-XXXX-1010'},
        }

    def verify(self, pid):
        return self.client.post('/api/public/payments/moyasar/verify/', {'payment_id': pid}, format='json')

    def attach(self, reg_id, pid):
        return self.client.post(f'/api/public/register/{reg_id}/payment/attach/', {'payment_id': pid}, format='json')

    def webhook(self, pid, token=WEBHOOK_SECRET, event='payment_paid'):
        return self.client.post('/api/public/payments/moyasar/webhook/',
                                {'type': event, 'secret_token': token, 'data': {'id': pid}}, format='json')

    def registered_and_paid(self, pid='pay_ok'):
        """Register (3 months = 23700 halalas) and complete a valid payment via the callback."""
        reg_id = self.register().data['id']
        self.pay(pid, reg_id, 23700)
        self.assertEqual(self.verify(pid).status_code, 200)
        return reg_id

    def assert_approval_refused(self, reg_id, fragment):
        with self.assertRaises(ValueError) as ctx:
            approve_registration(self.reg(reg_id))
        self.assertIn(fragment, str(ctx.exception))
        self.assertIsNone(self.reg(reg_id).created_user_id)


class RegistrationTests(PaymentTestBase):
    def test_rejects_iqama_not_starting_with_2(self):
        r = self.register(iqama_number='1234567890')
        self.assertEqual(r.status_code, 400)
        self.assertIn('iqama_number', r.data)

    def test_requires_photo(self):
        r = self.register(photo=None)
        self.assertEqual(r.status_code, 400)
        self.assertIn('photo', r.data)

    def test_creates_pending_registration_with_server_side_amount(self):
        r = self.register()
        self.assertEqual(r.status_code, 201)
        reg = self.reg(r.data['id'])
        p = r.data['payment']
        self.assertEqual(p['amount'], 23700)   # 3 x 79.00 SAR, in halalas
        self.assertEqual(p['currency'], 'SAR')
        self.assertEqual(p['metadata'], {'registration_id': str(reg.id), 'attempt': reg.payment_attempt_token})
        self.assertGreaterEqual(len(reg.payment_attempt_token), 30)
        self.assertEqual(reg.email, 'test@example.com')
        self.assertEqual((reg.status, reg.payment_status), ('pending', 'pending'))

    def test_responses_carry_no_personal_data(self):
        r = self.register()
        self.assertFalse({'full_name', 'email', 'iqama_number', 'phone', 'plan_name'} & set(r.data))
        status = self.client.get(f"/api/public/register/{r.data['id']}/status/").data
        self.assertEqual(set(status), {'id', 'status', 'payment_status', 'payment_failure_reason'})

    def test_old_unauthenticated_mark_paid_endpoint_is_gone(self):
        reg_id = self.register().data['id']
        r = self.client.post(f'/api/public/register/{reg_id}/payment/', {'status': 'paid'}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_requires_a_password(self):
        r = self.register(password=None)
        self.assertEqual(r.status_code, 400)
        self.assertIn('password', r.data)

    def test_rejects_a_weak_password(self):
        r = self.register(password='12345678')   # common + entirely numeric
        self.assertEqual(r.status_code, 400)
        self.assertIn('password', r.data)

    def test_password_is_stored_hashed(self):
        reg = self.reg(self.register().data['id'])
        self.assertNotIn(SIGNUP_PASSWORD, reg.password_hash)
        self.assertTrue(check_password(SIGNUP_PASSWORD, reg.password_hash))

    def test_same_iqama_with_different_email_is_rejected(self):
        self.register()
        r = self.register(email='other@example.com')
        self.assertEqual(r.status_code, 400)
        self.assertIn('iqama_number', r.data)


class FailedPaymentAndRetryTests(PaymentTestBase):
    def test_failed_payment_is_recorded_without_moving_status(self):
        reg_id = self.register().data['id']
        self.pay('pay_fail', reg_id, 23700, status='failed', msg='Insufficient funds')
        self.attach(reg_id, 'pay_fail')
        reg = self.reg(reg_id)
        self.assertEqual(reg.payment_status, 'failed')
        self.assertEqual(reg.payment_failure_reason, 'Insufficient funds')
        self.assertEqual(reg.status, 'pending')

    def test_resubmitting_unpaid_registration_reuses_it_with_new_amount_and_token(self):
        reg_id = self.register().data['id']
        old_token = self.reg(reg_id).payment_attempt_token
        self.pay('pay_fail', reg_id, 23700, status='failed')
        self.attach(reg_id, 'pay_fail')
        r = self.register(duration_months=1)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['id'], reg_id)
        self.assertEqual(r.data['payment']['amount'], 7900)
        self.assertNotEqual(self.reg(reg_id).payment_attempt_token, old_token)

    def test_payment_from_an_old_attempt_is_rejected(self):
        reg_id = self.register().data['id']
        old_token = self.reg(reg_id).payment_attempt_token
        self.register(duration_months=1)   # new attempt, new token
        self.pay('pay_stale', reg_id, 7900, attempt=old_token)
        self.assertEqual(self.verify('pay_stale').status_code, 400)
        self.assertNotEqual(self.reg(reg_id).payment_status, 'paid')

    def test_resubmit_during_moyasar_outage_keeps_the_attached_payment(self):
        reg_id = self.register().data['id']
        self.pay('pay_b', reg_id, 23700, status='initiated')
        self.attach(reg_id, 'pay_b')
        with mock.patch.object(moyasar, 'fetch_payment', side_effect=moyasar.MoyasarUnavailable('down')):
            r = self.register()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.reg(reg_id).moyasar_payment_id, 'pay_b')


class TamperingTests(PaymentTestBase):
    def test_forged_metadata_with_wrong_attempt_token_is_rejected(self):
        reg_id = self.register().data['id']
        self.pay('pay_forged', reg_id, 23700, attempt='guessed-token')
        self.assertEqual(self.verify('pay_forged').status_code, 400)
        self.assertNotEqual(self.reg(reg_id).payment_status, 'paid')

    def test_status_captured_is_not_accepted_as_paid(self):
        reg_id = self.register().data['id']
        self.pay('pay_cap', reg_id, 23700, status='captured')
        self.verify('pay_cap')
        self.assertNotEqual(self.reg(reg_id).payment_status, 'paid')

    def test_attach_rejects_another_registrations_payment(self):
        reg_id = self.register().data['id']
        self.pay('pay_x', reg_id + 999, 23700)
        self.assertEqual(self.attach(reg_id, 'pay_x').status_code, 400)

    def test_paid_but_wrong_amount_is_flagged_not_marked_paid(self):
        reg_id = self.register().data['id']
        self.pay('pay_cheap', reg_id, 100)
        self.verify('pay_cheap')
        reg = self.reg(reg_id)
        self.assertNotEqual(reg.payment_status, 'paid')
        self.assertEqual(reg.status, 'pending')
        self.assertTrue(reg.payment_failure_reason.startswith('Needs manual review'))


class PaidFlowTests(PaymentTestBase):
    def test_callback_verify_marks_paid_and_pending_admin_approval(self):
        reg = self.reg(self.registered_and_paid())
        self.assertEqual(reg.payment_status, 'paid')
        self.assertIsNotNone(reg.payment_paid_at)
        self.assertEqual(reg.status, R.STATUS_PAID)
        self.assertEqual(reg.get_status_display(), 'Pending admin approval')
        self.assertEqual(reg.payment_method, 'mada')

    def test_stored_payment_is_redacted(self):
        raw = self.reg(self.registered_and_paid()).payment_raw
        self.assertEqual(raw['id'], 'pay_ok')
        self.assertNotIn('name', raw['source'])
        self.assertNotIn('number', raw['source'])

    def test_webhook_after_callback_is_idempotent(self):
        reg_id = self.registered_and_paid()
        paid_at = self.reg(reg_id).payment_paid_at
        self.assertEqual(self.webhook('pay_ok').status_code, 200)
        self.assertEqual(self.reg(reg_id).payment_paid_at, paid_at)

    def test_late_failure_cannot_unpay(self):
        reg_id = self.registered_and_paid()
        self.pay('pay_fail2', reg_id, 23700, status='failed')
        self.webhook('pay_fail2', event='payment_failed')
        self.assertEqual(self.reg(reg_id).payment_status, 'paid')

    def test_paid_registration_cannot_be_overwritten_by_resubmit(self):
        self.registered_and_paid()
        self.assertEqual(self.register().status_code, 400)


class WebhookTests(PaymentTestBase):
    def test_bad_token_is_403_and_changes_nothing(self):
        reg_id = self.register().data['id']
        self.pay('pay_ok', reg_id, 23700)
        self.assertEqual(self.webhook('pay_ok', token='wrong').status_code, 403)
        self.assertNotEqual(self.reg(reg_id).payment_status, 'paid')

    def test_valid_webhook_marks_paid_without_callback(self):
        reg_id = self.register().data['id']   # customer closed the browser after paying
        self.pay('pay_ok', reg_id, 23700)
        self.assertEqual(self.webhook('pay_ok').status_code, 200)
        self.assertEqual(self.reg(reg_id).payment_status, 'paid')

    def test_unknown_payment_is_acknowledged(self):
        self.assertEqual(self.webhook('nope').status_code, 200)

    def test_moyasar_outage_returns_500_so_moyasar_retries(self):
        with mock.patch.object(moyasar, 'fetch_payment', side_effect=moyasar.MoyasarUnavailable('down')):
            self.assertEqual(self.webhook('pay_ok').status_code, 500)


class ApprovalGateTests(PaymentTestBase):
    def test_refuses_unpaid(self):
        reg_id = self.register().data['id']
        self.assert_approval_refused(reg_id, 'not been paid')

    def test_refuses_paid_set_by_hand_without_moyasar_payment(self):
        reg_id = self.register().data['id']
        R.objects.filter(id=reg_id).update(payment_status='paid')
        self.assert_approval_refused(reg_id, 'No Moyasar payment')

    def test_refuses_payment_refunded_after_it_was_paid(self):
        reg_id = self.registered_and_paid()
        self.payments['pay_ok']['refunded'] = 23700
        self.assert_approval_refused(reg_id, 'refunded')

    def test_refuses_when_moyasar_status_is_no_longer_paid(self):
        reg_id = self.registered_and_paid()
        self.payments['pay_ok']['status'] = 'voided'
        self.assert_approval_refused(reg_id, "status is 'voided'")

    def test_refuses_when_moyasar_is_unreachable(self):
        reg_id = self.registered_and_paid()
        with mock.patch.object(moyasar, 'fetch_payment', side_effect=moyasar.MoyasarUnavailable('down')):
            with self.assertRaises((ValueError, moyasar.MoyasarUnavailable)):
                approve_registration(self.reg(reg_id))
        self.assertIsNone(self.reg(reg_id).created_user_id)

    def test_approves_a_verified_payment(self):
        reg_id = self.registered_and_paid()
        user = approve_registration(self.reg(reg_id))
        self.assertEqual(Membership.objects.get(member=user).iqama_number, IQAMA)
        self.assertEqual(self.reg(reg_id).status, R.STATUS_APPROVED)


@override_settings(MOYASAR_SECRET_KEY='sk_test_dummy', MOYASAR_API_URL='https://api.moyasar.test/v1')
class FetchPaymentTests(SimpleTestCase):
    """The real HTTP client — urlopen is mocked, nothing leaves the machine."""

    def test_sends_a_user_agent(self):
        # Cloudflare in front of Moyasar 403s Python's default "Python-urllib" agent (error 1010).
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"id": "p1"}'
        with mock.patch.object(moyasar.urllib.request, 'urlopen', return_value=response) as urlopen:
            self.assertEqual(moyasar.fetch_payment('p1'), {'id': 'p1'})
        request = urlopen.call_args[0][0]
        self.assertEqual(request.get_header('User-agent'), moyasar.USER_AGENT)
        self.assertTrue(request.get_header('Authorization').startswith('Basic '))

    def test_auth_rejection_is_reported_as_unavailable(self):
        error = urllib.error.HTTPError('u', 403, 'Forbidden', {}, io.BytesIO(b'{"type":"error 1010"}'))
        with mock.patch.object(moyasar.urllib.request, 'urlopen', side_effect=error):
            with self.assertLogs('apps.public_api.moyasar', 'ERROR') as logs:
                with self.assertRaises(moyasar.MoyasarUnavailable):
                    moyasar.fetch_payment('p1')
        self.assertIn('rejected the request', logs.output[0])
