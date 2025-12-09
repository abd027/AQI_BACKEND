"""
WebSocket URL routing for AQI app
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/aqi/live/$', consumers.AQILiveDataConsumer.as_asgi()),
]


