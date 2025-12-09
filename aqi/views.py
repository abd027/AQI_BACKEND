"""
Views for Air Quality Index (AQI) endpoints
"""
import logging
import requests
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from typing import List, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)
from .services import OpenMeteoAQIService
from .waqi_service import WAQIService
from .cache import get_cached_aqi, set_cached_aqi, get_cached_city_rankings, set_cached_city_rankings
from .serializers import (
    AQIRequestSerializer,
    CoordinatesRequestSerializer,
    BatchLocationSerializer,
    CityRequestSerializer,
)
from core.utils import geocode_city, calculate_epa_aqi, get_aqi_category, search_city

# RAG Imports
try:
    from .rag import AQIRAGSystem
except ImportError:
    AQIRAGSystem = None
from rest_framework.views import APIView



# Initialize services
aqi_service = OpenMeteoAQIService()
waqi_service = WAQIService()


class AQIFetchView(generics.GenericAPIView):
    """
    GET /api/aqi/?lat=<>&lon=<>&type=hourly|current|daily
    
    Fetch AQI data by coordinates
    """
    permission_classes = [IsAuthenticated]
    serializer_class = AQIRequestSerializer
    
    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        lat = serializer.validated_data['lat']
        lon = serializer.validated_data['lon']
        data_type = serializer.validated_data.get('type', 'current')
        hours = serializer.validated_data.get('hours', 24)
        days = serializer.validated_data.get('days', 7)
        
        # Check cache first
        cache_key_type = data_type
        cached_data = get_cached_aqi(lat, lon, cache_key_type, hours if data_type == 'hourly' else None, days if data_type == 'daily' else None)
        
        if cached_data:
            return Response(cached_data)
        
        # Fetch from API
        try:
            if data_type == 'current':
                data = aqi_service.fetch_current_aqi(lat, lon)
            elif data_type == 'hourly':
                data = aqi_service.fetch_hourly_aqi(lat, lon, hours=hours)
            elif data_type == 'daily':
                data = aqi_service.fetch_daily_aqi(lat, lon, days=days)
            else:
                return Response(
                    {'error': True, 'detail': 'Invalid type. Use current, hourly, or daily.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not data:
                return Response(
                    {'error': True, 'detail': 'Failed to fetch AQI data from external API.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            # Cache the response
            set_cached_aqi(lat, lon, data, cache_key_type, hours if data_type == 'hourly' else None, days if data_type == 'daily' else None)
            
            return Response(data)
        except Exception as e:
            return Response(
                {'error': True, 'detail': f'Error fetching AQI data: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AQIByCoordinatesView(generics.GenericAPIView):
    """
    GET /api/aqi/coordinates/?lat=<>&lng=<>
    
    Fetch current AQI data by coordinates (alias for /api/aqi/?type=current)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CoordinatesRequestSerializer
    
    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        lat = serializer.validated_data['lat']
        lng = serializer.validated_data['lng']
        
        # Check cache
        cached_data = get_cached_aqi(lat, lng, 'current')
        if cached_data:
            return Response(cached_data)
        
        # Fetch from API
        try:
            from core.utils import reverse_geocode
            
            data = aqi_service.fetch_current_aqi(lat, lng)
            
            if not data:
                return Response(
                    {'error': True, 'detail': 'Failed to fetch AQI data from external API.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            # Add city name if not present
            # Add city name if not present
            if 'city' not in data or not data['city']:
                location_info = reverse_geocode(lat, lng)
                if location_info:
                    data['city'] = location_info.get('city')
                    data['country'] = location_info.get('country')
            
            # Cache the response
            set_cached_aqi(lat, lng, data, 'current')
            
            return Response(data)
        except Exception as e:
            return Response(
                {'error': True, 'detail': f'Error fetching AQI data: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EnhancedAQIView(generics.GenericAPIView):
    """
    GET /api/aqi/enhanced/?lat=<>&lng=<>
    
    Fetch enhanced AQI data with calculated EPA AQI values
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CoordinatesRequestSerializer
    
    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        lat = serializer.validated_data['lat']
        lng = serializer.validated_data['lng']
        
        # Check cache
        cached_data = get_cached_aqi(lat, lng, 'enhanced')
        if cached_data:
            return Response(cached_data)
        
        # Fetch from API
        try:
            import traceback
            from django.conf import settings
            
            logger.info(f"Fetching enhanced AQI for lat={lat}, lng={lng}")
            data = aqi_service.fetch_enhanced_aqi(lat, lng)
            
            if not data:
                logger.warning(f"Failed to fetch enhanced AQI data for lat={lat}, lng={lng}")
                # Try to fetch basic AQI data as fallback
                try:
                    logger.info(f"Attempting fallback to basic AQI data for lat={lat}, lng={lng}")
                    basic_data = aqi_service.fetch_current_aqi(lat, lng)
                    if basic_data:
                        logger.info(f"Successfully fetched basic AQI data as fallback")
                        # Enhance it with minimal calculations
                        enhanced_fallback = aqi_service._enhance_with_aqi_calculations(basic_data, None)
                        if enhanced_fallback:
                            # Cache the fallback response
                            set_cached_aqi(lat, lng, enhanced_fallback, 'enhanced')
                            return Response(enhanced_fallback)
                except Exception as fallback_error:
                    logger.error(f"Fallback also failed: {fallback_error}")
                
                return Response(
                    {
                        'error': True, 
                        'detail': 'Failed to fetch enhanced AQI data from external API. The service may be temporarily unavailable or rate-limited. Please try again in a few moments.'
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            # Cache the response
            set_cached_aqi(lat, lng, data, 'enhanced')
            
            return Response(data)
        except Exception as e:
            import traceback
            from django.conf import settings
            
            error_traceback = traceback.format_exc()
            logger.error(f"Error in EnhancedAQIView: {str(e)}")
            logger.error(f"Traceback: {error_traceback}")
            
            # Include traceback in response if DEBUG is enabled
            error_detail = {'error': True, 'detail': f'Error fetching enhanced AQI data: {str(e)}'}
            if settings.DEBUG:
                error_detail['traceback'] = error_traceback
            
            return Response(
                error_detail,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AQITrendView(generics.GenericAPIView):
    """
    GET /api/aqi/trend/?city=<>
    
    Fetch AQI trend data for a city (geocodes city name to coordinates)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CityRequestSerializer
    
    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        city = serializer.validated_data['city']
        
        # Geocode city to coordinates
        coords = geocode_city(city)
        if not coords:
            return Response(
                {'error': True, 'detail': f'Could not find coordinates for city: {city}'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        lat, lon = coords
        
        # Fetch hourly data for trend (last 24 hours)
        try:
            data = aqi_service.fetch_hourly_aqi(lat, lon, hours=24)
            
            if not data:
                return Response(
                    {'error': True, 'detail': 'Failed to fetch AQI trend data from external API.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            # Format as trend data (time series of AQI values)
            hourly = data.get('hourly', {})
            times = hourly.get('time', [])
            pm25_values = hourly.get('pm2_5', [])
            
            trend = []
            for i, time in enumerate(times):
                if i < len(pm25_values) and pm25_values[i] is not None:
                    aqi = calculate_epa_aqi('pm25', pm25_values[i])
                    trend.append({
                        'time': time,
                        'aqi': aqi if aqi else 0,
                    })
            
            return Response({
                'city': city,
                'location': {'lat': lat, 'lon': lon},
                'trend': trend,
            })
        except Exception as e:
            return Response(
                {'error': True, 'detail': f'Error fetching AQI trend: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CityRankingsView(generics.GenericAPIView):
    """
    GET /api/cities/rankings/
    
    Fetch AQI rankings for top world cities using WAQI API
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        try:
            # Check cache first
            cached_rankings = get_cached_city_rankings()
            if cached_rankings:
                logger.info(f"Returning cached city rankings ({len(cached_rankings)} cities)")
                return Response(cached_rankings)
            
            # Cache miss - build rankings from WAQI API
            logger.info("Cache miss - building city rankings from WAQI API")
            rankings = waqi_service.build_worst_aqi_rankings(top_n=30)
            
            if not rankings:
                logger.warning("No rankings returned from WAQI service")
                return Response([], status=status.HTTP_200_OK)
            
            # Cache the results
            set_cached_city_rankings(rankings)
            logger.info(f"Cached {len(rankings)} city rankings")
            
            logger.info(f"Returning {len(rankings)} ranked cities from WAQI")
            return Response(rankings)
            
        except Exception as e:
            logger.error(f"Error fetching city rankings: {e}", exc_info=True)
            # Return empty array instead of error to prevent frontend issues
            return Response([], status=status.HTTP_200_OK)


class BatchAQIView(generics.GenericAPIView):
    """
    POST /api/aqi/batch/
    
    Fetch AQI data for multiple locations
    
    Request body:
    {
        "locations": [
            {"lat": 1, "lng": 2, "city": "optional"},
            ...
        ]
    }
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BatchLocationSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        locations = serializer.validated_data['locations']
        results = []
        
        for location in locations:
            lat = location['lat']
            lng = location['lng']
            
            try:
                # Check cache
                cached_data = get_cached_aqi(lat, lng, 'current')
                if cached_data:
                    results.append(cached_data)
                    continue
                
                # Fetch from API
                data = aqi_service.fetch_current_aqi(lat, lng)
                
                if data:
                    # Add city name if provided
                    if location.get('city'):
                        data['city'] = location['city']
                    if location.get('area'):
                        data['area'] = location['area']
                    
                    # Cache the response
                    set_cached_aqi(lat, lng, data, 'current')
                    
                    results.append(data)
                else:
                    results.append({
                        'error': True,
                        'detail': f'Failed to fetch AQI for location ({lat}, {lng})',
                        'location': {'lat': lat, 'lon': lng}
                    })
            except Exception as e:
                results.append({
                    'error': True,
                    'detail': f'Error fetching AQI: {str(e)}',
                    'location': {'lat': lat, 'lon': lng}
                })
        
        return Response(results)


class BatchEnhancedAQIView(generics.GenericAPIView):
    """
    POST /api/aqi/batch/enhanced/
    
    Fetch enhanced AQI data for multiple locations
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BatchLocationSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        locations = serializer.validated_data['locations']
        results = []
        
        for location in locations:
            lat = location['lat']
            lng = location['lng']
            
            try:
                # Check cache
                cached_data = get_cached_aqi(lat, lng, 'enhanced')
                if cached_data:
                    results.append(cached_data)
                    continue
                
                # Fetch from API
                data = aqi_service.fetch_enhanced_aqi(lat, lng)
                
                if data:
                    # Add city name if provided
                    if location.get('city'):
                        data['city'] = location['city']
                    if location.get('area'):
                        data['area'] = location['area']
                    
                    # Cache the response
                    set_cached_aqi(lat, lng, data, 'enhanced')
                    
                    results.append(data)
                else:
                    results.append({
                        'error': True,
                        'detail': f'Failed to fetch enhanced AQI for location ({lat}, {lng})',
                        'location': {'lat': lat, 'lon': lng}
                    })
            except Exception as e:
                results.append({
                    'error': True,
                    'detail': f'Error fetching enhanced AQI: {str(e)}',
                    'location': {'lat': lat, 'lon': lng}
                })
        
        return Response(results)


class GeocodeCityView(generics.GenericAPIView):
    """
    GET /api/aqi/geocode/?city=Name
    
    Search for a city and return detailed location info
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CityRequestSerializer
    
    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        city = serializer.validated_data['city']
        
        result = search_city(city)
        if result:
            return Response(result)
        
        return Response(
            {'error': True, 'detail': f'City not found: {city}'},
            status=status.HTTP_404_NOT_FOUND
        )


class CityAutocompleteView(APIView):
    """
    GET /api/aqi/autocomplete/?q=query
    
    Autocomplete city suggestions using Nominatim API (proxied to avoid CORS)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        query = request.query_params.get('q', '').strip()
        
        if not query or len(query) < 2:
            return Response([])
        
        try:
            # Use Nominatim API
            nominatim_url = 'https://nominatim.openstreetmap.org/search'
            params = {
                'q': query,
                'format': 'json',
                'addressdetails': '1',
                'limit': '10',
                'featuretype': 'city',
            }
            
            headers = {
                'User-Agent': 'BreatheEasy-AQI-App/1.0',
            }
            
            response = requests.get(nominatim_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            suggestions = []
            
            if isinstance(data, list):
                for place in data:
                    # Filter to prioritize cities and major locations
                    is_city = (
                        place.get('type') in ['city', 'town', 'village'] or
                        place.get('class') == 'place'
                    )
                    
                    if is_city or len(suggestions) < 5:
                        place_id = str(place.get('place_id', '') or place.get('osm_id', ''))
                        display_name = place.get('display_name', '') or place.get('name', '')
                        
                        # Extract country from address
                        country = ''
                        if place.get('address'):
                            country = place['address'].get('country', '')
                        
                        suggestion = {
                            'placeId': place_id,
                            'displayName': display_name,
                            'formattedAddress': display_name,
                        }
                        
                        if place.get('lat') and place.get('lon'):
                            suggestion['location'] = {
                                'lat': float(place['lat']),
                                'lng': float(place['lon']),
                            }
                        
                        suggestions.append(suggestion)
            
            return Response(suggestions)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching autocomplete suggestions: {e}")
            return Response(
                {'error': True, 'detail': 'Failed to fetch city suggestions'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Unexpected error in autocomplete: {e}", exc_info=True)
            return Response(
                {'error': True, 'detail': 'An error occurred while fetching suggestions'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChatAPIView(APIView):
    """
    POST /api/aqi/chat/
    
    Chat with the AQI Assistant (RAG-based)
    Request: { "question": "..." }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        logger.info("\n" + "="*80)
        logger.info("CHATBOT REQUEST RECEIVED")
        logger.info("="*80)
        
        try:
            # Log request details
            logger.info(f"User: {request.user}")
            logger.info(f"Request data: {request.data}")
            
            # Check if RAG module is available
            logger.info(f"AQIRAGSystem available: {AQIRAGSystem is not None}")
            if not AQIRAGSystem:
                logger.error("RAG System module not imported!")
                return Response(
                    {"error": "RAG System module not available. Please check server logs."}, 
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            # Get question from request
            question = request.data.get('question')
            logger.info(f"Question received: '{question}'")
            
            if not question:
                logger.warning("No question provided in request")
                return Response(
                    {"error": "Question is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Initialize RAG system (singleton with lazy init)
            logger.info("Creating RAG system instance...")
            rag = AQIRAGSystem()
            logger.info(f"RAG instance created: {rag}")
            logger.info(f"RAG instance type: {type(rag)}")
            logger.info(f"RAG _initialized state: {rag._initialized}")
            
            # Query the RAG system
            logger.info(f"Calling rag.query() with question: '{question}'")
            answer = rag.query(question)
            logger.info(f"RAG query completed. Answer length: {len(answer)} characters")
            logger.info(f"Answer preview: {answer[:200]}..." if len(answer) > 200 else f"Answer: {answer}")
            
            # Return response
            logger.info("Returning successful response")
            logger.info("="*80 + "\n")
            return Response({"answer": answer})
            
        except Exception as e:
            logger.error("\n" + "!"*80)
            logger.error("EXCEPTION IN CHATBOT ENDPOINT")
            logger.error("!"*80)
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception message: {str(e)}")
            import traceback
            logger.error("Full traceback:")
            traceback.print_exc()
            logger.error("!"*80 + "\n")
            
            return Response(
                {"error": f"Server error: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
