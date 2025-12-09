"""
SSE (Server-Sent Events) streaming view for real-time city rankings updates
"""
from django.http import StreamingHttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
import time
from .services import OpenMeteoAQIService
from core.utils import get_aqi_category, calculate_epa_aqi

aqi_service = OpenMeteoAQIService()


@method_decorator(csrf_exempt, name='dispatch')
class CityRankingsStreamView(View):
    """
    GET /api/cities/rankings/stream
    
    SSE endpoint for real-time city rankings updates
    Sends:
    - event: heartbeat (every 30 seconds)
    - event: rankings (every 60 seconds)
    - event: status (on updates)
    - event: error (on failures)
    """
    
    # Popular cities for rankings (same as CityRankingsView)
    POPULAR_CITIES = [
        {'name': 'New York', 'lat': 40.7128, 'lon': -74.0060, 'country': 'USA', 'region': 'North America'},
        {'name': 'London', 'lat': 51.5074, 'lon': -0.1278, 'country': 'UK', 'region': 'Europe'},
        {'name': 'Tokyo', 'lat': 35.6762, 'lon': 139.6503, 'country': 'Japan', 'region': 'Asia'},
        {'name': 'Paris', 'lat': 48.8566, 'lon': 2.3522, 'country': 'France', 'region': 'Europe'},
        {'name': 'Beijing', 'lat': 39.9042, 'lon': 116.4074, 'country': 'China', 'region': 'Asia'},
        {'name': 'Delhi', 'lat': 28.6139, 'lon': 77.2090, 'country': 'India', 'region': 'Asia'},
        {'name': 'Los Angeles', 'lat': 34.0522, 'lon': -118.2437, 'country': 'USA', 'region': 'North America'},
        {'name': 'Mumbai', 'lat': 19.0760, 'lon': 72.8777, 'country': 'India', 'region': 'Asia'},
        {'name': 'Sydney', 'lat': -33.8688, 'lon': 151.2093, 'country': 'Australia', 'region': 'Oceania'},
        {'name': 'São Paulo', 'lat': -23.5505, 'lon': -46.6333, 'country': 'Brazil', 'region': 'South America'},
    ]
    
    def _fetch_rankings(self):
        """Helper method to fetch city rankings (extracted from CityRankingsView)"""
        rankings = []
        
        for city_info in self.POPULAR_CITIES:
            try:
                # Fetch current AQI
                data = aqi_service.fetch_current_aqi(city_info['lat'], city_info['lon'])
                
                if data:
                    aqi_value = data.get('aqi')
                    pm25 = data.get('current', {}).get('pm2_5')
                    pm10 = data.get('current', {}).get('pm10')
                    
                    if aqi_value:
                        aqi_info = get_aqi_category(aqi_value)
                        
                        # Get trend (simplified - just current value)
                        trend = [{'time': data.get('lastUpdated', ''), 'aqi': aqi_value}]
                        
                        rankings.append({
                            'rank': 0,  # Will be set after sorting
                            'city': city_info['name'],
                            'country': city_info['country'],
                            'aqi': aqi_value,
                            'category': aqi_info['category'],
                            'dominantPollutant': data.get('dominant_pollutant', 'pm2_5'),
                            'trend': trend,
                            'lastUpdated': data.get('lastUpdated', ''),
                            'region': city_info['region'],
                            'pm25': pm25,
                            'pm10': pm10,
                            'aqi_pm25': calculate_epa_aqi('pm25', pm25) if pm25 else None,
                            'aqi_pm10': calculate_epa_aqi('pm10', pm10) if pm10 else None,
                        })
            except Exception as e:
                print(f"Error fetching AQI for {city_info['name']}: {e}")
                continue
        
        # Sort by AQI (higher is worse) and assign ranks
        rankings.sort(key=lambda x: x['aqi'], reverse=True)
        for i, ranking in enumerate(rankings, 1):
            ranking['rank'] = i
        
        return rankings
    
    def get(self, request):
        """SSE streaming endpoint"""
        def event_stream():
            last_heartbeat = 0
            last_update = 0
            heartbeat_interval = 30  # 30 seconds
            update_interval = 60     # 60 seconds
            
            # Send initial status
            yield f"event: status\n"
            yield f"data: {json.dumps({'status': 'connected', 'message': 'SSE stream connected'})}\n\n"
            
            while True:
                try:
                    current_time = time.time()
                    
                    # Send heartbeat every 30 seconds
                    if current_time - last_heartbeat >= heartbeat_interval:
                        yield f"event: heartbeat\n"
                        yield f"data: {json.dumps({'timestamp': current_time})}\n\n"
                        last_heartbeat = current_time
                    
                    # Send rankings update every 60 seconds
                    if current_time - last_update >= update_interval or last_update == 0:
                        # Send loading status
                        yield f"event: status\n"
                        yield f"data: {json.dumps({'status': 'loading', 'message': 'Fetching city rankings...'})}\n\n"
                        
                        # Fetch rankings
                        rankings = self._fetch_rankings()
                        
                        # Send rankings data
                        yield f"event: rankings\n"
                        yield f"data: {json.dumps(rankings)}\n\n"
                        
                        last_update = current_time
                    
                    # Sleep for 5 seconds before next check
                    time.sleep(5)
                    
                except GeneratorExit:
                    # Client disconnected
                    print("SSE client disconnected")
                    break
                except Exception as e:
                    # Send error event
                    yield f"event: error\n"
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    time.sleep(5)
        
        # Create streaming response with proper SSE headers
        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        
        # SSE required headers
        response['Cache-Control'] = 'no-cache'
        response['Connection'] = 'keep-alive'
        response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
        
        # CORS headers (allow frontend access)
        response['Access-Control-Allow-Origin'] = '*'  # In production, set to specific domain
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response['Access-Control-Allow-Credentials'] = 'true'
        
        return response
    
    def options(self, request):
        """Handle CORS preflight requests"""
        response = StreamingHttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response['Access-Control-Allow-Credentials'] = 'true'
        return response
