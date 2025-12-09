"""
Serializers for sensor data and MQTT configuration
"""
from rest_framework import serializers
from .models import SensorReading, MQTTBrokerConfig


class SensorReadingSerializer(serializers.ModelSerializer):
    """
    Serializer for sensor reading data (read-only)
    """
    
    class Meta:
        model = SensorReading
        fields = [
            'id',
            'user',
            'received_at',
            'data',
            'temperature',
            'humidity',
            'co_ppm',
            'co2_ppm',
            'ch4_ppm',
            'calculated_aqi',
            'aqi_category',
            'aqi_color',
            'dominant_pollutant',
        ]
        read_only_fields = fields


class MQTTBrokerConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for MQTT broker configuration
    Password is masked in responses for security
    """
    password = serializers.SerializerMethodField()
    
    class Meta:
        model = MQTTBrokerConfig
        fields = [
            'id',
            'user',
            'host',
            'port',
            'topic',
            'username',
            'password',
            'client_id',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def get_password(self, obj):
        """
        Mask password in responses - return None if password exists, empty string if not
        """
        if obj.password:
            return '***'  # Masked password indicator
        return None
    
    def validate(self, attrs):
        """
        Validate required fields
        """
        host = attrs.get('host', '').strip()
        port = attrs.get('port')
        topic = attrs.get('topic', '').strip()
        
        if not host:
            raise serializers.ValidationError({'host': 'Host is required'})
        
        if port is None:
            raise serializers.ValidationError({'port': 'Port is required'})
        
        if port < 1 or port > 65535:
            raise serializers.ValidationError({'port': 'Port must be between 1 and 65535'})
        
        if not topic:
            raise serializers.ValidationError({'topic': 'Topic is required'})
        
        return attrs
    
    def create(self, validated_data):
        """
        Create MQTT config for the current user
        """
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """
        Update MQTT config - handle password update specially
        If password is '***' or empty, don't update it
        """
        # If password is provided and not masked, update it
        # If password is '***' (masked), don't update it
        password = validated_data.get('password')
        if password == '***' or password == '':
            validated_data.pop('password', None)
        
        return super().update(instance, validated_data)


