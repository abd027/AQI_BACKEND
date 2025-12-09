"""
Integration tests for AQI endpoints using real API calls
These tests make actual HTTP requests to external APIs and should be skipped in CI/CD
"""
import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
@pytest.mark.integration
@pytest.mark.aqi
class TestAQIIntegration:
    """Integration tests with real API calls"""
    
    def test_real_api_call_enhanced_aqi(self, authenticated_client):
        """Test real API call to Open-Meteo for enhanced AQI"""
        url = reverse('aqi:aqi-enhanced')
        response = authenticated_client.get(url, {
            'lat': 40.7128,
            'lng': -74.0060
        })
        
        # May succeed or fail depending on API availability and rate limits
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            status.HTTP_429_TOO_MANY_REQUESTS
        ]
    
    def test_real_api_call_coordinates(self, authenticated_client):
        """Test real API call for coordinates lookup"""
        url = reverse('aqi:aqi-coordinates')
        response = authenticated_client.get(url, {
            'lat': 24.8607,
            'lng': 67.0011  # Karachi
        })
        
        # May succeed or fail depending on API availability
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            status.HTTP_429_TOO_MANY_REQUESTS
        ]
    
    def test_real_api_call_city_search(self, authenticated_client):
        """Test real API call for city search"""
        url = reverse('aqi:aqi-geocode')
        response = authenticated_client.get(url, {
            'city': 'Karachi'
        })
        
        # May succeed or fail depending on API availability
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_503_SERVICE_UNAVAILABLE
        ]
    
    def test_end_to_end_flow(self, authenticated_client):
        """Test end-to-end flow: geocode -> fetch AQI"""
        # Step 1: Geocode city
        geocode_url = reverse('aqi:aqi-geocode')
        geocode_response = authenticated_client.get(geocode_url, {
            'city': 'New York'
        })
        
        if geocode_response.status_code == status.HTTP_200_OK:
            lat = geocode_response.data.get('lat')
            lng = geocode_response.data.get('lon')
            
            # Step 2: Fetch AQI for that location
            if lat and lng:
                aqi_url = reverse('aqi:aqi-enhanced')
                aqi_response = authenticated_client.get(aqi_url, {
                    'lat': lat,
                    'lng': lng
                })
                
                # May succeed or fail depending on API availability
                assert aqi_response.status_code in [
                    status.HTTP_200_OK,
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    status.HTTP_429_TOO_MANY_REQUESTS
                ]


