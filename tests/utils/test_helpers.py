"""
Test helper functions and utilities
"""
from typing import Dict, Any, Optional
from accounts.models import User
from aqi.models import SavedLocation
from rest_framework_simplejwt.tokens import RefreshToken


def create_test_user(
    email: str = 'test@example.com',
    username: str = 'testuser',
    password: str = 'testpass123',
    is_verified: bool = False,
    is_active: bool = True,
    **kwargs
) -> User:
    """
    Create a test user
    
    Args:
        email: User email
        username: Username
        password: User password
        is_verified: Whether user is verified
        is_active: Whether user is active
        **kwargs: Additional user fields
        
    Returns:
        Created User instance
    """
    return User.objects.create_user(
        email=email,
        username=username,
        password=password,
        is_verified=is_verified,
        is_active=is_active,
        **kwargs
    )


def get_auth_headers(token: str) -> Dict[str, str]:
    """
    Get authorization headers for API requests
    
    Args:
        token: JWT access token
        
    Returns:
        Dictionary with Authorization header
    """
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


def get_auth_token(user: User) -> str:
    """
    Get JWT access token for a user
    
    Args:
        user: User instance
        
    Returns:
        JWT access token string
    """
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


def create_saved_location(
    user: User,
    name: str = 'Test Location',
    latitude: float = 40.7128,
    longitude: float = -74.0060,
    city: Optional[str] = None,
    country: Optional[str] = None,
    **kwargs
) -> SavedLocation:
    """
    Create a saved location for testing
    
    Args:
        user: User instance
        name: Location name
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        city: City name (optional)
        country: Country name (optional)
        **kwargs: Additional location fields
        
    Returns:
        Created SavedLocation instance
    """
    return SavedLocation.objects.create(
        user=user,
        name=name,
        latitude=latitude,
        longitude=longitude,
        city=city or name,
        country=country,
        **kwargs
    )


def mock_open_meteo_current_response(
    latitude: float = 40.7128,
    longitude: float = -74.0060,
    pm25: float = 12.5,
    pm10: float = 25.0,
    **kwargs
) -> Dict[str, Any]:
    """
    Create a mock Open-Meteo current AQI API response
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        pm25: PM2.5 value
        pm10: PM10 value
        **kwargs: Additional pollutant values
        
    Returns:
        Mock API response dictionary
    """
    return {
        'latitude': latitude,
        'longitude': longitude,
        'generationtime_ms': 0.234,
        'utc_offset_seconds': -18000,
        'timezone': 'America/New_York',
        'timezone_abbreviation': 'EST',
        'elevation': 10.0,
        'current': {
            'time': '2025-12-09T00:00',
            'interval': 3600,
            'pm2_5': pm25,
            'pm10': pm10,
            'carbon_monoxide': kwargs.get('carbon_monoxide', 250.0),
            'nitrogen_dioxide': kwargs.get('nitrogen_dioxide', 30.0),
            'sulphur_dioxide': kwargs.get('sulphur_dioxide', 5.0),
            'ozone': kwargs.get('ozone', 45.0),
            'dust': kwargs.get('dust', 0.5),
            'uv_index': kwargs.get('uv_index', 2.0),
            'us_aqi': kwargs.get('us_aqi', 45),
            'european_aqi': kwargs.get('european_aqi', 30),
        },
        'current_units': {
            'time': 'iso8601',
            'interval': 'seconds',
            'pm2_5': 'µg/m³',
            'pm10': 'µg/m³',
            'carbon_monoxide': 'µg/m³',
            'nitrogen_dioxide': 'µg/m³',
            'sulphur_dioxide': 'µg/m³',
            'ozone': 'µg/m³',
            'dust': 'µg/m³',
            'uv_index': '',
        }
    }


def mock_open_meteo_hourly_response(
    latitude: float = 40.7128,
    longitude: float = -74.0060,
    hours: int = 24
) -> Dict[str, Any]:
    """
    Create a mock Open-Meteo hourly AQI API response
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        hours: Number of hours to include
        
    Returns:
        Mock hourly API response dictionary
    """
    times = [f'2025-12-09T{i:02d}:00' for i in range(hours)]
    pm25_values = [12.5 + (i * 0.1) for i in range(hours)]
    pm10_values = [25.0 + (i * 0.2) for i in range(hours)]
    
    return {
        'latitude': latitude,
        'longitude': longitude,
        'generationtime_ms': 0.234,
        'utc_offset_seconds': -18000,
        'timezone': 'America/New_York',
        'timezone_abbreviation': 'EST',
        'elevation': 10.0,
        'hourly': {
            'time': times,
            'pm2_5': pm25_values,
            'pm10': pm10_values,
            'carbon_monoxide': [250.0 + (i * 0.5) for i in range(hours)],
            'nitrogen_dioxide': [30.0 + (i * 0.1) for i in range(hours)],
            'sulphur_dioxide': [5.0 + (i * 0.05) for i in range(hours)],
            'ozone': [45.0 + (i * 0.2) for i in range(hours)],
        },
        'hourly_units': {
            'time': 'iso8601',
            'pm2_5': 'µg/m³',
            'pm10': 'µg/m³',
            'carbon_monoxide': 'µg/m³',
            'nitrogen_dioxide': 'µg/m³',
            'sulphur_dioxide': 'µg/m³',
            'ozone': 'µg/m³',
        }
    }


def mock_geocode_response(
    city: str = 'New York',
    country: str = 'United States',
    latitude: float = 40.7128,
    longitude: float = -74.0060
) -> Dict[str, Any]:
    """
    Create a mock geocoding response
    
    Args:
        city: City name
        country: Country name
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        
    Returns:
        Mock geocoding response dictionary
    """
    return {
        'city': city,
        'country': country,
        'state': None,
        'lat': latitude,
        'lon': longitude
    }

