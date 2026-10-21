from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ('member', 'Member'),
        ('trainer', 'Trainer'),
        ('nutritionist', 'Nutritionist'),
        ('receptionist', 'Receptionist'),
        ('manager', 'Branch Manager'),
        ('admin', 'Super Admin'),
    ]

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    # Set when an account is given a temporary password (registration approval).
    # While True the API only allows changing the password (see accounts.authentication).
    # db_default so code deployed before this column existed can still insert users.
    must_change_password = models.BooleanField(default=False, db_default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"

    # ⬇️ ADD THIS PROPERTY
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    @property
    def is_staff_member(self):
        return self.role in ['admin', 'manager']

    @property
    def is_member(self):
        return self.role == 'member'

class RateEvent(models.Model):
    """
    One counted event for rate limits that must hold across serverless instances
    (failed logins, website signups). Old rows are pruned as new ones are written.
    """
    kind = models.CharField(max_length=20)
    key = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'rate_events'
        indexes = [models.Index(fields=['kind', 'key', 'created_at'])]
