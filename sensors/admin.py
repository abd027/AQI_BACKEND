from django.contrib import admin
from .models import MQTTBrokerConfig, SensorReading


@admin.register(MQTTBrokerConfig)
class MQTTBrokerConfigAdmin(admin.ModelAdmin):
    list_display = ('user', 'host', 'port', 'topic', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__email', 'user__username', 'host', 'topic')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('User', {'fields': ('user',)}),
        ('Connection Settings', {'fields': ('host', 'port', 'topic', 'client_id')}),
        ('Authentication', {'fields': ('username', 'password')}),
        ('Status', {'fields': ('is_active',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ('user', 'received_at', 'temperature', 'humidity', 'co_ppm', 'calculated_aqi', 'aqi_category', 'dominant_pollutant')
    list_filter = ('aqi_category', 'dominant_pollutant', 'received_at')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('received_at',)
    date_hierarchy = 'received_at'
    fieldsets = (
        ('User', {'fields': ('user',)}),
        ('Sensor Data', {'fields': ('temperature', 'humidity', 'co_ppm', 'co2_ppm', 'ch4_ppm')}),
        ('AQI Calculation', {'fields': ('calculated_aqi', 'aqi_category', 'aqi_color', 'dominant_pollutant')}),
        ('Raw Data', {'fields': ('data',)}),
        ('Timestamp', {'fields': ('received_at',)}),
    )


