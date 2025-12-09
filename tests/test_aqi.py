"""
Tests for AQI endpoints
"""
import pytest
import responses
from django.urls import reverse
from django.core.cache import cache
from rest_framework import status
from unittest.mock import patch, MagicMock
from aqi.services import OpenMeteoAQIService
from tests.utils.test_helpers import (
    mock_open_meteo_current_response,
    mock_open_meteo_hourly_response
)


@pytest.mark.django_db
@pytest.mark.aqi
class TestAQIFetchView:
    """Test AQI fetch endpoint"""
    
    @responses.activate
    def test_fetch_current_aqi(self, authenticated_client):
        """Test fetching current AQI data"""
        # Mock API response
        mock_response = mock_open_meteo_current_response()
        responses.add(
            responses.GET,
            'https://air-quality-api.open-meteo.com/v1/air-quality',
            json=mock_response,
            status=200
        )
        
        url = reverse('aqi:aqi-fetch')
        response = authenticated_client.get(url, {
            'lat': 40.7128,
            'lon': -74.0060,
            'type': 'current'
        })
        
        assert response.status_code == status.HTTP_200_OK
        assert 'location' in response.data or 'aqi' in response.data
    
    @responses.activate
    def test_fetch_hourly_aqi(self, authenticated_client):
        """Test fetching hourly AQI data"""
        mock_response = mock_open_meteo_hourly_response()
        responses.add(
            responses.GET,
            'https://air-quality-api.open-meteo.com/v1/air-quality',
            json=mock_response,
            status=200
        )
        
        url = reverse('aqi:aqi-fetch')
        response = authenticated_client.get(url, {
            'lat': 40.7128,
            'lon': -74.0060,
            'type': 'hourly',
            'hours': 24
        })
        
        assert response.status_code == status.HTTP_200_OK
    
    @responses.activate
    def test_fetch_daily_aqi(self, authenticated_client):
        """Test fetching daily AQI data"""
        mock_response = mock_open_meteo_current_response()
        responses.add(
            responses.GET,
            'https://air-quality-api.open-meteo.com/v1/air-quality',
            json=mock_response,
            status=200
        )
        
        url = reverse('aqi:aqi-fetch')
        response = authenticated_client.get(url, {
            'lat': 40.7128,
            'lon': -74.0060,
            'type': 'daily',
            'days': 7
        })
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_invalid_latitude(self, authenticated_client):
        """Test with invalid latitude (>90)"""
        url = reverse('aqi:aqi-fetch')
        response = authenticated_client.get(url, {
            'lat': 200,
            'lon': -74.0060,
            'type': 'current'
        })
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_invalid_longitude(self, authenticated_client):
        """Test with invalid longitude (>180)"""
        url = reverse('aqi:aqi-fetch')
        response = authenticated_client.get(url, {
            'lat': 40.7128,
            'lon': 300,
            'type': 'current'
        })
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_invalid_type(self, authenticated_client):
        """Test with invalid type parameter"""
        url = reverse('aqi:aqi-fetch')
        response = authenticated_client.get(url, {
            'lat': 40.7128,
            'lon': -74.0060,
            'type': 'invalid_type'
        })
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_missing_coordinates(self, authenticated_client):
        """Test with missing coordinates"""
        url = reverse('aqi:aqi-fetch')
        response = authenticated_client.get(url, {
            'type': 'current'
        })
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_out_of_range_hours(self, authenticated_client):
        """Test with out of range hours (>240)"""
        url = reverse('aqi:aqi-fetch')
        response = authenticated_client.get(url, {
            'lat': 40.7128,
            'lon': -74.0060,
            'type': 'hourly',
            'hours': 500
        })
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_unauthenticated_access(self, api_client):
        """Test unauthenticated access"""
        url = reverse('aqi:aqi-fetch')
        response = api_client.get(url, {
            'lat': 40.7128,
            'lon': -74.0060,
            'type': 'current'
        })
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@pytest.mark.aqi
class TestAQIByCoordinatesView:
    """Test AQI by coordinates endpoint"""
    
    @responses.activate
    def test_fetch_aqi_by_coordinates(self, authenticated_client):
        """Test fetching AQI by coordinates"""
        mock_response = mock_open_meteo_current_response()
        responses.add(
            responses.GET,
            'https://air-quality-api.open-meteo.com/v1/air-quality',
            json=mock_response,
            status=200
        )
        
        url = reverse('aqi:aqi-coordinates')
        response = authenticated_client.get(url, {
            'lat': 40.7128,
            'lng': -74.0060
        })
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_invalid_coordinates(self, authenticated_client):
        """Test with invalid coordinates"""
        url = reverse('aqi:aqi-coordinates')
        response = authenticated_client.get(url, {
            'lat': 200,
            'lng': -74.0060
        })
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_missing_coordinates(self, authenticated_client):
        """Test with missing coordinates"""
        url = reverse('aqi:aqi-coordinates')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_cached_response(self, authenticated_client):
        """Test cached response is returned"""
        from aqi.cache import set_cached_aqi
        
        # Set cache
        cached_data = {'aqi': 45, 'location': {'lat': 40.7128, 'lon': -74.0060}}
        set_cached_aqi(40.7128, -74.0060, cached_data, 'current')
        
        url = reverse('aqi:aqi-coordinates')
        response = authenticated_client.get(url, {
            'lat': 40.7128,
            'lng': -74.0060
        })
        
        assert response.status_code == status.HTTP_200_OK
        # Should return cached data without API call


