"""
Public API test suite — payments (Moyasar), gate face checks, check-in.

Run (Command Prompt, from the backend folder):
    venv\\Scripts\\python.exe manage.py test apps.public_api -v 2

Moyasar is never called: tests replace fetch_payment with an in-memory fake.
"""
from django.conf import settings

# Test discovery imports this package before Django creates the test database,
# so this stops a run that would create test_<db> on the production server.
if 'sqlite' not in settings.DATABASES['default']['ENGINE']:
    raise RuntimeError(
        'Refusing to run tests against a non-SQLite DATABASE_URL '
        f"({settings.DATABASES['default']['ENGINE']}). Use DATABASE_URL=sqlite:///db.sqlite3."
    )
