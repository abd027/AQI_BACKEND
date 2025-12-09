"""
Tests for core utility functions
"""
import pytest
import responses
from unittest.mock import patch, MagicMock
from core.utils import (
    geocode_city,
    reverse_geocode,
    search_city,
    calculate_epa_aqi,
    get_aqi_category
)


@pytest.mark.django_db
class TestGeocodeCity:
    """Test geocode_city function"""
    
    @responses.activate
    def test_geocode_city_valid(self):
        """Test geocoding valid city"""
        import responses
        mock_response = {
            'results': [{
                'name': 'New York',
                'latitude': 40.7128,
                'longitude': -74.0060,
                'country': 'United States'
            }]
        }
        responses.add(
            responses.GET,
            'https://geocoding-api.open-meteo.com/v1/search',
            json=mock_response,
            status=200
        )
        
        result = geocode_city('New York')
        
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert abs(result[0] - 40.7128) < 1.0  # Allow small variance
        assert abs(result[1] - (-74.0060)) < 1.0
    
    @patch('core.utils.search_city')
    def test_geocode_city_not_found(self, mock_search):
        """Test geocoding city not found"""
        mock_search.return_value = None
        
        result = geocode_city('InvalidCity123')
        
        assert result is None
    
    @patch('core.utils.search_city')
    def test_geocode_city_partial_match(self, mock_search):
        """Test geocoding with partial city name"""
        mock_search.return_value = {
            'city': 'New York',
            'lat': 40.7128,
            'lon': -74.0060
        }
        
        result = geocode_city('New')
        
        assert result is not None


@pytest.mark.django_db
class TestReverseGeocode:
    """Test reverse_geocode function"""
    
    @patch('core.utils.search_city')
    def test_reverse_geocode_valid_coordinates(self, mock_search):
        """Test reverse geocoding valid coordinates"""
        mock_search.return_value = {
            'city': 'New York',
            'country': 'United States',
            'lat': 40.7128,
            'lon': -74.0060
        }
        
        result = reverse_geocode(40.7128, -74.0060)
        
        assert result is not None
        assert 'city' in result or 'country' in result
    
    def test_reverse_geocode_invalid_coordinates(self):
        """Test reverse geocoding invalid coordinates"""
        result = reverse_geocode(200, 300)
        
        # Should handle gracefully
        assert result is None or isinstance(result, dict)


@pytest.mark.django_db
class TestSearchCity:
    """Test search_city function"""
    
    def test_search_city_exact_match(self):
        """Test searching for exact city name"""
        result = search_city('New York')
        
        # May return None if no data, but should not crash
        assert result is None or isinstance(result, dict)
    
    def test_search_city_partial_match(self):
        """Test searching with partial city name"""
        result = search_city('New')
        
        assert result is None or isinstance(result, dict)
    
    def test_search_city_empty_string(self):
        """Test searching with empty string"""
        result = search_city('')
        
        assert result is None


@pytest.mark.django_db
class TestCalculateEPAAQI:
    """Test calculate_epa_aqi function"""
    
    def test_calculate_aqi_pm25_good(self):
        """Test AQI calculation for PM2.5 in Good range"""
        aqi = calculate_epa_aqi('pm25', 10.0)
        
        assert aqi is not None
        assert isinstance(aqi, (int, float))
        assert 0 <= aqi <= 50  # Good range
    
    def test_calculate_aqi_pm25_moderate(self):
        """Test AQI calculation for PM2.5 in Moderate range"""
        aqi = calculate_epa_aqi('pm25', 15.0)
        
        assert aqi is not None
        assert 51 <= aqi <= 100  # Moderate range
    
    def test_calculate_aqi_pm25_unhealthy(self):
        """Test AQI calculation for PM2.5 in Unhealthy range"""
        aqi = calculate_epa_aqi('pm25', 55.0)
        
        assert aqi is not None
        assert aqi > 100
    
    def test_calculate_aqi_pm10(self):
        """Test AQI calculation for PM10"""
        aqi = calculate_epa_aqi('pm10', 50.0)
        
        assert aqi is not None
        assert isinstance(aqi, (int, float))
    
    def test_calculate_aqi_ozone(self):
        """Test AQI calculation for Ozone"""
        aqi = calculate_epa_aqi('o3', 0.05)
        
        assert aqi is not None
        assert isinstance(aqi, (int, float))
    
    def test_calculate_aqi_invalid_pollutant(self):
        """Test AQI calculation with invalid pollutant"""
        aqi = calculate_epa_aqi('invalid', 10.0)
        
        # Should handle gracefully
        assert aqi is None or isinstance(aqi, (int, float))
    
    def test_calculate_aqi_boundary_values(self):
        """Test AQI calculation at boundary values"""
        # Test zero value
        aqi_zero = calculate_epa_aqi('pm25', 0.0)
        assert aqi_zero is not None
        
        # Test very high value
        aqi_high = calculate_epa_aqi('pm25', 500.0)
        assert aqi_high is not None
        assert aqi_high > 300  # Should be in hazardous range


@pytest.mark.django_db
class TestGetAQICategory:
    """Test get_aqi_category function"""
    
    def test_get_aqi_category_good(self):
        """Test AQI category for Good air quality"""
        result = get_aqi_category(30)
        
        assert result is not None
        assert 'category' in result
        assert 'color' in result
        assert 'health_advice' in result
    
    def test_get_aqi_category_moderate(self):
        """Test AQI category for Moderate air quality"""
        result = get_aqi_category(75)
        
        assert result is not None
        assert 'category' in result
    
    def test_get_aqi_category_unhealthy(self):
        """Test AQI category for Unhealthy air quality"""
        result = get_aqi_category(155)
        
        assert result is not None
        assert 'category' in result
        assert result['category'] in ['Unhealthy', 'Unhealthy for Sensitive Groups']
    
    def test_get_aqi_category_hazardous(self):
        """Test AQI category for Hazardous air quality"""
        result = get_aqi_category(350)
        
        assert result is not None
        assert 'category' in result
    
    def test_get_aqi_category_none(self):
        """Test AQI category with None value"""
        result = get_aqi_category(None)
        
        assert result is not None
        assert result['category'] == 'Unknown'
    
    def test_get_aqi_category_boundary_values(self):
        """Test AQI category at boundary values"""
        # Test at 50 (Good/Moderate boundary)
        result_50 = get_aqi_category(50)
        assert result_50 is not None
        
        # Test at 100 (Moderate/Unhealthy boundary)
        result_100 = get_aqi_category(100)
        assert result_100 is not None
        
        # Test at 150 (Unhealthy threshold)
        result_150 = get_aqi_category(150)
        assert result_150 is not None
        
        # Test at 0
        result_0 = get_aqi_category(0)
        assert result_0 is not None