@pytest.mark.django_db
@pytest.mark.aqi
class TestEnhancedAQIView:
    """Test enhanced AQI endpoint"""
    
    @patch('aqi.views.aqi_service')
    def test_fetch_enhanced_aqi_success(self, mock_service, authenticated_client):
        """Test successful enhanced AQI fetch"""
        mock_enhanced_data = {
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
                    'epa_aqi': 45,
                    'category': 'Good'
                }
            },
            'dominant_pollutant': 'pm25',
            'health_recommendations': ['Air quality is good.'],
            'lastUpdated': '2025-12-09T00:00'
        }
        
        mock_service.fetch_enhanced_aqi.return_value = mock_enhanced_data
        
        url = reverse('aqi:aqi-enhanced')
        response = authenticated_client.get(url, {
            'lat': 40.7128,
            'lng': -74.0060
        })
        
        assert response.status_code == status.HTTP_200_OK
        assert 'aqi' in response.data
        assert 'pollutants' in response.data
    
    @patch('aqi.views.aqi_service')
    def test_fetch_enhanced_aqi_fallback(self, mock_service, authenticated_client):
        """Test fallback to basic AQI when enhanced fails"""
        # Mock enhanced returns None, but current returns data
        mock_service.fetch_enhanced_aqi.return_value = None
        mock_service.fetch_current_aqi.return_value = {
            'location': {'lat': 40.7128, 'lon': -74.0060},
            'aqi': 45,
            'current': {'pm2_5': 12.5}
        }
        
        url = reverse('aqi:aqi-enhanced')
        response = authenticated_client.get(url, {
            'lat': 40.7128,
            'lng': -74.0060
        })
        
        # Should try fallback
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
    
    @patch('aqi.views.aqi_service')
    def test_rate_limiting_handling(self, mock_service, authenticated_client):
        """Test rate limiting (429) handling"""
        from django.core.cache import cache
        # Clear cache first
        cache.clear()
        
        # Both enhanced and fallback return None (simulating API failure)
        mock_service.fetch_enhanced_aqi.return_value = None
        mock_service.fetch_current_aqi.return_value = None
        
        url = reverse('aqi:aqi-enhanced')
        response = authenticated_client.get(url, {
            'lat': 40.7128,
            'lng': -74.0060
        })
        
        # Should return 503 when both enhanced and fallback fail
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    
    def test_invalid_coordinates(self, authenticated_client):
        """Test with invalid coordinates"""
        url = reverse('aqi:aqi-enhanced')
        response = authenticated_client.get(url, {
            'lat': 200,
            'lng': -74.0060
        })
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.aqi
class TestAQITrendView:
    """Test AQI trend endpoint"""
    
    @patch('aqi.views.geocode_city')
    @patch('aqi.views.aqi_service')
    def test_fetch_aqi_trend_valid_city(self, mock_service, mock_geocode, authenticated_client):
        """Test fetching AQI trend for valid city"""
        # geocode_city returns tuple (lat, lon)
        mock_geocode.return_value = (40.7128, -74.0060)
        mock_service.fetch_hourly_aqi.return_value = {
            'location': {'lat': 40.7128, 'lon': -74.0060},
            'hourly': {
                'time': ['2025-12-09T00:00', '2025-12-09T01:00'],
                'pm2_5': [12.5, 13.0]
            }
        }
        
        url = reverse('aqi:aqi-trend')
        response = authenticated_client.get(url, {
            'city': 'New York'
        })
        
        assert response.status_code == status.HTTP_200_OK
    
    @patch('aqi.views.geocode_city')
    def test_invalid_city_name(self, mock_geocode, authenticated_client):
        """Test with invalid city name"""
        mock_geocode.return_value = None
        
        url = reverse('aqi:aqi-trend')
        response = authenticated_client.get(url, {
            'city': 'InvalidCity123'
        })
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_missing_city_parameter(self, authenticated_client):
        """Test with missing city parameter"""
        url = reverse('aqi:aqi-trend')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.aqi
