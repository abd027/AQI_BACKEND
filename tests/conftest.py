"""
Pytest configuration and shared fixtures
"""
import pytest
from django.test import Client
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import User
from aqi.models import SavedLocation, AQINotification
import responses


@pytest.fixture
def api_client():
    """Create an API client for testing"""
    return APIClient()


@pytest.fixture
def test_user(db):
    """Create a test user"""
    return User.objects.create_user(
        email='test@example.com',
        username='testuser',
        password='testpass123',
        is_active=True,
        is_verified=False
    )


@pytest.fixture
def verified_user(db):
    """Create a verified test user"""
    return User.objects.create_user(
        email='verified@example.com',
        username='verifieduser',
        password='testpass123',
        is_active=True,
        is_verified=True
    )


@pytest.fixture
def inactive_user(db):
    """Create an inactive test user"""
    return User.objects.create_user(
        email='inactive@example.com',
        username='inactiveuser',
        password='testpass123',
        is_active=False,
        is_verified=False
    )


@pytest.fixture
def authenticated_client(api_client, test_user):
    """Create an authenticated API client"""
    refresh = RefreshToken.for_user(test_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.fixture
def authenticated_verified_client(api_client, verified_user):
    """Create an authenticated API client with verified user"""
    refresh = RefreshToken.for_user(verified_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.fixture
def mock_open_meteo_current_response():
    """Mock response for Open-Meteo current AQI API"""
    return {
        'latitude': 40.7128,
        'longitude': -74.0060,
        'generationtime_ms': 0.234,
        'utc_offset_seconds': -18000,
        'timezone': 'America/New_York',
        'timezone_abbreviation': 'EST',
        'elevation': 10.0,
        'current': {
            'time': '2025-12-09T00:00',
            'interval': 3600,
            'pm2_5': 12.5,
            'pm10': 25.0,
            'carbon_monoxide': 250.0,
            'nitrogen_dioxide': 30.0,
            'sulphur_dioxide': 5.0,
            'ozone': 45.0,
            'dust': 0.5,
            'uv_index': 2.0,
            'us_aqi': 45,
            'european_aqi': 30,
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


@pytest.fixture
def mock_open_meteo_hourly_response():
    """Mock response for Open-Meteo hourly AQI API"""
    return {
        'latitude': 40.7128,
        'longitude': -74.0060,
        'generationtime_ms': 0.234,
        'utc_offset_seconds': -18000,
        'timezone': 'America/New_York',
        'timezone_abbreviation': 'EST',
        'elevation': 10.0,
        'hourly': {
            'time': ['2025-12-09T00:00', '2025-12-09T01:00', '2025-12-09T02:00'],
            'pm2_5': [12.5, 13.0, 12.8],
            'pm10': [25.0, 26.0, 25.5],
            'carbon_monoxide': [250.0, 255.0, 252.0],
            'nitrogen_dioxide': [30.0, 32.0, 31.0],
            'sulphur_dioxide': [5.0, 5.5, 5.2],
            'ozone': [45.0, 46.0, 45.5],
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


@pytest.fixture
def mock_geocode_response():
    """Mock response for geocoding service"""
    return {
        'city': 'New York',
        'country': 'United States',
        'state': 'New York',
        'lat': 40.7128,
        'lon': -74.0060
    }


@pytest.fixture
def saved_location(test_user, db):
    """Create a saved location for test user"""
    return SavedLocation.objects.create(
        user=test_user,
        name='New York',
        latitude=40.7128,
        longitude=-74.0060,
        city='New York',
        country='United States'
    )


@pytest.fixture
def saved_location_karachi(test_user, db):
    """Create a saved location in Karachi"""
    return SavedLocation.objects.create(
        user=test_user,
        name='Karachi',
        latitude=24.8607,
        longitude=67.0011,
        city='Karachi',
        country='Pakistan'
    )


@pytest.fixture
def aqi_notification(test_user, saved_location, db):
    """Create an AQI notification"""
    from django.utils import timezone
    return AQINotification.objects.create(
        user=test_user,
        saved_location=saved_location,
        aqi_value=155,
        date=timezone.now().date()
    )


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Enable database access for all tests"""
    pass


@pytest.fixture
def mock_aqi_service(mocker):
    """Mock the OpenMeteoAQIService"""
    from aqi.services import OpenMeteoAQIService
    
    mock_service = mocker.Mock(spec=OpenMeteoAQIService)
    
    # Mock current AQI response
    mock_current_data = {
        'location': {'lat': 40.7128, 'lon': -74.0060},
        'timezone': 'America/New_York',
        'aqi': 45,
        'current': {
            'time': '2025-12-09T00:00',
            'pm2_5': 12.5,
            'pm10': 25.0,
            'ozone': 45.0,
            'nitrogen_dioxide': 30.0,
            'sulphur_dioxide': 5.0,
            'carbon_monoxide': 250.0,
        },
        'dominant_pollutant': 'pm2_5',
        'lastUpdated': '2025-12-09T00:00'
    }
    
    mock_service.fetch_current_aqi.return_value = mock_current_data
    mock_service.fetch_hourly_aqi.return_value = {
        'hourly': {
            'time': ['2025-12-09T00:00', '2025-12-09T01:00'],
            'pm2_5': [12.5, 13.0],
            'pm10': [25.0, 26.0],
        }
    }
    mock_service.fetch_enhanced_aqi.return_value = {
        'location': {'lat': 40.7128, 'lon': -74.0060},
        'timezone': 'America/New_York',
        'aqi': {
            'local_epa_aqi': {
                'value': 45,
                'category': 'Good',
                'color': '#00E400'
            }
        },
        'pollutants': {
            'pm25': {
                'value': 12.5,
                'unit': 'µg/m³',
                'epa_aqi': 45,
                'category': 'Good',
                'color': '#00E400'
            }
        },
        'dominant_pollutant': 'pm25',
        'health_recommendations': ['Air quality is good.'],
        'lastUpdated': '2025-12-09T00:00'
    }
    
    return mock_service

