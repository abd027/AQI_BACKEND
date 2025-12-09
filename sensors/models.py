"""
Sensor data models for MQTT integration
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class MQTTBrokerConfig(models.Model):
    """
    Per-user MQTT broker configuration
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mqtt_config',
        unique=True
    )
    host = models.CharField(max_length=255, default='127.0.0.1', help_text='MQTT broker host/IP address')
    port = models.IntegerField(default=1883, help_text='MQTT broker port')
    topic = models.CharField(max_length=255, default='sensor/data', help_text='MQTT topic to subscribe to')
    username = models.CharField(max_length=255, blank=True, null=True, help_text='MQTT username (optional)')
    password = models.CharField(max_length=255, blank=True, null=True, help_text='MQTT password (optional)')
    client_id = models.CharField(max_length=255, blank=True, null=True, help_text='MQTT client ID (optional)')
    is_active = models.BooleanField(default=True, help_text='Whether this configuration is active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'mqtt_broker_configs'
        verbose_name = 'MQTT Broker Configuration'
        verbose_name_plural = 'MQTT Broker Configurations'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.host}:{self.port}/{self.topic}"


class SensorReading(models.Model):
    """
    Sensor reading data from MQTT
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sensor_readings',
        null=True,
        blank=True,
        help_text='User who owns this sensor reading'
    )
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Raw sensor data stored as JSON
    data = models.JSONField(null=True, blank=True, help_text='Raw sensor payload from MQTT')
    
    # Extracted sensor values
    temperature = models.FloatField(null=True, blank=True, help_text='Temperature in Celsius (from temp_c)')
    humidity = models.FloatField(null=True, blank=True, help_text='Humidity percentage')
    co_ppm = models.FloatField(null=True, blank=True, help_text='Carbon Monoxide in ppm (from mq7_co)')
    co2_ppm = models.FloatField(null=True, blank=True, help_text='Carbon Dioxide in ppm (from mq135_co2)')
    ch4_ppm = models.FloatField(null=True, blank=True, help_text='Methane in ppm (from mq4_ch4)')
    
    # Calculated AQI values
    calculated_aqi = models.IntegerField(null=True, blank=True, db_index=True, help_text='Calculated AQI value')
    aqi_category = models.CharField(max_length=50, null=True, blank=True, help_text='AQI category (Good, Moderate, etc.)')
    aqi_color = models.CharField(max_length=20, null=True, blank=True, help_text='AQI color code')
    dominant_pollutant = models.CharField(max_length=20, null=True, blank=True, help_text='Dominant pollutant used for AQI calculation')
    
    class Meta:
        db_table = 'sensor_readings'
        verbose_name = 'Sensor Reading'
        verbose_name_plural = 'Sensor Readings'
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['user', 'received_at']),
            models.Index(fields=['received_at']),
            models.Index(fields=['calculated_aqi']),
        ]
    
    def __str__(self):
        aqi_str = f"AQI: {self.calculated_aqi}" if self.calculated_aqi else "No AQI"
        return f"{self.user.email if self.user else 'Unknown'} - {self.received_at} - {aqi_str}"


