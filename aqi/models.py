"""
Optional models for AQI app (saved locations, etc.)
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class SavedLocation(models.Model):
    """
    User's saved locations for quick AQI access
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_locations'
    )
    name = models.CharField(max_length=200)
    latitude = models.FloatField()
    longitude = models.FloatField()
    city = models.CharField(max_length=200, blank=True, null=True)
    country = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'saved_locations'
        unique_together = ['user', 'latitude', 'longitude']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.user.email})"


class AQINotification(models.Model):
    """
    Track AQI email notifications sent to users
    Prevents duplicate notifications for the same city on the same day
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='aqi_notifications'
    )
    saved_location = models.ForeignKey(
        SavedLocation,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    aqi_value = models.FloatField(help_text="AQI value when notification was sent")
    date = models.DateField(default=timezone.now, help_text="Date of notification (for daily deduplication)")
    notified_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when notification was sent")
    
    class Meta:
        db_table = 'aqi_notifications'
        unique_together = ['user', 'saved_location', 'date']
        ordering = ['-notified_at']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.saved_location.name} ({self.date}) - AQI: {self.aqi_value}"


class CitySubscription(models.Model):
    """
    User's city subscriptions for AQI email notifications
    Separate from SavedLocation to manage email notification preferences
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='city_subscriptions'
    )
    city = models.CharField(max_length=200)
    country = models.CharField(max_length=200, blank=True, null=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    is_active = models.BooleanField(default=True, help_text="Whether to send email notifications for this city")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'city_subscriptions'
        unique_together = ['user', 'city', 'country']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.user.email} - {self.city}, {self.country} ({status})"