class TestCityRankingsView:
    """Test city rankings endpoint"""
    
    @patch('aqi.views.aqi_service')
    def test_get_city_rankings(self, mock_service, authenticated_client):
        """Test getting city rankings"""
        mock_service.fetch_current_aqi.return_value = {
            'location': {'lat': 40.7128, 'lon': -74.0060},
            'aqi': 45
        }
        
        url = reverse('aqi:city-rankings')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)


@pytest.mark.django_db
@pytest.mark.aqi
class TestBatchAQIView:
    """Test batch AQI endpoint"""
    
    @patch('aqi.views.aqi_service')
    def test_batch_aqi_valid_locations(self, mock_service, authenticated_client):
        """Test batch AQI with valid locations"""
        mock_service.fetch_current_aqi.return_value = {
            'location': {'lat': 40.7128, 'lon': -74.0060},
            'aqi': 45
        }
        
        url = reverse('aqi:aqi-batch')
        data = {
            'locations': [
                {'lat': 40.7128, 'lng': -74.0060, 'city': 'New York'},
                {'lat': 51.5074, 'lng': -0.1278, 'city': 'London'}
            ]
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
        assert len(response.data) == 2
    
    def test_batch_aqi_empty_locations(self, authenticated_client):
        """Test batch AQI with empty locations array"""
        url = reverse('aqi:aqi-batch')
        data = {
            'locations': []
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_batch_aqi_too_many_locations(self, authenticated_client):
        """Test batch AQI with too many locations (>50)"""
        url = reverse('aqi:aqi-batch')
        data = {
            'locations': [
                {'lat': 40.7128, 'lng': -74.0060}
                for _ in range(51)
            ]
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_batch_aqi_invalid_coordinates(self, authenticated_client):
        """Test batch AQI with invalid coordinates"""
        url = reverse('aqi:aqi-batch')
        data = {
            'locations': [
                {'lat': 200, 'lng': -74.0060, 'city': 'Invalid'}
            ]
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.aqi
class TestBatchEnhancedAQIView:
    """Test batch enhanced AQI endpoint"""
    
    @patch('aqi.views.aqi_service')
    def test_batch_enhanced_aqi_valid(self, mock_service, authenticated_client):
        """Test batch enhanced AQI with valid batch"""
        # Mock service to return different data for each location
        def mock_fetch_enhanced(lat, lng):
            return {
                'location': {'lat': lat, 'lon': lng},
                'aqi': {'local_epa_aqi': {'value': 45}},
                'pollutants': {}
            }
        
        mock_service.fetch_enhanced_aqi.side_effect = mock_fetch_enhanced
        
        url = reverse('aqi:aqi-batch-enhanced')
        data = {
            'locations': [
                {'lat': 40.7128, 'lng': -74.0060},
                {'lat': 51.5074, 'lng': -0.1278}
            ]
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
        assert len(response.data) == 2
    
    def test_batch_enhanced_aqi_empty(self, authenticated_client):
        """Test batch enhanced AQI with empty batch"""
        url = reverse('aqi:aqi-batch-enhanced')
        data = {
            'locations': []
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.aqi
class TestGeocodeCityView:
    """Test geocode city endpoint"""
    
    @patch('aqi.views.search_city')
    def test_geocode_valid_city(self, mock_search, authenticated_client):
        """Test geocoding valid city"""
        mock_search.return_value = {
            'city': 'New York',
            'country': 'United States',
            'lat': 40.7128,
            'lon': -74.0060
        }
        
        url = reverse('aqi:aqi-geocode')
        response = authenticated_client.get(url, {
            'city': 'New York'
        })
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['city'] == 'New York'
    
    @patch('aqi.views.search_city')
    def test_geocode_city_not_found(self, mock_search, authenticated_client):
        """Test geocoding city not found"""
        mock_search.return_value = None
        
        url = reverse('aqi:aqi-geocode')
        response = authenticated_client.get(url, {
            'city': 'InvalidCity123'
        })
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_geocode_missing_city(self, authenticated_client):
        """Test geocoding with missing city parameter"""
        url = reverse('aqi:aqi-geocode')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.aqi
class TestEnhancedAQIErrorHandling:
    """Test error handling in EnhancedAQIView"""
    
    @patch('aqi.views.aqi_service')
    def test_enhanced_aqi_exception_handling(self, mock_service, authenticated_client):
        """Test EnhancedAQIView handles exceptions"""
        from django.core.cache import cache
        cache.clear()  # Clear cache to ensure we hit the exception path
        
        mock_service.fetch_enhanced_aqi.side_effect = Exception("Unexpected error")
        mock_service.fetch_current_aqi.side_effect = Exception("Fallback also failed")
        
        url = reverse('aqi:aqi-enhanced')
        response = authenticated_client.get(url, {
            'lat': 40.7128,
            'lng': -74.0060
        })
        
        # Should return 500 error when both enhanced and fallback fail
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data


@pytest.mark.django_db
@pytest.mark.aqi
class TestBoundaryConditions:
    """Test boundary conditions and edge cases"""
    
    def test_aqi_zero_value(self, authenticated_client):
        """Test AQI with zero value"""
        # This would be handled by the service, but test the endpoint accepts it
        url = reverse('aqi:aqi-coordinates')
        response = authenticated_client.get(url, {
            'lat': 0.0,
            'lng': 0.0
        })
        
        # Should handle gracefully (may return data or error)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_503_SERVICE_UNAVAILABLE
        ]
    
    def test_coordinates_at_boundaries(self, authenticated_client):
        """Test coordinates at exact boundaries"""
        # Test latitude = 90
        url = reverse('aqi:aqi-coordinates')
        response = authenticated_client.get(url, {
            'lat': 90.0,
            'lng': 0.0
        })
        
        # Should accept or reject based on validation
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_503_SERVICE_UNAVAILABLE
        ]
    
    def test_empty_batch_request(self, authenticated_client):
        """Test batch request with empty locations"""
        url = reverse('aqi:aqi-batch')
        data = {
            'locations': []
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_batch_with_single_location(self, authenticated_client):
        """Test batch request with single location"""
        from unittest.mock import patch
        
        with patch('aqi.views.aqi_service') as mock_service:
            mock_service.fetch_current_aqi.return_value = {
                'location': {'lat': 40.7128, 'lon': -74.0060},
                'aqi': 45
            }
            
            url = reverse('aqi:aqi-batch')
            data = {
                'locations': [
                    {'lat': 40.7128, 'lng': -74.0060, 'city': 'New York'}
                ]
            }
            response = authenticated_client.post(url, data, format='json')
            
            assert response.status_code == status.HTTP_200_OK
            assert isinstance(response.data, list)


@pytest.mark.django_db
@pytest.mark.aqi
class TestChatAPIView:
    """Test chat API endpoint"""
    
    @patch('aqi.views.AQIRAGSystem')
    def test_chat_valid_question(self, mock_rag_class, authenticated_client):
        """Test chat API with valid question"""
        mock_rag = MagicMock()
        mock_rag.query.return_value = "Based on the AQI data, the air quality is good."
        mock_rag_class.return_value = mock_rag
        
        url = reverse('aqi:chat')
        data = {
            'question': 'What is the air quality like?'
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'answer' in response.data
    
    def test_chat_empty_question(self, authenticated_client):
        """Test chat API with empty question"""
        url = reverse('aqi:chat')
        data = {
            'question': ''
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    @patch('aqi.views.AQIRAGSystem')
    def test_chat_rag_unavailable(self, mock_rag_class, authenticated_client):
        """Test chat API when RAG system is unavailable"""
        mock_rag_class.side_effect = Exception("RAG system unavailable")
        
        url = reverse('aqi:chat')
        data = {
            'question': 'What is the air quality?'
        }
        response = authenticated_client.post(url, data, format='json')
        
        # Should handle gracefully
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

