"""
Tests for AQI service methods
"""
import pytest
import responses
from unittest.mock import patch, MagicMock
from aqi.services import OpenMeteoAQIService
from tests.utils.test_helpers import (
    mock_open_meteo_current_response,
    mock_open_meteo_hourly_response
)


@pytest.mark.django_db
@pytest.mark.aqi
class TestOpenMeteoAQIService:
    """Test OpenMeteoAQIService methods"""
    
    @responses.activate
    def test_fetch_hourly_aqi(self):
        """Test fetching hourly AQI data"""
        mock_response = mock_open_meteo_hourly_response(hours=24)
        responses.add(
            responses.GET,
            'https://air-quality-api.open-meteo.com/v1/air-quality',
            json=mock_response,
            status=200,
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        
        service = OpenMeteoAQIService()
        result = service.fetch_hourly_aqi(40.7128, -74.0060, hours=24)
        
        assert result is not None
        assert 'hourly' in result or 'location' in result
    
    @responses.activate
    def test_fetch_daily_aqi(self):
        """Test fetching daily AQI data"""
        mock_response = mock_open_meteo_current_response()
        responses.add(
            responses.GET,
            'https://air-quality-api.open-meteo.com/v1/air-quality',
            json=mock_response,
            status=200,
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        
        service = OpenMeteoAQIService()
        result = service.fetch_daily_aqi(40.7128, -74.0060, days=7)
        
        assert result is not None
    
    @responses.activate
    def test_fetch_batch_current_aqi(self):
        """Test batch fetching current AQI for multiple locations"""
        mock_response = mock_open_meteo_current_response()
        responses.add(
            responses.GET,
            'https://air-quality-api.open-meteo.com/v1/air-quality',
            json=mock_response,
            status=200,
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        
        service = OpenMeteoAQIService()
        locations = [
            {'lat': 40.7128, 'lon': -74.0060},
            {'lat': 51.5074, 'lon': -0.1278}
        ]
        result = service.fetch_batch_current_aqi(locations)
        
        assert result is not None
        assert isinstance(result, list)
    
    @responses.activate
    def test_fetch_enhanced_aqi(self):
        """Test fetching enhanced AQI (which uses current + hourly)"""
        mock_current = mock_open_meteo_current_response()
        mock_hourly = mock_open_meteo_hourly_response()
        
        # Mock both current and hourly endpoints
        responses.add(
            responses.GET,
            'https://air-quality-api.open-meteo.com/v1/air-quality',
            json=mock_current,
            status=200,
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        responses.add(
            responses.GET,
            'https://air-quality-api.open-meteo.com/v1/air-quality',
            json=mock_hourly,
            status=200,
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        # Mock weather API call
        responses.add(
            responses.GET,
            'https://api.open-meteo.com/v1/forecast',
            json={'current': {'temperature_2m': 20.0, 'relative_humidity_2m': 65, 'wind_speed_10m': 5.0}},
            status=200,
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        
        service = OpenMeteoAQIService()
        result = service.fetch_enhanced_aqi(40.7128, -74.0060)
        
        assert result is not None
        assert isinstance(result, dict)
    
    @responses.activate
    def test_fetch_current_aqi_with_retry(self):
        """Test fetch_current_aqi with retry logic on 429 error"""
        # First request returns 429, second succeeds
        responses.add(
            responses.GET,
            'https://air-quality-api.open-meteo.com/v1/air-quality',
            json={'error': 'Rate limited'},
            status=429,
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        responses.add(
            responses.GET,
            'https://air-quality-api.open-meteo.com/v1/air-quality',
            json=mock_open_meteo_current_response(),
            status=200,
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        # Mock weather API call
        responses.add(
            responses.GET,
            'https://api.open-meteo.com/v1/forecast',
            json={'current': {'temperature_2m': 20.0, 'relative_humidity_2m': 65, 'wind_speed_10m': 5.0}},
            status=200,
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        
        service = OpenMeteoAQIService()
        result = service.fetch_current_aqi(40.7128, -74.0060)
        
        # Should retry and eventually succeed
        assert result is not None
    
    @responses.activate
    def test_fetch_current_aqi_timeout(self):
        """Test fetch_current_aqi handles timeout"""
        import requests
        responses.add(
            responses.GET,
            'https://air-quality-api.open-meteo.com/v1/air-quality',
            body=requests.exceptions.Timeout('Request timeout'),
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        
        service = OpenMeteoAQIService()
        result = service.fetch_current_aqi(40.7128, -74.0060)
        
        # Should return None on timeout after retries
        assert result is None
    
    @responses.activate
    def test_fetch_enhanced_aqi_with_hourly_failure(self):
        """Test fetch_enhanced_aqi continues when hourly fetch fails"""
        mock_current = mock_open_meteo_current_response()
        
        responses.add(
            responses.GET,
            'https://air-quality-api.open-meteo.com/v1/air-quality',
            json=mock_current,
            status=200,
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        # Hourly request fails
        responses.add(
            responses.GET,
            'https://air-quality-api.open-meteo.com/v1/air-quality',
            json={'error': 'Not found'},
            status=404,
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        # Mock weather API call
        responses.add(
            responses.GET,
            'https://api.open-meteo.com/v1/forecast',
            json={'current': {'temperature_2m': 20.0, 'relative_humidity_2m': 65, 'wind_speed_10m': 5.0}},
            status=200,
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        
        service = OpenMeteoAQIService()
        result = service.fetch_enhanced_aqi(40.7128, -74.0060)
        
        # Should still return data based on current AQI
        assert result is not None
    
    @responses.activate
    def test_format_current_response(self):
        """Test _format_current_response method"""
        # Mock weather API and reverse geocoding
        responses.add(
            responses.GET,
            'https://api.open-meteo.com/v1/forecast',
            json={'current': {'temperature_2m': 20.0, 'relative_humidity_2m': 65, 'wind_speed_10m': 5.0}},
            status=200,
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        
        service = OpenMeteoAQIService()
        mock_data = {
            'current': {
                'pm2_5': 12.5,
                'pm10': 25.0,
                'ozone': 45.0
            },
            'timezone': 'America/New_York'
        }
        
        result = service._format_current_response(mock_data, 40.7128, -74.0060)
        
        assert result is not None
        assert 'location' in result
        assert 'aqi' in result or 'pollutants' in result
    
    def test_format_hourly_response(self):
        """Test _format_hourly_response method"""
        service = OpenMeteoAQIService()
        mock_data = {
            'hourly': {
                'time': ['2025-12-09T00:00', '2025-12-09T01:00'],
                'pm2_5': [12.5, 13.0],
                'pm10': [25.0, 26.0]
            },
            'timezone': 'America/New_York'
        }
        
        result = service._format_hourly_response(mock_data, 40.7128, -74.0060)
        
        assert result is not None
        assert 'hourly' in result or 'location' in result
    
    def test_format_daily_response(self):
        """Test _format_daily_response method"""
        service = OpenMeteoAQIService()
        mock_data = {
            'daily': {
                'time': ['2025-12-09', '2025-12-10'],
                'pm2_5': [12.5, 13.0]
            },
            'timezone': 'America/New_York'
        }
        
        result = service._format_daily_response(mock_data, 40.7128, -74.0060)
        
        assert result is not None
        assert 'daily' in result or 'location' in result
    
    @responses.activate
    def test_fetch_weather_data(self):
        """Test fetch_weather_data uses throttled request method"""
        responses.add(
            responses.GET,
            'https://api.open-meteo.com/v1/forecast',
            json={'current': {'temperature_2m': 20.0, 'relative_humidity_2m': 65, 'wind_speed_10m': 5.0}},
            status=200,
            match=[responses.matchers.header_matcher({'User-Agent': 'BreatheEasy-AQI-App/1.0'})]
        )
        
        service = OpenMeteoAQIService()
        result = service.fetch_weather_data(40.7128, -74.0060)
        
        assert result is not None
        assert 'temperature' in result
        assert 'humidity' in result
        assert 'wind' in result
    
    def test_adaptive_throttling(self):
        """Test adaptive throttling mechanism"""
        service = OpenMeteoAQIService()
        initial_interval = service._min_request_interval
        
        # Simulate rate limit - should increase interval
        service._adjust_throttle_interval(increase=True)
        assert service._min_request_interval > initial_interval
        
        # Simulate success - should gradually decrease
        service._adjust_throttle_interval(increase=False)
        assert service._min_request_interval >= initial_interval

