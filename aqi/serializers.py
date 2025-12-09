"""
Serializers for AQI data requests and responses
"""
from rest_framework import serializers
from typing import List, Dict, Any
from .models import CitySubscription


class AQIRequestSerializer(serializers.Serializer):
    """Serializer for AQI fetch request"""
    lat = serializers.FloatField(
        required=True,
        min_value=-90,
        max_value=90,
        help_text="Latitude coordinate (-90 to 90)"
    )
    lon = serializers.FloatField(
        required=True,
        min_value=-180,
        max_value=180,
        help_text="Longitude coordinate (-180 to 180)"
    )
    type = serializers.ChoiceField(
        choices=['current', 'hourly', 'daily'],
        default='current',
        required=False,
        help_text="Type of AQI data to fetch"
    )
    hours = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=240,
        default=24,
        help_text="Number of hours for hourly forecast (1-240)"
    )
    days = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=16,
        default=7,
        help_text="Number of days for daily forecast (1-16)"
    )


class CoordinatesRequestSerializer(serializers.Serializer):
    """Serializer for coordinate-based AQI request"""
    lat = serializers.FloatField(
        required=True,
        min_value=-90,
        max_value=90
    )
    lng = serializers.FloatField(
        required=True,
        min_value=-180,
        max_value=180
    )


class LocationSerializer(serializers.Serializer):
    """Serializer for location in batch requests"""
    lat = serializers.FloatField(
        required=True,
        min_value=-90,
        max_value=90
    )
    lng = serializers.FloatField(
        required=True,
        min_value=-180,
        max_value=180
    )
    city = serializers.CharField(required=False, allow_blank=True)
    area = serializers.CharField(required=False, allow_blank=True)


class BatchLocationSerializer(serializers.Serializer):
    """Serializer for batch AQI request"""
    locations = serializers.ListField(
        child=LocationSerializer(),
        min_length=1,
        max_length=50,  # Limit batch size
        help_text="List of locations to fetch AQI for"
    )


class CityRequestSerializer(serializers.Serializer):
    """Serializer for city-based AQI request"""
    city = serializers.CharField(
        required=True,
        max_length=200,
        help_text="City name"
    )


# Response serializers (for documentation, actual responses are Dict)
class PollutantDataSerializer(serializers.Serializer):
    """Serializer for pollutant data"""
    value = serializers.FloatField(allow_null=True)
    unit = serializers.CharField(allow_null=True)
    epa_aqi = serializers.IntegerField(allow_null=True, required=False)
    category = serializers.CharField(allow_null=True, required=False)
    color = serializers.CharField(allow_null=True, required=False)


class AQIIndexSerializer(serializers.Serializer):
    """Serializer for AQI index"""
    value = serializers.IntegerField(allow_null=True)
    category = serializers.CharField(allow_null=True)
    color = serializers.CharField(allow_null=True)


class EnhancedAQIResponseSerializer(serializers.Serializer):
    """Serializer for enhanced AQI response structure"""
    location = serializers.DictField()
    timezone = serializers.CharField()
    aqi = serializers.DictField()
    pollutants = serializers.DictField(child=PollutantDataSerializer())
    dominant_pollutant = serializers.CharField(allow_null=True)
    health_recommendations = serializers.ListField(child=serializers.CharField())
    lastUpdated = serializers.CharField()
    current = serializers.DictField(required=False)
    hourly = serializers.DictField(required=False)


class CityRankingSerializer(serializers.Serializer):
    """Serializer for city ranking data"""
    rank = serializers.IntegerField()
    city = serializers.CharField()
    country = serializers.CharField()
    aqi = serializers.IntegerField()
    category = serializers.CharField()
    dominantPollutant = serializers.CharField()
    trend = serializers.ListField(child=serializers.DictField())
    lastUpdated = serializers.CharField()
    region = serializers.CharField(required=False)
    pm25 = serializers.FloatField(allow_null=True, required=False)
    pm10 = serializers.FloatField(allow_null=True, required=False)
    aqi_pm25 = serializers.IntegerField(allow_null=True, required=False)
    aqi_pm10 = serializers.IntegerField(allow_null=True, required=False)


class CitySubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for city subscription model"""
    
    class Meta:
        model = CitySubscription
        fields = ['id', 'city', 'country', 'latitude', 'longitude', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        """Validate subscription data"""
        # Validate required fields
        city = attrs.get('city', '').strip()
        country = attrs.get('country', '').strip() if attrs.get('country') else ''
        latitude = attrs.get('latitude')
        longitude = attrs.get('longitude')
        
        if not city:
            raise serializers.ValidationError({'city': 'City name is required'})
        
        if not country:
            raise serializers.ValidationError({'country': 'Country name is required'})
        
        # Validate coordinate ranges
        if latitude is not None:
            if latitude < -90 or latitude > 90:
                raise serializers.ValidationError({'latitude': 'Latitude must be between -90 and 90'})
        
        if longitude is not None:
            if longitude < -180 or longitude > 180:
                raise serializers.ValidationError({'longitude': 'Longitude must be between -180 and 180'})
        
        # Check if subscription already exists for this user
        user = self.context['request'].user
        
        if self.instance is None:  # Creating new subscription
            existing = CitySubscription.objects.filter(
                user=user,
                city=city,
                country=country
            )
            if existing.exists():
                raise serializers.ValidationError(
                    {'non_field_errors': [f"You are already subscribed to {city}, {country}"]}
                )
        
        # Update attrs with cleaned values
        attrs['city'] = city
        attrs['country'] = country
        
        return attrs
    
    def create(self, validated_data):
        """Create subscription for the current user"""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

