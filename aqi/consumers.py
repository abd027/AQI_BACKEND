"""
WebSocket consumer for live AQI data streaming
"""
import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import CitySubscription
from .services import OpenMeteoAQIService

User = get_user_model()
logger = logging.getLogger(__name__)

# Initialize AQI service
aqi_service = OpenMeteoAQIService()


class AQILiveDataConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for streaming live AQI data
    
    Message types from client:
    - subscribe: {type: 'subscribe', city: '...', country: '...', lat: ..., lon: ...}
    - unsubscribe: {type: 'unsubscribe', city: '...', country: '...'}
    - ping: {type: 'ping'}
    
    Message types to client:
    - aqi_update: {type: 'aqi_update', city: '...', data: {...}}
    - heartbeat: {type: 'heartbeat', timestamp: ...}
    - error: {type: 'error', message: '...'}
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.subscribed_cities = {}  # {city_key: {'city': ..., 'country': ..., 'lat': ..., 'lon': ...}}
        self.update_task = None
    
    async def connect(self):
        """Handle WebSocket connection"""
        # Get user from scope (set by AuthMiddlewareStack)
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)  # Unauthorized
            return
        
        await self.accept()
        # User is authenticated at this point (checked above), but use getattr for safety
        user_email = getattr(self.user, 'email', 'Unknown')
        logger.info(f"WebSocket connected: {user_email}")
        
        # Load user's active subscriptions
        await self.load_user_subscriptions()
        
        # Start periodic updates
        self.update_task = asyncio.create_task(self.periodic_updates())
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if self.update_task:
            self.update_task.cancel()
        # Safely get user email - handle AnonymousUser which doesn't have email attribute
        user_email = 'Unknown'
        if self.user and hasattr(self.user, 'is_authenticated') and self.user.is_authenticated:
            user_email = getattr(self.user, 'email', 'Unknown')
        logger.info(f"WebSocket disconnected: {user_email}")
    
    async def receive(self, text_data):
        """Handle messages from WebSocket client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'subscribe':
                await self.handle_subscribe(data)
            elif message_type == 'unsubscribe':
                await self.handle_unsubscribe(data)
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}", exc_info=True)
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    async def handle_subscribe(self, data):
        """Handle subscribe message"""
        city = data.get('city')
        country = data.get('country')
        lat = data.get('lat')
        lon = data.get('lon')
        
        if not all([city, country, lat is not None, lon is not None]):
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Missing required fields: city, country, lat, lon'
            }))
            return
        
        city_key = f"{city}_{country}".lower()
        self.subscribed_cities[city_key] = {
            'city': city,
            'country': country,
            'lat': float(lat),
            'lon': float(lon)
        }
        
        # Fetch and send initial AQI data
        await self.send_aqi_update(city, country, lat, lon)
    
    async def handle_unsubscribe(self, data):
        """Handle unsubscribe message"""
        city = data.get('city')
        country = data.get('country')
        
        if not city or not country:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Missing required fields: city, country'
            }))
            return
        
        city_key = f"{city}_{country}".lower()
        if city_key in self.subscribed_cities:
            del self.subscribed_cities[city_key]
    
    async def load_user_subscriptions(self):
        """Load user's active city subscriptions from database"""
        subscriptions = await self._get_user_active_subscriptions()
        
        for sub in subscriptions:
            city_key = f"{sub.city}_{sub.country}".lower()
            self.subscribed_cities[city_key] = {
                'city': sub.city,
                'country': sub.country,
                'lat': sub.latitude,
                'lon': sub.longitude
            }
    
    @database_sync_to_async
    def _get_user_active_subscriptions(self):
        """Get user's active subscriptions from database"""
        return list(CitySubscription.objects.filter(
            user=self.user,
            is_active=True
        ))
    
    async def periodic_updates(self):
        """Periodically send AQI updates for subscribed cities"""
        heartbeat_interval = 30  # seconds
        update_interval = 25  # seconds (reduced from 60 to match frontend polling)
        
        last_heartbeat = 0
        last_update = 0
        
        try:
            while True:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                current_time = asyncio.get_event_loop().time()
                
                # Send heartbeat every 30 seconds
                if current_time - last_heartbeat >= heartbeat_interval:
                    await self.send(text_data=json.dumps({
                        'type': 'heartbeat',
                        'timestamp': current_time
                    }))
                    last_heartbeat = current_time
                
                # Send AQI updates every 60 seconds
                if current_time - last_update >= update_interval or last_update == 0:
                    if self.subscribed_cities:
                        # Fetch AQI for all subscribed cities
                        for city_key, city_info in list(self.subscribed_cities.items()):
                            await self.send_aqi_update(
                                city_info['city'],
                                city_info['country'],
                                city_info['lat'],
                                city_info['lon']
                            )
                            # Small delay between requests to avoid rate limiting
                            await asyncio.sleep(1)
                    last_update = current_time
                    
        except asyncio.CancelledError:
            logger.info("Periodic update task cancelled")
        except Exception as e:
            logger.error(f"Error in periodic updates: {e}", exc_info=True)
    
    async def send_aqi_update(self, city, country, lat, lon):
        """Fetch and send AQI update for a city"""
        try:
            # Fetch AQI data (run in thread pool since it's sync)
            aqi_data = await asyncio.to_thread(
                aqi_service.fetch_current_aqi,
                lat,
                lon
            )
            
            if aqi_data:
                await self.send(text_data=json.dumps({
                    'type': 'aqi_update',
                    'city': city,
                    'country': country,
                    'data': aqi_data
                }))
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Failed to fetch AQI data for {city}, {country}'
                }))
        except Exception as e:
            logger.error(f"Error fetching AQI for {city}, {country}: {e}", exc_info=True)
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Error fetching AQI data: {str(e)}'
            }))

