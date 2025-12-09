"""
URL configuration for sensors app
"""
from django.urls import path
from .views import SensorReadingListView, MQTTBrokerConfigView

app_name = 'sensors'

urlpatterns = [
    path('sensor-readings/', SensorReadingListView.as_view(), name='sensor-readings-list'),
    path('mqtt-config/', MQTTBrokerConfigView.as_view(), name='mqtt-config'),
]


