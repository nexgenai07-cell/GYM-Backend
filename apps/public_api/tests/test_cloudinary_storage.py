"""Cloudinary media storage — Cloudinary's upload/destroy are mocked, nothing leaves the machine."""
import re
from unittest import mock

from django.core.files.base import ContentFile
from django.test import SimpleTestCase, override_settings

from apps.core import storage as cloud
from apps.core.storage import CloudinaryMediaStorage
from apps.members.models import MembershipRegistration as R

from .test_payments import PaymentTestBase
from .faces import one_face

# Test photos have no real face — stub the detector to find one well-placed face.
_faces = one_face()


def setUpModule():
    _faces.start()


def tearDownModule():
    _faces.stop()

CLOUD = dict(
    CLOUDINARY_CLOUD_NAME='demo', CLOUDINARY_API_KEY='123', CLOUDINARY_API_SECRET='abc',
    CLOUDINARY_FOLDER='smart-gym', CLOUDINARY_DELIVERY_TYPE='authenticated',
)
CLOUD_STORAGES = {
    'default': {'BACKEND': 'apps.core.storage.CloudinaryMediaStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


@override_settings(**CLOUD)
class StorageUnitTests(SimpleTestCase):
    def setUp(self):
        self.upload = mock.patch.object(cloud.cloudinary.uploader, 'upload', return_value={}).start()
        self.destroy = mock.patch.object(cloud.cloudinary.uploader, 'destroy', return_value={'result': 'ok'}).start()
        self.addCleanup(mock.patch.stopall)
        self.s = CloudinaryMediaStorage()

    def test_save_uploads_privately_under_the_folder(self):
        name = self.s.save('registrations/2026/10/live-photo.jpg', ContentFile(b'jpeg-bytes'))
        self.assertRegex(name, r'^registrations/2026/10/live-photo_[0-9a-f]{8}\.jpg$')
        kwargs = self.upload.call_args.kwargs
        self.assertEqual(kwargs['public_id'], 'smart-gym/' + name[:-len('.jpg')])
        self.assertEqual(kwargs['type'], 'authenticated')
        self.assertEqual(kwargs['resource_type'], 'image')
        self.assertFalse(kwargs['overwrite'])

    def test_every_save_gets_a_unique_name_without_asking_cloudinary(self):
        a = self.s.save('avatars/me.png', ContentFile(b'1'))
        b = self.s.save('avatars/me.png', ContentFile(b'2'))
        self.assertNotEqual(a, b)
        self.assertFalse(self.s.exists(a))   # no Admin API lookups

    def test_url_is_signed_and_private(self):
        url = self.s.url('registrations/2026/10/live-photo_ab12cd34.jpg')
        self.assertTrue(url.startswith('https://res.cloudinary.com/demo/image/authenticated/'))
        self.assertRegex(url, r'/s--[^/]+--/')                                  # signature
        self.assertTrue(url.endswith('/smart-gym/registrations/2026/10/live-photo_ab12cd34.jpg'))

    def test_delete_destroys_the_same_public_id(self):
        self.s.delete('avatars/me_ab12cd34.png')
        self.destroy.assert_called_once_with(
            'smart-gym/avatars/me_ab12cd34', resource_type='image', type='authenticated', invalidate=True,
        )

    @override_settings(CLOUDINARY_DELIVERY_TYPE='upload')
    def test_public_mode_gives_unsigned_urls(self):
        url = CloudinaryMediaStorage().url('avatars/me_ab12cd34.png')
        self.assertIn('/image/upload/', url)
        self.assertNotRegex(url, r'/s--[^/]+--/')

    def test_windows_backslash_paths_become_slashes(self):
        name = self.s.save('registrations\\2026\\10\\live.jpg', ContentFile(b'x'))
        self.assertRegex(name, r'^registrations/2026/10/live_[0-9a-f]{8}\.jpg$')
        self.assertNotIn('\\', self.upload.call_args.kwargs['public_id'])
        self.assertNotIn('\\', self.s.url('registrations\\2026\\10\\live_ab12cd34.jpg'))

    def test_long_names_are_trimmed_to_max_length(self):
        name = self.s.get_available_name('avatars/' + 'x' * 120 + '.png', max_length=100)
        self.assertLessEqual(len(name), 100)
        self.assertTrue(name.endswith('.png'))


@override_settings(STORAGES=CLOUD_STORAGES, **CLOUD)
class SignupPhotoOnCloudinaryTests(PaymentTestBase):
    """End to end through the API with Cloudinary as the default storage."""

    def setUp(self):
        super().setUp()
        self.upload = mock.patch.object(cloud.cloudinary.uploader, 'upload', return_value={}).start()
        self.destroy = mock.patch.object(cloud.cloudinary.uploader, 'destroy', return_value={'result': 'ok'}).start()

    def test_signup_photo_is_uploaded_and_served_by_signed_url(self):
        reg = self.reg(self.register().data['id'])
        self.upload.assert_called_once()
        self.assertTrue(reg.photo.name.startswith('registrations/'), reg.photo.name)
        self.assertIn('/image/authenticated/s--', reg.photo.url)

    def test_admin_and_gate_get_the_cloudinary_url(self):
        reg_id = self.registered_and_paid()
        from apps.members.services import approve_registration
        from django.contrib.auth import get_user_model
        approve_registration(self.reg(reg_id))
        staff = get_user_model().objects.create_user(username='s', email='s@t.local', password='x', is_staff=True)
        self.client.force_authenticate(staff)
        detail = self.client.get(f'/api/admin/registrations-api/registrations/{reg_id}/').data
        self.assertTrue(detail['photo_url'].startswith('https://res.cloudinary.com/demo/image/authenticated/'))
        lookup = self.client.get('/api/admin/registrations-api/members/lookup/', {'iqama': '2999888777'}).data
        self.assertTrue(lookup['registration_photo_url'].startswith('https://res.cloudinary.com/'))

    def test_resubmitting_replaces_and_deletes_the_old_photo(self):
        reg_id = self.register().data['id']
        old = self.reg(reg_id).photo.name
        self.register()   # unpaid → same registration, new photo
        new = self.reg(reg_id).photo.name
        self.assertNotEqual(old, new)
        self.destroy.assert_called_once()
        self.assertEqual(self.destroy.call_args.args[0], 'smart-gym/' + re.sub(r'\.\w+$', '', old))
