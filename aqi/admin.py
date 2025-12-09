"""
Admin configuration for AQI app
"""
from django.contrib import admin
from .models import SavedLocation


@admin.register(SavedLocation)
class SavedLocationAdmin(admin.ModelAdmin):
    """Admin for SavedLocation model"""
    list_display = ('name', 'user', 'city', 'country', 'latitude', 'longitude', 'created_at')
    list_filter = ('country', 'created_at')
    search_fields = ('name', 'city', 'country', 'user__email', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
