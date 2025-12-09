"""
Custom User model with role-based access control
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
import secrets
import uuid


class UserManager(BaseUserManager):
    """Custom user manager"""
    
    def create_user(self, email, username, password=None, **extra_fields):
        """Create and save a regular user"""
        if not email:
            raise ValueError('The Email field must be set')
        if not username:
            raise ValueError('The Username field must be set')
        
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, username, password=None, **extra_fields):
        """Create and save a superuser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model with role-based access control
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('admin', 'Admin'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=150, unique=True, db_index=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    
    # Email verification
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=64, blank=True, null=True)
    verification_token_created = models.DateTimeField(blank=True, null=True)
    
    # Password reset
    password_reset_token = models.CharField(max_length=64, blank=True, null=True)
    password_reset_expires = models.DateTimeField(blank=True, null=True)
    
    # Django auth fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'user'
        verbose_name_plural = 'users'
    
    def __str__(self):
        return self.email
    
    def generate_verification_token(self):
        """Generate a verification token"""
        token = secrets.token_urlsafe(32)
        self.verification_token = token
        self.verification_token_created = timezone.now()
        self.save(update_fields=['verification_token', 'verification_token_created'])
        return token
    
    def generate_password_reset_token(self):
        """Generate a password reset token (valid for 1 hour)"""
        token = secrets.token_urlsafe(32)
        self.password_reset_token = token
        self.password_reset_expires = timezone.now() + timezone.timedelta(hours=1)
        self.save(update_fields=['password_reset_token', 'password_reset_expires'])
        return token
    
    def is_password_reset_token_valid(self, token):
        """Check if password reset token is valid"""
        if not self.password_reset_token or not self.password_reset_expires:
            return False
        if self.password_reset_token != token:
            return False
        if timezone.now() > self.password_reset_expires:
            return False
        return True
    
    def clear_password_reset_token(self):
        """Clear password reset token after use"""
        self.password_reset_token = None
        self.password_reset_expires = None
        self.save(update_fields=['password_reset_token', 'password_reset_expires'])
