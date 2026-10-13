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