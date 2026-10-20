"""Admin-managed lists (facilities, articles) — public API, admin CRUD, validation."""
from django.contrib.auth import get_user_model

from apps.site_content.models import SiteItem
from apps.site_content.seeding import seed_collections

from .test_site_content import ContentTestBase, png

User = get_user_model()
ADMIN = '/api/admin/site-content/collections'
PUBLIC = '/api/public/collections'


def facility(**over):
    data = {'title': {'en': 'Sauna', 'ar': 'ساونا'}, 'category': 'recovery', 'status_tone': 'ok',
            'stat1_label': {'en': 'TEMP', 'ar': 'الحرارة'}, 'stat1_value': '90°C'}
    data.update(over)
    return data


class SeededCollectionTests(ContentTestBase):
    def test_shipped_facilities_and_articles(self):
        facilities = self.client.get(f'{PUBLIC}/facilities/').data
        self.assertEqual(len(facilities), 6)
        self.assertEqual(facilities[0]['data']['title']['en'], 'Olympic Swimming Pool')
        self.assertEqual(facilities[0]['data']['category'], 'aquatics')
        self.assertTrue(facilities[0]['image_url'].startswith('https://'))
        articles = self.client.get(f'{PUBLIC}/articles/').data
        self.assertEqual(len(articles), 5)
        self.assertNotIn('body', articles[0]['data'])              # list stays light
        self.assertTrue(articles[0]['slug'])
        self.assertEqual(articles[0]['data']['published'], '2026-10-24')

    def test_article_page_by_slug(self):
        slug = self.client.get(f'{PUBLIC}/articles/').data[0]['slug']
        r = self.client.get(f'{PUBLIC}/articles/{slug}/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('body', r.data['data'])
        self.assertEqual(self.client.get(f'{PUBLIC}/articles/no-such-post/').status_code, 404)
        self.assertEqual(self.client.get(f'{PUBLIC}/nope/').status_code, 404)

    def test_reseed_does_not_bring_back_deleted_items(self):
        SiteItem.objects.filter(collection='facilities').first().delete()
        self.assertEqual(seed_collections(SiteItem), 0)
        self.assertEqual(SiteItem.objects.filter(collection='facilities').count(), 5)


class AdminCollectionTests(ContentTestBase):
    def setUp(self):
        super().setUp()
        self.as_admin()

    def test_schemas_for_the_admin_form(self):
        cols = {c['name']: c for c in self.client.get(f'{ADMIN}/').data}
        self.assertEqual(cols['facilities']['count'], 6)
        title = next(fd for fd in cols['articles']['fields'] if fd['name'] == 'title')
        self.assertTrue(title['i18n'] and title['required'])
        self.assertTrue(cols['articles']['has_slug'])

    def test_create_appears_last_on_the_public_site(self):
        r = self.client.post(f'{ADMIN}/facilities/items/', {'data': facility()}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['order'], 7)
        public = self.client.get(f'{PUBLIC}/facilities/').data
        self.assertEqual(public[-1]['data']['title'], {'en': 'Sauna', 'ar': 'ساونا'})
        self.assertEqual(public[-1]['data']['stat2_value'], '')      # unspecified fields filled empty

    def test_article_gets_a_unique_slug(self):
        body = {'data': {'title': {'en': 'Deload Weeks', 'ar': ''}, 'category': 'training', 'published': '2026-11-01'}}
        a = self.client.post(f'{ADMIN}/articles/items/', body, format='json').data
        b = self.client.post(f'{ADMIN}/articles/items/', body, format='json').data
        self.assertEqual((a['slug'], b['slug']), ('deload-weeks', 'deload-weeks-2'))

    def test_validation_errors_per_field(self):
        r = self.client.post(f'{ADMIN}/facilities/items/', {'data': {
            'title': {'en': '', 'ar': 'x'}, 'category': 'spa', 'status_tone': 'ok', 'bogus': 1,
        }}, format='json')
        self.assertEqual(r.status_code, 400)
        errors = r.data['data']
        self.assertIn('Required', errors['title'])
        self.assertIn('Choose one of', errors['category'])
        self.assertEqual(errors['bogus'], 'Unknown field.')
        r = self.client.post(f'{ADMIN}/articles/items/', {'data': {
            'title': {'en': 'X'}, 'category': 'training', 'published': '24/10/2026', 'read_minutes': 'six',
        }}, format='json')
        self.assertIn('YYYY-MM-DD', r.data['data']['published'])
        self.assertIn('whole number', r.data['data']['read_minutes'])

    def test_patch_changes_only_the_fields_sent_and_keeps_the_slug(self):
        item = SiteItem.objects.filter(collection='articles').first()
        slug, category = item.slug, item.data['category']
        r = self.client.patch(f'{ADMIN}/articles/items/{item.pk}/',
                              {'data': {'title': {'en': 'New title', 'ar': 'عنوان'}}}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['data']['title']['en'], 'New title')
        self.assertEqual(r.data['data']['category'], category)
        self.assertEqual(r.data['slug'], slug)                         # links don't break
        other = SiteItem.objects.filter(collection='articles').exclude(pk=item.pk).first()
        self.assertEqual(self.client.patch(f'{ADMIN}/articles/items/{item.pk}/', {'slug': other.slug},
                                           format='json').status_code, 400)

    def test_hidden_items_leave_the_public_site(self):
        item = SiteItem.objects.filter(collection='facilities').first()
        self.client.patch(f'{ADMIN}/facilities/items/{item.pk}/', {'is_active': False}, format='json')
        public_ids = [i['id'] for i in self.client.get(f'{PUBLIC}/facilities/').data]
        self.assertNotIn(item.pk, public_ids)
        self.assertEqual(len(self.client.get(f'{ADMIN}/facilities/items/').data), 6)   # admin still sees it

    def test_reorder(self):
        ids = [i['id'] for i in self.client.get(f'{ADMIN}/facilities/items/').data][::-1]
        r = self.client.post(f'{ADMIN}/facilities/reorder/', {'ids': ids}, format='json')
        self.assertEqual([i['id'] for i in r.data], ids)
        self.assertEqual([i['id'] for i in self.client.get(f'{PUBLIC}/facilities/').data], ids)
        self.assertEqual(self.client.post(f'{ADMIN}/facilities/reorder/', {'ids': ids[:2]}, format='json').status_code, 400)

    def test_image_upload_reset_and_delete(self):
        item = SiteItem.objects.filter(collection='facilities').first()
        seeded = item.default_image_url
        r = self.client.post(f'{ADMIN}/facilities/items/{item.pk}/image/', {'image': png()}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotEqual(r.data['image_url'], seeded)
        item.refresh_from_db()
        storage, name = item.image.storage, item.image.name
        r = self.client.post(f'{ADMIN}/facilities/items/{item.pk}/image/reset/')
        self.assertEqual(r.data['image_url'], seeded)
        self.assertFalse(storage.exists(name))
        self.client.post(f'{ADMIN}/facilities/items/{item.pk}/image/', {'image': png()}, format='multipart')
        item.refresh_from_db()
        name = item.image.name
        self.assertEqual(self.client.delete(f'{ADMIN}/facilities/items/{item.pk}/').status_code, 204)
        self.assertFalse(storage.exists(name))

    def test_members_cannot_edit(self):
        member = User.objects.create_user(username='m', email='m@t.local', password='x')
        self.client.force_authenticate(member)
        self.assertEqual(self.client.post(f'{ADMIN}/facilities/items/', {'data': facility()}, format='json').status_code, 403)
