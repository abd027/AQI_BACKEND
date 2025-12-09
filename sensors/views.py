"""
API views for sensor data and MQTT configuration
"""
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import SensorReading, MQTTBrokerConfig
from .serializers import SensorReadingSerializer, MQTTBrokerConfigSerializer


class SensorReadingListView(generics.ListAPIView):
    """
    GET /api/sensor-readings/
    
    List sensor readings for the authenticated user
    Returns readings ordered by received_at descending
    """
    serializer_class = SensorReadingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return sensor readings for the current user only"""
        return SensorReading.objects.filter(user=self.request.user).order_by('-received_at')


class MQTTBrokerConfigView(generics.RetrieveUpdateAPIView):
    """
    GET /api/mqtt-config/ - Retrieve current user's MQTT broker configuration
    PUT /api/mqtt-config/ - Update current user's MQTT broker configuration
    PATCH /api/mqtt-config/ - Partially update current user's MQTT broker configuration
    
    Creates default configuration if none exists for the user
    """
    serializer_class = MQTTBrokerConfigSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        """
        Get or create MQTT broker configuration for the current user
        """
        config, created = MQTTBrokerConfig.objects.get_or_create(
            user=self.request.user,
            defaults={
                'host': '127.0.0.1',
                'port': 1883,
                'topic': 'sensor/data',
                'is_active': True,
            }
        )
        return config
    
    def update(self, request, *args, **kwargs):
        """
        Update MQTT broker configuration
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(serializer.data)
    
    def perform_update(self, serializer):
        """Save the updated configuration"""
        serializer.save()


