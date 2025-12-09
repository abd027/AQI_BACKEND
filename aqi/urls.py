"""
URL configuration for AQI app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AQIFetchView,
    AQIByCoordinatesView,
    EnhancedAQIView,
    AQITrendView,
    CityRankingsView,
    BatchAQIView,
    BatchEnhancedAQIView,
    GeocodeCityView,
    CityAutocompleteView,
    ChatAPIView,
)
from .views_sse import CityRankingsStreamView
from .subscription_views import CitySubscriptionViewSet

app_name = 'aqi'

# Router for subscription viewsets
router = DefaultRouter()
router.register(r'aqi/subscriptions', CitySubscriptionViewSet, basename='subscription')

urlpatterns = [
    # More specific paths first
    path('aqi/batch/enhanced/', BatchEnhancedAQIView.as_view(), name='aqi-batch-enhanced'),
    path('aqi/batch/', BatchAQIView.as_view(), name='aqi-batch'),
    path('aqi/autocomplete/', CityAutocompleteView.as_view(), name='aqi-autocomplete'),
    path('aqi/coordinates/', AQIByCoordinatesView.as_view(), name='aqi-coordinates'),
    path('aqi/enhanced/', EnhancedAQIView.as_view(), name='aqi-enhanced'),
    path('aqi/trend/', AQITrendView.as_view(), name='aqi-trend'),
    path('aqi/geocode/', GeocodeCityView.as_view(), name='aqi-geocode'),
    path('aqi/', AQIFetchView.as_view(), name='aqi-fetch'),  # General path last
    path('cities/rankings/stream/', CityRankingsStreamView.as_view(), name='city-rankings-stream'),  # SSE endpoint
    path('cities/rankings/', CityRankingsView.as_view(), name='city-rankings'),
    path('chat/', ChatAPIView.as_view(), name='chat'),
    path('', include(router.urls)),  # Subscription routes at /api/aqi/subscriptions/
]

