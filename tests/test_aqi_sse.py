"""
Tests for SSE (Server-Sent Events) streaming endpoint
"""
import pytest
import json
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch, MagicMock


@pytest.mark.django_db
@pytest.mark.aqi
class TestCityRankingsStreamView:
    """Test SSE streaming endpoint for city rankings"""
    
    @patch('aqi.views_sse.aqi_service')
    def test_sse_endpoint_connection(self, mock_service, authenticated_client):
        """Test SSE endpoint connects and sends initial status"""
        # Mock AQI service to return data
        mock_service.fetch_current_aqi.return_value = {
            'location': {'lat': 40.7128, 'lon': -74.0060},
            'aqi': 45,
            'current': {'pm2_5': 12.5, 'pm10': 25.0},
            'dominant_pollutant': 'pm2_5',
            'lastUpdated': '2025-12-09T00:00'
        }
        
        url = reverse('aqi:city-rankings-stream')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'text/event-stream'
        assert response['Cache-Control'] == 'no-cache'
        assert response['Connection'] == 'keep-alive'
    
    @patch('aqi.views_sse.aqi_service')
    def test_sse_sends_initial_status(self, mock_service, authenticated_client):
        """Test SSE endpoint sends initial status event"""
        mock_service.fetch_current_aqi.return_value = {
            'location': {'lat': 40.7128, 'lon': -74.0060},
            'aqi': 45,
            'current': {'pm2_5': 12.5},
            'lastUpdated': '2025-12-09T00:00'
        }
        
        url = reverse('aqi:city-rankings-stream')
        response = authenticated_client.get(url)
        
        # Read first few chunks of stream (limit to avoid hanging)
        content_chunks = []
        for i, chunk in enumerate(response.streaming_content):
            if i >= 3:  # Only read first 3 chunks
                break
            content_chunks.append(chunk)
        
        content_str = b''.join(content_chunks).decode('utf-8', errors='ignore')
        
        assert 'event: status' in content_str or 'connected' in content_str.lower()
    
    @patch('aqi.views_sse.aqi_service')
    def test_sse_sends_rankings_event(self, mock_service, authenticated_client):
        """Test SSE endpoint sends rankings event"""
        mock_service.fetch_current_aqi.return_value = {
            'location': {'lat': 40.7128, 'lon': -74.0060},
            'aqi': 45,
            'current': {'pm2_5': 12.5, 'pm10': 25.0},
            'dominant_pollutant': 'pm2_5',
            'lastUpdated': '2025-12-09T00:00'
        }
        
        url = reverse('aqi:city-rankings-stream')
        response = authenticated_client.get(url)
        
        # Read limited stream content to avoid hanging
        content_chunks = []
        for i, chunk in enumerate(response.streaming_content):
            if i >= 5:  # Only read first 5 chunks
                break
            content_chunks.append(chunk)
        
        content_str = b''.join(content_chunks).decode('utf-8', errors='ignore')
        
        # Should contain status or rankings event
        assert 'event:' in content_str
    
    @patch('aqi.views_sse.aqi_service')
    def test_sse_handles_api_failure(self, mock_service, authenticated_client):
        """Test SSE endpoint handles API failures gracefully"""
        mock_service.fetch_current_aqi.return_value = None
        
        url = reverse('aqi:city-rankings-stream')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'text/event-stream'
    
    def test_sse_cors_headers(self, authenticated_client):
        """Test SSE endpoint includes CORS headers"""
        url = reverse('aqi:city-rankings-stream')
        response = authenticated_client.get(url)
        
        assert 'Access-Control-Allow-Origin' in response
        assert 'Access-Control-Allow-Methods' in response
    
    def test_sse_options_request(self, authenticated_client):
        """Test SSE endpoint handles OPTIONS (CORS preflight) request"""
        url = reverse('aqi:city-rankings-stream')
        response = authenticated_client.options(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'Access-Control-Allow-Origin' in response

